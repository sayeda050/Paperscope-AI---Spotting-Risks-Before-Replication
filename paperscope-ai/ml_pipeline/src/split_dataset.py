from pathlib import Path
import argparse
import json

import pandas as pd
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent
IN_FILE = BASE_DIR / "data" / "processed" / "labeled_dataset.csv"
TRAIN_CSV = BASE_DIR / "data" / "processed" / "train.csv"
VAL_CSV = BASE_DIR / "data" / "processed" / "val.csv"
TEST_CSV = BASE_DIR / "data" / "processed" / "test.csv"
REPORT_FILE = BASE_DIR / "outputs" / "reports" / "split_report.json"


def main():
    parser = argparse.ArgumentParser(description="Split labeled dataset into train/val/test.")
    parser.add_argument("--min-model-chars", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing file: {IN_FILE}")

    df = pd.read_csv(IN_FILE)
    required_cols = {"model_text", "repro_label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["model_text"] = df["model_text"].fillna("").astype(str)
    df["repro_label"] = df["repro_label"].fillna("").astype(str)

    if "paper_uid" in df.columns:
        df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    df = df[df["model_text"].str.len() >= args.min_model_chars]
    df = df[df["repro_label"].isin(["YES", "NO"])].reset_index(drop=True)

    if len(df) < 50:
        raise RuntimeError("Too few rows left after filtering to split reliably.")

    train_df, temp_df = train_test_split(
        df,
        test_size=0.30,
        random_state=args.random_state,
        stratify=df["repro_label"],
    )

    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=args.random_state,
        stratify=temp_df["repro_label"],
    )

    TRAIN_CSV.parent.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(TRAIN_CSV, index=False)
    val_df.to_csv(VAL_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)

    report = {
        "total_rows_after_filtering": int(len(df)),
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "train_label_counts": train_df["repro_label"].value_counts().to_dict(),
        "val_label_counts": val_df["repro_label"].value_counts().to_dict(),
        "test_label_counts": test_df["repro_label"].value_counts().to_dict(),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Train split saved to: {TRAIN_CSV}")
    print(f"✅ Val split saved to: {VAL_CSV}")
    print(f"✅ Test split saved to: {TEST_CSV}")
    print(f"✅ Split report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
