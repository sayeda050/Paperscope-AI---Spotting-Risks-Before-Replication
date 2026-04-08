import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "processed" / "labeled_dataset.csv"
OUT_FILE = BASE_DIR / "outputs" / "reports" / "dataset_sanity_check.json"


def count_nonempty(series: pd.Series) -> int:
    return int(series.fillna("").astype(str).str.strip().ne("").sum())


def get_constant_columns(df: pd.DataFrame):
    constant_cols = []
    for col in df.columns:
        if df[col].nunique(dropna=False) == 1:
            constant_cols.append(col)
    return constant_cols


def reconstruct_rank_qcut_labels(df: pd.DataFrame) -> pd.Series:
    """
    Reconstruct the current label rule used by build_labels.py:
    balanced_rank_qcut over risk_score.
    """
    scores = df["risk_score"].astype(float)
    ranked_scores = scores.rank(method="first")

    reconstructed = pd.qcut(
        ranked_scores,
        q=3,
        labels=["LOW", "MEDIUM", "HIGH"]
    ).astype(str)

    return reconstructed


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Missing file: {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)

    if "risk_label" not in df.columns:
        raise ValueError("Column 'risk_label' not found in labeled_dataset.csv")
    if "risk_score" not in df.columns:
        raise ValueError("Column 'risk_score' not found in labeled_dataset.csv")

    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "review_text_nonempty": count_nonempty(df["review_text"]) if "review_text" in df.columns else 0,
        "decision_text_nonempty": count_nonempty(df["decision_text"]) if "decision_text" in df.columns else 0,
        "duplicate_paper_uid": int(df["paper_uid"].duplicated().sum()) if "paper_uid" in df.columns else None,
        "label_counts": {
            str(k): int(v)
            for k, v in df["risk_label"].value_counts(dropna=False).to_dict().items()
        },
        "constant_columns": get_constant_columns(df),
    }

    # Current correct consistency check
    reconstructed_labels = reconstruct_rank_qcut_labels(df)
    mismatch_current = int((df["risk_label"].astype(str) != reconstructed_labels.astype(str)).sum())

    # Optional reference check against old threshold style for comparison
    scores = df["risk_score"].astype(float)
    threshold_labels = pd.Series("MEDIUM", index=df.index, dtype="object")
    threshold_labels[scores < 40] = "LOW"
    threshold_labels[scores >= 70] = "HIGH"
    mismatch_old_threshold = int((df["risk_label"].astype(str) != threshold_labels.astype(str)).sum())

    report["labeling_method_expected"] = "balanced_rank_qcut"
    report["label_score_mismatch_rows_current_method"] = mismatch_current
    report["label_score_mismatch_rows_old_threshold_reference"] = mismatch_old_threshold

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\n✅ Saved sanity check to: {OUT_FILE}")


if __name__ == "__main__":
    main()