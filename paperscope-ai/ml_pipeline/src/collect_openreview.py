"""
collect_openreview.py — Collect ML/NLP papers from OpenReview API v2.

Outputs: data/raw/openreview_raw.jsonl
"""
from __future__ import annotations

import sys
from pathlib import Path

import openreview
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_text,
    ensure_dir,
    extract_arxiv_id,
    flatten_openreview_content,
    get_openreview_content_value,
    write_jsonl,
)

PIPELINE_DIR = SRC_DIR.parent
RAW_DIR      = PIPELINE_DIR / "data" / "raw"
OUT_FILE     = RAW_DIR / "openreview_raw.jsonl"
REPORT_FILE  = PIPELINE_DIR / "outputs" / "reports" / "openreview_collection_report.txt"

CLIENT = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

# Each venue maps to a domain. ICLR/NeurIPS/ICML → "ml"; ACL/EMNLP → "nlp"
VENUE_CONFIGS = [
    {"venue_id": "ICLR.cc/2025/Conference",   "domain": "ml"},
    {"venue_id": "ICLR.cc/2024/Conference",   "domain": "ml"},
    {"venue_id": "NeurIPS.cc/2024/Conference", "domain": "ml"},
]


def safe_str(x) -> str:
    return "" if x is None else str(x).strip()


def note_get(note_like, field_name, default=None):
    if note_like is None:
        return default
    if isinstance(note_like, dict):
        return note_like.get(field_name, default)
    return getattr(note_like, field_name, default)


def get_note_content(note_like) -> dict:
    content = note_get(note_like, "content", {}) or {}
    return content if isinstance(content, dict) else {}


def get_note_id(note_like) -> str:
    return safe_str(note_get(note_like, "id", ""))


def get_note_invitations(note_like) -> list[str]:
    invitations = note_get(note_like, "invitations", None)
    if invitations:
        if isinstance(invitations, list):
            return [safe_str(x) for x in invitations if safe_str(x)]
        return [safe_str(invitations)]
    invitation = safe_str(note_get(note_like, "invitation", ""))
    return [invitation] if invitation else []


def get_submission_name(venue_id: str) -> str:
    try:
        venue_group = CLIENT.get_group(venue_id)
        content = getattr(venue_group, "content", {}) or {}
        submission_name = content.get("submission_name", {})
        if isinstance(submission_name, dict):
            submission_name = submission_name.get("value", "")
        return safe_str(submission_name) or "Submission"
    except Exception:
        return "Submission"


def parse_replies(replies) -> tuple[str, str]:
    review_texts:   list[str] = []
    decision_texts: list[str] = []

    for reply in replies or []:
        content     = get_note_content(reply)
        invitations = get_note_invitations(reply)
        text_blob   = flatten_openreview_content(content)
        if not text_blob:
            continue

        inv_lows = [inv.lower() for inv in invitations]
        is_decision = any(
            "decision" in inv or "meta_review" in inv or "metareview" in inv
            for inv in inv_lows
        )
        is_review = any(
            "official_review" in inv or "ethics_review" in inv
            or "public_comment" in inv or "official_comment" in inv
            or ("comment" in inv and "author" not in inv)
            for inv in inv_lows
        )

        if is_decision:
            decision_texts.append(text_blob)
        elif is_review:
            review_texts.append(text_blob)

    return (
        clean_text(" ".join(review_texts)),
        clean_text(" ".join(decision_texts)),
    )


def fetch_forum_replies(forum_id: str, submission_id: str) -> list:
    if not forum_id:
        return []
    try:
        replies = CLIENT.get_all_notes(forum=forum_id)
    except Exception:
        return []
    return [r for r in replies if get_note_id(r) != submission_id]


def parse_submission(note, venue_id: str, domain: str) -> dict | None:
    content = get_note_content(note)
    note_id = get_note_id(note)
    if not note_id:
        return None

    forum_id = safe_str(note_get(note, "forum", "")) or note_id
    title    = get_openreview_content_value(content, "title", "")
    abstract = get_openreview_content_value(content, "abstract", "")
    if not title or not abstract:
        return None

    keywords = get_openreview_content_value(content, "keywords", "")
    pdf_url  = safe_str(note_get(note, "pdf", "")) or get_openreview_content_value(content, "pdf", "")
    paper_url = get_openreview_content_value(content, "paper_url", "")
    all_content_text = flatten_openreview_content(content)
    arxiv_id = (
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
        "schema_version":   PIPELINE_SCHEMA_VERSION,
        "paper_uid":        f"or_{note_id}",
        "source":           "openreview",
        "domain":           domain,
        "venue":            venue_id,
        "year":             venue_id.split("/")[1] if "/" in venue_id else "",
        "openreview_id":    note_id,
        "forum_id":         forum_id,
        "title":            title,
        "abstract":         abstract,
        "keywords":         keywords,
        "pdf_url":          pdf_url,
        "paper_url":        paper_url,
        "direct_arxiv_id":  arxiv_id,
        "decision_text":    decision_text,
        "review_text":      review_text,
        "review_count":     len(replies),
        "raw_invitations":  get_note_invitations(note),
    }


def fetch_submissions_for_venue(venue_id: str) -> list:
    submission_name = get_submission_name(venue_id)
    invitation_id   = f"{venue_id}/-/{submission_name}"
    notes = CLIENT.get_all_notes(invitation=invitation_id, details="replies")
    seen: set[str] = set()
    unique: list   = []
    for note in notes:
        nid = get_note_id(note)
        if nid and nid not in seen:
            seen.add(nid)
            unique.append(note)
    return unique


def main() -> None:
    ensure_dir(RAW_DIR)
    ensure_dir(REPORT_FILE.parent)

    all_rows:    list[dict] = []
    report_lines: list[str] = []
    total_reviews   = 0
    total_decisions = 0

    for config in VENUE_CONFIGS:
        venue_id = config["venue_id"]
        domain   = config["domain"]
        try:
            submissions = fetch_submissions_for_venue(venue_id)
        except Exception as e:
            report_lines.append(f"{venue_id} | ERROR | {e}")
            continue

        venue_rows      = []
        venue_reviews   = 0
        venue_decisions = 0

        for note in tqdm(submissions, desc=f"Collect {venue_id}"):
            try:
                row = parse_submission(note, venue_id, domain)
                if row is not None:
                    venue_rows.append(row)
                    if row["review_text"]:
                        venue_reviews += 1
                    if row["decision_text"]:
                        venue_decisions += 1
            except Exception as e:
                report_lines.append(
                    f"{venue_id} | parse_error | note_id={get_note_id(note)} | {e}"
                )

        all_rows.extend(venue_rows)
        total_reviews   += venue_reviews
        total_decisions += venue_decisions
        report_lines.append(
            f"{venue_id} | domain={domain} | kept={len(venue_rows)} "
            f"| with_review_text={venue_reviews} | with_decision_text={venue_decisions}"
        )

    write_jsonl(OUT_FILE, all_rows)
    report_lines += [
        "",
        f"Total rows: {len(all_rows)}",
        f"With review_text:   {total_reviews}",
        f"With decision_text: {total_decisions}",
    ]
    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"✅ OpenReview data → {OUT_FILE}")
    print(f"✅ Report          → {REPORT_FILE}")
    print(f"✅ Total rows:      {len(all_rows)}")
    print(f"   With reviews:    {total_reviews}")
    print(f"   With decisions:  {total_decisions}")


if __name__ == "__main__":
    main()
