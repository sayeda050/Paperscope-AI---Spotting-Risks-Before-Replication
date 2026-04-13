"""
merge_extracted_text.py — Merge per-domain extracted text files for the
distributed collection workflow.

DISTRIBUTED WORKFLOW OPTION
────────────────────────────
Instead of sharing PDF files, each teammate runs the full collection +
download + extract pipeline locally for their domain, then shares ONLY
their extracted_text_{domain}.jsonl file (~50 MB vs ~4 GB of PDFs).

Teammate steps:
  1. python collect_arxiv.py --domain physics --max-results 200
  2. python download_openreview_pdfs.py --input-file data/raw/arxiv_raw_physics.jsonl
                                        --domain physics --max-papers 200
  3. python extract_text.py --domain physics
  → produces: data/processed/extracted_text_physics.jsonl
  4. Share extracted_text_physics.jsonl with coordinator.

Coordinator step:
  python merge_extracted_text.py
  → produces: data/processed/extracted_text.jsonl (unified, used by all downstream scripts)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import SUPPORTED_DOMAINS
from utils import ensure_dir, read_jsonl, write_json, write_jsonl, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
PROCESSED_DIR = PIPELINE_DIR / "data" / "processed"
OUT_FILE = PROCESSED_DIR / "extracted_text.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "merge_extracted_report.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge per-domain extracted_text_{domain}.jsonl files into "
            "the unified extracted_text.jsonl that downstream scripts expect."
        )
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        default=SUPPORTED_DOMAINS,
        help="Domains to include (default: all supported).",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="",
        help="Override processed directory path.",
    )
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir) if args.processed_dir else PROCESSED_DIR
    ensure_dir(processed_dir)
    ensure_dir(REPORT_FILE.parent)

    all_rows: list[dict] = []
    seen_uids: set[str] = set()
    report: list[dict] = []

    for domain in args.domains:
        # Per-domain file produced by extract_text.py --domain {domain}
        domain_file = processed_dir / f"extracted_text_{domain}.jsonl"
        if not domain_file.exists():
            print(f"⚠  Not found (skipping): {domain_file.name}")
            report.append({"domain": domain, "rows": 0, "found": False})
            continue

        rows = read_jsonl(domain_file)
        deduped: list[dict] = []
        for row in rows:
            uid = row.get("paper_uid", "")
            if uid and uid not in seen_uids:
                # Ensure domain field is set
                row.setdefault("domain", domain)
                row.setdefault("schema_version", PIPELINE_SCHEMA_VERSION)
                seen_uids.add(uid)
                deduped.append(row)

        all_rows.extend(deduped)
        print(f"✅ {domain:12s}: {len(deduped):4d} rows from {domain_file.name}")
        report.append({"domain": domain, "rows": len(deduped), "found": True})

    # Also load the existing unified file if no per-domain files were found
    # (backward compatibility: if running extract_text.py without --domain)
    if not all_rows:
        existing = processed_dir / "extracted_text.jsonl"
        if existing.exists():
            print("⚠  No per-domain files found. Using existing extracted_text.jsonl as-is.")
            return
        print("❌ No extracted text files found. Run extract_text.py first.")
        sys.exit(1)

    write_jsonl(OUT_FILE, all_rows)
    write_json(
        REPORT_FILE,
        {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "total_rows": len(all_rows),
            "domain_breakdown": report,
            "output_file": str(OUT_FILE),
        },
    )

    print(f"\n✅ Merged {len(all_rows)} rows → {OUT_FILE}")


if __name__ == "__main__":
    main()
