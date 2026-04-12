import sys
from pathlib import Path
import argparse

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, ensure_dir, clean_text

BASE_DIR = SRC_DIR.parent
IN_FILE = BASE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_FILE = BASE_DIR / "data" / "processed" / "gold_score_dataset.csv"


def main():
    parser = argparse.ArgumentParser(description="Prepare a manual scoring template for calibrator training.")
    parser.add_argument("--sample-size", type=int, default=250)
    parser.add_argument("--min-model-chars", type=int, default=1200)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Input file not found or empty: {IN_FILE}")

    df = pd.DataFrame(rows)
    required = {"paper_uid", "title", "abstract", "model_text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in extracted_text.jsonl: {sorted(missing)}")

    df = df.copy()
    df["title"] = df["title"].fillna("").astype(str).map(clean_text)
    df["abstract"] = df["abstract"].fillna("").astype(str).map(clean_text)
    df["model_text"] = df["model_text"].fillna("").astype(str).map(clean_text)
    if "pdf_path" not in df.columns:
        df["pdf_path"] = ""
    if "venue" not in df.columns:
        df["venue"] = ""
    if "year" not in df.columns:
        df["year"] = ""

    df["model_text_chars"] = df["model_text"].str.len()
    df = df[df["model_text_chars"] >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    if df.empty:
        raise RuntimeError("No rows left after filtering. Lower --min-model-chars and try again.")

    sample_size = min(args.sample_size, len(df))
    df = df.sample(n=sample_size, random_state=args.random_state).reset_index(drop=True)

    out_df = df[
        ["paper_uid", "title", "abstract", "model_text", "pdf_path", "venue", "year", "model_text_chars"]
    ].copy()
    out_df["target_score"] = ""
    out_df["annotator_notes"] = ""

    ensure_dir(OUT_FILE.parent)
    out_df.to_csv(OUT_FILE, index=False)

    print(f"✅ Manual score template saved to: {OUT_FILE}")
    print(f"✅ Rows prepared: {len(out_df)}")
    print("Next step: fill target_score with values from 0 to 100, then run train_score_calibrator.py")


if __name__ == "__main__":
    main()
