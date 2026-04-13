"""
extract_text.py — Extract and clean text from downloaded PDFs.

Supports the distributed workflow:
  - Without --domain: reads linked_with_pdfs.jsonl, writes extracted_text.jsonl
  - With --domain:    filters to that domain, writes extracted_text_{domain}.jsonl
                      (each teammate runs this for their domain; coordinator merges)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import fitz
import pdfplumber
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import SUPPORTED_DOMAINS, validate_domain
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_multiline_text,
    clean_text,
    ensure_dir,
    read_jsonl,
    write_json,
    write_jsonl,
)

PIPELINE_DIR = SRC_DIR.parent
IN_FILE      = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
OUT_FILE     = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
REPORT_FILE  = PIPELINE_DIR / "outputs" / "reports" / "extraction_report.json"

ABSTRACT_RE = re.compile(r"\babstract\b[:\s]*", re.I)
KEYWORDS_RE = re.compile(r"\bkeywords?\b[:\s]*", re.I)


def extract_with_pymupdf(pdf_path: Path, max_pages: int = 60) -> tuple[list[str], int]:
    page_texts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            page_texts.append(page.get_text("text") or "")
        page_count = len(doc)
    finally:
        doc.close()
    return page_texts, page_count


def extract_with_pdfplumber(pdf_path: Path, max_pages: int = 60) -> tuple[list[str], int]:
    page_texts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            page_texts.append(page.extract_text() or "")
        page_count = len(pdf.pages)
    return page_texts, page_count


def guess_title(page_texts: list[str]) -> str:
    if not page_texts:
        return ""
    first_page = clean_multiline_text(page_texts[0])
    candidates: list[str] = []
    for line in first_page.split("\n")[:25]:
        line = clean_text(line)
        low  = line.lower()
        if not line or len(line) < 10:
            continue
        if low.startswith(("abstract", "keywords", "index terms", "introduction", "arxiv:", "preprint")):
            break
        if "@" in line or len(line.split()) > 30:
            continue
        candidates.append(line)
        if len(candidates) >= 2:
            break
    return clean_text(" ".join(candidates[:2]))


def guess_abstract(raw_text: str, max_chars: int = 2500) -> str:
    text = clean_multiline_text(raw_text)
    m = ABSTRACT_RE.search(text)
    if not m:
        return ""
    tail  = text[m.end(): m.end() + max_chars]
    stops = [
        r"\n\s*1[\.\s]+introduction\b",
        r"\n\s*i[\.\s]+introduction\b",
        r"\n\s*keywords?\b",
        r"\n\s*index terms\b",
    ]
    end = len(tail)
    for pat in stops:
        sm = re.search(pat, "\n" + tail, flags=re.I)
        if sm:
            end = min(end, max(0, sm.start()))
    return clean_text(tail[:end])[:1800]


def guess_keywords(raw_text: str, max_chars: int = 500) -> str:
    text = clean_multiline_text(raw_text)
    m = KEYWORDS_RE.search(text)
    if not m:
        return ""
    tail = text[m.end(): m.end() + max_chars]
    tail = re.split(r"\n\s*(?:1[\.\s]+introduction|introduction)\b", "\n" + tail, flags=re.I)[0]
    return clean_text(tail[:300])


def build_model_text(
    title: str, abstract: str, keywords: str, raw_text: str, max_chars: int = 80_000
) -> str:
    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    if keywords:
        parts.append(f"Keywords: {keywords}")
    if raw_text:
        parts.append(raw_text[:max_chars])
    return "\n\n".join(parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs (all domains or a single domain)."
    )
    parser.add_argument(
        "--domain", default="",
        help=(
            "Process only papers from this domain. "
            "Output goes to extracted_text_{domain}.jsonl for distributed merging."
        ),
    )
    parser.add_argument("--require-pdf-text",  action="store_true")
    parser.add_argument("--min-raw-chars",     type=int, default=1200)
    parser.add_argument("--max-pages",         type=int, default=60)
    parser.add_argument("--max-model-chars",   type=int, default=80_000)
    parser.add_argument(
        "--input-file", default="",
        help="Override input JSONL path (default: linked_with_pdfs.jsonl).",
    )
    args = parser.parse_args()

    domain_filter = ""
    if args.domain:
        domain_filter = validate_domain(args.domain)

    in_file = Path(args.input_file) if args.input_file else IN_FILE
    if not in_file.exists():
        raise FileNotFoundError(
            f"Missing input file: {in_file}\n"
            "Run download_openreview_pdfs.py first."
        )

    # Output path: domain-specific or global
    if domain_filter:
        out_file    = PIPELINE_DIR / "data" / "processed" / f"extracted_text_{domain_filter}.jsonl"
        report_file = PIPELINE_DIR / "outputs" / "reports" / f"extraction_report_{domain_filter}.json"
    else:
        out_file    = OUT_FILE
        report_file = REPORT_FILE

    ensure_dir(out_file.parent)
    ensure_dir(report_file.parent)

    rows = read_jsonl(in_file)
    if not rows:
        raise FileNotFoundError(f"Empty or missing input: {in_file}")

    if domain_filter:
        rows = [r for r in rows if r.get("domain", "") == domain_filter]
        print(f"Filtered to domain {domain_filter!r}: {len(rows)} rows")

    extracted:  list[dict] = []
    seen_uids:  set[str]   = set()
    stats = {
        "input_rows":                    len(rows),
        "kept_rows":                     0,
        "duplicate_uid_dropped":         0,
        "missing_pdf_path":              0,
        "pymupdf_success":               0,
        "pdfplumber_success":            0,
        "pdf_extract_failed":            0,
        "dropped_short_raw_text":        0,
        "rows_with_review_text":         0,
        "rows_with_decision_text":       0,
        "title_filled_from_pdf":         0,
        "abstract_filled_from_pdf":      0,
        "keywords_filled_from_pdf":      0,
    }

    for row in tqdm(rows, desc="Extracting text"):
        uid = str(row.get("paper_uid", "") or "").strip()
        if not uid:
            continue
        if uid in seen_uids:
            stats["duplicate_uid_dropped"] += 1
            continue
        seen_uids.add(uid)

        domain = str(row.get("domain", domain_filter or "ml") or "ml")

        pdf_path_str = str(row.get("pdf_path", "") or "").strip()
        page_texts:  list[str] = []
        page_count = 0

        if pdf_path_str:
            pdf_file = Path(pdf_path_str)
            if pdf_file.exists():
                try:
                    page_texts, page_count = extract_with_pymupdf(pdf_file, args.max_pages)
                    stats["pymupdf_success"] += 1
                except Exception:
                    try:
                        page_texts, page_count = extract_with_pdfplumber(pdf_file, args.max_pages)
                        stats["pdfplumber_success"] += 1
                    except Exception:
                        stats["pdf_extract_failed"] += 1
            else:
                stats["missing_pdf_path"] += 1
        else:
            stats["missing_pdf_path"] += 1

        raw_text = clean_multiline_text("\n\n".join(page_texts))
        if args.require_pdf_text and len(raw_text) < args.min_raw_chars:
            stats["dropped_short_raw_text"] += 1
            continue

        title         = clean_text(row.get("title", ""))
        abstract      = clean_text(row.get("abstract", ""))
        keywords      = clean_text(row.get("keywords", ""))
        review_text   = clean_text(row.get("review_text", ""))
        decision_text = clean_text(row.get("decision_text", ""))

        if not title and page_texts:
            title = guess_title(page_texts)
            if title:
                stats["title_filled_from_pdf"] += 1
        if not abstract and raw_text:
            abstract = guess_abstract(raw_text)
            if abstract:
                stats["abstract_filled_from_pdf"] += 1
        if not keywords and raw_text:
            keywords = guess_keywords(raw_text)
            if keywords:
                stats["keywords_filled_from_pdf"] += 1

        if review_text:
            stats["rows_with_review_text"] += 1
        if decision_text:
            stats["rows_with_decision_text"] += 1

        model_text = build_model_text(title, abstract, keywords, raw_text, args.max_model_chars)
        if not model_text:
            continue

        extracted.append({
            "schema_version":       PIPELINE_SCHEMA_VERSION,
            "paper_uid":            uid,
            "source":               clean_text(row.get("source", "")),
            "domain":               domain,
            "venue":                clean_text(row.get("venue", "")),
            "year":                 clean_text(row.get("year", "")),
            "openreview_id":        clean_text(row.get("openreview_id", "")),
            "forum_id":             clean_text(row.get("forum_id", "")),
            "title":                title,
            "abstract":             abstract,
            "keywords":             keywords,
            "pdf_url":              clean_text(row.get("pdf_url", "")),
            "pdf_path":             pdf_path_str,
            "pdf_downloaded":       bool(row.get("pdf_downloaded", False)),
            "pdf_download_source":  clean_text(row.get("pdf_download_source", "")),
            "raw_text":             raw_text,
            "page_count":           int(page_count),
            "review_text":          review_text,
            "decision_text":        decision_text,
            "model_text":           model_text,
            "raw_text_chars":       len(raw_text),
            "review_text_chars":    len(review_text),
            "decision_text_chars":  len(decision_text),
            "model_text_chars":     len(model_text),
        })

    write_jsonl(out_file, extracted)
    stats["kept_rows"] = len(extracted)
    write_json(report_file, {**stats, "schema_version": PIPELINE_SCHEMA_VERSION})

    print(f"✅ Extracted {len(extracted)} rows → {out_file}")
    print(f"✅ Report → {report_file}")
    if domain_filter:
        print(f"📤 Share this file with coordinator: {out_file.name}")


if __name__ == "__main__":
    main()
