"""
collect_arxiv.py — Generic arXiv paper collector for any non-ML domain.

TEAMMATE INSTRUCTIONS
─────────────────────
Each teammate runs ONE command. Example for the Physics team member:

    python collect_arxiv.py --domain physics --max-results 200

The script uses the arXiv API, requires NO API key, and saves a small JSONL
file (~2 MB for 200 papers).  Share ONLY this JSONL file with the central
coordinator (via Git, Google Drive, etc.) — do NOT share PDFs at this stage.

SUPPORTED DOMAINS: physics, biomed, nlp, finance, hardware, math
(ml uses collect_openreview.py instead)
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import DOMAIN_ARXIV_CATEGORIES, SUPPORTED_DOMAINS, validate_domain
from utils import clean_text, ensure_dir, extract_arxiv_id, write_jsonl, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
RAW_DIR = PIPELINE_DIR / "data" / "raw"

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
ARXIV_BASE_URL = "http://export.arxiv.org/api/query"

# arXiv rate limit: 3 seconds between requests
ARXIV_SLEEP = 3.0
BATCH_SIZE = 100   # arXiv API max per request


def build_api_url(category_query: str, start: int, max_results: int) -> str:
    params = {
        "search_query": category_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": str(start),
        "max_results": str(max_results),
    }
    return f"{ARXIV_BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch_xml(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Failed to fetch arXiv API after {retries} attempts: {e}") from e
            time.sleep(ARXIV_SLEEP * (attempt + 1))
    return b""


def parse_entries(xml_data: bytes, domain: str, venue_tag: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse arXiv XML response: {e}") from e

    ns = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
    rows: list[dict] = []

    for entry in root.findall("atom:entry", ns):
        try:
            id_elem = entry.find("atom:id", ns)
            if id_elem is None or not id_elem.text:
                continue
            paper_id_raw = id_elem.text.strip()
            arxiv_id = extract_arxiv_id(paper_id_raw) or paper_id_raw.split("/abs/")[-1]

            title_elem = entry.find("atom:title", ns)
            title = clean_text(title_elem.text if title_elem is not None else "")

            summary_elem = entry.find("atom:summary", ns)
            abstract = clean_text(summary_elem.text if summary_elem is not None else "")

            published_elem = entry.find("atom:published", ns)
            year = (published_elem.text or "")[:4] if published_elem is not None else ""

            # Collect author keywords if present
            keywords_parts: list[str] = []
            for cat in entry.findall("atom:category", ns):
                term = cat.attrib.get("term", "")
                if term:
                    keywords_parts.append(term)
            keywords = ", ".join(keywords_parts[:5])

            # PDF URL
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", "")
                    break
            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            if not title or not abstract:
                continue

            rows.append({
                "schema_version": PIPELINE_SCHEMA_VERSION,
                "paper_uid": f"arx_{arxiv_id.replace('.', '_').replace('/', '_')}",
                "source": "arxiv",
                "domain": domain,
                "venue": venue_tag,
                "year": year,
                "openreview_id": "",
                "forum_id": "",
                "title": title,
                "abstract": abstract,
                "keywords": keywords,
                "pdf_url": pdf_url,
                "paper_url": paper_id_raw,
                "direct_arxiv_id": arxiv_id,
                "decision_text": "",
                "review_text": "",
                "review_count": 0,
                "raw_invitations": [],
            })
        except Exception:
            continue

    return rows


def fetch_domain_papers(domain: str, max_results: int) -> list[dict]:
    category_query = DOMAIN_ARXIV_CATEGORIES.get(domain, "")
    if not category_query:
        raise ValueError(f"No arXiv category configured for domain {domain!r}")

    venue_tag = f"arXiv_{domain}"
    all_rows: list[dict] = []
    seen_ids: set[str] = set()

    total_fetched = 0
    pbar = tqdm(total=max_results, desc=f"Fetching {domain} from arXiv")

    while total_fetched < max_results:
        batch = min(BATCH_SIZE, max_results - total_fetched)
        url = build_api_url(category_query, start=total_fetched, max_results=batch)

        try:
            xml_data = fetch_xml(url)
        except RuntimeError as e:
            print(f"\n⚠ arXiv API error at offset {total_fetched}: {e}")
            break

        entries = parse_entries(xml_data, domain=domain, venue_tag=venue_tag)
        if not entries:
            break

        for row in entries:
            uid = row["paper_uid"]
            if uid not in seen_ids:
                seen_ids.add(uid)
                all_rows.append(row)
                pbar.update(1)

        total_fetched += len(entries)

        if len(entries) < batch:
            # arXiv returned fewer than requested → no more results
            break

        time.sleep(ARXIV_SLEEP)

    pbar.close()
    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Collect papers from arXiv for a given domain and save as JSONL.\n"
            "Run this once per domain on each teammate's machine, "
            "then share the output JSONL file with the central coordinator."
        )
    )
    parser.add_argument(
        "--domain",
        required=True,
        choices=[d for d in SUPPORTED_DOMAINS if d != "ml"],
        help="Domain to collect. ml uses collect_openreview.py instead.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=200,
        help="Maximum number of papers to collect (default 200).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Override output directory (default: data/raw/).",
    )
    args = parser.parse_args()

    domain = validate_domain(args.domain)
    out_dir = Path(args.output_dir) if args.output_dir else RAW_DIR
    ensure_dir(out_dir)
    out_file = out_dir / f"arxiv_raw_{domain}.jsonl"

    print(f"Collecting up to {args.max_results} {domain} papers from arXiv...")
    print(f"Categories: {DOMAIN_ARXIV_CATEGORIES[domain]}")

    rows = fetch_domain_papers(domain, max_results=args.max_results)

    if not rows:
        print("⚠  No papers collected. Check your network connection and arXiv category query.")
        return

    write_jsonl(out_file, rows)

    print(f"\n✅ Collected {len(rows)} {domain} papers → {out_file}")
    print(f"📤 Share this file with your coordinator: {out_file.name}")
    print(f"   (Do NOT share PDFs at this stage — just this JSONL file.)")


if __name__ == "__main__":
    main()
