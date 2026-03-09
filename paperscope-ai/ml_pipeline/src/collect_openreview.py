import sys
from pathlib import Path
import json

import openreview
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import (
    ensure_dir,
    write_jsonl,
    clean_text,
    extract_arxiv_id,
    get_openreview_content_value,
    flatten_openreview_content,
)

PIPELINE_DIR = SRC_DIR.parent
RAW_DIR = PIPELINE_DIR / "data" / "raw"
OUT_FILE = RAW_DIR / "openreview_raw.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "openreview_collection_report.txt"

# Use public API2 client (no login needed for public data)
CLIENT = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

# Start with venues that usually expose public submissions/replies well enough
VENUE_IDS = [
    "ICLR.cc/2025/Conference",
    "ICLR.cc/2024/Conference",
    "NeurIPS.cc/2024/Conference",
]

HEADERS = {
    "User-Agent": "PaperScopeAI-DatasetBuilder/1.0"
}


def safe_str(x):
    if x is None:
        return ""
    return str(x).strip()


def parse_replies(replies):
    review_texts = []
    decision_texts = []

    for reply in replies or []:
        content = getattr(reply, "content", {}) or {}
        invitation = safe_str(getattr(reply, "invitation", ""))

        text_blob = flatten_openreview_content(content)
        if not text_blob:
            continue

        inv_low = invitation.lower()

        if "decision" in inv_low or "meta" in inv_low:
            decision_texts.append(text_blob)
        elif "review" in inv_low or "comment" in inv_low or "public_comment" in inv_low:
            review_texts.append(text_blob)

    return clean_text(" ".join(review_texts)), clean_text(" ".join(decision_texts))


def parse_submission(note, venue_id):
    content = getattr(note, "content", {}) or {}

    title = get_openreview_content_value(content, "title", "")
    abstract = get_openreview_content_value(content, "abstract", "")
    keywords = get_openreview_content_value(content, "keywords", "")
    pdf_url = safe_str(getattr(note, "pdf", "")) or get_openreview_content_value(content, "pdf", "")
    paper_url = get_openreview_content_value(content, "paper_url", "")

    all_content_text = flatten_openreview_content(content)
    direct_arxiv_id = (
        extract_arxiv_id(pdf_url)
        or extract_arxiv_id(paper_url)
        or extract_arxiv_id(all_content_text)
    )

    details = getattr(note, "details", {}) or {}
    replies = details.get("replies", []) or details.get("directReplies", []) or []
    review_text, decision_text = parse_replies(replies)

    return {
        "paper_uid": f"or_{safe_str(note.id)}",
        "source": "openreview",
        "venue": venue_id,
        "year": safe_str(venue_id).split("/")[1] if "/" in venue_id else "",
        "openreview_id": safe_str(note.id),
        "forum_id": safe_str(getattr(note, "forum", "")) or safe_str(note.id),
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "pdf_url": pdf_url,
        "paper_url": paper_url,
        "direct_arxiv_id": direct_arxiv_id,
        "decision_text": decision_text,
        "review_text": review_text,
        "review_count": len(replies),
        "raw_invitation": safe_str(getattr(note, "invitation", "")),
    }


def fetch_submissions_for_venue(venue_id):
    """
    API v2:
    docs show using content={'venueid': venue_id} for accepted submissions.
    We also try common under-review variants because not all papers are accepted.
    """
    candidate_venueids = [
        venue_id,
        f"{venue_id}/Submission",
        f"{venue_id}/-/Submission",
        f"{venue_id}/Submitted",
        f"{venue_id}/Under_Review",
    ]

    all_notes = []
    seen = set()

    for v in candidate_venueids:
        try:
            notes = client_get_all_notes(v)
        except Exception:
            notes = []

        for n in notes:
            nid = safe_str(getattr(n, "id", ""))
            if nid and nid not in seen:
                seen.add(nid)
                all_notes.append(n)

    return all_notes


def client_get_all_notes(venueid_value):
    # details='replies' is useful for reviews/comments in API2 examples
    return CLIENT.get_all_notes(
        content={"venueid": venueid_value},
        details="replies"
    )


def main():
    ensure_dir(RAW_DIR)
    ensure_dir(REPORT_FILE.parent)

    all_rows = []
    report_lines = []

    for venue_id in VENUE_IDS:
        try:
            submissions = fetch_submissions_for_venue(venue_id)
        except Exception as e:
            report_lines.append(f"{venue_id} | ERROR | {e}")
            continue

        report_lines.append(f"{venue_id} | submissions_found={len(submissions)}")

        for note in tqdm(submissions, desc=f"Collect {venue_id}"):
            try:
                row = parse_submission(note, venue_id)
                if row["title"] and row["abstract"]:
                    all_rows.append(row)
            except Exception as e:
                report_lines.append(f"{venue_id} | parse_error | note_id={getattr(note, 'id', '')} | {e}")

    write_jsonl(OUT_FILE, all_rows)

    report_lines.append("")
    report_lines.append(f"Total collected rows: {len(all_rows)}")
    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"✅ OpenReview raw data saved to: {OUT_FILE}")
    print(f"✅ Collection report saved to: {REPORT_FILE}")
    print(f"✅ Total rows: {len(all_rows)}")


if __name__ == "__main__":
    main()