"""
manage_reserved_uids.py — Manage the gold-eval reserved UID list (Gap 8).

The reserved_uids.txt file lists paper_uid values that must NEVER appear in
any training split. These are papers reserved exclusively for gold evaluation.

USAGE:
  # Add UIDs manually
  python manage_reserved_uids.py add or_abc123 or_def456

  # Import UIDs from a CSV (e.g., gold_eval_template.csv)
  python manage_reserved_uids.py import-csv data/gold_eval/gold_eval_template.csv

  # Show all reserved UIDs
  python manage_reserved_uids.py show

  # Check whether a UID is reserved
  python manage_reserved_uids.py check or_abc123

  # Audit: find reserved UIDs that leaked into labeled_dataset.csv
  python manage_reserved_uids.py audit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir

PIPELINE_DIR   = SRC_DIR.parent
RESERVED_FILE  = PIPELINE_DIR / "data" / "gold_eval" / "reserved_uids.txt"
LABELED_CSV    = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"


def load_reserved() -> set[str]:
    if not RESERVED_FILE.exists():
        return set()
    return {
        line.strip()
        for line in RESERVED_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def save_reserved(uids: set[str]) -> None:
    ensure_dir(RESERVED_FILE.parent)
    RESERVED_FILE.write_text(
        "# Reserved gold-eval UIDs — NEVER include in training data\n"
        "# Managed by manage_reserved_uids.py\n"
        + "\n".join(sorted(uids)) + "\n",
        encoding="utf-8",
    )


def cmd_add(args) -> None:
    reserved = load_reserved()
    new_uids = set(args.uids)
    added    = new_uids - reserved
    reserved |= new_uids
    save_reserved(reserved)
    print(f"✅ Added {len(added)} new UIDs. Total reserved: {len(reserved)}")
    for uid in sorted(added):
        print(f"   + {uid}")


def cmd_import_csv(args) -> None:
    path = Path(args.csv_file)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    if "paper_uid" not in df.columns and "pdf_id" not in df.columns:
        raise ValueError("CSV must have 'paper_uid' or 'pdf_id' column.")
    uid_col = "paper_uid" if "paper_uid" in df.columns else "pdf_id"
    new_uids = set(df[uid_col].dropna().astype(str).tolist())
    # Convert pdf_id to paper_uid format if needed
    if uid_col == "pdf_id":
        new_uids = {f"gold_{uid}" for uid in new_uids}
    reserved = load_reserved()
    added    = new_uids - reserved
    reserved |= new_uids
    save_reserved(reserved)
    print(f"✅ Imported {len(added)} new UIDs from {path.name}. Total: {len(reserved)}")


def cmd_show(args) -> None:
    reserved = load_reserved()
    if not reserved:
        print("No reserved UIDs yet.")
        return
    print(f"Reserved UIDs ({len(reserved)} total):")
    for uid in sorted(reserved):
        print(f"  {uid}")


def cmd_check(args) -> None:
    reserved = load_reserved()
    for uid in args.uids:
        status = "🚫 RESERVED (must not be in training)" if uid in reserved else "✅ Not reserved"
        print(f"  {uid}: {status}")


def cmd_audit(args) -> None:
    reserved = load_reserved()
    if not reserved:
        print("No reserved UIDs configured. Nothing to audit.")
        return
    if not LABELED_CSV.exists():
        print(f"Labeled dataset not found: {LABELED_CSV}")
        return

    df      = pd.read_csv(LABELED_CSV)
    if "paper_uid" not in df.columns:
        print("labeled_dataset.csv has no paper_uid column.")
        return

    leaked = df[df["paper_uid"].isin(reserved)]
    if leaked.empty:
        print("✅ No reserved UIDs found in labeled_dataset.csv — clean!")
    else:
        print(f"❌ LEAKAGE DETECTED: {len(leaked)} reserved UIDs are in labeled_dataset.csv!")
        for uid in leaked["paper_uid"].tolist():
            print(f"   {uid}")
        print("\nFix: Remove these rows from labeled_dataset.csv and re-split.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the gold-eval reserved UID list."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add UIDs to the reserved list.")
    add_p.add_argument("uids", nargs="+", help="paper_uid values to reserve.")

    imp_p = sub.add_parser("import-csv", help="Import UIDs from a CSV file.")
    imp_p.add_argument("csv_file", help="Path to CSV with paper_uid or pdf_id column.")

    sub.add_parser("show",  help="List all reserved UIDs.")

    chk_p = sub.add_parser("check", help="Check if specific UIDs are reserved.")
    chk_p.add_argument("uids", nargs="+")

    sub.add_parser("audit", help="Check for reserved UIDs that leaked into labeled_dataset.csv.")

    args = parser.parse_args()

    if   args.command == "add":        cmd_add(args)
    elif args.command == "import-csv": cmd_import_csv(args)
    elif args.command == "show":       cmd_show(args)
    elif args.command == "check":      cmd_check(args)
    elif args.command == "audit":      cmd_audit(args)


if __name__ == "__main__":
    main()
