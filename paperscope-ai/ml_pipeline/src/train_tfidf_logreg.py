from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

from discover_pdf_features import ATTRIBUTE_ORDER
from utils import clean_text, ensure_dir

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v3"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

VECTORIZER_PATH = OUT_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"
COEFFICIENTS_PATH = OUT_DIR / "feature_coefficients.csv"
CONF_MATRIX_PATH = OUT_DIR / "confusion_matrix_test.csv"

# Canonical class set — defined once so every encoder is consistent.
KNOWN_CLASSES = ["NO", "YES"]

TEXT_COLUMN_CANDIDATES = ["train_text_input", "model_text"]
EXPLICIT_FEATURE_COLUMNS = ATTRIBUTE_ORDER


def load_split(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing file: {csv_path}")

    df = pd.read_csv(csv_path)
    required_cols = {"repro_label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path.name} is missing columns: {sorted(missing)}")

    text_col = None
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in df.columns:
            text_col = candidate
            break
    if text_col is None:
        raise ValueError(
            f"{csv_path.name} does not contain any expected text column: {TEXT_COLUMN_CANDIDATES}"
        )

    df = df.copy()
    df[text_col] = df[text_col].fillna("").astype(str).map(clean_text)
    df["repro_label"] = df["repro_label"].fillna("").astype(str)
    df = df[df[text_col].str.len() > 0]
    df = df[df["repro_label"].isin(["YES", "NO"])].copy()

    for col in EXPLICIT_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    if df.empty:
        raise ValueError(f"{csv_path.name} has no usable rows after cleaning.")

    # Store the resolved column name so callers can retrieve it consistently.
    df["text_column_used"] = text_col
    return df.reset_index(drop=True)


def build_matrix(
    vectorizer: TfidfVectorizer,
    texts: list[str],
    explicit_df: pd.DataFrame,
    fit: bool = False,
):
    X_text = vectorizer.fit_transform(texts) if fit else vectorizer.transform(texts)
    X_num = sp.csr_matrix(explicit_df[EXPLICIT_FEATURE_COLUMNS].astype(float).to_numpy())
    return sp.hstack([X_text, X_num], format="csr")


def evaluate_split(
    name: str,
    clf,
    X,
    y_true_labels: list[str],
    label_encoder: LabelEncoder,
):
    y_pred_num = clf.predict(X)
    y_pred = label_encoder.inverse_transform(y_pred_num)

    acc = float(accuracy_score(y_true_labels, y_pred))
    report = classification_report(y_true_labels, y_pred, output_dict=True, zero_division=0)

    print(f"\n{name} accuracy: {acc:.4f}")
    print(classification_report(y_true_labels, y_pred, zero_division=0))

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
    feature_names = list(vectorizer.get_feature_names_out()) + EXPLICIT_FEATURE_COLUMNS
    coef = clf.coef_

    rows = []
    if coef.shape[0] == 1 and len(class_names) == 2:
        negative_class = class_names[0]
        positive_class = class_names[1]
        for feat_idx, feat_name in enumerate(feature_names):
            weight = float(coef[0, feat_idx])
            rows.append({"class_name": negative_class, "feature": feat_name, "coefficient": -weight})
            rows.append({"class_name": positive_class, "feature": feat_name, "coefficient": weight})
    else:
        for class_idx, class_name in enumerate(class_names):
            for feat_idx, feat_name in enumerate(feature_names):
                rows.append(
                    {
                        "class_name": class_name,
                        "feature": feat_name,
                        "coefficient": float(coef[class_idx, feat_idx]),
                    }
                )

    coef_df = pd.DataFrame(rows)
    coef_df["abs_coefficient"] = coef_df["coefficient"].abs()
    coef_df = coef_df.sort_values(
        by=["class_name", "abs_coefficient"], ascending=[True, False]
    ).reset_index(drop=True)
    return coef_df


def main():
    ensure_dir(OUT_DIR)

    train_df = load_split(TRAIN_CSV)
    val_df = load_split(VAL_CSV)
    test_df = load_split(TEST_CSV)

    # -----------------------------------------------------------------------
    # BUG FIX 6 — consistent text column selection
    # -----------------------------------------------------------------------
    # Original code used `val_df[val_df["text_column_used"].iloc[0]]` and
    # `test_df[test_df["text_column_used"].iloc[0]]` for val and test while
    # using the cleaner `text_col = train_df["text_column_used"].iloc[0]`
    # pattern only for train.  The val/test lines were fragile: they accidentally
    # worked only because the stored value string happened to equal a column name.
    # Fix: derive `text_col` once from the train split and reuse it for all three.
    # -----------------------------------------------------------------------
    text_col: str = train_df["text_column_used"].iloc[0]

    X_train_text: list[str] = train_df[text_col].tolist()
    X_val_text: list[str] = val_df[text_col].tolist()   # consistent with train
    X_test_text: list[str] = test_df[text_col].tolist()  # consistent with train

    y_train_labels: list[str] = train_df["repro_label"].tolist()
    y_val_labels: list[str] = val_df["repro_label"].tolist()
    y_test_labels: list[str] = test_df["repro_label"].tolist()

    # -----------------------------------------------------------------------
    # BUG FIX 7 — label encoder: explicit fit on known classes
    # -----------------------------------------------------------------------
    # Original code called `label_encoder.fit_transform(y_train_labels)` and
    # later `label_encoder.fit_transform(y_trainval_labels)`.  The second
    # fit_transform re-fit the encoder, which is harmless when both classes are
    # present in every split (LabelEncoder sorts alphabetically so NO=0, YES=1
    # is stable).  However it introduces a subtle risk: if the train split
    # happens to contain only one class (possible with very small datasets), the
    # initial encoding differs from the final one, making val search metrics
    # inconsistent with the final model.
    #
    # Fix: fit the encoder once on the known class list so it is stable
    # regardless of what labels happen to appear in any individual split.
    # -----------------------------------------------------------------------
    label_encoder = LabelEncoder()
    label_encoder.fit(KNOWN_CLASSES)  # always NO=0, YES=1

    y_train = label_encoder.transform(y_train_labels)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=100_000,
        sublinear_tf=True,
    )

    X_train = build_matrix(vectorizer, X_train_text, train_df, fit=True)
    X_val = build_matrix(vectorizer, X_val_text, val_df, fit=False)
    X_test = build_matrix(vectorizer, X_test_text, test_df, fit=False)

    candidate_configs = [
        {"C": 0.05, "class_weight": None},
        {"C": 0.10, "class_weight": None},
        {"C": 0.30, "class_weight": None},
        {"C": 1.00, "class_weight": None},
        {"C": 3.00, "class_weight": None},
        {"C": 10.0, "class_weight": None},
        {"C": 0.05, "class_weight": "balanced"},
        {"C": 0.10, "class_weight": "balanced"},
        {"C": 0.30, "class_weight": "balanced"},
        {"C": 1.00, "class_weight": "balanced"},
        {"C": 3.00, "class_weight": "balanced"},
        {"C": 10.0, "class_weight": "balanced"},
    ]

    search_results = []
    best: dict | None = None

    for cfg in candidate_configs:
        clf = LogisticRegression(
            C=cfg["C"],
            class_weight=cfg["class_weight"],
            max_iter=5000,
            solver="lbfgs",
            random_state=42,
        )
        clf.fit(X_train, y_train)

        y_val_pred_num = clf.predict(X_val)
        y_val_pred = label_encoder.inverse_transform(y_val_pred_num)
        val_acc = float(accuracy_score(y_val_labels, y_val_pred))
        val_report = classification_report(
            y_val_labels, y_val_pred, output_dict=True, zero_division=0
        )
        val_macro_f1 = float(val_report["macro avg"]["f1-score"])
        val_weighted_f1 = float(val_report["weighted avg"]["f1-score"])

        row = {
            "C": cfg["C"],
            "class_weight": cfg["class_weight"],
            "val_accuracy": val_acc,
            "val_macro_f1": val_macro_f1,
            "val_weighted_f1": val_weighted_f1,
        }
        search_results.append(row)

        if best is None or val_macro_f1 > best["val_macro_f1"] or (
            val_macro_f1 == best["val_macro_f1"] and val_acc > best["val_accuracy"]
        ):
            best = {
                "config": cfg,
                "val_accuracy": val_acc,
                "val_macro_f1": val_macro_f1,
                "val_weighted_f1": val_weighted_f1,
            }

    # Refit best config on the combined train+val set.
    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_trainval_text: list[str] = combined_df[text_col].tolist()
    y_trainval_labels: list[str] = combined_df["repro_label"].tolist()
    # Use .transform() — the encoder was already fit on KNOWN_CLASSES above.
    y_trainval = label_encoder.transform(y_trainval_labels)

    vectorizer_final = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=100_000,
        sublinear_tf=True,
    )
    X_trainval = build_matrix(vectorizer_final, X_trainval_text, combined_df, fit=True)
    X_test_final = build_matrix(vectorizer_final, X_test_text, test_df, fit=False)

    best_clf = LogisticRegression(
        C=best["config"]["C"],
        class_weight=best["config"]["class_weight"],
        max_iter=5000,
        solver="lbfgs",
        random_state=42,
    )
    best_clf.fit(X_trainval, y_trainval)

    final_test_metrics = evaluate_split(
        "Test", best_clf, X_test_final, y_test_labels, label_encoder
    )

    y_test_pred_num = best_clf.predict(X_test_final)
    y_test_pred = label_encoder.inverse_transform(y_test_pred_num)
    cm = confusion_matrix(
        y_test_labels, y_test_pred, labels=label_encoder.classes_
    )
    cm_df = pd.DataFrame(
        cm,
        index=[f"true_{x}" for x in label_encoder.classes_],
        columns=[f"pred_{x}" for x in label_encoder.classes_],
    )
    cm_df.to_csv(CONF_MATRIX_PATH)

    joblib.dump(vectorizer_final, VECTORIZER_PATH)
    joblib.dump(best_clf, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    coef_df = build_coefficients_df(
        best_clf, vectorizer_final, label_encoder.classes_.tolist()
    )
    coef_df.to_csv(COEFFICIENTS_PATH, index=False)

    metadata = {
        "model_name": "tfidf_logreg_auto_v3",
        "vectorizer_type": "TfidfVectorizer",
        "classifier_type": "LogisticRegression",
        "input_text_column": text_col,
        "target_column": "repro_label",
        "feature_engineering": "tfidf_bigrams_plus_transparent_attribute_features_v3",
        "explicit_feature_names": EXPLICIT_FEATURE_COLUMNS,
        "selected_hyperparameters": best["config"],
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "class_names": label_encoder.classes_.tolist(),
        "known_classes": KNOWN_CLASSES,
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = {
        "search_results": search_results,
        "best_validation": best,
        "final_test_metrics": final_test_metrics,
        "artifacts": {
            "vectorizer": str(VECTORIZER_PATH),
            "classifier": str(CLASSIFIER_PATH),
            "label_encoder": str(LABEL_ENCODER_PATH),
            "metadata": str(METADATA_PATH),
            "coefficients": str(COEFFICIENTS_PATH),
            "confusion_matrix_test": str(CONF_MATRIX_PATH),
        },
    }
    TRAIN_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Model saved to: {OUT_DIR}")
    print(f"✅ Train report saved to: {TRAIN_REPORT_PATH}")
    print(f"✅ Metadata saved to: {METADATA_PATH}")


if __name__ == "__main__":
    main()