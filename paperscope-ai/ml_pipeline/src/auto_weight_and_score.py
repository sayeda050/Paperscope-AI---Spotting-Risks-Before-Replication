import sys
from pathlib import Path
import json
import argparse

import joblib
import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FEATURES_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_features.joblib"
IN_TEXT_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_SCORED_CSV = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_WEIGHTS_CSV = PIPELINE_DIR / "data" / "processed" / "feature_weights.csv"
OUT_REPORT = PIPELINE_DIR / "outputs" / "reports" / "auto_scoring_report.json"


def minmax_scale_columns(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    mins = X.min(axis=0)
    maxs = X.max(axis=0)
    denom = np.where((maxs - mins) == 0, 1.0, (maxs - mins))
    return (X - mins) / denom


def entropy_weights(X_scaled: np.ndarray) -> np.ndarray:
    eps = 1e-12
    X = np.clip(X_scaled, 0.0, None)
    col_sums = X.sum(axis=0)
    col_sums = np.where(col_sums == 0, 1.0, col_sums)
    P = X / col_sums
    n = X.shape[0]
    k = 1.0 / np.log(max(n, 2))
    entropy = -k * np.sum(P * np.log(P + eps), axis=0)
    divergence = 1.0 - entropy
    if np.allclose(divergence.sum(), 0.0):
        return np.full(shape=(X.shape[1],), fill_value=1.0 / X.shape[1], dtype=float)
    return divergence / divergence.sum()


def load_text_rows():
    rows = []
    with IN_TEXT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Automatically weight latent PDF features and compute paper score.")
    parser.add_argument("--invert-score", action="store_true")
    args = parser.parse_args()

    ensure_dir(OUT_SCORED_CSV.parent)
    ensure_dir(OUT_REPORT.parent)

    if not IN_FEATURES_PATH.exists():
        raise FileNotFoundError(f"Missing feature artifact: {IN_FEATURES_PATH}")
    if not IN_TEXT_FILE.exists():
        raise FileNotFoundError(f"Missing extracted text file: {IN_TEXT_FILE}")

    artifact = joblib.load(IN_FEATURES_PATH)
    paper_uids = artifact["paper_uids"]
    feature_cols = artifact["feature_columns"]
    Z = np.asarray(artifact["matrix"], dtype=float)

    Z_shifted = Z - Z.min(axis=0, keepdims=True)
    Z_scaled = minmax_scale_columns(Z_shifted)
    weights = entropy_weights(Z_scaled)

    auto_score = (Z_scaled @ weights).astype(float)
    if args.invert_score:
        auto_score = 1.0 - auto_score

    feature_df = pd.DataFrame(Z_scaled, columns=feature_cols)
    feature_df.insert(0, "paper_uid", paper_uids)
    feature_df["auto_score"] = auto_score

    weights_df = pd.DataFrame({"feature": feature_cols, "weight": weights})
    weights_df = weights_df.sort_values(by="weight", ascending=False).reset_index(drop=True)
    weights_df.to_csv(OUT_WEIGHTS_CSV, index=False)

    text_df = load_text_rows()
    merged = text_df.merge(feature_df, on="paper_uid", how="inner")
    merged = merged.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)
    merged.to_csv(OUT_SCORED_CSV, index=False)

    report = {
        "rows_scored": int(len(merged)),
        "feature_count": int(len(feature_cols)),
        "score_min": float(np.min(auto_score)),
        "score_max": float(np.max(auto_score)),
        "score_mean": float(np.mean(auto_score)),
        "weights_csv": str(OUT_WEIGHTS_CSV),
        "scored_csv": str(OUT_SCORED_CSV),
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Auto-scored paper file saved to: {OUT_SCORED_CSV}")
    print(f"✅ Feature weights saved to: {OUT_WEIGHTS_CSV}")
    print(f"✅ Auto scoring report saved to: {OUT_REPORT}")


if __name__ == "__main__":
    main()
