import sys
from pathlib import Path
import requests
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
   sys.path.append(str(SRC_DIR))

from utils import read_jsonl, write_jsonl, ensure_dir, safe_filename

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "linked.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl"
PDF_DIR = PIPELINE_DIR / "data" / "raw" / "pdfs"

HEADERS = {
   "User-Agent": "PaperScopeAI-PDFDownloader/1.0 (research-use)"
}


def download_pdf(url: str, out_path: Path):
   out_path.parent.mkdir(parents=True, exist_ok=True)
   with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
       r.raise_for_status()
       with out_path.open("wb") as f:
           for chunk in r.iter_content(chunk_size=8192):
               if chunk:
                   f.write(chunk)


def main():
   ensure_dir(PDF_DIR)
   rows = read_jsonl(IN_FILE)
   updated = []

   for row in tqdm(rows, desc="Downloading arXiv PDFs"):
       arxiv_id = row.get("arxiv_id", "")
       title = row.get("title", "")
       pdf_url = row.get("arxiv_pdf_url", "")

       if not pdf_url and arxiv_id:
           pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

       filename = f"{safe_filename(arxiv_id or title)}.pdf"
       pdf_path = PDF_DIR / filename

       try:
           if not pdf_path.exists():
               download_pdf(pdf_url, pdf_path)
           row["pdf_path"] = str(pdf_path.resolve())
           row["pdf_downloaded"] = True
       except Exception as e:
           row["pdf_path"] = ""
           row["pdf_downloaded"] = False
           row["pdf_download_error"] = str(e)

       updated.append(row)

   write_jsonl(OUT_FILE, updated)
   print(f"✅ PDF-downloaded metadata saved to: {OUT_FILE}")


if __name__ == "__main__":
   main()
