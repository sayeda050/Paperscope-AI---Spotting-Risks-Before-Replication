from __future__ import annotations

import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape

import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_ABS_URL = "https://arxiv.org/abs/{arxiv_id}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}.pdf"


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    pdf_url: str
    pdf_bytes: bytes


class ArxivClientError(Exception):
    pass


class ArxivClient:
    timeout = 30
    max_attempts = 5
    base_sleep_seconds = 2.0

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "PaperScopeAI/1.0 "
                    "(Research project; PDF analysis service)"
                ),
                "Accept": "*/*",
                "Connection": "keep-alive",
            }
        )

    def fetch(self, arxiv_id: str) -> ArxivPaper:
        arxiv_id = str(arxiv_id or "").strip()
        if not arxiv_id:
            raise ArxivClientError("arXiv ID is required.")

        entry = None
        pdf_url = ""

        # 1) Try API first
        try:
            response = self._request_with_backoff(
                ARXIV_API_URL,
                params={
                    "search_query": f"id:{arxiv_id}",
                    "start": 0,
                    "max_results": 1,
                },
            )
            entry = self._parse_entry(response.text)
        except Exception:
            entry = None

        # 2) Fallback: fetch metadata from arXiv abstract page
        if entry is None:
            entry = self._fetch_from_abs_page(arxiv_id)

        if entry is None:
            raise ArxivClientError(f"No arXiv record found for {arxiv_id}.")

        pdf_url = entry.get("pdf_url") or ARXIV_PDF_URL.format(arxiv_id=arxiv_id)
        pdf_bytes = self._download_pdf_bytes(pdf_url, arxiv_id)

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=entry.get("title") or arxiv_id,
            abstract=entry.get("summary") or "",
            pdf_url=pdf_url,
            pdf_bytes=pdf_bytes,
        )

    def _request_with_backoff(self, url: str, *, params=None, allow_not_found=False):
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 404 and allow_not_found:
                    return response

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        sleep_for = float(retry_after)
                    else:
                        sleep_for = self.base_sleep_seconds * (2 ** (attempt - 1)) + random.uniform(0.0, 0.8)
                    time.sleep(sleep_for)
                    last_error = ArxivClientError(f"429 rate limit from arXiv at {url}")
                    continue

                if 500 <= response.status_code < 600:
                    sleep_for = self.base_sleep_seconds * (2 ** (attempt - 1)) + random.uniform(0.0, 0.8)
                    time.sleep(sleep_for)
                    last_error = ArxivClientError(f"{response.status_code} server error from arXiv at {url}")
                    continue

                response.raise_for_status()
                return response

            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    sleep_for = self.base_sleep_seconds * (2 ** (attempt - 1)) + random.uniform(0.0, 0.8)
                    time.sleep(sleep_for)
                else:
                    break

        raise ArxivClientError(str(last_error) if last_error else "Failed to reach arXiv.")

    def _download_pdf_bytes(self, pdf_url: str, arxiv_id: str) -> bytes:
        candidate_urls = []
        if pdf_url:
            candidate_urls.append(pdf_url)
        candidate_urls.append(ARXIV_PDF_URL.format(arxiv_id=arxiv_id))

        seen = set()
        for url in candidate_urls:
            if not url or url in seen:
                continue
            seen.add(url)

            try:
                response = self._request_with_backoff(url)
                content = response.content or b""
                if not content:
                    continue

                content_type = (response.headers.get("Content-Type") or "").lower()
                if (
                    "application/pdf" in content_type
                    or content.startswith(b"%PDF")
                    or url.lower().endswith(".pdf")
                ):
                    return content
            except Exception:
                continue

        raise ArxivClientError(f"Could not download PDF for arXiv ID {arxiv_id}.")

    def _fetch_from_abs_page(self, arxiv_id: str):
        url = ARXIV_ABS_URL.format(arxiv_id=arxiv_id)
        response = self._request_with_backoff(url)
        html_text = response.text or ""

        title = self._extract_meta_content(html_text, "citation_title")
        abstract = self._extract_meta_content(html_text, "citation_abstract")
        pdf_url = self._extract_meta_content(html_text, "citation_pdf_url")

        if not title:
            m = re.search(r'<title>\s*(.*?)\s*</title>', html_text, flags=re.I | re.S)
            if m:
                title = re.sub(r"^\s*arXiv:\s*", "", unescape(m.group(1))).strip()

        if not abstract:
            m = re.search(
                r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>',
                html_text,
                flags=re.I | re.S,
            )
            if m:
                abstract = re.sub(r"<[^>]+>", " ", m.group(1))
                abstract = re.sub(r"^\s*Abstract:\s*", "", unescape(abstract), flags=re.I).strip()

        if not pdf_url:
            pdf_url = ARXIV_PDF_URL.format(arxiv_id=arxiv_id)

        if not title and not abstract:
            return None

        return {
            "title": " ".join((title or "").split()),
            "summary": " ".join((abstract or "").split()),
            "pdf_url": pdf_url,
        }

    def _extract_meta_content(self, html_text: str, meta_name: str) -> str:
        patterns = [
            rf'<meta\s+name="{re.escape(meta_name)}"\s+content="([^"]*)"',
            rf"<meta\s+name='{re.escape(meta_name)}'\s+content='([^']*)'",
            rf'<meta\s+content="([^"]*)"\s+name="{re.escape(meta_name)}"',
            rf"<meta\s+content='([^']*)'\s+name='{re.escape(meta_name)}'",
        ]

        for pattern in patterns:
            m = re.search(pattern, html_text, flags=re.I)
            if m:
                return unescape(m.group(1)).strip()
        return ""

    def _parse_entry(self, xml_text: str):
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")
        pdf_url = ""

        for link in entry.findall("atom:link", ns):
            title_attr = link.attrib.get("title", "")
            if title_attr.lower() == "pdf":
                pdf_url = link.attrib.get("href", "")
                break

        return {
            "title": " ".join(title.split()),
            "summary": " ".join(summary.split()),
            "pdf_url": pdf_url,
        }