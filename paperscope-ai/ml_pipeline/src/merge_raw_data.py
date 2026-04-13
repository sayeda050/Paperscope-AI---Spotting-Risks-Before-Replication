"""
merge_raw_data.py — Merge all per-domain raw JSONL files into one unified file.

Run this AFTER all teammates have placed their arxiv_raw_{domain}.jsonl files
in data/raw/.  This is the coordinator's step.

Output: data/raw/unified_raw_dataset.jsonl
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
RAW_DIR = PIPELINE_DIR / "data" / "raw"
OUT_FILE = RAW_DIR / "unified_raw_dataset.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "merge_report.json"

# Maximum papers to include per domain (prevents one domain from dominating)
DEFAULT_MAX_PER_DOMAIN: dict[str, int] = {
    "ml":       1000,   # existing OpenReview corpus
    "physics":   200,
    "biomed":    200,
    "nlp":       200,
    "finance":   200,
    "hardware":  200,
    "math":      200,
}


def load_domain_rows(raw_dir: Path, domain: str, max_rows: int) -> list[dict]:
    """Load rows for a domain from its canonical raw file."""
    # ML uses openreview_raw.jsonl; all others use arxiv_raw_{domain}.jsonl
    if domain == "ml":
        candidates = [
            raw_dir / "openreview_raw.jsonl",
        ]
    else:
        candidates = [
            raw_dir / f"arxiv_raw_{domain}.jsonl",
        ]

    for path in candidates:
        if path.exists():
            rows = read_jsonl(path)
            # Ensure domain field is set
            for row in rows:
                row.setdefault("domain", domain)
                row.setdefault("schema_version", PIPELINE_SCHEMA_VERSION)
            if max_rows and len(rows) > max_rows:
                rows = rows[:max_rows]
            return rows

    return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge all per-domain raw JSONL files into unified_raw_dataset.jsonl.\n"
            "Run this after all teammates have shared their domain collection files."
        )
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        default=SUPPORTED_DOMAINS,
        help="Domains to include (default: all supported domains).",
    )
    parser.add_argument(
        "--max-per-domain",
        type=int,
        default=0,
        help="Override max rows per domain (0 = use defaults per domain).",
    )
    args = parser.parse_args()

    ensure_dir(RAW_DIR)
    ensure_dir(REPORT_FILE.parent)

    all_rows: list[dict] = []
    seen_uids: set[str] = set()
    report_rows: list[dict] = []

    for domain in args.domains:
        if domain not in SUPPORTED_DOMAINS:
            print(f"⚠  Skipping unknown domain: {domain!r}")
            continue

        max_rows = args.max_per_domain or DEFAULT_MAX_PER_DOMAIN.get(domain, 200)
        rows = load_domain_rows(RAW_DIR, domain, max_rows)

        # Deduplicate by paper_uid across all domains
        deduped: list[dict] = []
        for row in rows:
            uid = row.get("paper_uid", "")
            if uid and uid not in seen_uids:
                seen_uids.add(uid)
                deduped.append(row)

        all_rows.extend(deduped)
        status = "✅" if deduped else "⚠ "
        print(f"{status} {domain:12s}: {len(deduped):4d} rows")
        report_rows.append({
            "domain": domain,
            "rows_loaded": len(deduped),
            "file_found": len(rows) > 0,
        })

    if not all_rows:
        print("\n❌ No rows loaded. Check that raw JSONL files exist in data/raw/")
        sys.exit(1)

    write_jsonl(OUT_FILE, all_rows)

    report = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "total_rows": len(all_rows),
        "unique_domains": list({r.get("domain", "unknown") for r in all_rows}),
        "domain_breakdown": report_rows,
        "output_file": str(OUT_FILE),
    }
    write_json(REPORT_FILE, report)

    print(f"\n✅ Unified dataset: {len(all_rows)} total rows → {OUT_FILE}")
    print(f"✅ Merge report → {REPORT_FILE}")


if __name__ == "__main__":
    main()
