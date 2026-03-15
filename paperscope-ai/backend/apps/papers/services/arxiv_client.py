from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"


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

    def fetch(self, arxiv_id: str) -> ArxivPaper:
        response = requests.get(
            ARXIV_API_URL,
            params={"search_query": f"id:{arxiv_id}", "start": 0, "max_results": 1},
            timeout=self.timeout,
            headers={"User-Agent": "PaperScopeAI/1.0"},
        )
        response.raise_for_status()

        entry = self._parse_entry(response.text)
        if entry is None:
            raise ArxivClientError(f"No arXiv record found for {arxiv_id}.")

        pdf_url = entry["pdf_url"] or f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_response = requests.get(
            pdf_url,
            timeout=self.timeout,
            headers={"User-Agent": "PaperScopeAI/1.0"},
        )
        pdf_response.raise_for_status()

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=entry["title"],
            abstract=entry["summary"],
            pdf_url=pdf_url,
            pdf_bytes=pdf_response.content,
        )

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