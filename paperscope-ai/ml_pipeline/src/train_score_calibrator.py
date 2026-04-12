import sys
from pathlib import Path
import argparse
import json
import math

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

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
from utils import ensure_dir, clean_text

DATA_FILE = BASE_DIR / "data" / "processed" / "gold_score_dataset.csv"
DEFAULT_MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v2"


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
    df["model_text"] = df["model_text"].fillna("").astype(str).map(clean_text)
    df["target_score"] = pd.to_numeric(df["target_score"], errors="coerce")
    df = df[df["target_score"].notna()].copy()
    df = df[(df["target_score"] >= 0.0) & (df["target_score"] <= 100.0)].copy()
    df = df[df["model_text"].str.len() > 0].copy()

    if len(df) < 60:
        raise RuntimeError("Too few labeled rows. Label at least 60 papers before training the score calibrator.")

    return df.reset_index(drop=True)


def build_feature_table(df: pd.DataFrame, model_dir: Path):
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8")) if (model_dir / "metadata.json").exists() else {}
    vectorizer = joblib.load(model_dir / "vectorizer.joblib")
    classifier = joblib.load(model_dir / "classifier.joblib")
    label_encoder = joblib.load(model_dir / "label_encoder.joblib")

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

        prediction = {
            "prediction": pred_label,
            "probabilities": pred_probs,
        }
        rows.append(build_score_feature_row(payload, prediction))

    feature_df = pd.DataFrame(rows)
    for col in DEFAULT_SCORE_FEATURE_COLUMNS:
        if col not in feature_df.columns:
            feature_df[col] = 0.0
    feature_df = feature_df[DEFAULT_SCORE_FEATURE_COLUMNS].copy()

    for col in feature_df.columns:
        feature_df[col] = pd.to_numeric(feature_df[col], errors="coerce").fillna(0.0).astype(float)

    return feature_df


def evaluate_regression(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    y_true_s = pd.Series(y_true)
    y_pred_s = pd.Series(y_pred)
    spearman = float(y_true_s.corr(y_pred_s, method="spearman")) if len(y_true_s) > 1 else 0.0

    true_band = y_true_s.map(score_to_band)
    pred_band = y_pred_s.map(score_to_band)
    band_accuracy = float((true_band == pred_band).mean())

    return {
        "mae": mae,
        "rmse": rmse,
        "spearman": spearman if not np.isnan(spearman) else 0.0,
        "band_accuracy": band_accuracy,
    }


def main():
    parser = argparse.ArgumentParser(description="Train a learned score calibrator on top of an existing classifier.")
    parser.add_argument("--model-name", default="tfidf_logreg_auto_v2")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    model_dir = BASE_DIR / "outputs" / "models" / args.model_name
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    df = load_gold_dataset(DATA_FILE)
    X = build_feature_table(df, model_dir)
    y = df["target_score"].astype(float).to_numpy()

    train_idx, temp_idx = train_test_split(
        np.arange(len(df)),
        test_size=0.30,
        random_state=args.random_state,
    )
    val_idx, test_idx = train_test_split(
        temp_idx,
        test_size=0.50,
        random_state=args.random_state,
    )

    X_train = X.iloc[train_idx].reset_index(drop=True)
    y_train = y[train_idx]
    X_val = X.iloc[val_idx].reset_index(drop=True)
    y_val = y[val_idx]
    X_test = X.iloc[test_idx].reset_index(drop=True)
    y_test = y[test_idx]

    candidates = [
        ("rf_300_depth_none_leaf2", RandomForestRegressor(
            n_estimators=300,
            max_depth=None,
            min_samples_leaf=2,
            random_state=args.random_state,
            n_jobs=-1,
        )),
        ("rf_500_depth_12_leaf2", RandomForestRegressor(
            n_estimators=500,
            max_depth=12,
            min_samples_leaf=2,
            random_state=args.random_state,
            n_jobs=-1,
        )),
        ("gbr_200_lr005_depth3", GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            random_state=args.random_state,
            subsample=0.9,
        )),
        ("gbr_400_lr003_depth3", GradientBoostingRegressor(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=3,
            random_state=args.random_state,
            subsample=0.9,
        )),
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

        if best_metrics is None or metrics["mae"] < best_metrics["mae"] or (
            metrics["mae"] == best_metrics["mae"] and metrics["rmse"] < best_metrics["rmse"]
        ):
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
    feature_cols_path.write_text(json.dumps(DEFAULT_SCORE_FEATURE_COLUMNS, indent=2), encoding="utf-8")
    holdout_df.to_csv(holdout_path, index=False)

    report = {
        "gold_rows_used": int(len(df)),
        "train_rows": int(len(train_idx)),
        "val_rows": int(len(val_idx)),
        "test_rows": int(len(test_idx)),
        "selected_model": best_name,
        "feature_count": int(len(DEFAULT_SCORE_FEATURE_COLUMNS)),
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
        "enabled": True,
        "model_type": best_name,
        "feature_count": len(DEFAULT_SCORE_FEATURE_COLUMNS),
        "test_metrics": test_metrics,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"✅ Score calibrator saved to: {calibrator_path}")
    print(f"✅ Score feature columns saved to: {feature_cols_path}")
    print(f"✅ Score calibrator report saved to: {report_path}")
    print(f"✅ Holdout predictions saved to: {holdout_path}")
    print("\nSelected calibrator:", best_name)
    print("Validation MAE:", round(best_metrics["mae"], 4))
    print("Test MAE:", round(test_metrics["mae"], 4))
    print("Test RMSE:", round(test_metrics["rmse"], 4))
    print("Test Spearman:", round(test_metrics["spearman"], 4))
    print("Test band accuracy:", round(test_metrics["band_accuracy"], 4))


if __name__ == "__main__":
    main()
