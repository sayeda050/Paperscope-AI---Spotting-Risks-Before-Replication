"""
llm_auto_label.py — Auto-label gold score dataset using Groq, Gemini, or OpenAI.

════════════════════════════════════════════════════════
  QUICKEST FREE SOLUTION — USE GROQ (no card, no quota issues)
════════════════════════════════════════════════════════
  1. Go to https://console.groq.com  →  sign up with email only (NO card needed)
  2. Create an API key
  3. Run:
       pip install groq
       $env:GROQ_API_KEY = "gsk_your_key_here"
       python src\\llm_auto_label.py --domain ml --provider groq --sample-size 250

  Groq free tier: 30 RPM / 14,400 req per day — handles 250 papers in ~7 minutes.

════════════════════════════════════════════════════════
  OTHER PROVIDERS
════════════════════════════════════════════════════════
  Gemini (if your daily quota is not exhausted):
       pip install google-genai
       $env:GOOGLE_API_KEY = "your-key"
       python src\\llm_auto_label.py --domain ml --provider gemini --sample-size 250

  OpenAI (paid):
       pip install openai
       $env:OPENAI_API_KEY = "sk-your-key"
       python src\\llm_auto_label.py --domain ml --provider openai --sample-size 250

  Dry run (no API, for testing):
       python src\\llm_auto_label.py --domain ml --dry-run --sample-size 50
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import get_domain_llm_prompt, validate_domain, SUPPORTED_DOMAINS
from utils import clean_text, ensure_dir, read_jsonl, write_json, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
IN_FILE      = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
GOLD_DIR     = PIPELINE_DIR / "data" / "processed"
REPORT_DIR   = PIPELINE_DIR / "outputs" / "reports"

# ── Rate-limit / retry settings ───────────────────────────────────────────────
BATCH_SIZE            = 5      # papers per API call
GROQ_SLEEP            = 3.0    # seconds between batches (~10 RPM, Groq limit is 30 RPM)
GEMINI_SLEEP          = 8.0    # seconds between batches (~7.5 RPM, Gemini limit is 15 RPM)
MAX_RETRIES           = 5
BACKOFF_BASE          = 30.0
BACKOFF_MULTIPLIER    = 2.0
BODY_CHARS            = 3500   # max body text chars per paper sent to API


# ── Prompt builder ─────────────────────────────────────────────────────────────
def build_batch_prompt(papers: list[dict], system_prompt: str) -> str:
    papers_text = ""
    for i, paper in enumerate(papers, 1):
        title    = clean_text(paper.get("title", ""))
        abstract = clean_text(paper.get("abstract", ""))
        body     = str(paper.get("model_text", ""))[:BODY_CHARS]
        papers_text += f"""
--- PAPER {i} (uid: {paper['paper_uid']}) ---
Title: {title}
Abstract: {abstract}
Body excerpt: {body}
"""

    return f"""{system_prompt}

You will score {len(papers)} papers. For EACH paper, output a JSON object.
Return ONLY a JSON array with exactly {len(papers)} objects, one per paper, in order.
Each object must have exactly these fields:
  "paper_uid": the uid shown in the paper header
  "score": integer 0-100 (reproducibility score)
  "label": "YES" if score >= 60, else "NO"
  "reason": one sentence explanation

Return ONLY the JSON array. No markdown, no backticks, no extra text.

{papers_text}"""


def _parse_json_response(raw_text: str) -> list[dict] | None:
    """Strip fences and parse JSON array from a raw LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


def _is_quota_error(err: Exception) -> bool:
    s = str(err).lower()
    return any(w in s for w in [
        "quota", "rate", "429", "resource_exhausted",
        "too many", "retry_delay", "ratelimit",
    ])


# ── Groq batch call ────────────────────────────────────────────────────────────
def call_groq_batch(papers: list[dict], system_prompt: str, model: str) -> list[dict] | None:
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq not installed. Run: pip install groq")

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set.\n"
            "  1. Get a FREE key at https://console.groq.com (email only, no card)\n"
            "  2. $env:GROQ_API_KEY = 'gsk_your_key_here'"
        )

    client = Groq(api_key=api_key)
    prompt = build_batch_prompt(papers, system_prompt)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            raw = response.choices[0].message.content or ""
            result = _parse_json_response(raw)
            if result is not None:
                return result
            print(f"  ⚠  JSON parse failed (attempt {attempt+1}). Raw snippet: {raw[:300]}")
            time.sleep(3)

        except Exception as e:
            print(f"  ⚠  Groq error ({type(e).__name__}): {e}")
            if _is_quota_error(e):
                wait = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                print(f"  ⏳ Rate limit. Waiting {wait:.0f}s ... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                return None

    print(f"  🚫 All {MAX_RETRIES} retries failed.")
    return None


# ── Gemini batch call ──────────────────────────────────────────────────────────
def call_gemini_batch(papers: list[dict], system_prompt: str, model: str) -> list[dict] | None:
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise RuntimeError(
            "google-genai not installed.\n"
            "Run: pip install google-genai\n"
            "(Also run: pip uninstall google-generativeai -y  — the old package is dead)"
        )

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set.")

    client = genai.Client(api_key=api_key)
    prompt = build_batch_prompt(papers, system_prompt)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                    system_instruction=system_prompt,
                ),
            )
            raw = response.text.strip()
            result = _parse_json_response(raw)
            if result is not None:
                return result
            print(f"  ⚠  JSON parse failed (attempt {attempt+1}). Raw snippet: {raw[:300]}")
            time.sleep(5)

        except Exception as e:
            print(f"  ⚠  Gemini error ({type(e).__name__}): {e}")
            if _is_quota_error(e):
                wait = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                print(f"  ⏳ Quota hit. Waiting {wait:.0f}s ... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                return None

    print(f"  🚫 All {MAX_RETRIES} retries failed.")
    return None


# ── OpenAI batch call ──────────────────────────────────────────────────────────
def call_openai_batch(papers: list[dict], system_prompt: str, model: str) -> list[dict] | None:
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set.")

    client = openai.OpenAI(api_key=api_key)
    prompt = build_batch_prompt(papers, system_prompt)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            raw = response.choices[0].message.content or ""
            result = _parse_json_response(raw)
            if result is not None:
                return result
            print(f"  ⚠  JSON parse failed (attempt {attempt+1}). Raw snippet: {raw[:300]}")
            time.sleep(5)

        except Exception as e:
            print(f"  ⚠  OpenAI error ({type(e).__name__}): {e}")
            if _is_quota_error(e):
                wait = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                print(f"  ⏳ Rate limit. Waiting {wait:.0f}s ... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                return None

    print(f"  🚫 All {MAX_RETRIES} retries failed.")
    return None


# ── Dry-run heuristic (no API) ─────────────────────────────────────────────────
def heuristic_batch(papers: list[dict]) -> list[dict]:
    return [
        {
            "paper_uid": p["paper_uid"],
            "score":     int(min(100, max(0, float(p.get("reproducibility_score", 50))))),
            "label":     "YES" if float(p.get("reproducibility_score", 50)) >= 60 else "NO",
            "reason":    "Heuristic based on rubric score (dry-run mode).",
        }
        for p in papers
    ]


# ── Result parser ──────────────────────────────────────────────────────────────
def parse_single_result(raw: dict) -> tuple[int | None, str | None, str]:
    try:
        score_raw = raw.get("score", raw.get("reproducibility_score"))
        label_raw = str(raw.get("label", "")).strip().upper()
        reason    = clean_text(str(raw.get("reason", raw.get("justification", ""))))
        if score_raw is None:
            return None, None, "missing_score"
        score = int(float(str(score_raw)))
        if not (0 <= score <= 100):
            return None, None, f"score_out_of_range_{score}"
        label = label_raw if label_raw in ("YES", "NO") else ("YES" if score >= 60 else "NO")
        return score, label, reason
    except Exception as exc:
        return None, None, f"parse_error: {exc}"


# ── Per-domain processing ──────────────────────────────────────────────────────
def run_for_domain(
    domain: str,
    args,
    model_name: str,
    sleep_secs: float,
    out_file: Path,
    full_df: pd.DataFrame,
    text_col: str,
) -> dict:
    """Label papers for a single domain. Returns a stats dict."""
    system_prompt = get_domain_llm_prompt(domain)

    domain_df = full_df[full_df["domain"] == domain].copy()
    if domain_df.empty:
        print(f"⚠  No rows found for domain {domain!r} — skipping.")
        return {"domain": domain, "skipped": True}

    domain_df = domain_df[domain_df[text_col].str.len() >= args.min_model_chars]
    domain_df = domain_df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)
    if domain_df.empty:
        print(f"⚠  No usable rows for domain {domain!r} after filtering — skipping.")
        return {"domain": domain, "skipped": True}

    # Auto-resume: load already-labeled rows for this domain from the shared out_file
    already_labeled: dict[str, dict] = {}
    if out_file.exists():
        existing_df = pd.read_csv(out_file)
        existing_df["target_score"] = pd.to_numeric(
            existing_df.get("target_score", pd.Series([])), errors="coerce"
        )
        done_rows = existing_df[
            existing_df["target_score"].notna() &
            (existing_df.get("domain", pd.Series([])).astype(str) == domain)
        ]
        for _, row in done_rows.iterrows():
            already_labeled[str(row["paper_uid"])] = row.to_dict()
        if already_labeled:
            print(f"  📂 Auto-resume ({domain}): {len(already_labeled)} already done — skipping.")

    sample_size = min(args.sample_size, len(domain_df))
    sample_df   = domain_df.sample(n=sample_size, random_state=args.random_state).reset_index(drop=True)
    pending_df  = sample_df[~sample_df["paper_uid"].isin(already_labeled.keys())].reset_index(drop=True)
    n_pending   = len(pending_df)

    mode_str = "🔍 DRY RUN" if args.dry_run else f"🤖 {args.provider.upper()} ({model_name})"
    print(f"\n{mode_str} — domain={domain!r} | {sample_size} papers "
          f"({len(already_labeled)} done, {n_pending} to process now)")

    if n_pending == 0:
        print(f"  ✅ All {domain} papers already labeled.")
        return {"domain": domain, "labeled": 0, "failed": 0, "skipped": False}

    batch_size  = args.batch_size
    n_batches   = (n_pending + batch_size - 1) // batch_size
    est_minutes = (n_batches * sleep_secs) / 60
    print(f"  📊 {n_pending} papers → {n_batches} batches → ~{est_minutes:.1f} min")

    new_results:  list[dict] = []
    failed_uids:  list[str]  = []
    labeled_count = 0
    pbar = tqdm(total=n_pending, desc=f"  Labeling {domain}", unit="paper")

    for batch_idx in range(n_batches):
        start      = batch_idx * batch_size
        end        = min(start + batch_size, n_pending)
        batch_rows = pending_df.iloc[start:end]

        papers_for_api = [
            {
                "paper_uid":             str(row["paper_uid"]),
                "title":                 str(row.get("title", "")),
                "abstract":              str(row.get("abstract", "")),
                "model_text":            str(row.get(text_col, ""))[:BODY_CHARS],
                "reproducibility_score": float(row.get("reproducibility_score", 50)),
            }
            for _, row in batch_rows.iterrows()
        ]

        if args.dry_run:
            batch_results = heuristic_batch(papers_for_api)
        elif args.provider == "groq":
            batch_results = call_groq_batch(papers_for_api, system_prompt, model_name)
        elif args.provider == "gemini":
            batch_results = call_gemini_batch(papers_for_api, system_prompt, model_name)
        else:
            batch_results = call_openai_batch(papers_for_api, system_prompt, model_name)

        if batch_results is None:
            for paper in papers_for_api:
                failed_uids.append(paper["paper_uid"])
            pbar.update(len(papers_for_api))
        else:
            result_map: dict[str, dict] = {
                str(r.get("paper_uid", "")).strip(): r
                for r in batch_results if r.get("paper_uid")
            }

            for _, row in batch_rows.iterrows():
                uid        = str(row["paper_uid"])
                raw_result = result_map.get(uid)
                if raw_result is None:
                    pos = list(batch_rows["paper_uid"]).index(uid)
                    if pos < len(batch_results):
                        raw_result = batch_results[pos]

                score, label, reason = (
                    parse_single_result(raw_result) if raw_result is not None
                    else (None, None, "not_in_response")
                )

                new_results.append({
                    "paper_uid":        uid,
                    "title":            clean_text(str(row.get("title", ""))),
                    "abstract":         clean_text(str(row.get("abstract", ""))),
                    "model_text":       str(row.get(text_col, "")),
                    "domain":           domain,
                    "pdf_path":         str(row.get("pdf_path", "")),
                    "venue":            str(row.get("venue", "")),
                    "year":             str(row.get("year", "")),
                    "model_text_chars": len(str(row.get(text_col, ""))),
                    "target_score":     score,
                    "llm_label":        label,
                    "llm_reason":       clean_text(str(reason))[:500] if reason else "",
                    "rubric_score":     round(float(row.get("reproducibility_score", 50)), 2),
                    "schema_version":   PIPELINE_SCHEMA_VERSION,
                })

                if score is not None:
                    labeled_count += 1
                else:
                    failed_uids.append(uid)

                pbar.update(1)

        # Incremental save after every batch (appends to shared file safely)
        combined_rows = list(already_labeled.values()) + new_results
        if out_file.exists():
            existing_df = pd.read_csv(out_file)
            # Drop rows for this domain that we are actively rewriting
            other_domains_df = existing_df[
                existing_df.get("domain", pd.Series([])).astype(str) != domain
            ]
            pd.concat(
                [other_domains_df, pd.DataFrame(combined_rows)], ignore_index=True
            ).to_csv(out_file, index=False)
        else:
            pd.DataFrame(combined_rows).to_csv(out_file, index=False)

        if batch_idx < n_batches - 1 and not args.dry_run:
            time.sleep(sleep_secs)

    pbar.close()
    print(f"  ✅ {domain}: labeled {labeled_count}, failed {len(failed_uids)}")
    return {
        "domain":   domain,
        "labeled":  labeled_count,
        "failed":   len(failed_uids),
        "skipped":  False,
        "sample_size": sample_size,
        "failed_uids": failed_uids[:20],
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-label gold score dataset using LLM with batch processing."
    )
    parser.add_argument(
        "--domain",
        default="all",
        choices=SUPPORTED_DOMAINS + ["all"],
        help="Domain to label, or 'all' to label every domain present in the data (default: all).",
    )
    parser.add_argument("--provider",        choices=["groq", "gemini", "openai"], default="groq")
    parser.add_argument("--model",           default="")
    parser.add_argument("--sample-size",     type=int, default=250)
    parser.add_argument("--min-model-chars", type=int, default=500)
    parser.add_argument("--random-state",    type=int, default=42)
    parser.add_argument("--batch-size",      type=int, default=BATCH_SIZE)
    parser.add_argument("--sleep",           type=float, default=-1,
                        help="Seconds between batches (-1 = auto)")
    parser.add_argument("--dry-run",         action="store_true")
    parser.add_argument("--output-file",     default="")
    args = parser.parse_args()

    if not args.model:
        model_name = {
            "groq":   "llama-3.3-70b-versatile",
            "gemini": "gemini-2.0-flash-lite",
            "openai": "gpt-4o-mini",
        }.get(args.provider, "llama-3.3-70b-versatile")
    else:
        model_name = args.model

    sleep_secs = (GEMINI_SLEEP if args.provider == "gemini" else GROQ_SLEEP) \
                 if args.sleep < 0 else args.sleep

    out_file = Path(args.output_file) if args.output_file else GOLD_DIR / "gold_score_dataset.csv"
    ensure_dir(out_file.parent)
    ensure_dir(REPORT_DIR)

    # ── Load all extracted text once ──────────────────────────────────────────
    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Missing: {IN_FILE}\nRun extract_text.py first.")

    full_df  = pd.DataFrame(rows)
    text_col = "model_text" if "model_text" in full_df.columns else "raw_text"
    full_df[text_col]   = full_df[text_col].fillna("").astype(str)
    full_df["title"]    = full_df.get("title",    pd.Series([""] * len(full_df))).fillna("").astype(str).map(clean_text)
    full_df["abstract"] = full_df.get("abstract", pd.Series([""] * len(full_df))).fillna("").astype(str).map(clean_text)
    if "reproducibility_score" not in full_df.columns:
        full_df["reproducibility_score"] = 50.0

    # ── Determine which domains to run ────────────────────────────────────────
    if args.domain == "all":
        # Only process domains actually present in the data
        domains_in_data = sorted(full_df["domain"].dropna().astype(str).unique().tolist())
        domains_to_run  = [d for d in domains_in_data if d in SUPPORTED_DOMAINS]
        if not domains_to_run:
            raise RuntimeError(
                "No recognised domains found in extracted_text.jsonl. "
                "Check that 'domain' field is set correctly."
            )
        print(f"🌐 Running ALL domains found in data: {domains_to_run}")
    else:
        domains_to_run = [validate_domain(args.domain)]

    # ── Loop over domains ─────────────────────────────────────────────────────
    all_stats: list[dict] = []
    for domain in domains_to_run:
        stats = run_for_domain(
            domain=domain,
            args=args,
            model_name=model_name,
            sleep_secs=sleep_secs,
            out_file=out_file,
            full_df=full_df,
            text_col=text_col,
        )
        all_stats.append(stats)

    # ── Final summary ─────────────────────────────────────────────────────────
    if out_file.exists():
        final_df      = pd.read_csv(out_file)
        total_labeled = int(pd.to_numeric(final_df["target_score"], errors="coerce").notna().sum())
        total_pending = int(pd.to_numeric(final_df["target_score"], errors="coerce").isna().sum())
        avg_score     = float(pd.to_numeric(final_df["target_score"], errors="coerce").dropna().mean()) \
                        if total_labeled else None
    else:
        total_labeled = total_pending = 0
        avg_score = None

    write_json(REPORT_DIR / "llm_auto_label_report.json", {
        "schema_version":   PIPELINE_SCHEMA_VERSION,
        "domains_run":      domains_to_run,
        "provider":         "dry_run" if args.dry_run else args.provider,
        "model":            "heuristic" if args.dry_run else model_name,
        "batch_size":       args.batch_size,
        "sample_size":      args.sample_size,
        "total_labeled":    total_labeled,
        "total_pending":    total_pending,
        "avg_target_score": avg_score,
        "output_file":      str(out_file),
        "domain_stats":     all_stats,
    })

    print(f"\n{'='*60}")
    print(f"✅ All domains done!")
    print(f"   Total labeled : {total_labeled}")
    print(f"   Total pending : {total_pending}")
    print(f"✅ Gold dataset  → {out_file}")

    if total_pending > 0 and not args.dry_run:
        print(f"\n⏰ {total_pending} papers still pending. Re-run to auto-resume.")
    elif total_labeled > 0:
        print(f"\n🎯 Next step:")
        for d in domains_to_run:
            print(f"   python src\\train_score_calibrator.py --domain {d}")


if __name__ == "__main__":
    main()
