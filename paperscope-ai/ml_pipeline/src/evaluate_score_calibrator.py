
from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import mean_absolute_error, mean_squared_error

from discover_pdf_features import ATTRIBUTE_ORDER, extract_feature_record
from utils import clean_text, risk_label_from_score

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v3"
DATA_FILE = BASE_DIR / "data" / "processed" / "gold_score_dataset.csv"


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
    supported = sum(1 for a in record["attributes"] if a["state"] == "SUPPORTED")
    partial = sum(1 for a in record["attributes"] if a["state"] == "PARTIAL")
    missing = sum(1 for a in record["attributes"] if a["state"] == "NOT_FOUND")
    attr_map = {a["name"]: a for a in record["attributes"]}
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
    spearman = float(pd.Series(y_true).corr(pd.Series(y_pred), method="spearman"))
    band_accuracy = float((pd.Series(y_true).map(score_to_band) == pd.Series(y_pred).map(score_to_band)).mean())
    return mae, rmse, 0.0 if np.isnan(spearman) else spearman, band_accuracy


def main():
    calibrator_path = MODEL_DIR / "score_calibrator.joblib"
    feature_cols_path = MODEL_DIR / "score_feature_columns.json"
    if not calibrator_path.exists():
        raise FileNotFoundError(f"Missing score calibrator artifact: {calibrator_path}")
    if not feature_cols_path.exists():
        raise FileNotFoundError(f"Missing score feature column file: {feature_cols_path}")

    df = load_gold_dataset(DATA_FILE)
    vectorizer = joblib.load(MODEL_DIR / "vectorizer.joblib")
    classifier = joblib.load(MODEL_DIR / "classifier.joblib")
    label_encoder = joblib.load(MODEL_DIR / "label_encoder.joblib")
    calibrator = joblib.load(calibrator_path)
    feature_columns = json.loads(feature_cols_path.read_text(encoding="utf-8"))

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
        explicit_rows.append({a["name"]: a["value"] for a in record["attributes"]})
        texts.append(str(row.get("model_text", "")))

    explicit_df = pd.DataFrame(explicit_rows)
    for col in ATTRIBUTE_ORDER:
        if col not in explicit_df.columns:
            explicit_df[col] = 0.0
    X_cls = build_classifier_matrix(vectorizer, texts, explicit_df)
    pred_prob_rows = [safe_predict_proba(classifier, X_cls[i], label_encoder) for i in range(X_cls.shape[0])]

    rows = []
    for (_, item), probs in zip(df.iterrows(), pred_prob_rows):
        rows.append(build_score_feature_row(item, probs))

    X_score = pd.DataFrame(rows)
    for col in feature_columns:
        if col not in X_score.columns:
            X_score[col] = 0.0
        X_score[col] = pd.to_numeric(X_score[col], errors="coerce").fillna(0.0).astype(float)
    X_score = X_score[feature_columns].copy()

    y_true = df["target_score"].astype(float).to_numpy()
    y_pred = np.clip(calibrator.predict(X_score), 0.0, 100.0)

    mae, rmse, spearman, band_accuracy = evaluate_regression(y_true, y_pred)

    out_df = df.copy()
    out_df["predicted_score"] = np.round(y_pred, 2)
    out_df["true_band"] = out_df["target_score"].map(score_to_band)
    out_df["predicted_band"] = out_df["predicted_score"].map(score_to_band)

    out_path = MODEL_DIR / "score_calibrator_full_eval_predictions.csv"
    out_df.to_csv(out_path, index=False)

    summary = {
        "rows": int(len(out_df)),
        "mae": mae,
        "rmse": rmse,
        "spearman": spearman,
        "band_accuracy": band_accuracy,
        "predictions_csv": str(out_path),
    }
    summary_path = MODEL_DIR / "score_calibrator_full_eval.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"✅ Full evaluation predictions saved to: {out_path}")
    print(f"✅ Summary saved to: {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
