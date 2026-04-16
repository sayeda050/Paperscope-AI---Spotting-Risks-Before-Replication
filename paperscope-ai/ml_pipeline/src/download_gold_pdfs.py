import sys
import csv
import json
import re
import time
import argparse
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from collections import defaultdict

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, ensure_dir


PIPELINE_DIR = SRC_DIR.parent
REPORTS_DIR = PIPELINE_DIR / "outputs" / "reports"

SOURCE_CANDIDATES = [
    PIPELINE_DIR / "data" / "processed" / "linked.jsonl",
    PIPELINE_DIR / "data" / "processed" / "linked_with_pdfs.jsonl",
    PIPELINE_DIR / "data" / "raw" / "openreview_raw.jsonl",
]


def resolve_gold_dirs():
    """
    Use the folder structure that already exists in the project.
    Prefer:
      data/processed/gold_pdfs + data/processed/gold_eval
    Fallback:
      data/gold_pdfs + data/gold_eval
    """
    candidate_pairs = [
        (
            PIPELINE_DIR / "data" / "processed" / "gold_pdfs",
            PIPELINE_DIR / "data" / "processed" / "gold_eval",
        ),
        (
            PIPELINE_DIR / "data" / "gold_pdfs",
            PIPELINE_DIR / "data" / "gold_eval",
        ),
    ]

    for pdf_dir, eval_dir in candidate_pairs:
        if pdf_dir.exists() or eval_dir.exists():
            ensure_dir(pdf_dir)
            ensure_dir(eval_dir)
            return pdf_dir, eval_dir

    # default to processed structure because that matches your screenshots
    pdf_dir, eval_dir = candidate_pairs[0]
    ensure_dir(pdf_dir)
    ensure_dir(eval_dir)
    return pdf_dir, eval_dir


def choose_source_rows():
    for path in SOURCE_CANDIDATES:
        if path.exists():
            rows = read_jsonl(path)
            if rows:
                return path, rows
    raise FileNotFoundError(
        "No source JSONL file found. Expected one of:\n"
        + "\n".join(str(p) for p in SOURCE_CANDIDATES)
    )


def safe_text(x):
    if x is None:
        return ""
    return str(x).strip()


def combined_text(row):
    return " ".join(
        [
            safe_text(row.get("title")),
            safe_text(row.get("abstract")),
            safe_text(row.get("keywords")),
            safe_text(row.get("arxiv_title")),
            safe_text(row.get("arxiv_abstract")),
            safe_text(row.get("venue")),
        ]
    ).lower()


def infer_bucket(row):
    """
    Rough heuristic bucket so the gold set is not all one type.
    """
    text = combined_text(row)

    theory_keywords = [
        "theorem", "proof", "lemma", "corollary", "formal",
        "verification", "verified", "logic", "symbolic", "soundness",
        "completeness", "provable"
    ]
    llm_keywords = [
        "llm", "large language model", "language model", "gpt",
        "prompt", "instruction tuning", "reasoning", "rag",
        "retrieval-augmented", "agent"
    ]
    systems_keywords = [
        "systems", "system", "hardware", "rtl", "fpga", "gpu",
        "accelerator", "compiler", "kernel", "network", "distributed",
        "database", "microarchitecture", "throughput", "latency"
    ]

    if any(k in text for k in theory_keywords):
        return "theory_formal"
    if any(k in text for k in llm_keywords):
        return "llm"
    if any(k in text for k in systems_keywords):
        return "systems_hardware"
    return "empirical_ml"


def normalize_url(url):
    url = safe_text(url)
    if not url:
        return ""

    # OpenReview can sometimes give relative paths
    if url.startswith("/"):
        url = "https://openreview.net" + url

    # Convert arXiv abs URL to pdf URL if needed
    if "arxiv.org/abs/" in url:
        paper_id = url.split("/abs/")[-1].strip()
        if paper_id:
            return f"https://arxiv.org/pdf/{paper_id}.pdf"

    return url


def get_best_pdf_url(row):
    # Best preference order
    candidates = [
        row.get("arxiv_pdf_url", ""),
        row.get("pdf_url", ""),
    ]

    arxiv_id = safe_text(row.get("arxiv_id") or row.get("direct_arxiv_id"))
    if arxiv_id:
        candidates.append(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

    for url in candidates:
        url = normalize_url(url)
        if url:
            return url
    return ""


def slugify(text, max_len=120):
    text = safe_text(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "paper"
    return text[:max_len]


def unique_pdf_name(row, index):
    title = safe_text(row.get("title") or row.get("arxiv_title") or f"paper_{index}")
    uid = safe_text(row.get("paper_uid") or row.get("openreview_id") or row.get("arxiv_id"))
    base = slugify(title)
    suffix_seed = uid or title or str(index)
    suffix = hashlib.md5(suffix_seed.encode("utf-8")).hexdigest()[:8]
    return f"{base}__{suffix}.pdf"


def deduplicate_rows(rows):
    seen = set()
    cleaned = []

    for row in rows:
        title_key = safe_text(row.get("title") or row.get("arxiv_title")).lower()
        url_key = get_best_pdf_url(row).lower()
        key = (title_key, url_key)

        if not title_key and not url_key:
            continue
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(row)

    return cleaned


def interleave_buckets(bucketed_rows, target_count):
    """
    Make a balanced ordered list.
    """
    ordered = []
    buckets = ["theory_formal", "llm", "systems_hardware", "empirical_ml"]

    # distribute roughly evenly first
    quota = target_count // len(buckets)
    remainder = target_count % len(buckets)

    # take balanced base quota
    leftovers = []
    for i, bucket in enumerate(buckets):
        rows = bucketed_rows[bucket]
        need = quota + (1 if i < remainder else 0)
        take = rows[:need]
        ordered.extend(take)
        leftovers.extend(rows[need:])

    # fill shortage if some buckets had fewer papers
    if len(ordered) < target_count:
        needed = target_count - len(ordered)
        ordered.extend(leftovers[:needed])

    return ordered


def build_candidates(rows):
    rows = deduplicate_rows(rows)

    usable = []
    skipped_no_url = 0

    for row in rows:
        pdf_url = get_best_pdf_url(row)
        if not pdf_url:
            skipped_no_url += 1
            continue

        item = dict(row)
        item["resolved_pdf_url"] = pdf_url
        item["bucket"] = infer_bucket(item)
        usable.append(item)

    bucketed = defaultdict(list)
    for row in usable:
        bucketed[row["bucket"]].append(row)

    # deterministic ordering
    for bucket in bucketed:
        bucketed[bucket] = sorted(
            bucketed[bucket],
            key=lambda r: (
                safe_text(r.get("year")),
                safe_text(r.get("venue")),
                safe_text(r.get("title") or r.get("arxiv_title")),
            ),
            reverse=True,
        )

    return bucketed, skipped_no_url, len(usable)


def is_probably_pdf(file_path: Path):
    if not file_path.exists() or file_path.stat().st_size < 1000:
        return False
    try:
        with file_path.open("rb") as f:
            header = f.read(5)
        return header.startswith(b"%PDF")
    except Exception:
        return False


def download_pdf(url, dest_path: Path, timeout=60):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Paperscope-AI GoldEval Downloader)"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()

    dest_path.write_bytes(data)
    return True


def main():
    parser = argparse.ArgumentParser(description="Download a gold evaluation PDF set.")
    parser.add_argument(
        "--count",
        type=int,
        default=60,
        help="How many PDFs to download (recommended: 50 to 100). Default=60",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise ValueError("--count must be at least 1")

    gold_pdf_dir, gold_eval_dir = resolve_gold_dirs()
    ensure_dir(REPORTS_DIR)

    source_path, rows = choose_source_rows()
    bucketed, skipped_no_url, usable_count = build_candidates(rows)
    selected = interleave_buckets(bucketed, args.count)

    report = {
        "source_file": str(source_path),
        "target_count": args.count,
        "gold_pdf_dir": str(gold_pdf_dir),
        "gold_eval_dir": str(gold_eval_dir),
        "input_rows": len(rows),
        "usable_rows_with_pdf_url": usable_count,
        "skipped_no_pdf_url": skipped_no_url,
        "bucket_counts_available": {k: len(v) for k, v in bucketed.items()},
        "downloaded_ok": 0,
        "failed": 0,
        "download_failures": [],
    }

    manifest_path = gold_eval_dir / "gold_pdf_manifest.csv"
    report_path = REPORTS_DIR / "gold_pdf_download_report.json"

    downloaded_rows = []
    success_count = 0

    # Also keep fallback pool in case some selected downloads fail
    all_candidates = []
    for bucket_name in ["theory_formal", "llm", "systems_hardware", "empirical_ml"]:
        all_candidates.extend(bucketed[bucket_name])

    selected_keys = set()
    ordered_candidates = []

    for row in selected:
        key = (safe_text(row.get("title")), safe_text(row.get("resolved_pdf_url")))
        if key not in selected_keys:
            selected_keys.add(key)
            ordered_candidates.append(row)

    for row in all_candidates:
        key = (safe_text(row.get("title")), safe_text(row.get("resolved_pdf_url")))
        if key not in selected_keys:
            ordered_candidates.append(row)

    for idx, row in enumerate(ordered_candidates, start=1):
        if success_count >= args.count:
            break

        url = row["resolved_pdf_url"]
        filename = unique_pdf_name(row, idx)
        out_path = gold_pdf_dir / filename

        try:
            # Skip already-downloaded valid PDFs
            if out_path.exists() and is_probably_pdf(out_path):
                success = True
            else:
                if out_path.exists():
                    out_path.unlink(missing_ok=True)

                download_pdf(url, out_path)
                success = is_probably_pdf(out_path)

            if not success:
                out_path.unlink(missing_ok=True)
                raise ValueError("Downloaded file is not a valid PDF")

            success_count += 1
            report["downloaded_ok"] = success_count

            downloaded_rows.append(
                {
                    "paper_uid": safe_text(row.get("paper_uid")),
                    "openreview_id": safe_text(row.get("openreview_id")),
                    "arxiv_id": safe_text(row.get("arxiv_id") or row.get("direct_arxiv_id")),
                    "title": safe_text(row.get("title") or row.get("arxiv_title")),
                    "venue": safe_text(row.get("venue")),
                    "year": safe_text(row.get("year")),
                    "bucket": safe_text(row.get("bucket")),
                    "pdf_url": url,
                    "local_pdf_path": str(out_path),
                }
            )

            print(f"[{success_count}/{args.count}] Downloaded: {out_path.name}")

            # be polite to servers
            time.sleep(0.5)

        except Exception as e:
            report["failed"] += 1
            report["download_failures"].append(
                {
                    "title": safe_text(row.get("title") or row.get("arxiv_title")),
                    "url": url,
                    "error": str(e),
                }
            )
            print(f"Failed: {safe_text(row.get('title') or row.get('arxiv_title'))} | {e}")

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "paper_uid",
                "openreview_id",
                "arxiv_id",
                "title",
                "venue",
                "year",
                "bucket",
                "pdf_url",
                "local_pdf_path",
            ],
        )
        writer.writeheader()
        writer.writerows(downloaded_rows)

    report["manifest_path"] = str(manifest_path)
    report["final_downloaded"] = len(downloaded_rows)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nDone.")
    print(f"Source rows used: {source_path}")
    print(f"Gold PDFs saved in: {gold_pdf_dir}")
    print(f"Manifest saved in: {manifest_path}")
    print(f"Report saved in: {report_path}")
    print(f"Final downloaded PDFs: {len(downloaded_rows)}")


if __name__ == "__main__":
    main()