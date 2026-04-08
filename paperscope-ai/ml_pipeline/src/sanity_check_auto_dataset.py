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


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Missing file: {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)

    if "repro_label" not in df.columns:
        raise ValueError("Column 'repro_label' not found in labeled_dataset.csv")
    if "auto_score" not in df.columns:
        raise ValueError("Column 'auto_score' not found in labeled_dataset.csv")

    leakage_columns_present = [c for c in ["review_text", "decision_text", "risk_score", "weak_score", "risk_label"] if c in df.columns]

    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "model_text_nonempty": count_nonempty(df["model_text"]) if "model_text" in df.columns else 0,
        "raw_text_nonempty": count_nonempty(df["raw_text"]) if "raw_text" in df.columns else 0,
        "duplicate_paper_uid": int(df["paper_uid"].duplicated().sum()) if "paper_uid" in df.columns else None,
        "label_counts": {str(k): int(v) for k, v in df["repro_label"].value_counts(dropna=False).to_dict().items()},
        "constant_columns": get_constant_columns(df),
        "auto_score_min": float(df["auto_score"].min()),
        "auto_score_max": float(df["auto_score"].max()),
        "auto_score_mean": float(df["auto_score"].mean()),
        "leakage_columns_present": leakage_columns_present,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\n✅ Saved sanity check to: {OUT_FILE}")


if __name__ == "__main__":
    main()
