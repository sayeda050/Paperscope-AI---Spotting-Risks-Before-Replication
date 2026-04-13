"""
prepare_score_training_dataset.py — Prepare the gold score dataset template.

Produces a CSV with target_score and llm_label columns ready to be filled by
llm_auto_label.py.  Uses stratified sampling across domains so the calibrator
learns domain-conditional scoring.

Per-domain minimum: 60 rows (or all available if fewer exist).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import SUPPORTED_DOMAINS
from utils import clean_text, ensure_dir, read_jsonl, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
IN_FILE      = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_FILE     = PIPELINE_DIR / "data" / "processed" / "gold_score_dataset.csv"

# Target rows per domain for a well-balanced calibrator
DEFAULT_PER_DOMAIN = 100


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare stratified gold score dataset template for the score calibrator."
    )
    parser.add_argument(
        "--per-domain", type=int, default=DEFAULT_PER_DOMAIN,
        help=f"Target rows per domain (default {DEFAULT_PER_DOMAIN}).",
    )
    parser.add_argument("--min-model-chars", type=int, default=1200)
    parser.add_argument("--random-state",    type=int, default=42)
    args = parser.parse_args()

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Empty or missing: {IN_FILE}\nRun extract_text.py first.")

    df = pd.DataFrame(rows)
    df["model_text"] = df.get("model_text", df.get("raw_text", pd.Series([""] * len(df)))).fillna("").astype(str).map(clean_text)
    df["title"]      = df.get("title",      pd.Series([""] * len(df))).fillna("").astype(str).map(clean_text)
    df["abstract"]   = df.get("abstract",   pd.Series([""] * len(df))).fillna("").astype(str).map(clean_text)
    if "domain" not in df.columns:
        df["domain"] = "ml"
    df["domain"] = df["domain"].fillna("ml").astype(str)

    df = df[df["model_text"].str.len() >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"] if "paper_uid" in df.columns else ["title"]).reset_index(drop=True)

    if df.empty:
        raise RuntimeError("No rows left after filtering. Lower --min-model-chars.")

    # Stratified sample: N rows per domain
    parts: list[pd.DataFrame] = []
    for domain in SUPPORTED_DOMAINS:
        sub = df[df["domain"] == domain].copy()
        if sub.empty:
            continue
        n = min(args.per_domain, len(sub))
        parts.append(sub.sample(n=n, random_state=args.random_state))
        print(f"  {domain:12s}: sampled {n:4d} / {len(sub):4d} available rows")

    if not parts:
        # Fallback: no domain column, sample everything
        print("⚠  No domain-specific rows found. Sampling globally.")
        n = min(args.per_domain * 3, len(df))
        parts.append(df.sample(n=n, random_state=args.random_state))

    sample_df = pd.concat(parts, ignore_index=True).sample(
        frac=1, random_state=args.random_state
    ).reset_index(drop=True)

    base_cols = ["paper_uid", "title", "abstract", "model_text", "domain"]
    optional  = ["pdf_path", "venue", "year", "model_text_chars"]
    keep_cols = base_cols + [c for c in optional if c in sample_df.columns]
    out_df    = sample_df[keep_cols].copy()
    out_df["model_text_chars"] = out_df["model_text"].str.len()
    out_df["target_score"]     = ""   # to be filled by llm_auto_label.py
    out_df["llm_label"]        = ""   # YES / NO
    out_df["llm_reason"]       = ""
    out_df["annotator_notes"]  = ""
    out_df["schema_version"]   = PIPELINE_SCHEMA_VERSION

    ensure_dir(OUT_FILE.parent)
    out_df.to_csv(OUT_FILE, index=False)

    domain_breakdown = out_df["domain"].value_counts().to_dict() if "domain" in out_df.columns else {}
    print(f"\n✅ Gold score template → {OUT_FILE}")
    print(f"   Total rows:  {len(out_df)}")
    print(f"   By domain:   {domain_breakdown}")
    print("\n📋 Next steps:")
    print("   Option A (recommended): python llm_auto_label.py --domain <domain> --provider openai")
    print("   Option B (manual):      Fill target_score column manually (0–100), then:")
    print("   python train_score_calibrator.py --domain <domain>")


if __name__ == "__main__":
    main()
