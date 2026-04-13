"""
split_dataset.py — Standalone stratified train/val/test split.

Used when you want to re-split an existing labeled_dataset.csv without
re-running the full labeling process (e.g., after adding correction log rows).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir, write_json, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
IN_FILE   = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
TRAIN_CSV = PIPELINE_DIR / "data" / "processed" / "train.csv"
VAL_CSV   = PIPELINE_DIR / "data" / "processed" / "val.csv"
TEST_CSV  = PIPELINE_DIR / "data" / "processed" / "test.csv"
REPORT    = PIPELINE_DIR / "outputs" / "reports" / "split_report.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-split labeled_dataset.csv.")
    parser.add_argument("--min-model-chars", type=int, default=500)
    parser.add_argument("--val-ratio",       type=float, default=0.15)
    parser.add_argument("--test-ratio",      type=float, default=0.15)
    parser.add_argument("--random-state",    type=int, default=42)
    parser.add_argument(
        "--domain", default="",
        help="Split only rows from this domain (default: all domains).",
    )
    args = parser.parse_args()

    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing: {IN_FILE}")

    df = pd.read_csv(IN_FILE)
    required = {"model_text", "repro_label"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df = df.copy()
    df["model_text"]  = df["model_text"].fillna("").astype(str)
    df["repro_label"] = df["repro_label"].fillna("").astype(str)

    if args.domain and "domain" in df.columns:
        df = df[df["domain"] == args.domain].copy()
        print(f"Filtered to domain {args.domain!r}: {len(df)} rows")

    if "paper_uid" in df.columns:
        df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    df = df[df["model_text"].str.len() >= args.min_model_chars]
    df = df[df["repro_label"].isin(["YES", "NO"])].reset_index(drop=True)

    if len(df) < 50:
        raise RuntimeError(
            f"Only {len(df)} rows after filtering — too few to split reliably."
        )

    holdout = args.val_ratio + args.test_ratio
    if holdout >= 0.5:
        raise ValueError("val_ratio + test_ratio must be < 0.5")

    train_df, temp_df = train_test_split(
        df, test_size=holdout, random_state=args.random_state, stratify=df["repro_label"]
    )
    test_share = args.test_ratio / holdout
    val_df, test_df = train_test_split(
        temp_df, test_size=test_share, random_state=args.random_state, stratify=temp_df["repro_label"]
    )

    ensure_dir(TRAIN_CSV.parent)
    ensure_dir(REPORT.parent)

    train_df.reset_index(drop=True).to_csv(TRAIN_CSV, index=False)
    val_df.reset_index(drop=True).to_csv(VAL_CSV,   index=False)
    test_df.reset_index(drop=True).to_csv(TEST_CSV,  index=False)

    report = {
        "schema_version":       PIPELINE_SCHEMA_VERSION,
        "domain_filter":        args.domain or "all",
        "total_after_filter":   int(len(df)),
        "train_rows":           int(len(train_df)),
        "val_rows":             int(len(val_df)),
        "test_rows":            int(len(test_df)),
        "train_label_counts":   train_df["repro_label"].value_counts().to_dict(),
        "val_label_counts":     val_df["repro_label"].value_counts().to_dict(),
        "test_label_counts":    test_df["repro_label"].value_counts().to_dict(),
    }
    write_json(REPORT, report)

    print(f"✅ Train: {len(train_df)} → {TRAIN_CSV}")
    print(f"✅ Val:   {len(val_df)}   → {VAL_CSV}")
    print(f"✅ Test:  {len(test_df)}  → {TEST_CSV}")
    print(f"✅ Report → {REPORT}")


if __name__ == "__main__":
    main()
