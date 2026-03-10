import sys
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, write_jsonl, clean_text, ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"


def extract_with_pymupdf(pdf_path: Path, max_pages=50):
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


def extract_with_pdfplumber(pdf_path: Path, max_pages=50):
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)


def build_model_text(title: str, abstract: str, raw_text: str):
    title = clean_text(title)
    abstract = clean_text(abstract)
    raw_text = clean_text(raw_text)

    # Keep the most useful text for CPU-friendly TF-IDF
    raw_text = raw_text[:40000]
    model_text = f"{title}. {abstract}. {raw_text}"
    return clean_text(model_text)


def main():
    ensure_dir(OUT_FILE.parent)
    rows = read_jsonl(IN_FILE)
    extracted = []

    for row in tqdm(rows, desc="Extracting PDF text"):
        pdf_path = row.get("pdf_path", "")
        raw_text = ""

        if pdf_path:
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                try:
                    raw_text = extract_with_pymupdf(pdf_file)
                except Exception:
                    try:
                        raw_text = extract_with_pdfplumber(pdf_file)
                    except Exception:
                        raw_text = ""

        title = row.get("title", "")
        abstract = row.get("abstract", "")
        review_text = row.get("review_text", "")
        decision_text = row.get("decision_text", "")
        keywords = row.get("keywords", "")

        model_text = build_model_text(title, abstract, raw_text)

        extracted.append({
            "paper_uid": row.get("paper_uid", ""),
            "source": row.get("source", ""),
            "venue": row.get("venue", ""),
            "year": row.get("year", ""),
            "openreview_id": row.get("openreview_id", ""),
            "forum_id": row.get("forum_id", ""),
            "arxiv_id": row.get("arxiv_id", ""),
            "title": title,
            "abstract": abstract,
            "keywords": clean_text(keywords),
            "review_text": clean_text(review_text),
            "decision_text": clean_text(decision_text),
            "review_count": row.get("review_count", 0),
            "pdf_path": pdf_path,
            "pdf_downloaded": row.get("pdf_downloaded", False),
            "raw_text": clean_text(raw_text),
            "model_text": model_text,
        })

    write_jsonl(OUT_FILE, extracted)
    print(f"✅ Extracted text saved to: {OUT_FILE}")


if __name__ == "__main__":
    main()
