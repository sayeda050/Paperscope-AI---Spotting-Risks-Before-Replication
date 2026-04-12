from __future__ import annotations

import sys
from pathlib import Path
import argparse
import re

import pandas as pd
from sklearn.model_selection import train_test_split

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir, write_json

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_CSV = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
OUT_TRAIN_CSV = PIPELINE_DIR / "data" / "processed" / "train.csv"
OUT_VAL_CSV = PIPELINE_DIR / "data" / "processed" / "val.csv"
OUT_TEST_CSV = PIPELINE_DIR / "data" / "processed" / "test.csv"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "labeling_summary.json"

# High-precision review/decision cues only.
POS_PATTERNS = [
    re.compile(r"\bcode (?:is|was|has been)?\s*(?:available|released|shared|provided)\b", re.I),
    re.compile(r"\bartifact(?:s)? (?:are|is)?\s*available\b", re.I),
    re.compile(r"\breproducib(?:ility|le) (?:is )?(?:good|strong|excellent|verified)\b", re.I),
    re.compile(r"\bwell[- ]documented implementation\b", re.I),
]
NEG_PATTERNS = [
    re.compile(r"\bno (?:public )?(?:code|implementation|artifact)\b", re.I),
    re.compile(r"\bwithout (?:code|implementation|artifact)\b", re.I),
    re.compile(r"\breproducib(?:ility )?(?:concern|issue|problem|unclear)\b", re.I),
    re.compile(r"\bmissing (?:detail|details|hyperparameter|hyperparameters|training details|implementation details)\b", re.I),
    re.compile(r"\black(?:s|ing)? (?:code|detail|details|reproducibility)\b", re.I),
]


def label_from_text(text: str):
    text = str(text or "").strip()
    if not text:
        return None, 0.0
    has_pos = any(p.search(text) for p in POS_PATTERNS)
    has_neg = any(p.search(text) for p in NEG_PATTERNS)
    if has_pos and not has_neg:
        return "YES", 0.95
    if has_neg and not has_pos:
        return "NO", 0.95
    return None, 0.0


def strong_yes_feature_consensus(row: pd.Series) -> bool:
    # NOTE: the parentheses around the final `or` clause are intentional and
    # required — `and` binds tighter than `or` in Python.  Without them the
    # expression would short-circuit incorrectly.
    return (
        float(row.get("reproducibility_score", 0.0)) >= 78.0
        and float(row.get("code_artifact", 0.0)) >= 0.5
        and float(row.get("hyperparams_detail", 0.0)) >= 0.5
        and (
            float(row.get("evaluation_protocol", 0.0)) >= 0.5
            or float(row.get("baseline_comparison", 0.0)) >= 1.0
        )
    )


def strong_no_feature_consensus(row: pd.Series) -> bool:
    return (
        float(row.get("reproducibility_score", 0.0)) <= 25.0
        and float(row.get("code_artifact", 0.0)) == 0.0
        and float(row.get("execution_instructions", 0.0)) == 0.0
        and float(row.get("hyperparams_detail", 0.0)) <= 0.5
        and float(row.get("evaluation_protocol", 0.0)) <= 0.5
    )


# ---------------------------------------------------------------------------
# BUG FIX 5 — automated train / val / test split
# ---------------------------------------------------------------------------
# The original file ended after producing labeled_dataset.csv.
# train_tfidf_logreg.py expects three separate split files (train.csv,
# val.csv, test.csv) which were never created anywhere in the pipeline,
# causing a FileNotFoundError on every training run.
#
# Fix: perform a stratified 70 / 15 / 15 split at the end of this script so
# the pipeline is fully automated end-to-end.  Stratification by repro_label
# maintains class balance in every split.  A minimum-size guard prevents
# silently under-populated splits from masking labeling issues.
# ---------------------------------------------------------------------------
def make_splits(
    df: pd.DataFrame,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = 42,
    min_per_split: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Stratified split.  Returns (train_df, val_df, test_df).

    The split is done in two stages:
      1. Split off (val + test) from train using `val_ratio + test_ratio`.
      2. Split the held-out pool 50/50 into val and test.

    This guarantees that the train fraction is exactly
    1 - val_ratio - test_ratio regardless of rounding.
    """
    holdout_ratio = val_ratio + test_ratio  # fraction to hold out

    train_df, holdout_df = train_test_split(
        df,
        test_size=holdout_ratio,
        random_state=random_state,
        stratify=df["repro_label"],
    )
    # Within the held-out pool split evenly between val and test.
    val_df, test_df = train_test_split(
        holdout_df,
        test_size=0.5,
        random_state=random_state,
        stratify=holdout_df["repro_label"],
    )

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if len(split_df) < min_per_split:
            raise RuntimeError(
                f"Split '{split_name}' has only {len(split_df)} rows "
                f"(minimum={min_per_split}).  Collect more labeled data."
            )
        # Verify both classes are present in every split to avoid degenerate
        # training or evaluation.
        present_classes = set(split_df["repro_label"].unique())
        if not {"YES", "NO"}.issubset(present_classes):
            raise RuntimeError(
                f"Split '{split_name}' is missing at least one class. "
                f"Found: {present_classes}.  Ensure both YES and NO labels exist."
            )

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build a leakage-aware labeled dataset using review/decision text first "
            "and strict feature-consensus fallback, then produce stratified train/val/test splits."
        )
    )
    parser.add_argument("--min-rows", type=int, default=20)
    parser.add_argument("--enable-feature-fallback", action="store_true", default=True)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--split-seed", type=int, default=42)
    args = parser.parse_args()

    ensure_dir(OUT_CSV.parent)
    ensure_dir(REPORT_FILE.parent)

    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing file: {IN_FILE}")

    df = pd.read_csv(IN_FILE)
    required_cols = {"paper_uid", "model_text", "reproducibility_score"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in auto_scored_papers.csv: {sorted(missing)}"
        )

    df = df.copy()
    stats = {
        "input_rows": int(len(df)),
        "labeled_from_reviewer_text": 0,
        "labeled_from_decision_text": 0,
        "labeled_from_feature_fallback": 0,
        "dropped_ambiguous": 0,
    }

    labels: list[str | None] = []
    sources: list[str] = []
    confidences: list[float] = []

    for _, row in df.iterrows():
        review_text = str(row.get("review_text", "") or "")
        decision_text = str(row.get("decision_text", "") or "")

        label, conf = label_from_text(review_text)
        if label is not None:
            labels.append(label)
            sources.append("review_text")
            confidences.append(conf)
            stats["labeled_from_reviewer_text"] += 1
            continue

        label, conf = label_from_text(decision_text)
        if label is not None:
            labels.append(label)
            sources.append("decision_text")
            confidences.append(conf)
            stats["labeled_from_decision_text"] += 1
            continue

        label = None
        conf = 0.0
        if args.enable_feature_fallback:
            if strong_yes_feature_consensus(row):
                label, conf = "YES", 0.70
            elif strong_no_feature_consensus(row):
                label, conf = "NO", 0.70

        if label is not None:
            labels.append(label)
            sources.append("feature_consensus")
            confidences.append(conf)
            stats["labeled_from_feature_fallback"] += 1
            continue

        labels.append(None)
        sources.append("dropped")
        confidences.append(0.0)
        stats["dropped_ambiguous"] += 1

    df["repro_label"] = labels
    df["label_source"] = sources
    df["label_confidence"] = confidences
    df = df[df["repro_label"].notna()].copy().reset_index(drop=True)

    if len(df) < args.min_rows:
        raise RuntimeError(
            f"Only {len(df)} rows labeled (min={args.min_rows}). "
            "Collect more papers or widen the weak-labeling sources."
        )

    # Defensive leakage cleanup: keep review/decision columns for audit, but
    # training text is always sourced from model_text only.
    df["train_text_input"] = df["model_text"]
    df["training_text_source"] = "model_text_only"

    df.to_csv(OUT_CSV, index=False)

    # ------------------------------------------------------------------
    # Produce stratified train / val / test splits.
    # These are what train_tfidf_logreg.py reads.
    # ------------------------------------------------------------------
    train_df, val_df, test_df = make_splits(
        df,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        random_state=args.split_seed,
    )
    train_df.to_csv(OUT_TRAIN_CSV, index=False)
    val_df.to_csv(OUT_VAL_CSV, index=False)
    test_df.to_csv(OUT_TEST_CSV, index=False)

    report = {
        "input_rows": stats["input_rows"],
        "rows_labeled": int(len(df)),
        "dropped_ambiguous": stats["dropped_ambiguous"],
        "labeled_from_reviewer_text": stats["labeled_from_reviewer_text"],
        "labeled_from_decision_text": stats["labeled_from_decision_text"],
        "labeled_from_feature_fallback": stats["labeled_from_feature_fallback"],
        "label_counts": {
            str(k): int(v) for k, v in df["repro_label"].value_counts().to_dict().items()
        },
        "label_source_counts": {
            str(k): int(v) for k, v in df["label_source"].value_counts().to_dict().items()
        },
        "labeling_method": "review_then_decision_then_strict_feature_consensus",
        "split": {
            "train_rows": int(len(train_df)),
            "val_rows": int(len(val_df)),
            "test_rows": int(len(test_df)),
            "val_ratio": args.val_ratio,
            "test_ratio": args.test_ratio,
            "random_state": args.split_seed,
            "stratified": True,
            "train_label_counts": {
                str(k): int(v)
                for k, v in train_df["repro_label"].value_counts().to_dict().items()
            },
            "val_label_counts": {
                str(k): int(v)
                for k, v in val_df["repro_label"].value_counts().to_dict().items()
            },
            "test_label_counts": {
                str(k): int(v)
                for k, v in test_df["repro_label"].value_counts().to_dict().items()
            },
        },
        "output_csv": str(OUT_CSV),
        "train_csv": str(OUT_TRAIN_CSV),
        "val_csv": str(OUT_VAL_CSV),
        "test_csv": str(OUT_TEST_CSV),
    }
    write_json(REPORT_FILE, report)

    print(f"✅ Labeled dataset saved to: {OUT_CSV}")
    print(f"✅ Train split ({len(train_df)} rows) → {OUT_TRAIN_CSV}")
    print(f"✅ Val split   ({len(val_df)} rows) → {OUT_VAL_CSV}")
    print(f"✅ Test split  ({len(test_df)} rows) → {OUT_TEST_CSV}")
    print(f"✅ Report saved to: {REPORT_FILE}")
    print(f"✅ Total labeled: {len(df)}")


if __name__ == "__main__":
    main()