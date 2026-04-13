"""
build_gold_eval_template.py — Build a gold evaluation template CSV from gold PDFs.

Reads PDFs from data/gold_pdfs/, auto-fills rubric predictions, leaves
gold_* columns blank for human/LLM review.

Also manages the reserved_uids.txt file to prevent gold papers from ever
appearing in training data (Gap 8 fix).
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path
from typing import Iterable

import fitz

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from discover_pdf_features import extract_feature_record
from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_multiline_text,
    clean_text,
    ensure_dir,
    risk_label_from_score,
)

BASE_DIR = SRC_DIR.parent
PDF_DIR  = BASE_DIR / "data" / "gold_pdfs"
OUT_DIR  = BASE_DIR / "data" / "gold_eval"
OUT_CSV  = OUT_DIR / "gold_eval_template.csv"
RESERVED_UIDS_FILE = OUT_DIR / "reserved_uids.txt"

HEADERS = (
    ["pdf_id", "pdf_filename", "pdf_path", "domain", "title_auto", "page_count", "text_char_count"]
    + [f"prefill_{name}" for name in ATTRIBUTE_ORDER]
    + ["prefill_risk_score", "prefill_risk_label", "manual_title"]
    + [f"gold_{name}" for name in ATTRIBUTE_ORDER]
    + ["gold_risk_score", "gold_risk_label", "notes"]
)


def iter_pdfs(pdf_dir: Path) -> Iterable[Path]:
    for path in sorted(pdf_dir.rglob("*.pdf")):
        if path.is_file():
            yield path


def guess_domain_from_path(pdf_path: Path) -> str:
    """Infer domain from parent folder name if PDFs are organized by domain."""
    parent = pdf_path.parent.name.lower()
    for dom in SUPPORTED_DOMAINS:
        if dom in parent:
            return dom
    return "ml"


def extract_title(doc: fitz.Document) -> str:
    meta_title = clean_text((doc.metadata or {}).get("title", ""))
    if meta_title and len(meta_title) >= 12 and "@" not in meta_title:
        return meta_title
    if len(doc) == 0:
        return ""
    first_page = doc[0].get_text("text") or ""
    lines      = [clean_text(x) for x in first_page.splitlines() if clean_text(x)]
    candidates: list[str] = []
    for line in lines[:20]:
        low = line.lower()
        if low.startswith(("abstract", "arxiv:", "index terms", "keywords")):
            break
        if "@" in line or len(line) < 8:
            continue
        candidates.append(line)
        if len(candidates) >= 2:
            break
    return clean_text(" ".join(candidates[:2]))


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, str, int]:
    with fitz.open(pdf_path) as doc:
        title = extract_title(doc)
        parts = [page.get_text("text") or "" for page in doc]
        text  = clean_multiline_text("\n".join(parts))
        return title, text, len(doc)


def score_to_prefills(record: dict) -> dict:
    attr_map = {a["name"]: a for a in record["attributes"]}
    row = {f"prefill_{name}": attr_map[name]["state"] for name in ATTRIBUTE_ORDER}
    row["prefill_risk_score"] = round(float(record["risk_score"]), 2)
    row["prefill_risk_label"] = risk_label_from_score(float(record["risk_score"]))
    return row


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Build gold eval template from PDFs in data/gold_pdfs/."
    )
    parser.add_argument(
        "--default-domain", default="ml",
        help="Default domain for PDFs without a domain subfolder (default: ml).",
    )
    args = parser.parse_args()

    ensure_dir(OUT_DIR)
    ensure_dir(PDF_DIR)

    pdf_paths = list(iter_pdfs(PDF_DIR))
    if not pdf_paths:
        print(f"⚠  No PDFs found in {PDF_DIR}")
        print("   Place your gold evaluation PDFs there and re-run.")
        return

    rows: list[dict] = []
    reserved_uids:  list[str] = []

    for pdf_path in pdf_paths:
        try:
            title, text, page_count = extract_text_from_pdf(pdf_path)
        except Exception as e:
            print(f"⚠  Failed to extract {pdf_path.name}: {e}")
            continue

        sha1   = hashlib.sha1(pdf_path.read_bytes()).hexdigest()[:12]
        domain = guess_domain_from_path(pdf_path) or args.default_domain

        uid = f"gold_{sha1}"
        reserved_uids.append(uid)

        try:
            record = extract_feature_record(
                {
                    "paper_uid": uid,
                    "domain":    domain,
                    "title":     title,
                    "abstract":  "",
                    "keywords":  "",
                    "raw_text":  text,
                },
                domain=domain,
            )
        except Exception as e:
            print(f"⚠  Feature extraction failed for {pdf_path.name}: {e}")
            continue

        row = {
            "pdf_id":         sha1,
            "pdf_filename":   pdf_path.name,
            "pdf_path":       str(pdf_path.relative_to(BASE_DIR)).replace("\\", "/"),
            "domain":         domain,
            "title_auto":     title,
            "page_count":     page_count,
            "text_char_count": len(text),
            **score_to_prefills(record),
            "manual_title":   "",
            **{f"gold_{name}": "" for name in ATTRIBUTE_ORDER},
            "gold_risk_score": "",
            "gold_risk_label": "",
            "notes":           "",
        }
        rows.append(row)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Write / update reserved UIDs file (Gap 8 fix)
    existing_reserved: set[str] = set()
    if RESERVED_UIDS_FILE.exists():
        existing_reserved = {
            line.strip()
            for line in RESERVED_UIDS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    all_reserved = sorted(existing_reserved | set(reserved_uids))
    RESERVED_UIDS_FILE.write_text(
        "# Reserved gold-eval UIDs — never include in training data\n"
        + "\n".join(all_reserved) + "\n",
        encoding="utf-8",
    )

    print(f"✅ Gold eval template → {OUT_CSV}  ({len(rows)} rows)")
    print(f"✅ Reserved UIDs file → {RESERVED_UIDS_FILE}  ({len(all_reserved)} UIDs)")
    print("\nNext steps:")
    print("  Option A: python llm_auto_label.py --domain ml   (auto-fill scores with LLM)")
    print("  Option B: Fill gold_* columns manually in gold_eval_template.csv")
    print("  Then:     python evaluate_gold_eval.py")


if __name__ == "__main__":
    main()
