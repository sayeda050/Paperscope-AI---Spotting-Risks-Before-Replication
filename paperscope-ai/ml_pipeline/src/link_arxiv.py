import sys
from pathlib import Path
import json
from rapidfuzz import fuzz
import arxiv
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
   sys.path.append(str(SRC_DIR))

from utils import (
   read_jsonl,
   write_jsonl,
   normalize_title,
   extract_arxiv_id,
   ensure_dir,
)

PIPELINE_DIR = SRC_DIR.parent
RAW_FILE = PIPELINE_DIR / "data" / "raw" / "openreview_raw.jsonl"
OUT_FILE = PIPELINE_DIR / "data" / "processed" / "linked.jsonl"
UNMATCHED_FILE = PIPELINE_DIR / "data" / "processed" / "unmatched_openreview.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "arxiv_link_report.json"

MATCH_THRESHOLD = 90
MAX_RESULTS = 5


def fetch_arxiv_by_id(client, arxiv_id: str):
   try:
       search = arxiv.Search(id_list=[arxiv_id])
       results = list(client.results(search))
       if results:
           return results[0]
   except Exception:
       return None
   return None


def fetch_arxiv_by_title(client, title: str):
   try:
       query = f'ti:"{title}"'
       search = arxiv.Search(query=query, max_results=MAX_RESULTS, sort_by=arxiv.SortCriterion.Relevance)
       return list(client.results(search))
   except Exception:
       return []


def result_to_dict(r):
   short_id = ""
   try:
       short_id = r.get_short_id()
   except Exception:
       short_id = r.entry_id.rsplit("/", 1)[-1].replace("v1", "")

   return {
       "arxiv_id": short_id,
       "arxiv_title": r.title,
       "arxiv_abstract": r.summary,
       "arxiv_pdf_url": r.pdf_url,
       "arxiv_entry_url": r.entry_id,
       "arxiv_primary_category": getattr(r, "primary_category", ""),
       "arxiv_categories": list(getattr(r, "categories", [])),
       "arxiv_published": str(getattr(r, "published", "")),
   }


def main():
   ensure_dir(OUT_FILE.parent)
   rows = read_jsonl(RAW_FILE)
   client = arxiv.Client(page_size=5, delay_seconds=2.5, num_retries=3)

   linked = []
   unmatched = []

   direct_matches = 0
   title_matches = 0

   for row in tqdm(rows, desc="Linking OpenReview ↔ arXiv"):
       title = row.get("title", "")
       direct_id = row.get("direct_arxiv_id", "") or extract_arxiv_id(row.get("paper_url", ""))

       match = None
       match_type = ""
       match_score = 0

       # 1) Direct ID match
       if direct_id:
           res = fetch_arxiv_by_id(client, direct_id)
           if res:
               match = res
               match_type = "direct_arxiv_id"
               match_score = 100
               direct_matches += 1

       # 2) Title search + fuzzy match
       if match is None and title:
           candidates = fetch_arxiv_by_title(client, title)
           best = None
           best_score = -1
           title_norm = normalize_title(title)

           for cand in candidates:
               score = fuzz.token_set_ratio(title_norm, normalize_title(cand.title))
               if score > best_score:
                   best_score = score
                   best = cand

           if best is not None and best_score >= MATCH_THRESHOLD:
               match = best
               match_type = "title_fuzzy"
               match_score = float(best_score)
               title_matches += 1

       if match is None:
           unmatched.append(row)
           continue

       linked.append({
           **row,
           **result_to_dict(match),
           "match_type": match_type,
           "match_score": match_score,
       })

   write_jsonl(OUT_FILE, linked)
   write_jsonl(UNMATCHED_FILE, unmatched)

   report = {
       "input_rows": len(rows),
       "linked_rows": len(linked),
       "unmatched_rows": len(unmatched),
       "direct_id_matches": direct_matches,
       "title_fuzzy_matches": title_matches,
       "match_threshold": MATCH_THRESHOLD,
   }
   REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

   print(f"✅ Linked rows saved to: {OUT_FILE}")
   print(f"✅ Unmatched rows saved to: {UNMATCHED_FILE}")
   print(f"✅ Link report saved to: {REPORT_FILE}")
   print(f"✅ Linked rows: {len(linked)}")


if __name__ == "__main__":
   main()
