import sys
from pathlib import Path
import json
import time
import hashlib
import argparse
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, write_jsonl, ensure_dir, clean_text

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "raw" / "openreview_raw.jsonl"
PDF_DIR = PIPELINE_DIR / "data" / "pdfs" / "openreview"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "pdf_download_report.json"

TIMEOUT_SECONDS = 90


def build_safe_filename(row: dict, fallback_index: int) -> str:
    paper_uid = clean_text(row.get("paper_uid", "")) or f"paper_{fallback_index}"
    digest = hashlib.md5(paper_uid.encode("utf-8")).hexdigest()[:10]
    safe_uid = re.sub(r"[^a-zA-Z0-9_\-]+", "_", paper_uid)[:120]
    return f"{safe_uid}_{digest}.pdf"


def resolve_pdf_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return ""
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    if raw_url.startswith("/"):
        return f"https://openreview.net{raw_url}"
    return raw_url


def build_candidate_urls(row: dict):
    urls = []

    raw_pdf_url = resolve_pdf_url(row.get("pdf_url", ""))
    openreview_id = (row.get("openreview_id", "") or "").strip()
    forum_id = (row.get("forum_id", "") or "").strip()

    if raw_pdf_url:
        urls.append(raw_pdf_url)

    # Strong fallbacks for OpenReview PDF endpoint
    if openreview_id:
        urls.append(f"https://openreview.net/pdf?id={openreview_id}")
    if forum_id and forum_id != openreview_id:
        urls.append(f"https://openreview.net/pdf?id={forum_id}")

    # remove duplicates while keeping order
    seen = set()
    unique_urls = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            unique_urls.append(u)

    return unique_urls


def build_session():
    session = requests.Session()

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://openreview.net/",
            "Connection": "keep-alive",
        }
    )
    return session


def looks_like_pdf(first_bytes: bytes, content_type: str) -> bool:
    content_type = (content_type or "").lower()

    if "application/pdf" in content_type:
        return True
    if "application/octet-stream" in content_type:
        return True

    # Some servers mislabel content-type; trust PDF signature too
    if first_bytes.startswith(b"%PDF"):
        return True

    return False


def download_from_candidates(session, candidate_urls, out_path: Path):
    last_error = "no_candidate_url"

    for url in candidate_urls:
        tmp_path = out_path.with_suffix(".tmp")
        try:
            with session.get(url, timeout=TIMEOUT_SECONDS, stream=True) as resp:
                if resp.status_code != 200:
                    last_error = f"http_{resp.status_code}"
                    continue

                content_type = resp.headers.get("Content-Type", "")
                iterator = resp.iter_content(chunk_size=1024 * 256)

                first_chunk = b""
                for chunk in iterator:
                    if chunk:
                        first_chunk = chunk
                        break

                if not first_chunk:
                    last_error = "empty_response"
                    continue

                if not looks_like_pdf(first_chunk, content_type):
                    preview = first_chunk[:120].decode("utf-8", errors="ignore").strip().replace("\n", " ")
                    last_error = f"not_pdf_content_type={content_type} preview={preview[:80]}"
                    continue

                with tmp_path.open("wb") as f:
                    f.write(first_chunk)
                    for chunk in iterator:
                        if chunk:
                            f.write(chunk)

                if tmp_path.exists() and tmp_path.stat().st_size > 1000:
                    tmp_path.replace(out_path)
                    return True, "", url
                else:
                    last_error = "downloaded_file_too_small"
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)

        except Exception as e:
            last_error = str(e)
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    return False, last_error, ""


def main():
    parser = argparse.ArgumentParser(description="Download PDFs directly from OpenReview.")
    parser.add_argument("--max-papers", type=int, default=1000)
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    args = parser.parse_args()

    ensure_dir(PDF_DIR)
    ensure_dir(OUT_FILE.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"No rows found in {IN_FILE}. Run collect_openreview.py first.")

    session = build_session()

    updated = []
    processed = 0
    downloaded_ok = 0
    already_present = 0
    failed = 0
    skipped_no_url = 0
    errors = []

    for idx, row in enumerate(tqdm(rows, desc="Downloading OpenReview PDFs")):
        if processed >= args.max_papers:
            break

        row = dict(row)
        candidate_urls = build_candidate_urls(row)

        pdf_path = ""
        pdf_downloaded = False
        pdf_download_error = ""
        pdf_download_source = "openreview_pdf_url"

        if not candidate_urls:
            skipped_no_url += 1
            pdf_download_error = "missing_pdf_url"
        else:
            filename = build_safe_filename(row, idx)
            target_pdf = PDF_DIR / filename
            pdf_path = str(target_pdf)

            if args.only_missing and target_pdf.exists() and target_pdf.stat().st_size > 1000:
                already_present += 1
                pdf_downloaded = True
            else:
                ok, err, used_url = download_from_candidates(session, candidate_urls, target_pdf)
                if ok and target_pdf.exists() and target_pdf.stat().st_size > 1000:
                    downloaded_ok += 1
                    pdf_downloaded = True
                    pdf_download_source = used_url
                else:
                    failed += 1
                    pdf_download_error = err or "download_failed"
                    if target_pdf.exists():
                        try:
                            target_pdf.unlink()
                        except Exception:
                            pass
                    pdf_path = ""
                    errors.append(
                        {
                            "paper_uid": row.get("paper_uid", ""),
                            "openreview_id": row.get("openreview_id", ""),
                            "forum_id": row.get("forum_id", ""),
                            "candidate_urls": candidate_urls,
                            "error": pdf_download_error,
                        }
                    )

                time.sleep(max(0.0, args.sleep_seconds))

        row["pdf_path"] = pdf_path
        row["pdf_downloaded"] = pdf_downloaded
        row["pdf_download_source"] = pdf_download_source
        row["pdf_download_error"] = pdf_download_error

        updated.append(row)
        processed += 1

    write_jsonl(OUT_FILE, updated)

    report = {
        "mode": "openreview_direct_pdf_download",
        "input_rows_total": len(rows),
        "processed_rows": len(updated),
        "max_papers_requested": args.max_papers,
        "downloaded_ok": downloaded_ok,
        "already_present": already_present,
        "failed": failed,
        "missing_pdf_url": skipped_no_url,
        "output_file": str(OUT_FILE),
        "pdf_dir": str(PDF_DIR),
        "sample_errors": errors[:50],
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Metadata with PDF paths saved to: {OUT_FILE}")
    print(f"✅ PDF download report saved to: {REPORT_FILE}")
    print(f"✅ Processed rows: {len(updated)}")
    print(f"✅ Downloaded OK: {downloaded_ok}")
    print(f"✅ Already present: {already_present}")
    print(f"✅ Failed: {failed}")
    print(f"✅ Missing pdf_url: {skipped_no_url}")


if __name__ == "__main__":
    main()