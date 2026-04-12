import sys
from pathlib import Path
import json
import argparse
import re

import fitz
import pdfplumber
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, write_jsonl, clean_text, ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "extraction_report.json"


def normalize_pdf_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        lines.append(stripped)
    return clean_text("\n".join(lines))


def extract_with_pymupdf(pdf_path: Path, max_pages: int = 50) -> str:
    text_parts = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            txt = page.get_text("text")
            if txt:
                text_parts.append(txt)
    finally:
        doc.close()
    return "\n".join(text_parts)


def extract_with_pdfplumber(pdf_path: Path, max_pages: int = 50) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)


def build_model_text(title: str, abstract: str, keywords: str, raw_text: str) -> str:
    """
    Build the text used by the text classifier.

    Important: review_text and decision_text are kept in the output JSONL for
    downstream weak labeling and analysis, but are intentionally NOT included in
    model_text. If labels are partly derived from review/decision text, putting
    them inside model_text creates target leakage and inflates validation/test
    performance unrealistically.
    """
    title = clean_text(title)
    abstract = clean_text(abstract)
    keywords = clean_text(keywords)
    raw_text = normalize_pdf_text(raw_text)[:60000]
    parts = [p for p in [title, abstract, keywords, raw_text] if p]
    return clean_text(". ".join(parts))


def main():
    parser = argparse.ArgumentParser(description="Extract and clean PDF text.")
    parser.add_argument("--require-pdf-text", action="store_true")
    parser.add_argument("--min-raw-chars", type=int, default=1500)
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args()

    ensure_dir(OUT_FILE.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(
            f"Input file not found or empty: {IN_FILE}. Run download_openreview_pdfs.py first."
        )

    extracted = []
    duplicate_seen = set()
    stats = {
        "input_rows": len(rows),
        "kept_rows": 0,
        "dropped_missing_pdf": 0,
        "dropped_short_raw_text": 0,
        "duplicate_paper_uid_dropped": 0,
        "pymupdf_success": 0,
        "pdfplumber_fallback_success": 0,
        "pdf_extract_failed": 0,
        "rows_with_review_text": 0,
        "rows_with_decision_text": 0,
    }

    for row in tqdm(rows, desc="Extracting PDF text"):
        paper_uid = row.get("paper_uid", "")
        if paper_uid in duplicate_seen:
            stats["duplicate_paper_uid_dropped"] += 1
            continue
        duplicate_seen.add(paper_uid)

        pdf_path = row.get("pdf_path", "")
        raw_text = ""

        if pdf_path:
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                try:
                    raw_text = extract_with_pymupdf(pdf_file, max_pages=args.max_pages)
                    stats["pymupdf_success"] += 1
                except Exception:
                    try:
                        raw_text = extract_with_pdfplumber(pdf_file, max_pages=args.max_pages)
                        stats["pdfplumber_fallback_success"] += 1
                    except Exception:
                        raw_text = ""
                        stats["pdf_extract_failed"] += 1

        raw_text = normalize_pdf_text(raw_text)

        if args.require_pdf_text:
            if not pdf_path:
                stats["dropped_missing_pdf"] += 1
                continue
            if len(raw_text) < args.min_raw_chars:
                stats["dropped_short_raw_text"] += 1
                continue

        title = row.get("title", "")
        abstract = row.get("abstract", "")
        keywords = row.get("keywords", "")
        review_text = clean_text(row.get("review_text", "") or "")
        decision_text = clean_text(row.get("decision_text", "") or "")

        if review_text:
            stats["rows_with_review_text"] += 1
        if decision_text:
            stats["rows_with_decision_text"] += 1

        model_text = build_model_text(title, abstract, keywords, raw_text)
        if not model_text:
            continue

        extracted.append(
            {
                "paper_uid": paper_uid,
                "source": row.get("source", ""),
                "venue": row.get("venue", ""),
                "year": row.get("year", ""),
                "openreview_id": row.get("openreview_id", ""),
                "forum_id": row.get("forum_id", ""),
                "title": clean_text(title),
                "abstract": clean_text(abstract),
                "keywords": clean_text(keywords),
                "pdf_url": row.get("pdf_url", ""),
                "pdf_path": pdf_path,
                "pdf_downloaded": row.get("pdf_downloaded", False),
                "raw_text": raw_text,
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
    REPORT_FILE.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"✅ Extracted text saved to: {OUT_FILE}")
    print(f"✅ Extraction report saved to: {REPORT_FILE}")
    print(f"✅ Kept rows: {len(extracted)}")
    print(f"✅ Rows with review_text: {stats['rows_with_review_text']}")
    print(f"✅ Rows with decision_text: {stats['rows_with_decision_text']}")


if __name__ == "__main__":
    main()