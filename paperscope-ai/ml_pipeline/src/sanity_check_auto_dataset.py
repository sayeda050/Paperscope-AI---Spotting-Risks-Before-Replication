"""
sanity_check_auto_dataset.py — Comprehensive dataset sanity checker.

Validates labeled_dataset.csv and split files.
Raises RuntimeError on critical issues so run_pipeline.py stops cleanly.

Fixed vs. original:
  - Removed nonexistent "auto_score" / "weak_score" columns (crashed every run).
  - Correctly checks "reproducibility_score" and "risk_score".
  - Validates domain distribution across splits.
  - Checks leakage guard is active.
  - Validates split file row counts and class balance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
DATA_DIR     = PIPELINE_DIR / "data" / "processed"
DATA_FILE    = DATA_DIR / "labeled_dataset.csv"
TRAIN_FILE   = DATA_DIR / "train.csv"
VAL_FILE     = DATA_DIR / "val.csv"
TEST_FILE    = DATA_DIR / "test.csv"
OUT_FILE     = PIPELINE_DIR / "outputs" / "reports" / "dataset_sanity_check.json"


def count_nonempty(series: pd.Series) -> int:
    return int(series.fillna("").astype(str).str.strip().ne("").sum())


def get_constant_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if df[col].nunique(dropna=False) == 1]


def check_split(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "rows": 0, "label_counts": {}, "has_both_classes": False}
    try:
        df = pd.read_csv(path)
        lc: dict = {}
        if "repro_label" in df.columns:
            lc = {str(k): int(v) for k, v in df["repro_label"].value_counts(dropna=False).items()}
        dom: dict = {}
        if "domain" in df.columns:
            dom = {str(k): int(v) for k, v in df["domain"].value_counts(dropna=False).items()}
        return {
            "exists":          True,
            "rows":            int(len(df)),
            "label_counts":    lc,
            "has_both_classes": {"YES", "NO"}.issubset(lc.keys()),
            "domain_counts":   dom,
            "has_model_text":       "model_text" in df.columns,
            "has_train_text_input": "train_text_input" in df.columns,
        }
    except Exception as exc:
        return {"exists": True, "rows": 0, "error": str(exc)}


def main() -> None:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Missing: {DATA_FILE}\n"
            "Run build_labeled_dataset_auto.py first."
        )

    df = pd.read_csv(DATA_FILE)

    # ── Required columns ────────────────────────────────────────────────────
    required = {
        "paper_uid", "model_text", "train_text_input",
        "repro_label", "label_source", "label_confidence",
        "reproducibility_score",   # not "auto_score" — fixed
        "risk_score",
    }
    missing_required = sorted(required - set(df.columns))

    # ── Label distribution ───────────────────────────────────────────────────
    label_counts: dict = {}
    if "repro_label" in df.columns:
        label_counts = {
            str(k): int(v)
            for k, v in df["repro_label"].value_counts(dropna=False).items()
        }
    both_classes = {"YES", "NO"}.issubset(label_counts.keys())

    # ── Domain distribution ──────────────────────────────────────────────────
    domain_counts: dict = {}
    if "domain" in df.columns:
        domain_counts = {
            str(k): int(v)
            for k, v in df["domain"].value_counts(dropna=False).items()
        }

    # ── Score stats ──────────────────────────────────────────────────────────
    score_stats: dict = {}
    for col in ("reproducibility_score", "risk_score"):
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            score_stats[col] = {
                "min": float(s.min()),
                "max": float(s.max()),
                "mean": float(s.mean()),
                "out_of_range_count": int(((s < 0) | (s > 100)).sum()),
            }

    # ── Leakage audit ────────────────────────────────────────────────────────
    leakage_cols = [c for c in ["review_text", "decision_text"] if c in df.columns]
    training_locked = False
    if "training_text_source" in df.columns:
        sources = df["training_text_source"].dropna().unique().tolist()
        training_locked = all(s == "model_text_only" for s in sources)

    # ── Schema version check ─────────────────────────────────────────────────
    schema_ok = False
    if "schema_version" in df.columns:
        versions = df["schema_version"].dropna().unique().tolist()
        schema_ok = all(v == PIPELINE_SCHEMA_VERSION for v in versions)

    # ── Reserved UID check ───────────────────────────────────────────────────
    reserved_path = PIPELINE_DIR / "data" / "gold_eval" / "reserved_uids.txt"
    reserved_overlap = 0
    if reserved_path.exists() and "paper_uid" in df.columns:
        reserved = {
            line.strip()
            for line in reserved_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        reserved_overlap = int(df["paper_uid"].isin(reserved).sum())

    # ── Split checks ─────────────────────────────────────────────────────────
    splits = {
        "train": check_split(TRAIN_FILE),
        "val":   check_split(VAL_FILE),
        "test":  check_split(TEST_FILE),
    }

    report = {
        "schema_version":           PIPELINE_SCHEMA_VERSION,
        "rows":                     int(len(df)),
        "columns":                  int(df.shape[1]),
        "missing_required_columns": missing_required,
        "both_classes_present":     both_classes,
        "label_counts":             label_counts,
        "domain_counts":            domain_counts,
        "label_source_counts": (
            {str(k): int(v) for k, v in df["label_source"].value_counts(dropna=False).items()}
            if "label_source" in df.columns else {}
        ),
        "model_text_nonempty":      (count_nonempty(df["model_text"])  if "model_text"  in df.columns else 0),
        "train_text_nonempty":      (count_nonempty(df["train_text_input"]) if "train_text_input" in df.columns else 0),
        "duplicate_paper_uid":      (int(df["paper_uid"].duplicated().sum()) if "paper_uid" in df.columns else None),
        "constant_columns":         get_constant_columns(df),
        "score_stats":              score_stats,
        "leakage_audit": {
            "audit_columns_present":        leakage_cols,
            "training_text_source_locked":  training_locked,
        },
        "schema_check": {
            "expected_version": PIPELINE_SCHEMA_VERSION,
            "schema_ok":        schema_ok,
        },
        "reserved_uid_overlap":     reserved_overlap,
        "split_files":              splits,
    }

    ensure_dir(OUT_FILE.parent)
    OUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\n✅ Sanity check report → {OUT_FILE}")

    # ── Critical issues ───────────────────────────────────────────────────────
    critical: list[str] = []
    if missing_required:
        critical.append(f"Missing required columns: {missing_required}")
    if not both_classes:
        critical.append(f"Not both classes present: {label_counts}")
    if report["duplicate_paper_uid"]:
        critical.append(f"{report['duplicate_paper_uid']} duplicate paper_uid rows")
    for col, stats in score_stats.items():
        if stats["out_of_range_count"] > 0:
            critical.append(f"{col} has {stats['out_of_range_count']} rows outside [0, 100]")
    if not training_locked:
        critical.append("training_text_source is NOT locked to 'model_text_only' — potential leakage!")
    if reserved_overlap > 0:
        critical.append(
            f"{reserved_overlap} reserved gold-eval UIDs found in training data — test contamination!"
        )
    for split_name, split_info in splits.items():
        if not split_info.get("exists"):
            critical.append(f"Split file missing: {split_name}.csv")
        elif not split_info.get("has_both_classes"):
            critical.append(f"Split {split_name!r} missing a class: {split_info.get('label_counts')}")

    if critical:
        print("\n⚠  CRITICAL ISSUES:")
        for issue in critical:
            print(f"  ❌ {issue}")
        raise RuntimeError(
            f"Sanity check failed with {len(critical)} critical issue(s). See above."
        )

    print("\n✅ All critical checks passed.")


if __name__ == "__main__":
    main()
