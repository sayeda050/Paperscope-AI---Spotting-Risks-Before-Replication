"""
run_pipeline.py — End-to-end pipeline runner for PaperScope AI.

Runs all processing stages in dependency order with:
  - File existence and freshness checks (no stale intermediates)
  - Clear error reporting
  - --from-stage to resume after failures
  - --domain to run domain-specific training

USAGE:
  # Full pipeline for ML (first time):
  python run_pipeline.py --domain ml

  # Skip collection (already done), run from extraction:
  python run_pipeline.py --domain ml --from-stage extract_text

  # Multi-domain: collect physics papers then merge:
  python run_pipeline.py --domain physics --skip-to merge_raw

  # Train only:
  python run_pipeline.py --domain ml --from-stage train
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SRC_DIR.parent
DATA_DIR     = PIPELINE_DIR / "data"
PROCESSED    = DATA_DIR / "processed"
RAW          = DATA_DIR / "raw"
OUTPUTS      = PIPELINE_DIR / "outputs"


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
# Each stage: name, script, args_template, output_file (freshness check)
# {domain} is replaced with the actual domain argument.

STAGES = [
    # ── Collection ─────────────────────────────────────────────────────────
    {
        "name":   "collect_ml",
        "script": "collect_openreview.py",
        "args":   [],
        "output": RAW / "openreview_raw.jsonl",
        "only_domains": ["ml"],
        "description": "Collect ML papers from OpenReview",
    },
    {
        "name":   "collect_arxiv",
        "script": "collect_arxiv.py",
        "args":   ["--domain", "{domain}", "--max-results", "200"],
        "output": None,   # domain-specific, checked separately
        "only_domains": ["physics", "biomed", "nlp", "finance", "hardware", "math"],
        "description": "Collect {domain} papers from arXiv",
    },
    # ── Merging ────────────────────────────────────────────────────────────
    {
        "name":   "merge_raw",
        "script": "merge_raw_data.py",
        "args":   [],
        "output": RAW / "unified_raw_dataset.jsonl",
        "only_domains": [],   # always runs
        "description": "Merge all domain raw files",
    },
    # ── Download ───────────────────────────────────────────────────────────
    {
        "name":   "download_pdfs",
        "script": "download_openreview_pdfs.py",
        "args":   ["--max-papers", "2000"],
        "output": PROCESSED / "linked_with_pdfs.jsonl",
        "only_domains": [],
        "description": "Download PDFs",
    },
    # ── Text extraction ────────────────────────────────────────────────────
    {
        "name":   "extract_text",
        "script": "extract_text.py",
        "args":   [],
        "output": PROCESSED / "extracted_text.jsonl",
        "only_domains": [],
        "description": "Extract text from PDFs",
    },
    # ── Feature discovery ──────────────────────────────────────────────────
    {
        "name":   "discover_features",
        "script": "discover_pdf_features.py",
        "args":   [],
        "output": PROCESSED / "discovered_feature_records.jsonl",
        "only_domains": [],
        "description": "Discover reproducibility features",
    },
    # ── Scoring ────────────────────────────────────────────────────────────
    {
        "name":   "score",
        "script": "auto_weight_and_score.py",
        "args":   [],
        "output": PROCESSED / "auto_scored_papers.csv",
        "only_domains": [],
        "description": "Auto-score papers",
    },
    # ── Labeling ───────────────────────────────────────────────────────────
    {
        "name":   "label",
        "script": "build_labeled_dataset_auto.py",
        "args":   [],
        "output": PROCESSED / "labeled_dataset.csv",
        "only_domains": [],
        "description": "Build labeled dataset",
    },
    # ── Sanity check ───────────────────────────────────────────────────────
    {
        "name":   "sanity_check",
        "script": "sanity_check_auto_dataset.py",
        "args":   [],
        "output": OUTPUTS / "reports" / "dataset_sanity_check.json",
        "only_domains": [],
        "description": "Run dataset sanity checks",
    },
    # ── Training ───────────────────────────────────────────────────────────
    {
        "name":   "train",
        "script": "train_tfidf_logreg.py",
        "args":   ["--domain", "{domain}"],
        "output": None,   # versioned dir — freshness checked via latest.json
        "only_domains": [],
        "description": "Train TF-IDF + LogReg classifier",
    },
    # ── LLM Gold Labeling (optional) ───────────────────────────────────────
    {
        "name":   "llm_label",
        "script": "llm_auto_label.py",
        "args":   ["--domain", "{domain}", "--sample-size", "250"],
        "output": PROCESSED / "gold_score_dataset.csv",
        "only_domains": [],
        "optional": True,
        "description": "LLM-based gold score labeling (requires API key)",
    },
    # ── Score calibrator ───────────────────────────────────────────────────
    {
        "name":   "train_calibrator",
        "script": "train_score_calibrator.py",
        "args":   ["--domain", "{domain}"],
        "output": None,
        "only_domains": [],
        "optional": True,   # requires gold_score_dataset.csv with target_score filled
        "description": "Train score calibrator (requires gold_score_dataset.csv)",
    },
    # ── Evaluation ─────────────────────────────────────────────────────────
    {
        "name":   "evaluate",
        "script": "evaluate_tfidf_logreg.py",
        "args":   ["--domain", "{domain}"],
        "output": OUTPUTS / "reports" / "evaluation_summary.json",
        "only_domains": [],
        "description": "Evaluate classifier on test set",
    },
    # ── Export ─────────────────────────────────────────────────────────────
    {
        "name":   "export",
        "script": "export_artifacts.py",
        "args":   ["--domain", "{domain}"],
        "output": None,
        "only_domains": [],
        "description": "Export model artifacts to backend/ml_assets",
    },
]

STAGE_NAMES = [s["name"] for s in STAGES]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def format_args(args_template: list[str], domain: str) -> list[str]:
    return [a.replace("{domain}", domain) for a in args_template]


def is_fresh(output_path: Path | None, input_paths: list[Path]) -> bool:
    """Return True if output exists and is newer than all inputs."""
    if output_path is None:
        return False
    if not output_path.exists():
        return False
    out_mtime = output_path.stat().st_mtime
    for inp in input_paths:
        if inp.exists() and inp.stat().st_mtime > out_mtime:
            return False
    return True


def run_stage(stage: dict, domain: str, dry_run: bool, force: bool) -> bool:
    """Run a single stage. Returns True on success."""
    script = SRC_DIR / stage["script"]
    if not script.exists():
        print(f"  ⚠  Script not found: {script} — skipping")
        return True   # non-fatal for optional stages

    # Check if domain should run this stage
    only = stage.get("only_domains", [])
    if only and domain not in only:
        print(f"  ⏭  Skipping {stage['name']} (not applicable to domain {domain!r})")
        return True

    args = format_args(stage.get("args", []), domain)
    cmd  = [sys.executable, str(script)] + args

    output_path = stage.get("output")
    is_opt = stage.get("optional", False)

    if not force and output_path is not None and output_path.exists():
        print(f"  ✅ {stage['name']} — output already exists, skipping. (use --force to re-run)")
        return True

    desc = stage["description"].replace("{domain}", domain)
    print(f"\n{'='*60}")
    print(f"  STAGE: {stage['name']}")
    print(f"  DESC:  {desc}")
    print(f"  CMD:   {' '.join(str(c) for c in cmd)}")
    print(f"{'='*60}")

    if dry_run:
        print("  [DRY RUN] — not executing")
        return True

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(SRC_DIR))
    elapsed = time.time() - t0

    if result.returncode == 0:
        print(f"  ✅ {stage['name']} completed in {elapsed:.1f}s")
        return True
    else:
        msg = f"  ❌ {stage['name']} FAILED (exit code {result.returncode})"
        if is_opt:
            print(f"  ⚠  {stage['name']} FAILED but is optional — continuing.")
            return True
        print(msg)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full PaperScope AI ML pipeline."
    )
    parser.add_argument(
        "--domain", default="ml",
        help="Domain to process (default: ml).",
    )
    parser.add_argument(
        "--from-stage", default="",
        choices=[""] + STAGE_NAMES,
        help="Resume pipeline from this stage (skip earlier stages).",
    )
    parser.add_argument(
        "--to-stage", default="",
        choices=[""] + STAGE_NAMES,
        help="Stop after this stage.",
    )
    parser.add_argument(
        "--only-stage", default="",
        choices=[""] + STAGE_NAMES,
        help="Run only this single stage.",
    )
    parser.add_argument(
        "--skip-collection", action="store_true",
        help="Skip collect_ml and collect_arxiv stages.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run all stages even if outputs already exist.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print commands without executing.",
    )
    args = parser.parse_args()

    domain = args.domain
    print(f"\n🚀 PaperScope AI Pipeline")
    print(f"   Domain:     {domain}")
    print(f"   From stage: {args.from_stage or '(start)'}")
    print(f"   To stage:   {args.to_stage or '(end)'}")
    print(f"   Force:      {args.force}")
    print(f"   Dry run:    {args.dry_run}")

    start_idx = 0
    stop_idx  = len(STAGES)

    if args.only_stage:
        idx = STAGE_NAMES.index(args.only_stage)
        stages_to_run = [STAGES[idx]]
    else:
        if args.from_stage:
            start_idx = STAGE_NAMES.index(args.from_stage)
        if args.to_stage:
            stop_idx = STAGE_NAMES.index(args.to_stage) + 1
        stages_to_run = STAGES[start_idx:stop_idx]

    for stage in stages_to_run:
        name = stage["name"]
        if args.skip_collection and name in ("collect_ml", "collect_arxiv"):
            print(f"  ⏭  Skipping {name} (--skip-collection)")
            continue

        ok = run_stage(stage, domain=domain, dry_run=args.dry_run, force=args.force)
        if not ok:
            print(f"\n❌ Pipeline stopped at stage: {name}")
            print(f"   Fix the error above, then re-run with: --from-stage {name}")
            sys.exit(1)

    print(f"\n🎉 Pipeline completed successfully for domain: {domain}")


if __name__ == "__main__":
    main()
