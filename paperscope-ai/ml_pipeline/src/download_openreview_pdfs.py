"""
download_openreview_pdfs.py — Download PDFs for all domains from the unified raw dataset.

Reads:  data/raw/unified_raw_dataset.jsonl   (or openreview_raw.jsonl as fallback)
Writes: data/processed/linked_with_pdfs.jsonl
        outputs/reports/pdf_download_report.json

Works for both OpenReview (https://openreview.net/pdf?id=...) and
arXiv (https://arxiv.org/pdf/...) URLs — the URL resolution logic handles both.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_text,
    ensure_dir,
    read_jsonl,
    write_json,
    write_jsonl,
)

PIPELINE_DIR  = SRC_DIR.parent
# Read from unified dataset if it exists, fall back to openreview-only
_UNIFIED      = PIPELINE_DIR / "data" / "raw" / "unified_raw_dataset.jsonl"
_OR_ONLY      = PIPELINE_DIR / "data" / "raw" / "openreview_raw.jsonl"
IN_FILE       = _UNIFIED if _UNIFIED.exists() else _OR_ONLY
PDF_BASE_DIR  = PIPELINE_DIR / "data" / "pdfs"
OUT_FILE      = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
REPORT_FILE   = PIPELINE_DIR / "outputs" / "reports" / "pdf_download_report.json"

TIMEOUT_SECS  = 90


def get_pdf_dir(domain: str) -> Path:
    """Each domain gets its own subfolder: data/pdfs/{domain}/"""
    return PDF_BASE_DIR / (domain or "unknown")


def build_safe_filename(row: dict, idx: int) -> str:
    uid    = clean_text(row.get("paper_uid", "")) or f"paper_{idx}"
    digest = hashlib.md5(uid.encode()).hexdigest()[:10]
    safe   = re.sub(r"[^a-zA-Z0-9_\-]+", "_", uid)[:100]
    return f"{safe}_{digest}.pdf"


def resolve_pdf_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return ""
    if raw_url.startswith(("http://", "https://")):
        return raw_url
    if raw_url.startswith("/"):
        return f"https://openreview.net{raw_url}"
    return raw_url


def build_candidate_urls(row: dict) -> list[str]:
    urls: list[str] = []
    raw_pdf = resolve_pdf_url(row.get("pdf_url", ""))
    or_id   = (row.get("openreview_id", "") or "").strip()
    forum   = (row.get("forum_id", "") or "").strip()
    arxiv   = (row.get("direct_arxiv_id", "") or "").strip()

    if raw_pdf:
        urls.append(raw_pdf)
    if or_id:
        urls.append(f"https://openreview.net/pdf?id={or_id}")
    if forum and forum != or_id:
        urls.append(f"https://openreview.net/pdf?id={forum}")
    if arxiv:
        # Normalize arXiv ID: replace underscores back to dots
        arxiv_normalized = arxiv.replace("_", ".")
        urls.append(f"https://arxiv.org/pdf/{arxiv_normalized}.pdf")

    seen: set[str] = set()
    return [u for u in urls if u and not (seen.add(u) or u in seen - {u})]


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://",  adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://openreview.net/",
        "Connection":      "keep-alive",
    })
    return session


def looks_like_pdf(first_bytes: bytes, content_type: str) -> bool:
    ct = (content_type or "").lower()
    if "application/pdf" in ct:
        return True
    if "application/octet-stream" in ct:
        return True
    if first_bytes.startswith(b"%PDF"):
        return True
    return False


def download_from_candidates(
    session: requests.Session,
    candidate_urls: list[str],
    out_path: Path,
) -> tuple[bool, str, str]:
    last_error = "no_candidate_url"
    for url in candidate_urls:
        tmp = out_path.with_suffix(".tmp")
        try:
            with session.get(url, timeout=TIMEOUT_SECS, stream=True) as resp:
                if resp.status_code != 200:
                    last_error = f"http_{resp.status_code}"
                    continue
                ct      = resp.headers.get("Content-Type", "")
                itr     = resp.iter_content(chunk_size=256 * 1024)
                first   = b""
                for chunk in itr:
                    if chunk:
                        first = chunk
                        break
                if not first:
                    last_error = "empty_response"
                    continue
                if not looks_like_pdf(first, ct):
                    preview = first[:100].decode("utf-8", errors="ignore").replace("\n", " ")
                    last_error = f"not_pdf|ct={ct}|preview={preview[:60]}"
                    continue
                with tmp.open("wb") as f:
                    f.write(first)
                    for chunk in itr:
                        if chunk:
                            f.write(chunk)
                if tmp.exists() and tmp.stat().st_size > 1000:
                    tmp.replace(out_path)
                    return True, "", url
                last_error = "file_too_small"
                tmp.unlink(missing_ok=True)
        except Exception as exc:
            last_error = str(exc)
            tmp.unlink(missing_ok=True)
    return False, last_error, ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download PDFs for all domains from the unified raw dataset."
    )
    parser.add_argument("--max-papers",   type=int,   default=2000)
    parser.add_argument("--only-missing", action="store_true",
                        help="Skip papers whose PDF already exists on disk.")
    parser.add_argument("--sleep-seconds", type=float, default=0.20,
                        help="Polite delay between downloads (default 0.20s).")
    parser.add_argument(
        "--input-file", default="",
        help="Override input JSONL path (default: unified_raw_dataset.jsonl or openreview_raw.jsonl).",
    )
    parser.add_argument(
        "--domain", default="",
        help="Filter to a specific domain (default: all domains).",
    )
    args = parser.parse_args()

    in_file = Path(args.input_file) if args.input_file else IN_FILE
    if not in_file.exists():
        raise FileNotFoundError(
            f"Input file not found: {in_file}\n"
            "Run collect_openreview.py and/or merge_raw_data.py first."
        )

    ensure_dir(PDF_BASE_DIR)
    ensure_dir(OUT_FILE.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(in_file)
    if not rows:
        raise FileNotFoundError(f"No rows in {in_file}")

    if args.domain:
        rows = [r for r in rows if r.get("domain", "") == args.domain]
        print(f"Filtered to domain {args.domain!r}: {len(rows)} rows")

    session  = build_session()
    updated: list[dict] = []
    processed = downloaded_ok = already_present = failed = skipped_no_url = 0
    errors: list[dict] = []

    for idx, row in enumerate(tqdm(rows, desc="Downloading PDFs")):
        if processed >= args.max_papers:
            break

        row = dict(row)
        domain      = str(row.get("domain", "unknown") or "unknown")
        pdf_dir     = get_pdf_dir(domain)
        ensure_dir(pdf_dir)

        candidates      = build_candidate_urls(row)
        pdf_path        = ""
        pdf_downloaded  = False
        pdf_dl_error    = ""
        pdf_dl_source   = ""

        if not candidates:
            skipped_no_url += 1
            pdf_dl_error    = "missing_pdf_url"
        else:
            fname      = build_safe_filename(row, idx)
            target     = pdf_dir / fname
            pdf_path   = str(target)

            if args.only_missing and target.exists() and target.stat().st_size > 1000:
                already_present += 1
                pdf_downloaded   = True
                pdf_dl_source    = "already_on_disk"
            else:
                ok, err, used_url = download_from_candidates(session, candidates, target)
                if ok and target.exists() and target.stat().st_size > 1000:
                    downloaded_ok += 1
                    pdf_downloaded  = True
                    pdf_dl_source   = used_url
                else:
                    failed       += 1
                    pdf_dl_error  = err or "download_failed"
                    target.unlink(missing_ok=True)
                    pdf_path = ""
                    errors.append({
                        "paper_uid":      row.get("paper_uid", ""),
                        "domain":         domain,
                        "candidate_urls": candidates,
                        "error":          pdf_dl_error,
                    })

                time.sleep(max(0.0, args.sleep_seconds))

        row["pdf_path"]            = pdf_path
        row["pdf_downloaded"]      = pdf_downloaded
        row["pdf_download_source"] = pdf_dl_source
        row["pdf_download_error"]  = pdf_dl_error
        row["schema_version"]      = PIPELINE_SCHEMA_VERSION

        updated.append(row)
        processed += 1

    write_jsonl(OUT_FILE, updated)

    report = {
        "schema_version":       PIPELINE_SCHEMA_VERSION,
        "input_file":           str(in_file),
        "input_rows_total":     len(rows),
        "processed_rows":       len(updated),
        "max_papers_requested": args.max_papers,
        "downloaded_ok":        downloaded_ok,
        "already_present":      already_present,
        "failed":               failed,
        "missing_pdf_url":      skipped_no_url,
        "output_file":          str(OUT_FILE),
        "pdf_base_dir":         str(PDF_BASE_DIR),
        "sample_errors":        errors[:50],
    }
    write_json(REPORT_FILE, report)

    print(f"✅ Linked JSONL   → {OUT_FILE}")
    print(f"✅ Report         → {REPORT_FILE}")
    print(f"   Processed:      {len(updated)}")
    print(f"   Downloaded OK:  {downloaded_ok}")
    print(f"   Already exist:  {already_present}")
    print(f"   Failed:         {failed}")
    print(f"   No URL:         {skipped_no_url}")


if __name__ == "__main__":
    main()
