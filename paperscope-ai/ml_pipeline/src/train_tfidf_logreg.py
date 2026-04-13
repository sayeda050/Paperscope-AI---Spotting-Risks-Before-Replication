"""
train_tfidf_logreg.py — Domain-aware TF-IDF + Logistic Regression trainer.

Key upgrades:
  - Per-domain training (--domain flag)
  - Model versioning: outputs/models/{domain}/{run_id}/
  - Calibrated probabilities via Platt scaling (CalibratedClassifierCV)
  - Stable label encoding (NO=0, YES=1 always)
  - Domain one-hot feature injected into explicit feature matrix
  - latest.json pointer updated after every successful run
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_text,
    ensure_dir,
    get_run_id,
    write_json,
    write_latest_pointer,
)

PIPELINE_DIR = SRC_DIR.parent
DATA_DIR = PIPELINE_DIR / "data" / "processed"
MODELS_BASE = PIPELINE_DIR / "outputs" / "models"

KNOWN_CLASSES = ["NO", "YES"]
TEXT_COLUMN_CANDIDATES = ["train_text_input", "model_text"]
EXPLICIT_FEATURE_COLUMNS = ATTRIBUTE_ORDER


def load_split(csv_path: Path, domain_filter: str = "") -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing split file: {csv_path}")

    df = pd.read_csv(csv_path)
    if "repro_label" not in df.columns:
        raise ValueError(f"{csv_path.name}: missing 'repro_label' column.")

    # Domain filter
    if domain_filter and "domain" in df.columns:
        df = df[df["domain"] == domain_filter].copy()

    text_col = next((c for c in TEXT_COLUMN_CANDIDATES if c in df.columns), None)
    if text_col is None:
        raise ValueError(
            f"{csv_path.name}: no text column found. Expected one of {TEXT_COLUMN_CANDIDATES}"
        )

    df = df.copy()
    df[text_col] = df[text_col].fillna("").astype(str).map(clean_text)
    df["repro_label"] = df["repro_label"].fillna("").astype(str)
    df = df[df[text_col].str.len() > 0]
    df = df[df["repro_label"].isin(KNOWN_CLASSES)].copy()

    for col in EXPLICIT_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    if df.empty:
        raise ValueError(f"{csv_path.name}: no usable rows after filtering (domain={domain_filter!r}).")

    df["text_column_used"] = text_col
    return df.reset_index(drop=True)


def get_domain_onehot(df: pd.DataFrame) -> sp.csr_matrix:
    """Encode domain as one-hot sparse columns."""
    if "domain" not in df.columns:
        return sp.csr_matrix((len(df), 0))
    dummies = pd.get_dummies(df["domain"].fillna("ml").astype(str), prefix="dom")
    # Ensure consistent columns across splits
    for dom in SUPPORTED_DOMAINS:
        col = f"dom_{dom}"
        if col not in dummies.columns:
            dummies[col] = 0.0
    dummies = dummies.sort_index(axis=1)
    return sp.csr_matrix(dummies.astype(float).to_numpy())


def build_matrix(
    vectorizer: TfidfVectorizer,
    texts: list[str],
    explicit_df: pd.DataFrame,
    domain_matrix: sp.csr_matrix,
    fit: bool = False,
) -> sp.csr_matrix:
    X_text = vectorizer.fit_transform(texts) if fit else vectorizer.transform(texts)
    X_num = sp.csr_matrix(explicit_df[EXPLICIT_FEATURE_COLUMNS].astype(float).to_numpy())
    parts = [X_text, X_num]
    if domain_matrix.shape[1] > 0:
        parts.append(domain_matrix)
    return sp.hstack(parts, format="csr")


def evaluate_split(
    name: str,
    clf,
    X: sp.csr_matrix,
    y_true: list[str],
    le: LabelEncoder,
) -> dict:
    y_pred_num = clf.predict(X)
    y_pred = le.inverse_transform(y_pred_num)
    acc = float(accuracy_score(y_true, y_pred))
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    print(f"\n{name} accuracy: {acc:.4f}")
    print(classification_report(y_true, y_pred, zero_division=0))
    return {
        "accuracy": acc,
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        "classification_report": report,
    }


def build_coefficients_df(
    clf,
    vectorizer: TfidfVectorizer,
    class_names: list[str],
) -> pd.DataFrame:
    feature_names = (
        list(vectorizer.get_feature_names_out())
        + EXPLICIT_FEATURE_COLUMNS
        + [f"dom_{d}" for d in SUPPORTED_DOMAINS]
    )
    # For CalibratedClassifierCV, get the underlying estimator
    base_clf = getattr(clf, "estimator", clf)
    if not hasattr(base_clf, "coef_"):
        return pd.DataFrame()
    coef = base_clf.coef_
    rows = []
    if coef.shape[0] == 1 and len(class_names) == 2:
        for fi, fn in enumerate(feature_names):
            if fi >= coef.shape[1]:
                break
            w = float(coef[0, fi])
            rows.append({"class_name": class_names[0], "feature": fn, "coefficient": -w})
            rows.append({"class_name": class_names[1], "feature": fn, "coefficient": w})
    else:
        for ci, cn in enumerate(class_names):
            for fi, fn in enumerate(feature_names):
                if fi >= coef.shape[1]:
                    break
                rows.append({"class_name": cn, "feature": fn, "coefficient": float(coef[ci, fi])})
    coef_df = pd.DataFrame(rows)
    coef_df["abs_coefficient"] = coef_df["coefficient"].abs()
    return coef_df.sort_values(["class_name", "abs_coefficient"], ascending=[True, False]).reset_index(drop=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Train domain-aware TF-IDF + Logistic Regression classifier.")
    parser.add_argument(
        "--domain", default="",
        help="Train on a specific domain only (default: all domains combined).",
    )
    parser.add_argument(
        "--train-csv", default="", help="Override train split CSV path."
    )
    parser.add_argument(
        "--val-csv", default="", help="Override val split CSV path."
    )
    parser.add_argument(
        "--test-csv", default="", help="Override test split CSV path."
    )
    args = parser.parse_args()

    domain_tag = validate_domain(args.domain) if args.domain else "all"
    domain_filter = domain_tag if domain_tag != "all" else ""
    run_id = get_run_id()
    out_dir = MODELS_BASE / domain_tag / run_id
    ensure_dir(out_dir)

    train_path = Path(args.train_csv) if args.train_csv else DATA_DIR / "train.csv"
    val_path   = Path(args.val_csv)   if args.val_csv   else DATA_DIR / "val.csv"
    test_path  = Path(args.test_csv)  if args.test_csv  else DATA_DIR / "test.csv"

    train_df = load_split(train_path, domain_filter)
    val_df   = load_split(val_path,   domain_filter)
    test_df  = load_split(test_path,  domain_filter)

    text_col: str = train_df["text_column_used"].iloc[0]
    X_train_text = train_df[text_col].tolist()
    X_val_text   = val_df[text_col].tolist()
    X_test_text  = test_df[text_col].tolist()

    y_train = train_df["repro_label"].tolist()
    y_val   = val_df["repro_label"].tolist()
    y_test  = test_df["repro_label"].tolist()

    # Stable label encoder: NO=0, YES=1
    label_encoder = LabelEncoder()
    label_encoder.fit(KNOWN_CLASSES)
    y_train_enc = label_encoder.transform(y_train)
    y_val_enc   = label_encoder.transform(y_val)

    # Domain one-hot features
    dom_train = get_domain_onehot(train_df)
    dom_val   = get_domain_onehot(val_df)
    dom_test  = get_domain_onehot(test_df)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=100_000,
        sublinear_tf=True,
    )

    X_train = build_matrix(vectorizer, X_train_text, train_df, dom_train, fit=True)
    X_val   = build_matrix(vectorizer, X_val_text,   val_df,   dom_val,   fit=False)
    X_test  = build_matrix(vectorizer, X_test_text,  test_df,  dom_test,  fit=False)

    candidate_configs = [
        {"C": c, "class_weight": cw}
        for c in [0.05, 0.10, 0.30, 1.00, 3.00, 10.0]
        for cw in [None, "balanced"]
    ]

    search_results = []
    best: dict | None = None

    for cfg in candidate_configs:
        base_clf = LogisticRegression(
            C=cfg["C"],
            class_weight=cfg["class_weight"],
            max_iter=5000,
            solver="lbfgs",
            random_state=42,
        )
        base_clf.fit(X_train, y_train_enc)
        y_pred_num = base_clf.predict(X_val)
        y_pred = label_encoder.inverse_transform(y_pred_num)
        val_acc = float(accuracy_score(y_val, y_pred))
        val_report = classification_report(y_val, y_pred, output_dict=True, zero_division=0)
        val_macro_f1 = float(val_report["macro avg"]["f1-score"])
        val_weighted_f1 = float(val_report["weighted avg"]["f1-score"])

        row = {
            "C": cfg["C"],
            "class_weight": str(cfg["class_weight"]),
            "val_accuracy": val_acc,
            "val_macro_f1": val_macro_f1,
            "val_weighted_f1": val_weighted_f1,
        }
        search_results.append(row)
        if best is None or val_macro_f1 > best["val_macro_f1"]:
            best = {
                "config": cfg,
                "val_accuracy": val_acc,
                "val_macro_f1": val_macro_f1,
                "val_weighted_f1": val_weighted_f1,
            }

    # Refit on train+val
    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_tv_text = combined_df[text_col].tolist()
    y_tv = combined_df["repro_label"].tolist()
    y_tv_enc = label_encoder.transform(y_tv)
    dom_tv = get_domain_onehot(combined_df)

    vectorizer_final = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=100_000,
        sublinear_tf=True,
    )
    X_tv = build_matrix(vectorizer_final, X_tv_text, combined_df, dom_tv, fit=True)
    X_test_final = build_matrix(vectorizer_final, X_test_text, test_df, dom_test, fit=False)

    best_base = LogisticRegression(
        C=best["config"]["C"],
        class_weight=best["config"]["class_weight"],
        max_iter=5000,
        solver="lbfgs",
        random_state=42,
    )
    best_base.fit(X_tv, y_tv_enc)

    # ── Platt scaling calibration (Gap 6 fix) ────────────────────────────────
    # Refit X_val for calibration using the final vectorizer
    X_val_final = build_matrix(vectorizer_final, X_val_text, val_df, dom_val, fit=False)

    # SCIKIT-LEARN 1.6+ COMPATIBILITY PATCH
    # FrozenEstimator tells sklearn the model is pre-fitted — do NOT clone/retrain it.
    # Without this, cv=5 default would discard best_base and retrain on ~70 val rows.
    try:
        from sklearn.frozen import FrozenEstimator
        calibrated_clf = CalibratedClassifierCV(FrozenEstimator(best_base), method="isotonic")
    except ImportError:
        # Fallback for scikit-learn <= 1.5
        calibrated_clf = CalibratedClassifierCV(best_base, cv="prefit", method="isotonic")

    calibrated_clf.fit(X_val_final, y_val_enc)
    # ─────────────────────────────────────────────────────────────────────────

    final_test_metrics = evaluate_split("Test", calibrated_clf, X_test_final, y_test, label_encoder)

    y_test_pred_num = calibrated_clf.predict(X_test_final)
    y_test_pred = label_encoder.inverse_transform(y_test_pred_num)
    cm = confusion_matrix(y_test, y_test_pred, labels=label_encoder.classes_)
    cm_df = pd.DataFrame(
        cm,
        index=[f"true_{x}" for x in label_encoder.classes_],
        columns=[f"pred_{x}" for x in label_encoder.classes_],
    )

    # Save artifacts
    vectorizer_path     = out_dir / "vectorizer.joblib"
    classifier_path     = out_dir / "classifier.joblib"
    label_encoder_path  = out_dir / "label_encoder.joblib"
    metadata_path       = out_dir / "metadata.json"
    train_report_path   = out_dir / "train_report.json"
    coefficients_path   = out_dir / "feature_coefficients.csv"
    conf_matrix_path    = out_dir / "confusion_matrix_test.csv"

    joblib.dump(vectorizer_final, vectorizer_path)
    joblib.dump(calibrated_clf,   classifier_path)
    joblib.dump(label_encoder,    label_encoder_path)
    cm_df.to_csv(conf_matrix_path)

    coef_df = build_coefficients_df(best_base, vectorizer_final, label_encoder.classes_.tolist())
    if not coef_df.empty:
        coef_df.to_csv(coefficients_path, index=False)

    metadata = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "run_id": run_id,
        "domain": domain_tag,
        "model_name": f"tfidf_logreg_{domain_tag}_{run_id}",
        "vectorizer_type": "TfidfVectorizer",
        "classifier_type": "LogisticRegression+IsotonicCalibration",
        "input_text_column": text_col,
        "target_column": "repro_label",
        "feature_engineering": "tfidf_bigrams_plus_attribute_features_plus_domain_onehot_v3",
        "explicit_feature_names": EXPLICIT_FEATURE_COLUMNS,
        "domain_onehot_features": [f"dom_{d}" for d in SUPPORTED_DOMAINS],
        "selected_hyperparameters": {
            "C": best["config"]["C"],
            "class_weight": str(best["config"]["class_weight"]),
        },
        "calibration": "isotonic",
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "class_names": label_encoder.classes_.tolist(),
        "known_classes": KNOWN_CLASSES,
    }
    write_json(metadata_path, metadata)

    report = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "run_id": run_id,
        "domain": domain_tag,
        "search_results": search_results,
        "best_validation": best,
        "final_test_metrics": final_test_metrics,
        "artifacts": {
            "vectorizer": str(vectorizer_path),
            "classifier": str(classifier_path),
            "label_encoder": str(label_encoder_path),
            "metadata": str(metadata_path),
            "coefficients": str(coefficients_path),
            "confusion_matrix_test": str(conf_matrix_path),
        },
    }
    write_json(train_report_path, report)

    # Update latest.json pointer
    write_latest_pointer(MODELS_BASE, domain_tag, run_id, out_dir)

    print(f"\n✅ Model saved to: {out_dir}")
    print(f"✅ Train report  → {train_report_path}")
    print(f"✅ latest.json   → {MODELS_BASE / domain_tag / 'latest.json'}")
    print(f"   Calibration: isotonic (Platt scaling). Raw probabilities are now statistically meaningful.")


if __name__ == "__main__":
    main()
