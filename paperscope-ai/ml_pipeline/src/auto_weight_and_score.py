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

# Higher auto_score = more reproducible (candidate YES).
EXPLICIT_FEATURE_WEIGHTS = {
    "has_code_link": 0.26,
    "has_data_link": 0.18,
    "reports_hyperparams": 0.14,
    "reports_seed": 0.08,
    "reports_uncertainty": 0.10,
    "reports_compute": 0.08,
    "has_ablation": 0.07,
    "compares_baselines": 0.05,
    "has_limitations": 0.02,
    "has_statistical_tests": 0.02,
}
SVD_FEATURE_WEIGHT = 0.01


def load_text_rows() -> pd.DataFrame:
    rows = []
    with IN_TEXT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def minmax_scale(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    lo, hi = x.min(), x.max()
    if hi == lo:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def compute_scores(artifact: dict) -> tuple[np.ndarray, pd.DataFrame]:
    feature_cols = artifact["feature_columns"]
    explicit_cols = artifact.get("explicit_feature_columns", [])
    svd_cols = artifact.get("svd_feature_columns", [])
    Z = np.asarray(artifact["matrix"], dtype=float)

    col_index = {c: i for i, c in enumerate(feature_cols)}
    weights = np.zeros(len(feature_cols), dtype=float)

    for feat_name, weight in EXPLICIT_FEATURE_WEIGHTS.items():
        idx = col_index.get(feat_name)
        if idx is not None:
            weights[idx] = weight

    for feat_name in svd_cols:
        idx = col_index.get(feat_name)
        if idx is not None:
            weights[idx] = SVD_FEATURE_WEIGHT

    Z_used = Z.copy()
    for feat_name in svd_cols:
        idx = col_index.get(feat_name)
        if idx is not None:
            Z_used[:, idx] = minmax_scale(Z_used[:, idx])

    raw_score = (Z_used * weights).sum(axis=1)
    score = minmax_scale(raw_score)

    weights_df = pd.DataFrame({"feature": feature_cols, "weight": weights})
    weights_df = weights_df[weights_df["weight"] != 0].sort_values(by="weight", ascending=False).reset_index(drop=True)
    return score.astype(float), weights_df


def main():
    parser = argparse.ArgumentParser(description="Score papers using paper-accessible reproducibility features.")
    parser.add_argument(
        "--invert-score",
        action="store_true",
        help="Invert score so 1=high risk instead of 1=more reproducible.",
    )
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

    auto_score, weights_df = compute_scores(artifact)
    if args.invert_score:
        auto_score = 1.0 - auto_score

    weights_df.to_csv(OUT_WEIGHTS_CSV, index=False)

    feature_df = pd.DataFrame(Z, columns=feature_cols)
    feature_df.insert(0, "paper_uid", paper_uids)
    feature_df["auto_score"] = auto_score

    text_df = load_text_rows()
    merged = text_df.merge(feature_df[["paper_uid", "auto_score"]], on="paper_uid", how="inner")
    merged = merged.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    explicit_cols = artifact.get("explicit_feature_columns", [])
    if explicit_cols:
        explicit_df = feature_df[["paper_uid"] + explicit_cols].copy()
        merged = merged.merge(explicit_df, on="paper_uid", how="left")

    merged.to_csv(OUT_SCORED_CSV, index=False)

    report = {
        "rows_scored": int(len(merged)),
        "feature_count": int(len(feature_cols)),
        "score_min": float(np.min(auto_score)),
        "score_max": float(np.max(auto_score)),
        "score_mean": float(np.mean(auto_score)),
        "scoring_method": "paper_content_checklist_weights_plus_small_svd",
        "weights_csv": str(OUT_WEIGHTS_CSV),
        "scored_csv": str(OUT_SCORED_CSV),
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Reproducibility-scored file saved to: {OUT_SCORED_CSV}")
    print(f"✅ Feature weights saved to: {OUT_WEIGHTS_CSV}")
    print(f"✅ Scoring report saved to: {OUT_REPORT}")


if __name__ == "__main__":
    main()