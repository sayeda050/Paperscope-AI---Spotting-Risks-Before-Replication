"""
evaluate_tfidf_logreg.py — Evaluate the latest trained classifier for a domain.

Reads the test split (data/processed/test.csv) and the latest model for the
specified domain via outputs/models/{domain}/latest.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import clean_text, ensure_dir, read_latest_model_dir, write_json, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR  = SRC_DIR.parent
DATA_DIR      = PIPELINE_DIR / "data" / "processed"
MODELS_BASE   = PIPELINE_DIR / "outputs" / "models"
REPORT_DIR    = PIPELINE_DIR / "outputs" / "reports"
TEST_CSV      = DATA_DIR / "test.csv"

EXPLICIT_FEATURE_COLUMNS = ATTRIBUTE_ORDER
TEXT_COLUMN_CANDIDATES   = ["train_text_input", "model_text"]


def load_test_data(domain_filter: str) -> pd.DataFrame:
    if not TEST_CSV.exists():
        raise FileNotFoundError(
            f"Missing test split: {TEST_CSV}\n"
            "Run build_labeled_dataset_auto.py first."
        )
    df = pd.read_csv(TEST_CSV)
    if "repro_label" not in df.columns:
        raise ValueError("test.csv missing 'repro_label' column.")

    text_col = next((c for c in TEXT_COLUMN_CANDIDATES if c in df.columns), None)
    if text_col is None:
        raise ValueError(f"test.csv: no text column. Expected one of {TEXT_COLUMN_CANDIDATES}")

    df = df.copy()
    df[text_col]       = df[text_col].fillna("").astype(str).map(clean_text)
    df["repro_label"]  = df["repro_label"].fillna("").astype(str)

    if domain_filter and "domain" in df.columns:
        df = df[df["domain"] == domain_filter].copy()

    df = df[df[text_col].str.len() > 0]
    df = df[df["repro_label"].isin(["YES", "NO"])].copy()

    for col in EXPLICIT_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    if df.empty:
        raise ValueError(f"Test set is empty after filtering (domain={domain_filter!r}).")

    df["text_column_used"] = text_col
    return df.reset_index(drop=True)


def get_domain_onehot(df: pd.DataFrame) -> sp.csr_matrix:
    if "domain" not in df.columns:
        return sp.csr_matrix((len(df), 0))
    dummies = pd.get_dummies(df["domain"].fillna("ml").astype(str), prefix="dom")
    for d in SUPPORTED_DOMAINS:
        col = f"dom_{d}"
        if col not in dummies.columns:
            dummies[col] = 0.0
    dummies = dummies.sort_index(axis=1)
    return sp.csr_matrix(dummies.astype(float).to_numpy())


def build_features(
    vectorizer,
    texts: list[str],
    explicit_df: pd.DataFrame,
    domain_matrix: sp.csr_matrix,
) -> sp.csr_matrix:
    X_text = vectorizer.transform(texts)
    X_num  = sp.csr_matrix(explicit_df[EXPLICIT_FEATURE_COLUMNS].astype(float).to_numpy())
    parts  = [X_text, X_num]
    if domain_matrix.shape[1] > 0:
        parts.append(domain_matrix)
    return sp.hstack(parts, format="csr")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate domain classifier on test split.")
    parser.add_argument(
        "--domain", default="all",
        help="Domain model to evaluate (default: all).",
    )
    parser.add_argument(
        "--test-csv", default="",
        help="Override test CSV path.",
    )
    args = parser.parse_args()

    domain_tag    = validate_domain(args.domain) if args.domain not in ("", "all") else "all"
    domain_filter = domain_tag if domain_tag != "all" else ""

    ensure_dir(REPORT_DIR)

    test_path = Path(args.test_csv) if args.test_csv else TEST_CSV
    test_df   = load_test_data(domain_filter)
    text_col  = test_df["text_column_used"].iloc[0]

    # Load model via latest.json
    try:
        model_dir = read_latest_model_dir(MODELS_BASE, domain_tag)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    vectorizer    = joblib.load(model_dir / "vectorizer.joblib")
    clf           = joblib.load(model_dir / "classifier.joblib")
    label_encoder = joblib.load(model_dir / "label_encoder.joblib")
    metadata: dict = {}
    meta_path = model_dir / "metadata.json"
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    X_test_text = test_df[text_col].tolist()
    y_test      = test_df["repro_label"].tolist()
    dom_test    = get_domain_onehot(test_df)

    X_test      = build_features(vectorizer, X_test_text, test_df, dom_test)
    y_pred_num  = clf.predict(X_test)
    y_pred      = label_encoder.inverse_transform(y_pred_num)

    # Calibrated probabilities
    proba_rows: list[dict] = []
    if hasattr(clf, "predict_proba"):
        probas = clf.predict_proba(X_test)
        for i in range(len(y_pred)):
            proba_rows.append({
                label_encoder.classes_[j]: float(probas[i, j])
                for j in range(len(label_encoder.classes_))
            })

    acc         = float(accuracy_score(y_test, y_pred))
    report_text = classification_report(y_test, y_pred, digits=4, zero_division=0)
    report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    labels = list(label_encoder.classes_)
    cm     = confusion_matrix(y_test, y_pred, labels=labels)
    cm_df  = pd.DataFrame(
        cm,
        index=[f"true_{x}"  for x in labels],
        columns=[f"pred_{x}" for x in labels],
    )

    eval_txt_path  = REPORT_DIR / f"evaluation_{domain_tag}.txt"
    conf_mat_path  = REPORT_DIR / f"confusion_matrix_{domain_tag}.csv"
    eval_json_path = REPORT_DIR / f"evaluation_summary_{domain_tag}.json"

    eval_txt_path.write_text(f"Test accuracy: {acc:.4f}\n\n{report_text}", encoding="utf-8")
    cm_df.to_csv(conf_mat_path, index=True)

    # Calibration check: mean predicted probability vs actual positive rate
    calibration_info: dict = {}
    if proba_rows:
        yes_probs = [r.get("YES", 0.0) for r in proba_rows]
        actual    = [1 if y == "YES" else 0 for y in y_test]
        calibration_info = {
            "mean_predicted_yes_prob": float(np.mean(yes_probs)),
            "actual_yes_rate":         float(np.mean(actual)),
            "calibration_gap":         float(abs(np.mean(yes_probs) - np.mean(actual))),
        }

    summary = {
        "schema_version":       PIPELINE_SCHEMA_VERSION,
        "domain":               domain_tag,
        "model_dir":            str(model_dir),
        "calibration":          metadata.get("calibration", "unknown"),
        "test_accuracy":        float(acc),
        "labels":               labels,
        "classification_report": report_dict,
        "test_rows":            int(len(test_df)),
        "calibration_check":    calibration_info,
        "feature_engineering":  metadata.get("feature_engineering", ""),
    }
    write_json(eval_json_path, summary)

    print(f"✅ Evaluation report → {eval_json_path}")
    print(f"✅ Confusion matrix  → {conf_mat_path}")
    print(f"\nTest accuracy ({domain_tag}): {round(acc, 4)}")
    print(report_text)
    if calibration_info:
        gap = calibration_info["calibration_gap"]
        quality = "✅ Good" if gap < 0.05 else ("⚠ Moderate" if gap < 0.10 else "❌ Poor")
        print(f"Calibration gap: {gap:.4f}  {quality}")


if __name__ == "__main__":
    main()
