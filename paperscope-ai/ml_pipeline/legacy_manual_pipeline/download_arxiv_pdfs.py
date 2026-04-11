import sys
from pathlib import Path
import json

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, write_jsonl, ensure_dir

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "raw" / "openreview_raw.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "openreview_pdf_download_report.json"


def main():
    ensure_dir(OUT_FILE.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(
            f"No input rows found in {IN_FILE}. Run collect_openreview.py first."
        )

    updated = []
    for row in rows:
        row = dict(row)

        # Keep downstream compatibility
        row["arxiv_id"] = row.get("arxiv_id", "") or row.get("direct_arxiv_id", "")

        # Intentionally skip downloading PDFs for now.
        # extract_text.py can still build model_text from title + abstract.
        row["pdf_path"] = ""
        row["pdf_downloaded"] = False
        row["pdf_download_source"] = "skipped_no_pdf_mode"
        row["pdf_download_error"] = ""

        updated.append(row)

    write_jsonl(OUT_FILE, updated)

    report = {
        "mode": "no_pdf_fast_mode",
        "input_rows": len(rows),
        "rows_written": len(updated),
        "downloaded_ok": 0,
        "failed": 0,
        "note": "PDF download intentionally skipped. Downstream extract_text.py will use title + abstract when pdf_path is empty."
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Metadata saved to: {OUT_FILE}")
    print(f"✅ Report saved to: {REPORT_FILE}")
    print(f"✅ Rows written: {len(updated)}")
    print("✅ PDF downloading skipped intentionally (fast mode).")


if __name__ == "__main__":
    main()