import sys
from pathlib import Path

import openreview
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import (
    write_jsonl,
    ensure_dir,
    clean_text,
    get_openreview_content_value,
    flatten_openreview_content,
    extract_arxiv_id,
)

PIPELINE_DIR = SRC_DIR.parent
RAW_DIR = PIPELINE_DIR / "data" / "raw"
OUT_FILE = RAW_DIR / "openreview_raw.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "openreview_collection_report.txt"

CLIENT = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

VENUE_IDS = [
    "ICLR.cc/2025/Conference",
    "ICLR.cc/2024/Conference",
    "NeurIPS.cc/2024/Conference",
]


def safe_str(x):
    if x is None:
        return ""
    return str(x).strip()


def note_get(note_like, field_name, default=None):
    if note_like is None:
        return default
    if isinstance(note_like, dict):
        return note_like.get(field_name, default)
    return getattr(note_like, field_name, default)


def get_note_content(note_like):
    content = note_get(note_like, "content", {}) or {}
    if isinstance(content, dict):
        return content
    return {}


def get_note_id(note_like):
    return safe_str(note_get(note_like, "id", ""))


def get_note_invitations(note_like):
    """
    API v2 replies often expose type information in `invitations` (list),
    while some older patterns use `invitation` (string). Support both.
    """
    invitations = note_get(note_like, "invitations", None)
    if invitations:
        if isinstance(invitations, list):
            return [safe_str(x) for x in invitations if safe_str(x)]
        return [safe_str(invitations)]

    invitation = safe_str(note_get(note_like, "invitation", ""))
    return [invitation] if invitation else []


def get_submission_name(venue_id: str) -> str:
    venue_group = CLIENT.get_group(venue_id)
    content = getattr(venue_group, "content", {}) or {}
    submission_name = content.get("submission_name", {})
    if isinstance(submission_name, dict):
        submission_name = submission_name.get("value", "")
    submission_name = safe_str(submission_name)
    return submission_name or "Submission"


def parse_replies(replies):
    review_texts = []
    decision_texts = []

    for reply in replies or []:
        content = get_note_content(reply)
        invitations = get_note_invitations(reply)

        text_blob = flatten_openreview_content(content)
        if not text_blob:
            continue

        inv_lows = [inv.lower() for inv in invitations]

        is_decision = any(
            ("decision" in inv)
            or ("meta_review" in inv)
            or ("metareview" in inv)
            for inv in inv_lows
        )

        is_review_like = any(
            ("official_review" in inv)
            or ("ethics_review" in inv)
            or ("review" in inv and "official_review" in inv)
            or ("public_comment" in inv)
            or ("official_comment" in inv)
            or ("comment" in inv and "author" not in inv)
            for inv in inv_lows
        )

        if is_decision:
            decision_texts.append(text_blob)
        elif is_review_like:
            review_texts.append(text_blob)

    return clean_text(" ".join(review_texts)), clean_text(" ".join(decision_texts))


def fetch_forum_replies(forum_id: str, submission_id: str):
    if not forum_id:
        return []

    try:
        replies = CLIENT.get_all_notes(forum=forum_id)
    except Exception:
        return []

    cleaned = []
    for reply in replies:
        reply_id = get_note_id(reply)
        if reply_id and reply_id == submission_id:
            continue
        cleaned.append(reply)

    return cleaned


def parse_submission(note, venue_id):
    content = get_note_content(note)

    note_id = get_note_id(note)
    forum_id = safe_str(note_get(note, "forum", "")) or note_id

    title = get_openreview_content_value(content, "title", "")
    abstract = get_openreview_content_value(content, "abstract", "")
    keywords = get_openreview_content_value(content, "keywords", "")
    pdf_url = safe_str(note_get(note, "pdf", "")) or get_openreview_content_value(content, "pdf", "")
    paper_url = get_openreview_content_value(content, "paper_url", "")

    all_content_text = flatten_openreview_content(content)
    direct_arxiv_id = (
        extract_arxiv_id(pdf_url)
        or extract_arxiv_id(paper_url)
        or extract_arxiv_id(all_content_text)
    )

    details = note_get(note, "details", {}) or {}
    replies = []
    if isinstance(details, dict):
        replies = details.get("replies") or details.get("directReplies") or []

    if not replies:
        replies = fetch_forum_replies(forum_id=forum_id, submission_id=note_id)

    review_text, decision_text = parse_replies(replies)

    return {
        "paper_uid": f"or_{note_id}",
        "source": "openreview",
        "venue": venue_id,
        "year": safe_str(venue_id).split("/")[1] if "/" in venue_id else "",
        "openreview_id": note_id,
        "forum_id": forum_id,
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "pdf_url": pdf_url,
        "paper_url": paper_url,
        "direct_arxiv_id": direct_arxiv_id,
        "decision_text": decision_text,
        "review_text": review_text,
        "review_count": len(replies),
        "raw_invitations": get_note_invitations(note),
    }


def fetch_submissions_for_venue(venue_id):
    """
    API v2 canonical path:
    1) read venue group
    2) get submission_name
    3) query exactly that invitation with details='replies'

    Do NOT query multiple invitation variants here, because that can
    inflate the row count with extra note types.
    """
    submission_name = get_submission_name(venue_id)
    invitation_id = f"{venue_id}/-/{submission_name}"

    notes = CLIENT.get_all_notes(
        invitation=invitation_id,
        details="replies",
    )

    seen = set()
    unique_notes = []

    for note in notes:
        note_id = get_note_id(note)
        if not note_id or note_id in seen:
            continue
        seen.add(note_id)
        unique_notes.append(note)

    return unique_notes


def main():
    ensure_dir(RAW_DIR)
    ensure_dir(REPORT_FILE.parent)

    all_rows = []
    report_lines = []

    total_with_reviews = 0
    total_with_decisions = 0

    for venue_id in VENUE_IDS:
        try:
            submissions = fetch_submissions_for_venue(venue_id)
        except Exception as e:
            report_lines.append(f"{venue_id} | ERROR | {e}")
            continue

        venue_rows = []
        venue_with_reviews = 0
        venue_with_decisions = 0

        for note in tqdm(submissions, desc=f"Collect {venue_id}"):
            try:
                row = parse_submission(note, venue_id)
                if row["title"] and row["abstract"]:
                    venue_rows.append(row)
                    if row["review_text"]:
                        venue_with_reviews += 1
                    if row["decision_text"]:
                        venue_with_decisions += 1
            except Exception as e:
                report_lines.append(
                    f"{venue_id} | parse_error | note_id={get_note_id(note)} | {e}"
                )

        all_rows.extend(venue_rows)
        total_with_reviews += venue_with_reviews
        total_with_decisions += venue_with_decisions

        report_lines.append(
            f"{venue_id} | submissions_found={len(submissions)} | kept={len(venue_rows)} "
            f"| with_review_text={venue_with_reviews} | with_decision_text={venue_with_decisions}"
        )

    write_jsonl(OUT_FILE, all_rows)

    report_lines.append("")
    report_lines.append(f"Total collected rows: {len(all_rows)}")
    report_lines.append(f"Rows with non-empty review_text: {total_with_reviews}")
    report_lines.append(f"Rows with non-empty decision_text: {total_with_decisions}")

    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"✅ OpenReview raw data saved to: {OUT_FILE}")
    print(f"✅ Collection report saved to: {REPORT_FILE}")
    print(f"✅ Total rows: {len(all_rows)}")
    print(f"✅ Rows with review_text: {total_with_reviews}")
    print(f"✅ Rows with decision_text: {total_with_decisions}")


if __name__ == "__main__":
    main()