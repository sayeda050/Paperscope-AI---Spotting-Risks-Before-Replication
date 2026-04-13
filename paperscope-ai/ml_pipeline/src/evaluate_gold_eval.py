"""
evaluate_gold_eval.py — Evaluate rubric predictions against manually labeled gold papers.

Reads: data/gold_eval/gold_eval_labeled.csv (gold_eval_template.csv filled in)
Writes: data/gold_eval/gold_eval_report.json
        data/gold_eval/gold_eval_confusion_matrix.csv
        data/gold_eval/gold_eval_attribute_accuracy.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
)

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS
from utils import ensure_dir, PIPELINE_SCHEMA_VERSION

BASE_DIR      = SRC_DIR.parent
GOLD_CSV      = BASE_DIR / "data" / "gold_eval" / "gold_eval_labeled.csv"
OUT_DIR       = BASE_DIR / "data" / "gold_eval"
REPORT_JSON   = OUT_DIR / "gold_eval_report.json"
CONFUSION_CSV = OUT_DIR / "gold_eval_confusion_matrix.csv"
ATTR_ACC_CSV  = OUT_DIR / "gold_eval_attribute_accuracy.csv"

LABEL_ORDER = ["LOW", "MEDIUM", "HIGH"]


def normalize_label(value: str) -> str:
    v = str(value or "").strip().upper()
    mapping = {
        "LOW": "LOW", "MEDIUM": "MEDIUM", "MED": "MEDIUM", "HIGH": "HIGH",
        "LOW RISK": "LOW", "MEDIUM RISK": "MEDIUM", "HIGH RISK": "HIGH",
    }
    return mapping.get(v, v)


def normalize_state(value: str) -> str:
    v = str(value or "").strip().upper()
    mapping = {
        "YES": "SUPPORTED", "SUPPORTED": "SUPPORTED",
        "PARTIAL": "PARTIAL",
        "NO": "NOT_FOUND", "NOT_FOUND": "NOT_FOUND", "MISSING": "NOT_FOUND",
    }
    return mapping.get(v, v)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate rubric vs gold labels.")
    parser.add_argument(
        "--gold-csv", default="",
        help=f"Override gold CSV path (default: {GOLD_CSV}).",
    )
    parser.add_argument(
        "--domain", default="",
        help="Filter evaluation to a specific domain.",
    )
    args = parser.parse_args()

    gold_path = Path(args.gold_csv) if args.gold_csv else GOLD_CSV
    if not gold_path.exists():
        raise FileNotFoundError(
            f"Missing gold evaluation file: {gold_path}\n"
            "Run build_gold_eval_template.py and fill in the gold_* columns."
        )

    df = pd.read_csv(gold_path)
    required = {"gold_risk_label", "prefill_risk_label", "gold_risk_score", "prefill_risk_score"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}\n"
            "Make sure gold_eval_labeled.csv has both gold_* and prefill_* columns filled."
        )

    if args.domain and "domain" in df.columns:
        df = df[df["domain"] == args.domain].copy()
        print(f"Filtered to domain {args.domain!r}: {len(df)} rows")

    work = df.copy()
    work["gold_risk_label"]    = work["gold_risk_label"].map(normalize_label)
    work["prefill_risk_label"] = work["prefill_risk_label"].map(normalize_label)
    work = work[
        work["gold_risk_label"].isin(LABEL_ORDER)
        & work["prefill_risk_label"].isin(LABEL_ORDER)
    ].copy()

    if work.empty:
        raise ValueError("No usable labeled rows found. Fill in gold_risk_label and prefill_risk_label.")

    y_true = work["gold_risk_label"].tolist()
    y_pred = work["prefill_risk_label"].tolist()

    # MAE on continuous scores
    score_mask = work["gold_risk_score"].notna() & work["prefill_risk_score"].notna()
    mae = None
    if score_mask.any():
        mae = float(
            mean_absolute_error(
                work.loc[score_mask, "gold_risk_score"].astype(float),
                work.loc[score_mask, "prefill_risk_score"].astype(float),
            )
        )

    acc         = float(accuracy_score(y_true, y_pred))
    report_dict = classification_report(
        y_true, y_pred, labels=LABEL_ORDER, output_dict=True, zero_division=0
    )

    # Confusion matrix
    cm    = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)
    cm_df = pd.DataFrame(
        cm,
        index=[f"true_{x}"  for x in LABEL_ORDER],
        columns=[f"pred_{x}" for x in LABEL_ORDER],
    )
    ensure_dir(OUT_DIR)
    cm_df.to_csv(CONFUSION_CSV, index=True)

    # Per-attribute accuracy
    attr_rows: list[dict] = []
    for attr in ATTRIBUTE_ORDER:
        gold_col   = f"gold_{attr}"
        prefill_col = f"prefill_{attr}"
        if gold_col not in work.columns or prefill_col not in work.columns:
            continue
        attr_df = work[[gold_col, prefill_col]].copy()
        attr_df[gold_col]    = attr_df[gold_col].map(normalize_state)
        attr_df[prefill_col] = attr_df[prefill_col].map(normalize_state)
        valid = attr_df[
            attr_df[gold_col].isin(["SUPPORTED", "PARTIAL", "NOT_FOUND"])
            & attr_df[prefill_col].isin(["SUPPORTED", "PARTIAL", "NOT_FOUND"])
        ].copy()
        if valid.empty:
            continue
        attr_acc = float((valid[gold_col] == valid[prefill_col]).mean())
        fp_rate  = float(
            ((valid[gold_col] == "NOT_FOUND") & (valid[prefill_col] == "SUPPORTED")).mean()
        )
        attr_rows.append({
            "attribute":           attr,
            "rows_used":           int(len(valid)),
            "accuracy":            attr_acc,
            "false_positive_rate": fp_rate,
        })

    attr_df_out = pd.DataFrame(attr_rows)
    attr_df_out.to_csv(ATTR_ACC_CSV, index=False)

    # Per-domain breakdown if domain column available
    domain_breakdown: dict = {}
    if "domain" in work.columns:
        for dom, grp in work.groupby("domain"):
            dy = grp["gold_risk_label"].tolist()
            dp = grp["prefill_risk_label"].tolist()
            domain_breakdown[str(dom)] = {
                "rows": int(len(grp)),
                "accuracy": float(accuracy_score(dy, dp)),
            }

    summary = {
        "schema_version":                   PIPELINE_SCHEMA_VERSION,
        "rows_used":                        int(len(work)),
        "domain_filter":                    args.domain or "all",
        "label_accuracy":                   acc,
        "score_mae":                        mae,
        "classification_report":            report_dict,
        "attribute_accuracy_mean":          float(attr_df_out["accuracy"].mean()) if not attr_df_out.empty else None,
        "attribute_false_positive_rate_mean": float(attr_df_out["false_positive_rate"].mean()) if not attr_df_out.empty else None,
        "domain_breakdown":                 domain_breakdown,
        "confusion_matrix_path":            str(CONFUSION_CSV),
        "attribute_accuracy_csv":           str(ATTR_ACC_CSV),
    }

    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\n✅ Report               → {REPORT_JSON}")
    print(f"✅ Confusion matrix     → {CONFUSION_CSV}")
    print(f"✅ Attribute accuracy   → {ATTR_ACC_CSV}")


if __name__ == "__main__":
    main()
