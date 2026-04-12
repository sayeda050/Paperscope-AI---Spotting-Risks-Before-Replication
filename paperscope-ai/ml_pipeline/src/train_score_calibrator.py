
from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

from discover_pdf_features import ATTRIBUTE_ORDER, extract_feature_record
from utils import clean_text, ensure_dir, risk_label_from_score

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "processed" / "gold_score_dataset.csv"
DEFAULT_MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v3"


SCORE_FEATURE_COLUMNS = (
    ATTRIBUTE_ORDER
    + [
        "supported_count",
        "partial_count",
        "missing_count",
        "classifier_prob_yes",
        "classifier_prob_no",
        "model_text_chars",
        "page_count",
    ]
)


def load_gold_dataset(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Gold score dataset not found: {path}")

    df = pd.read_csv(path)
    required = {"title", "abstract", "model_text", "target_score"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Gold score dataset is missing columns: {sorted(missing)}")

    df = df.copy()
    df["title"] = df["title"].fillna("").astype(str).map(clean_text)
    df["abstract"] = df["abstract"].fillna("").astype(str).map(clean_text)
    df["model_text"] = df["model_text"].fillna("").astype(str)
    df["target_score"] = pd.to_numeric(df["target_score"], errors="coerce")
    if "page_count" not in df.columns:
        df["page_count"] = 0
    df["page_count"] = pd.to_numeric(df["page_count"], errors="coerce").fillna(0).astype(int)
    df = df[df["target_score"].notna()].copy()
    df = df[(df["target_score"] >= 0.0) & (df["target_score"] <= 100.0)].copy()
    df = df[df["model_text"].str.len() > 0].copy()

    if len(df) < 60:
        raise RuntimeError("Too few labeled rows. Label at least 60 papers before training the score calibrator.")
    return df.reset_index(drop=True)


def build_classifier_matrix(vectorizer, texts: list[str], explicit_feature_df: pd.DataFrame):
    X_text = vectorizer.transform(texts)
    X_num = sp.csr_matrix(explicit_feature_df[ATTRIBUTE_ORDER].astype(float).to_numpy())
    return sp.hstack([X_text, X_num], format="csr")


def safe_predict_proba(classifier, X, label_encoder):
    try:
        if hasattr(classifier, "predict_proba"):
            proba = classifier.predict_proba(X)[0]
            classes = label_encoder.classes_.tolist()
            return {classes[i]: float(proba[i]) for i in range(len(classes))}
    except Exception:
        pass
    return {}


def build_score_feature_row(row: pd.Series, pred_probs: dict) -> dict:
    record = extract_feature_record(
        {
            "paper_uid": row.get("paper_uid", ""),
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "keywords": row.get("keywords", ""),
            "raw_text": row.get("model_text", ""),
        }
    )
    attr_map = {a["name"]: a for a in record["attributes"]}
    supported = sum(1 for a in record["attributes"] if a["state"] == "SUPPORTED")
    partial = sum(1 for a in record["attributes"] if a["state"] == "PARTIAL")
    missing = sum(1 for a in record["attributes"] if a["state"] == "NOT_FOUND")
    out = {name: float(attr_map[name]["value"]) for name in ATTRIBUTE_ORDER}
    out.update(
        {
            "supported_count": float(supported),
            "partial_count": float(partial),
            "missing_count": float(missing),
            "classifier_prob_yes": float(pred_probs.get("YES", 0.0)),
            "classifier_prob_no": float(pred_probs.get("NO", 0.0)),
            "model_text_chars": float(len(str(row.get("model_text", "") or ""))),
            "page_count": float(row.get("page_count", 0) or 0),
        }
    )
    return out


def score_to_band(score: float) -> str:
    return risk_label_from_score(score)


def evaluate_regression(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    y_true_s = pd.Series(y_true)
    y_pred_s = pd.Series(y_pred)
    spearman = float(y_true_s.corr(y_pred_s, method="spearman")) if len(y_true_s) > 1 else 0.0
    band_accuracy = float((y_true_s.map(score_to_band) == y_pred_s.map(score_to_band)).mean())
    return {
        "mae": mae,
        "rmse": rmse,
        "spearman": 0.0 if np.isnan(spearman) else spearman,
        "band_accuracy": band_accuracy,
    }


def main():
    model_dir = DEFAULT_MODEL_DIR
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    df = load_gold_dataset(DATA_FILE)

    vectorizer = joblib.load(model_dir / "vectorizer.joblib")
    classifier = joblib.load(model_dir / "classifier.joblib")
    label_encoder = joblib.load(model_dir / "label_encoder.joblib")

    explicit_rows = []
    texts = []
    for _, row in df.iterrows():
        record = extract_feature_record(
            {
                "paper_uid": row.get("paper_uid", ""),
                "title": row.get("title", ""),
                "abstract": row.get("abstract", ""),
                "keywords": row.get("keywords", ""),
                "raw_text": row.get("model_text", ""),
            }
        )
        attr_row = {a["name"]: a["value"] for a in record["attributes"]}
        explicit_rows.append(attr_row)
        texts.append(str(row.get("model_text", "")))

    explicit_df = pd.DataFrame(explicit_rows)
    for col in ATTRIBUTE_ORDER:
        if col not in explicit_df.columns:
            explicit_df[col] = 0.0
    X_cls = build_classifier_matrix(vectorizer, texts, explicit_df)
    pred_prob_rows = [safe_predict_proba(classifier, X_cls[i], label_encoder) for i in range(X_cls.shape[0])]

    feature_rows = []
    for (_, row), probs in zip(df.iterrows(), pred_prob_rows):
        feature_rows.append(build_score_feature_row(row, probs))

    X = pd.DataFrame(feature_rows)
    for col in SCORE_FEATURE_COLUMNS:
        if col not in X.columns:
            X[col] = 0.0
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0.0).astype(float)
    X = X[SCORE_FEATURE_COLUMNS].copy()
    y = df["target_score"].astype(float).to_numpy()

    train_idx, temp_idx = train_test_split(np.arange(len(df)), test_size=0.30, random_state=42)
    val_idx, test_idx = train_test_split(temp_idx, test_size=0.50, random_state=42)

    X_train = X.iloc[train_idx].reset_index(drop=True)
    y_train = y[train_idx]
    X_val = X.iloc[val_idx].reset_index(drop=True)
    y_val = y[val_idx]
    X_test = X.iloc[test_idx].reset_index(drop=True)
    y_test = y[test_idx]

    candidates = [
        ("rf_400_depth_none_leaf2", RandomForestRegressor(n_estimators=400, max_depth=None, min_samples_leaf=2, random_state=42, n_jobs=-1)),
        ("rf_600_depth_12_leaf2", RandomForestRegressor(n_estimators=600, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=-1)),
        ("gbr_250_lr005_depth3", GradientBoostingRegressor(n_estimators=250, learning_rate=0.05, max_depth=3, random_state=42, subsample=0.9)),
        ("gbr_400_lr003_depth3", GradientBoostingRegressor(n_estimators=400, learning_rate=0.03, max_depth=3, random_state=42, subsample=0.9)),
    ]

    search_rows = []
    best_name = None
    best_model = None
    best_metrics = None

    for name, model in candidates:
        model.fit(X_train, y_train)
        val_pred = np.clip(model.predict(X_val), 0.0, 100.0)
        metrics = evaluate_regression(y_val, val_pred)
        search_rows.append({"model": name, **metrics})
        if best_metrics is None or metrics["mae"] < best_metrics["mae"] or (metrics["mae"] == best_metrics["mae"] and metrics["rmse"] < best_metrics["rmse"]):
            best_name = name
            best_model = model
            best_metrics = metrics

    X_trainval = pd.concat([X_train, X_val], axis=0).reset_index(drop=True)
    y_trainval = np.concatenate([y_train, y_val], axis=0)

    final_model = None
    for name, model in candidates:
        if name == best_name:
            final_model = model
            break
    final_model.fit(X_trainval, y_trainval)

    test_pred = np.clip(final_model.predict(X_test), 0.0, 100.0)
    test_metrics = evaluate_regression(y_test, test_pred)

    holdout_df = df.iloc[test_idx].copy().reset_index(drop=True)
    holdout_df["predicted_score"] = np.round(test_pred, 2)
    holdout_df["true_band"] = holdout_df["target_score"].map(score_to_band)
    holdout_df["predicted_band"] = holdout_df["predicted_score"].map(score_to_band)

    calibrator_path = model_dir / "score_calibrator.joblib"
    feature_cols_path = model_dir / "score_feature_columns.json"
    report_path = model_dir / "score_calibrator_report.json"
    holdout_path = model_dir / "score_calibrator_holdout_predictions.csv"

    ensure_dir(model_dir)
    joblib.dump(final_model, calibrator_path)
    feature_cols_path.write_text(json.dumps(SCORE_FEATURE_COLUMNS, indent=2), encoding="utf-8")
    holdout_df.to_csv(holdout_path, index=False)

    report = {
        "gold_rows_used": int(len(df)),
        "train_rows": int(len(train_idx)),
        "val_rows": int(len(val_idx)),
        "test_rows": int(len(test_idx)),
        "selected_model": best_name,
        "feature_count": int(len(SCORE_FEATURE_COLUMNS)),
        "validation_search": search_rows,
        "best_validation_metrics": best_metrics,
        "test_metrics": test_metrics,
        "artifacts": {
            "score_calibrator": str(calibrator_path),
            "score_feature_columns": str(feature_cols_path),
            "holdout_predictions": str(holdout_path),
        },
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    metadata_path = model_dir / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}
    metadata["score_calibrator"] = {
        "selected_model": best_name,
        "feature_columns_path": str(feature_cols_path),
        "report_path": str(report_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"✅ Score calibrator saved to: {calibrator_path}")
    print(f"✅ Calibrator report saved to: {report_path}")


if __name__ == "__main__":
    main()
