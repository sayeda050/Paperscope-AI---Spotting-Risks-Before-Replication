import sys
from pathlib import Path
import argparse
import json
import math

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
BACKEND_DIR = BASE_DIR.parent / "backend"

if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from apps.analysis.model_registry_service import (
    build_text_input,
    build_score_feature_row,
    DEFAULT_SCORE_FEATURE_COLUMNS,
)
from utils import clean_text

DATA_FILE = BASE_DIR / "data" / "processed" / "gold_score_dataset.csv"


def safe_predict_proba(classifier, X, label_encoder):
    try:
        if hasattr(classifier, "predict_proba"):
            proba = classifier.predict_proba(X)[0]
            classes = label_encoder.classes_.tolist()
            return {classes[i]: float(proba[i]) for i in range(len(classes))}
    except Exception:
        pass
    return {}


def score_to_band(score: float) -> str:
    if score < 35.0:
        return "Low"
    if score < 65.0:
        return "Med"
    return "High"


def evaluate_regression(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    spearman = float(pd.Series(y_true).corr(pd.Series(y_pred), method="spearman"))
    band_accuracy = float((pd.Series(y_true).map(score_to_band) == pd.Series(y_pred).map(score_to_band)).mean())
    return mae, rmse, 0.0 if np.isnan(spearman) else spearman, band_accuracy


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained score calibrator on the labeled score dataset.")
    parser.add_argument("--model-name", default="tfidf_logreg_auto_v2")
    args = parser.parse_args()

    model_dir = BASE_DIR / "outputs" / "models" / args.model_name
    calibrator_path = model_dir / "score_calibrator.joblib"
    if not calibrator_path.exists():
        raise FileNotFoundError(f"Missing score calibrator artifact: {calibrator_path}")

    df = pd.read_csv(DATA_FILE)
    df["title"] = df["title"].fillna("").astype(str).map(clean_text)
    df["abstract"] = df["abstract"].fillna("").astype(str).map(clean_text)
    df["model_text"] = df["model_text"].fillna("").astype(str).map(clean_text)
    df["target_score"] = pd.to_numeric(df["target_score"], errors="coerce")
    df = df[df["target_score"].notna()].copy().reset_index(drop=True)

    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8")) if (model_dir / "metadata.json").exists() else {}
    vectorizer = joblib.load(model_dir / "vectorizer.joblib")
    classifier = joblib.load(model_dir / "classifier.joblib")
    label_encoder = joblib.load(model_dir / "label_encoder.joblib")
    calibrator = joblib.load(calibrator_path)

    rows = []
    for _, item in df.iterrows():
        payload = {
            "title": item.get("title", ""),
            "abstract": item.get("abstract", ""),
            "model_text": item.get("model_text", ""),
            "review_text": "",
            "decision_text": "",
            "venue": item.get("venue", ""),
            "year": item.get("year", 0),
            "review_count": 0,
        }
        text_input = build_text_input(payload, metadata)
        X_text = vectorizer.transform([text_input])
        pred_numeric = classifier.predict(X_text)[0]
        pred_label = label_encoder.inverse_transform([pred_numeric])[0]
        pred_probs = safe_predict_proba(classifier, X_text, label_encoder)
        prediction = {"prediction": pred_label, "probabilities": pred_probs}
        rows.append(build_score_feature_row(payload, prediction))

    X_score = pd.DataFrame(rows)
    for col in DEFAULT_SCORE_FEATURE_COLUMNS:
        if col not in X_score.columns:
            X_score[col] = 0.0
    X_score = X_score[DEFAULT_SCORE_FEATURE_COLUMNS].copy()
    for col in X_score.columns:
        X_score[col] = pd.to_numeric(X_score[col], errors="coerce").fillna(0.0).astype(float)

    y_true = df["target_score"].astype(float).to_numpy()
    y_pred = np.clip(calibrator.predict(X_score), 0.0, 100.0)

    mae, rmse, spearman, band_accuracy = evaluate_regression(y_true, y_pred)

    out_df = df.copy()
    out_df["predicted_score"] = np.round(y_pred, 2)
    out_df["true_band"] = out_df["target_score"].map(score_to_band)
    out_df["predicted_band"] = out_df["predicted_score"].map(score_to_band)

    out_path = model_dir / "score_calibrator_full_eval_predictions.csv"
    out_df.to_csv(out_path, index=False)

    summary = {
        "rows": int(len(out_df)),
        "mae": mae,
        "rmse": rmse,
        "spearman": spearman,
        "band_accuracy": band_accuracy,
        "predictions_csv": str(out_path),
    }
    summary_path = model_dir / "score_calibrator_full_eval.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"✅ Full evaluation predictions saved to: {out_path}")
    print(f"✅ Full evaluation summary saved to: {summary_path}")
    print("MAE:", round(mae, 4))
    print("RMSE:", round(rmse, 4))
    print("Spearman:", round(spearman, 4))
    print("Band accuracy:", round(band_accuracy, 4))


if __name__ == "__main__":
    main()
