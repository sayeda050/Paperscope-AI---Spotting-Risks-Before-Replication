from __future__ import annotations

import io
import re
from typing import Tuple

import fitz
import pdfplumber


class PDFExtractionError(Exception):
    pass


WS_RE = re.compile(r"\s+")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_raw_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = CONTROL_RE.sub(" ", text)
    return text


def _sanitize_title(text: str) -> str:
    text = _sanitize_raw_text(text)
    text = text.replace("\n", " ")
    text = WS_RE.sub(" ", text).strip()
    return text


def clean_extracted_text(text: str) -> str:
    text = _sanitize_raw_text(text)
    text = WS_RE.sub(" ", text)
    return text.strip()


def extract_title_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Best-effort PDF title extraction.
    Priority:
    1) PDF metadata title
    2) First-page visible title
    """
    if not pdf_bytes:
        return ""

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            meta_title = _sanitize_title((doc.metadata or {}).get("title", ""))
            if _looks_like_real_title(meta_title):
                return meta_title

            if len(doc) == 0:
                return ""

            page = doc[0]
            visible_title = _extract_first_page_title(page)
            if _looks_like_real_title(visible_title):
                return visible_title
    except Exception:
        return ""

    return ""


def _looks_like_real_title(title: str) -> bool:
    if not title:
        return False

    lowered = title.lower()

    bad_starts = (
        "arxiv:",
        "abstract",
        "index terms",
        "introduction",
        "this work was supported",
    )
    if lowered.startswith(bad_starts):
        return False

    if "@" in title:
        return False

    if len(title) < 12:
        return False

    letters = sum(ch.isalpha() for ch in title)
    if letters < 8:
        return False

    return True


def _extract_first_page_title(page: fitz.Page) -> str:
    """
    Extract likely title from page 1.
    Uses the top lines before author/abstract blocks.
    """
    text = page.get_text("text") or ""
    lines = [_sanitize_title(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    candidates = []
    for line in lines[:20]:
        lowered = line.lower()

        if lowered.startswith("arxiv:"):
            continue
        if lowered.startswith("abstract"):
            break
        if lowered.startswith("index terms"):
            break
        if lowered.startswith("this work was supported"):
            break
        if "student member" in lowered:
            continue
        if "member, ieee" in lowered:
            continue
        if "@" in line:
            continue
        if line.isupper() and len(line) <= 4:
            continue

        candidates.append(line)

        # many papers keep the title within the first 1–2 lines
        if len(candidates) >= 2:
            break

    if not candidates:
        return ""

    # join first two title-like lines if needed
    title = " ".join(candidates[:2])
    title = _sanitize_title(title)
    return title


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Tuple[str, str]:
    if not pdf_bytes:
        raise PDFExtractionError("Empty PDF content.")

    raw_text = _extract_with_pymupdf(pdf_bytes)
    if not raw_text.strip():
        raw_text = _extract_with_pdfplumber(pdf_bytes)

    raw_text = _sanitize_raw_text(raw_text)
    cleaned = clean_extracted_text(raw_text)

    if not cleaned:
        raise PDFExtractionError("No readable text could be extracted from the PDF.")

    return raw_text, cleaned


def _extract_with_pymupdf(pdf_bytes: bytes) -> str:
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            parts = []
            for page in doc:
                parts.append(page.get_text("text"))
            return "\n\n".join(parts)
    except Exception as exc:
        raise PDFExtractionError(f"PyMuPDF extraction failed: {exc}") from exc


def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    try:
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    except Exception as exc:
        raise PDFExtractionError(f"pdfplumber extraction failed: {exc}") from exc