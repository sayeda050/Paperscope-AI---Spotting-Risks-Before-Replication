
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Iterable

import fitz

from discover_pdf_features import ATTRIBUTE_ORDER, extract_feature_record
from utils import clean_multiline_text, clean_text, ensure_dir, risk_label_from_score, safe_filename

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "gold_pdfs"
OUT_DIR = BASE_DIR / "data" / "gold_eval"
OUT_CSV = OUT_DIR / "gold_eval_template.csv"


HEADERS = [
    "pdf_id",
    "pdf_filename",
    "pdf_path",
    "title_auto",
    "page_count",
    "text_char_count",
] + [f"prefill_{name}" for name in ATTRIBUTE_ORDER] + [
    "prefill_risk_score",
    "prefill_risk_label",
    "manual_title",
] + [f"gold_{name}" for name in ATTRIBUTE_ORDER] + [
    "gold_risk_score",
    "gold_risk_label",
    "notes",
]


def iter_pdfs(pdf_dir: Path) -> Iterable[Path]:
    for path in sorted(pdf_dir.rglob("*.pdf")):
        if path.is_file():
            yield path


def extract_title(doc: fitz.Document) -> str:
    meta_title = clean_text((doc.metadata or {}).get("title", ""))
    if meta_title and len(meta_title) >= 12 and "@" not in meta_title:
        return meta_title

    if len(doc) == 0:
        return ""

    first_page = doc[0].get_text("text") or ""
    lines = [clean_text(x) for x in first_page.splitlines()]
    lines = [x for x in lines if x]

    candidates = []
    for line in lines[:20]:
        low = line.lower()
        if low.startswith(("abstract", "arxiv:", "index terms", "keywords")):
            break
        if "@" in line:
            continue
        if len(line) < 8:
            continue
        candidates.append(line)
        if len(candidates) >= 2:
            break
    return clean_text(" ".join(candidates[:2]))


def extract_text(pdf_path: Path) -> tuple[str, str, int]:
    with fitz.open(pdf_path) as doc:
        title = extract_title(doc)
        parts = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        text = clean_multiline_text("\n".join(parts))
        return title, text, len(doc)


def score_to_prefills(record: dict) -> dict:
    attr_map = {a["name"]: a for a in record["attributes"]}
    row = {f"prefill_{name}": attr_map[name]["state"] for name in ATTRIBUTE_ORDER}
    row["prefill_risk_score"] = round(float(record["risk_score"]), 2)
    row["prefill_risk_label"] = risk_label_from_score(float(record["risk_score"]))
    return row


def main() -> None:
    ensure_dir(OUT_DIR)
    ensure_dir(PDF_DIR)

    rows = []
    for pdf_path in iter_pdfs(PDF_DIR):
        title, text, page_count = extract_text(pdf_path)
        sha1 = hashlib.sha1(pdf_path.read_bytes()).hexdigest()[:12]
        record = extract_feature_record(
            {
                "paper_uid": sha1,
                "title": title,
                "abstract": "",
                "keywords": "",
                "raw_text": text,
            }
        )
        row = {
            "pdf_id": sha1,
            "pdf_filename": pdf_path.name,
            "pdf_path": str(pdf_path.relative_to(BASE_DIR)).replace("\\", "/"),
            "title_auto": title,
            "page_count": page_count,
            "text_char_count": len(text),
            **score_to_prefills(record),
            "manual_title": "",
            **{f"gold_{name}": "" for name in ATTRIBUTE_ORDER},
            "gold_risk_score": "",
            "gold_risk_label": "",
            "notes": "",
        }
        rows.append(row)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"✅ Gold eval template saved to: {OUT_CSV}")
    print(f"✅ Rows prepared: {len(rows)}")


if __name__ == "__main__":
    main()
