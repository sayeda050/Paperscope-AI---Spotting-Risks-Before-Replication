import sys
from pathlib import Path
import json
import argparse

import pandas as pd
from sklearn.cluster import KMeans

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_CSV = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "labeling_summary.json"


def main():
    parser = argparse.ArgumentParser(description="Create YES/NO labels automatically from auto_score.")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    ensure_dir(OUT_CSV.parent)
    ensure_dir(REPORT_FILE.parent)

    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing file: {IN_FILE}")

    df = pd.read_csv(IN_FILE)
    if "auto_score" not in df.columns:
        raise ValueError("Column 'auto_score' not found in auto_scored_papers.csv")

    df = df.copy()
    df["auto_score"] = pd.to_numeric(df["auto_score"], errors="coerce")
    df = df[df["auto_score"].notna()].copy()

    if len(df) < 20:
        raise RuntimeError("Too few rows to build a stable auto-labeled dataset.")

    score_values = df[["auto_score"]].to_numpy(dtype=float)
    kmeans = KMeans(n_clusters=2, n_init=20, random_state=args.random_state)
    clusters = kmeans.fit_predict(score_values)
    centers = kmeans.cluster_centers_.reshape(-1)
    higher_cluster = int(centers.argmax())

    df["repro_label"] = ["YES" if c == higher_cluster else "NO" for c in clusters]
    df.to_csv(OUT_CSV, index=False)

    label_counts = df["repro_label"].value_counts().to_dict()
    report = {
        "rows_labeled": int(len(df)),
        "label_counts": {str(k): int(v) for k, v in label_counts.items()},
        "cluster_centers": [float(x) for x in centers.tolist()],
        "labeling_method": "kmeans_2clusters_over_auto_score",
        "output_csv": str(OUT_CSV),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Auto-labeled dataset saved to: {OUT_CSV}")
    print(f"✅ Labeling summary saved to: {REPORT_FILE}")
    print(f"✅ Label counts: {label_counts}")


if __name__ == "__main__":
    main()
