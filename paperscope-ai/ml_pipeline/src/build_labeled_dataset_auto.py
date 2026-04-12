import sys
from pathlib import Path
import json
import argparse
import re

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_CSV = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "labeling_summary.json"

# Reproducibility-specific signals only. Pure accept/reject is NOT used as a
# ground-truth label because publication outcome is not the same thing as
# reproducibility quality.
POS_RE = re.compile(
    r"code\s+(?:is\s+)?(?:provided|released|available|shared)|"
    r"reproducib(?:le|ility)\s+(?:is\s+)?(?:good|strong|excellent|verified)|"
    r"artifact(?:s)?\s+(?:are\s+)?available|"
    r"supplementary\s+(?:material|code)\s+(?:is\s+)?available",
    re.I,
)
NEG_RE = re.compile(
    r"(?:no|missing|lack(?:s|ing)?|without)\s+(?:code|implementation|data|artifact)|"
    r"(?:cannot|could\s+not|failed\s+to)\s+reproduc|"
    r"reproducib(?:ility\s+)?(?:concern|issue|problem|unclear)|"
    r"missing\s+(?:detail|details|hyperparameter|baseline|training\s+details)",
    re.I,
)


def label_from_text(text: str):
    text = str(text or "").strip()
    if not text:
        return None
    has_pos = bool(POS_RE.search(text))
    has_neg = bool(NEG_RE.search(text))
    if has_pos and not has_neg:
        return "YES"
    if has_neg and not has_pos:
        return "NO"
    return None


def label_from_score(score: float, high_thresh: float, low_thresh: float):
    if pd.isna(score):
        return None
    if score >= high_thresh:
        return "YES"
    if score <= low_thresh:
        return "NO"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Build YES/NO labels from reproducibility-specific review/decision text and score fallback."
    )
    parser.add_argument("--score-high-thresh", type=float, default=0.70)
    parser.add_argument("--score-low-thresh", type=float, default=0.30)
    parser.add_argument("--min-rows", type=int, default=20)
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

    stats = {
        "input_rows": int(len(df)),
        "labeled_from_reviewer_text": 0,
        "labeled_from_decision_text": 0,
        "labeled_from_score_fallback": 0,
        "dropped_ambiguous": 0,
    }

    labels = []
    sources = []

    for _, row in df.iterrows():
        review_text = str(row.get("review_text", "") or "")
        decision_text = str(row.get("decision_text", "") or "")
        auto_score = row.get("auto_score")

        label = label_from_text(review_text)
        if label is not None:
            stats["labeled_from_reviewer_text"] += 1
            labels.append(label)
            sources.append("review_text")
            continue

        label = label_from_text(decision_text)
        if label is not None:
            stats["labeled_from_decision_text"] += 1
            labels.append(label)
            sources.append("decision_text")
            continue

        label = label_from_score(auto_score, args.score_high_thresh, args.score_low_thresh)
        if label is not None:
            stats["labeled_from_score_fallback"] += 1
            labels.append(label)
            sources.append("score_fallback")
            continue

        stats["dropped_ambiguous"] += 1
        labels.append(None)
        sources.append("dropped")

    df["repro_label"] = labels
    df["label_source"] = sources
    df = df[df["repro_label"].notna()].copy().reset_index(drop=True)

    if len(df) < args.min_rows:
        raise RuntimeError(
            f"Only {len(df)} rows labeled (min={args.min_rows}). "
            f"Consider widening score thresholds or collecting more papers."
        )

    label_counts = {str(k): int(v) for k, v in df["repro_label"].value_counts().to_dict().items()}
    source_counts = {str(k): int(v) for k, v in df["label_source"].value_counts().to_dict().items()}

    df.to_csv(OUT_CSV, index=False)

    report = {
        "input_rows": stats["input_rows"],
        "rows_labeled": int(len(df)),
        "dropped_ambiguous": stats["dropped_ambiguous"],
        "labeled_from_reviewer_text": stats["labeled_from_reviewer_text"],
        "labeled_from_decision_text": stats["labeled_from_decision_text"],
        "labeled_from_score_fallback": stats["labeled_from_score_fallback"],
        "label_counts": label_counts,
        "label_source_counts": source_counts,
        "labeling_method": "repro_text_then_score_fallback",
        "score_thresholds": {"high": args.score_high_thresh, "low": args.score_low_thresh},
        "output_csv": str(OUT_CSV),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Labeled dataset saved to: {OUT_CSV}")
    print(f"✅ Labeling summary saved to: {REPORT_FILE}")
    print(f"✅ Rows labeled: {len(df)}")
    print(f"✅ Label counts: {label_counts}")
    print(f"✅ Label sources: {source_counts}")


if __name__ == "__main__":
    main()