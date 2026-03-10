from pathlib import Path
import json

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
REPORT_DIR = BASE_DIR / "outputs" / "reports"

CSV_PATH = DATA_DIR / "labeled_dataset.csv"
OUT_JSON = REPORT_DIR / "dataset_sanity_check.json"


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing file: {CSV_PATH}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV_PATH)

    summary = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "review_text_nonempty": int(df["review_text"].fillna("").astype(str).str.len().gt(0).sum()) if "review_text" in df.columns else 0,
        "decision_text_nonempty": int(df["decision_text"].fillna("").astype(str).str.len().gt(0).sum()) if "decision_text" in df.columns else 0,
        "duplicate_paper_uid": int(df["paper_uid"].duplicated().sum()) if "paper_uid" in df.columns else 0,
        "label_counts": df["risk_label"].value_counts(dropna=False).to_dict() if "risk_label" in df.columns else {},
        "constant_columns": [],
        "label_score_mismatch_rows": 0,
    }

    for col in df.columns:
        if df[col].nunique(dropna=False) <= 1:
            summary["constant_columns"].append(col)

    if {"risk_score", "risk_label"}.issubset(df.columns):
        expected = []
        for score in df["risk_score"]:
            if score <= 57.5:
                expected.append("LOW")
            elif score < 62.5:
                expected.append("MEDIUM")
            else:
                expected.append("HIGH")
        mismatch = (pd.Series(expected) != df["risk_label"].astype(str)).sum()
        summary["label_score_mismatch_rows"] = int(mismatch)

    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\n✅ Saved sanity check to: {OUT_JSON}")


if __name__ == "__main__":
    main()
