
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, mean_absolute_error

from discover_pdf_features import ATTRIBUTE_ORDER

BASE_DIR = Path(__file__).resolve().parent.parent
GOLD_CSV = BASE_DIR / "data" / "gold_eval" / "gold_eval_labeled.csv"
OUT_DIR = BASE_DIR / "data" / "gold_eval"
REPORT_JSON = OUT_DIR / "gold_eval_report.json"
CONFUSION_CSV = OUT_DIR / "gold_eval_confusion_matrix.csv"
ATTRIBUTE_ACCURACY_CSV = OUT_DIR / "gold_eval_attribute_accuracy.csv"

LABEL_ORDER = ["LOW", "MEDIUM", "HIGH"]


def normalize_label(value: str) -> str:
    value = str(value or "").strip().upper()
    mapping = {
        "LOW": "LOW",
        "MEDIUM": "MEDIUM",
        "MED": "MEDIUM",
        "HIGH": "HIGH",
        "LOW RISK": "LOW",
        "MEDIUM RISK": "MEDIUM",
        "HIGH RISK": "HIGH",
    }
    return mapping.get(value, value)


def normalize_state(value: str) -> str:
    value = str(value or "").strip().upper()
    mapping = {
        "YES": "SUPPORTED",
        "SUPPORTED": "SUPPORTED",
        "PARTIAL": "PARTIAL",
        "NO": "NOT_FOUND",
        "NOT_FOUND": "NOT_FOUND",
        "MISSING": "NOT_FOUND",
    }
    return mapping.get(value, value)


def main() -> None:
    if not GOLD_CSV.exists():
        raise FileNotFoundError(f"Missing file: {GOLD_CSV}")

    df = pd.read_csv(GOLD_CSV)
    required = {"gold_risk_label", "pred_risk_label", "gold_risk_score", "pred_risk_score"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    work = df.copy()
    work["gold_risk_label"] = work["gold_risk_label"].map(normalize_label)
    work["pred_risk_label"] = work["pred_risk_label"].map(normalize_label)
    work = work[
        work["gold_risk_label"].isin(LABEL_ORDER)
        & work["pred_risk_label"].isin(LABEL_ORDER)
    ].copy()

    if work.empty:
        raise ValueError("No usable labeled rows were found.")

    y_true = work["gold_risk_label"].tolist()
    y_pred = work["pred_risk_label"].tolist()

    score_mask = work["gold_risk_score"].notna() & work["pred_risk_score"].notna()
    mae = None
    if score_mask.any():
        mae = float(
            mean_absolute_error(
                work.loc[score_mask, "gold_risk_score"].astype(float),
                work.loc[score_mask, "pred_risk_score"].astype(float),
            )
        )

    acc = float(accuracy_score(y_true, y_pred))
    report = classification_report(y_true, y_pred, labels=LABEL_ORDER, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)
    cm_df = pd.DataFrame(cm, index=[f"true_{x}" for x in LABEL_ORDER], columns=[f"pred_{x}" for x in LABEL_ORDER])
    cm_df.to_csv(CONFUSION_CSV, index=True)

    attr_rows = []
    for attr in ATTRIBUTE_ORDER:
        gold_col = f"gold_{attr}"
        pred_col = f"pred_{attr}"
        if gold_col not in work.columns or pred_col not in work.columns:
            continue
        attr_df = work[[gold_col, pred_col]].copy()
        attr_df[gold_col] = attr_df[gold_col].map(normalize_state)
        attr_df[pred_col] = attr_df[pred_col].map(normalize_state)
        attr_df = attr_df[
            attr_df[gold_col].isin(["SUPPORTED", "PARTIAL", "NOT_FOUND"])
            & attr_df[pred_col].isin(["SUPPORTED", "PARTIAL", "NOT_FOUND"])
        ].copy()
        if attr_df.empty:
            continue
        attr_acc = float((attr_df[gold_col] == attr_df[pred_col]).mean())
        false_positive_rate = float(((attr_df[gold_col] == "NOT_FOUND") & (attr_df[pred_col] == "SUPPORTED")).mean())
        attr_rows.append(
            {
                "attribute": attr,
                "rows_used": int(len(attr_df)),
                "accuracy": attr_acc,
                "false_positive_rate": false_positive_rate,
            }
        )

    attr_df = pd.DataFrame(attr_rows)
    attr_df.to_csv(ATTRIBUTE_ACCURACY_CSV, index=False)

    summary = {
        "rows_used": int(len(work)),
        "label_accuracy": acc,
        "score_mae": mae,
        "classification_report": report,
        "attribute_accuracy_mean": float(attr_df["accuracy"].mean()) if not attr_df.empty else None,
        "attribute_false_positive_rate_mean": float(attr_df["false_positive_rate"].mean()) if not attr_df.empty else None,
        "confusion_matrix_path": str(CONFUSION_CSV),
        "attribute_accuracy_csv": str(ATTRIBUTE_ACCURACY_CSV),
    }

    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
