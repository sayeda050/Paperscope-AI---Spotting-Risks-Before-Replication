"""
correction_log.py — Active learning feedback loop for PaperScope AI.

When predict_pdf.py produces a wrong prediction on a real paper, this script
records the correction and injects it back into the training pipeline with
label_source = "human_correction" and label_confidence = 1.0.

USAGE:
  # Log a correction
  python correction_log.py log --paper-uid or_abc123 --predicted NO --corrected YES --reason "Code is on GitHub"

  # Apply all pending corrections to labeled_dataset.csv
  python correction_log.py apply

  # Show correction history
  python correction_log.py show

ARCHITECTURE (Gap 7 fix):
  - Corrections go to data/corrections/correction_log.jsonl
  - apply mode merges corrections into labeled_dataset.csv with highest priority
  - Re-run split_dataset.py + train_tfidf_logreg.py after applying
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir, read_jsonl, write_json, write_jsonl, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
CORRECTIONS_DIR  = PIPELINE_DIR / "data" / "corrections"
CORRECTION_LOG   = CORRECTIONS_DIR / "correction_log.jsonl"
LABELED_DATASET  = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
REPORT_FILE      = PIPELINE_DIR / "outputs" / "reports" / "correction_report.json"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_log(args) -> None:
    """Record a single correction."""
    ensure_dir(CORRECTIONS_DIR)

    if args.predicted not in ("YES", "NO"):
        raise ValueError("--predicted must be YES or NO")
    if args.corrected not in ("YES", "NO"):
        raise ValueError("--corrected must be YES or NO")

    entry = {
        "schema_version":    PIPELINE_SCHEMA_VERSION,
        "paper_uid":         args.paper_uid,
        "domain":            args.domain or "ml",
        "predicted_label":   args.predicted,
        "corrected_label":   args.corrected,
        "corrected_by":      args.corrected_by or "human",
        "reason":            args.reason or "",
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "applied":           False,
    }

    # Append to log
    existing = read_jsonl(CORRECTION_LOG)
    existing.append(entry)
    write_jsonl(CORRECTION_LOG, existing)

    print(f"✅ Correction logged for paper_uid={args.paper_uid!r}")
    print(f"   Predicted: {args.predicted} → Corrected: {args.corrected}")
    print(f"   Reason: {args.reason or '(none)'}")
    print(f"\n📋 To apply: python correction_log.py apply")


def cmd_apply(args) -> None:
    """Merge pending corrections into labeled_dataset.csv."""
    if not CORRECTION_LOG.exists():
        print("No correction log found. Nothing to apply.")
        return

    corrections = read_jsonl(CORRECTION_LOG)
    pending     = [c for c in corrections if not c.get("applied", False)]

    if not pending:
        print("No pending corrections. All already applied.")
        return

    if not LABELED_DATASET.exists():
        raise FileNotFoundError(
            f"Missing: {LABELED_DATASET}\nRun build_labeled_dataset_auto.py first."
        )

    df = pd.read_csv(LABELED_DATASET)
    if "paper_uid" not in df.columns:
        raise ValueError("labeled_dataset.csv missing 'paper_uid' column.")

    applied_count = 0
    skipped_not_found = 0

    for correction in pending:
        uid     = correction["paper_uid"]
        label   = correction["corrected_label"]
        domain  = correction.get("domain", "ml")

        if uid in df["paper_uid"].values:
            # Update existing row
            mask = df["paper_uid"] == uid
            df.loc[mask, "repro_label"]        = label
            df.loc[mask, "label_source"]       = "human_correction"
            df.loc[mask, "label_confidence"]   = 1.0
            df.loc[mask, "label_reason"]       = f"human_correction: {correction.get('reason', '')}"[:200]
            applied_count += 1
        else:
            # Skip: we only correct papers already in the dataset
            print(f"⚠  paper_uid {uid!r} not found in labeled_dataset.csv — skipping.")
            skipped_not_found += 1

    df.to_csv(LABELED_DATASET, index=False)

    # Mark corrections as applied
    for c in corrections:
        if not c.get("applied", False):
            c["applied"]    = True
            c["applied_at"] = datetime.now(timezone.utc).isoformat()
    write_jsonl(CORRECTION_LOG, corrections)

    report = {
        "schema_version":       PIPELINE_SCHEMA_VERSION,
        "pending_corrections":  len(pending),
        "applied_count":        applied_count,
        "skipped_not_found":    skipped_not_found,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
    }
    ensure_dir(REPORT_FILE.parent)
    write_json(REPORT_FILE, report)

    print(f"✅ Applied {applied_count} corrections to labeled_dataset.csv")
    if skipped_not_found:
        print(f"⚠  Skipped {skipped_not_found} (paper not found in dataset)")
    print("\n📋 Next steps:")
    print("   python split_dataset.py")
    print("   python train_tfidf_logreg.py --domain <domain>")


def cmd_show(args) -> None:
    """Display correction history."""
    if not CORRECTION_LOG.exists():
        print("No correction log found.")
        return

    corrections = read_jsonl(CORRECTION_LOG)
    if not corrections:
        print("Correction log is empty.")
        return

    pending  = [c for c in corrections if not c.get("applied", False)]
    applied_ = [c for c in corrections if c.get("applied", False)]

    print(f"\n{'='*70}")
    print(f"CORRECTION LOG — {len(corrections)} total | {len(pending)} pending | {len(applied_)} applied")
    print(f"{'='*70}")
    for c in corrections[-20:]:   # show last 20
        status = "✅ applied" if c.get("applied") else "⏳ pending"
        print(
            f"  {status} | {c.get('timestamp', '')[:19]} | "
            f"{c.get('paper_uid', '')[:30]:30s} | "
            f"{c.get('predicted_label', '?')} → {c.get('corrected_label', '?')} | "
            f"{c.get('reason', '')[:40]}"
        )

    if len(corrections) > 20:
        print(f"  ... and {len(corrections) - 20} more")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="PaperScope AI active learning correction loop."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    log_p = sub.add_parser("log", help="Record a correction for a specific paper.")
    log_p.add_argument("--paper-uid",    required=True, help="paper_uid of the mislabeled paper.")
    log_p.add_argument("--predicted",    required=True, choices=["YES", "NO"], help="What the model predicted.")
    log_p.add_argument("--corrected",    required=True, choices=["YES", "NO"], help="The correct label.")
    log_p.add_argument("--domain",       default="ml",  help="Domain (default: ml).")
    log_p.add_argument("--reason",       default="",    help="Brief reason for correction.")
    log_p.add_argument("--corrected-by", default="human", help="Who made the correction.")

    # apply
    apply_p = sub.add_parser("apply", help="Apply pending corrections to labeled_dataset.csv.")

    # show
    show_p = sub.add_parser("show", help="Show correction history.")

    args = parser.parse_args()

    if args.command == "log":
        cmd_log(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "show":
        cmd_show(args)


if __name__ == "__main__":
    main()
