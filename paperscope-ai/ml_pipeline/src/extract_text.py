
from __future__ import annotations

import sys
from pathlib import Path
import argparse
import re

import fitz
import pdfplumber
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import clean_text, clean_multiline_text, ensure_dir, read_jsonl, write_json, write_jsonl

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "extraction_report.json"


ABSTRACT_RE = re.compile(r"\babstract\b[:\s]*", re.I)
KEYWORDS_RE = re.compile(r"\bkeywords?\b[:\s]*", re.I)


def extract_with_pymupdf(pdf_path: Path, max_pages: int = 60) -> tuple[list[str], int]:
    page_texts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            txt = page.get_text("text") or ""
            page_texts.append(txt)
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
            txt = page.extract_text() or ""
            page_texts.append(txt)
        page_count = len(pdf.pages)
    return page_texts, page_count


def guess_title_from_pages(page_texts: list[str]) -> str:
    if not page_texts:
        return ""
    first_page = clean_multiline_text(page_texts[0])
    if not first_page:
        return ""
    candidates = []
    for line in first_page.split("\n")[:25]:
        line = clean_text(line)
        low = line.lower()
        if not line:
            continue
        if low.startswith(("abstract", "keywords", "index terms", "introduction", "arxiv:", "preprint")):
            break
        if "@" in line:
            continue
        if len(line) < 10:
            continue
        if len(line.split()) > 30:
            continue
        candidates.append(line)
        if len(candidates) >= 2:
            break
    return clean_text(" ".join(candidates[:2]))


def guess_abstract_from_text(raw_text: str, max_chars: int = 2500) -> str:
    text = clean_multiline_text(raw_text)
    if not text:
        return ""
    m = ABSTRACT_RE.search(text)
    if not m:
        return ""
    start = m.end()
    tail = text[start : start + max_chars]
    stop_patterns = [
        r"\n\s*1[\.\s]+introduction\b",
        r"\n\s*i[\.\s]+introduction\b",
        r"\n\s*keywords?\b",
        r"\n\s*index terms\b",
    ]
    end = len(tail)
    for pat in stop_patterns:
        sm = re.search(pat, "\n" + tail, flags=re.I)
        if sm:
            end = min(end, max(0, sm.start()))
    abstract = clean_text(tail[:end])
    return abstract[:1800]


def guess_keywords_from_text(raw_text: str, max_chars: int = 500) -> str:
    text = clean_multiline_text(raw_text)
    if not text:
        return ""
    m = KEYWORDS_RE.search(text)
    if not m:
        return ""
    tail = text[m.end() : m.end() + max_chars]
    tail = re.split(r"\n\s*(?:1[\.\s]+introduction|introduction)\b", "\n" + tail, flags=re.I)[0]
    return clean_text(tail[:300])


def build_model_text(title: str, abstract: str, keywords: str, raw_text: str, max_chars: int = 80000) -> str:
    title = clean_text(title)
    abstract = clean_text(abstract)
    keywords = clean_text(keywords)
    raw_text = clean_multiline_text(raw_text)
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    if keywords:
        parts.append(f"Keywords: {keywords}")
    if raw_text:
        parts.append(raw_text[:max_chars])
    return "\n\n".join(parts).strip()


def main():
    parser = argparse.ArgumentParser(description="Extract and clean PDF text with better metadata recovery.")
    parser.add_argument("--require-pdf-text", action="store_true")
    parser.add_argument("--min-raw-chars", type=int, default=1200)
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--max-model-chars", type=int, default=80000)
    args = parser.parse_args()

    ensure_dir(OUT_FILE.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Input file not found or empty: {IN_FILE}")

    extracted = []
    seen_uids = set()
    stats = {
        "input_rows": len(rows),
        "kept_rows": 0,
        "duplicate_paper_uid_dropped": 0,
        "missing_pdf_path": 0,
        "pymupdf_success": 0,
        "pdfplumber_success": 0,
        "pdf_extract_failed": 0,
        "dropped_short_raw_text": 0,
        "rows_with_review_text": 0,
        "rows_with_decision_text": 0,
        "title_filled_from_pdf": 0,
        "abstract_filled_from_pdf": 0,
        "keywords_filled_from_pdf": 0,
    }

    for row in tqdm(rows, desc="Extracting PDF text"):
        paper_uid = str(row.get("paper_uid", "") or "").strip()
        if not paper_uid:
            continue
        if paper_uid in seen_uids:
            stats["duplicate_paper_uid_dropped"] += 1
            continue
        seen_uids.add(paper_uid)

        pdf_path = str(row.get("pdf_path", "") or "").strip()
        page_texts: list[str] = []
        page_count = 0

        if pdf_path:
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                try:
                    page_texts, page_count = extract_with_pymupdf(pdf_file, max_pages=args.max_pages)
                    stats["pymupdf_success"] += 1
                except Exception:
                    try:
                        page_texts, page_count = extract_with_pdfplumber(pdf_file, max_pages=args.max_pages)
                        stats["pdfplumber_success"] += 1
                    except Exception:
                        page_texts = []
                        page_count = 0
                        stats["pdf_extract_failed"] += 1
            else:
                stats["missing_pdf_path"] += 1
        else:
            stats["missing_pdf_path"] += 1

        raw_text = clean_multiline_text("\n\n".join(page_texts))
        if args.require_pdf_text and len(raw_text) < args.min_raw_chars:
            stats["dropped_short_raw_text"] += 1
            continue

        title = clean_text(row.get("title", ""))
        abstract = clean_text(row.get("abstract", ""))
        keywords = clean_text(row.get("keywords", ""))
        review_text = clean_text(row.get("review_text", ""))
        decision_text = clean_text(row.get("decision_text", ""))

        if not title and page_texts:
            title = guess_title_from_pages(page_texts)
            if title:
                stats["title_filled_from_pdf"] += 1
        if not abstract and raw_text:
            abstract = guess_abstract_from_text(raw_text)
            if abstract:
                stats["abstract_filled_from_pdf"] += 1
        if not keywords and raw_text:
            keywords = guess_keywords_from_text(raw_text)
            if keywords:
                stats["keywords_filled_from_pdf"] += 1

        if review_text:
            stats["rows_with_review_text"] += 1
        if decision_text:
            stats["rows_with_decision_text"] += 1

        model_text = build_model_text(title, abstract, keywords, raw_text, max_chars=args.max_model_chars)
        if not model_text:
            continue

        extracted.append(
            {
                "paper_uid": paper_uid,
                "source": clean_text(row.get("source", "")),
                "venue": clean_text(row.get("venue", "")),
                "year": clean_text(row.get("year", "")),
                "openreview_id": clean_text(row.get("openreview_id", "")),
                "forum_id": clean_text(row.get("forum_id", "")),
                "title": title,
                "abstract": abstract,
                "keywords": keywords,
                "pdf_url": clean_text(row.get("pdf_url", "")),
                "pdf_path": pdf_path,
                "pdf_downloaded": bool(row.get("pdf_downloaded", False)),
                "pdf_download_source": clean_text(row.get("pdf_download_source", "")),
                "raw_text": raw_text,
                "page_count": int(page_count),
                "review_text": review_text,
                "decision_text": decision_text,
                "model_text": model_text,
                "raw_text_chars": len(raw_text),
                "review_text_chars": len(review_text),
                "decision_text_chars": len(decision_text),
                "model_text_chars": len(model_text),
            }
        )

    write_jsonl(OUT_FILE, extracted)
    stats["kept_rows"] = len(extracted)
    write_json(REPORT_FILE, stats)

    print(f"✅ Extracted rows saved to: {OUT_FILE}")
    print(f"✅ Report saved to: {REPORT_FILE}")
    print(f"✅ Rows kept: {len(extracted)}")


if __name__ == "__main__":
    main()
