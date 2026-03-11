from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "feature_random_forest_v1"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"
FEATURE_IMPORTANCES_PATH = OUT_DIR / "feature_importances.csv"

FEATURE_COLUMNS = [
    "has_code_link",
    "has_data_link",
    "has_hyperparams",
    "has_seed",
    "has_env_details",
    "has_metrics",
    "has_baselines",
    "has_ablation",
    "has_limitations",
    "has_statistical_tests",
    "review_missing_details",
    "review_repro_concern",
    "review_code_missing",
    "review_dataset_unclear",
    "review_hyperparams_unclear",
    "review_missing_ablation",
    "review_weak_baselines",
    "review_insufficient_experiments",
]


def make_json_safe(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(v) for v in obj]

    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass

    return str(obj)


def load_split(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing file: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = set(FEATURE_COLUMNS) | {"risk_label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path.name} is missing columns: {sorted(missing)}")

    df = df.copy()

    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)

    df["risk_label"] = df["risk_label"].fillna("").astype(str)
    df = df[df["risk_label"].str.len() > 0]

    if df.empty:
        raise ValueError(f"{csv_path.name} has no usable rows after cleaning.")

    return df


def evaluate_split(name, clf, X, y_true_labels, label_encoder):
    y_pred = clf.predict(X)
    y_pred_labels = label_encoder.inverse_transform(y_pred)

    acc = accuracy_score(y_true_labels, y_pred_labels)
    report = classification_report(
        y_true_labels,
        y_pred_labels,
        output_dict=True,
        zero_division=0,
    )

    print(f"\n{name} accuracy: {acc:.4f}")
    print(classification_report(y_true_labels, y_pred_labels, zero_division=0))

    return {
        "accuracy": acc,
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        "classification_report": report,
    }


def build_feature_importances_df(clf, feature_names):
    df = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": clf.feature_importances_,
        }
    )
    df = df.sort_values(by="importance", ascending=False).reset_index(drop=True)
    return df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_df = load_split(TRAIN_CSV)
    val_df = load_split(VAL_CSV)
    test_df = load_split(TEST_CSV)

    X_train = train_df[FEATURE_COLUMNS].copy()
    X_val = val_df[FEATURE_COLUMNS].copy()
    X_test = test_df[FEATURE_COLUMNS].copy()

    y_train_labels = train_df["risk_label"].tolist()
    y_val_labels = val_df["risk_label"].tolist()
    y_test_labels = test_df["risk_label"].tolist()

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(y_train_labels)

    # Legit validation-based hyperparameter search.
    # Select by validation macro-F1 first, then validation accuracy.
    candidate_configs = [
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": None},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": None},
        {"n_estimators": 500, "max_depth": 20,   "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": None},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": None},
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1, "max_features": None,   "class_weight": None},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "max_features": None,   "class_weight": None},
        {"n_estimators": 500, "max_depth": 20,   "min_samples_leaf": 1, "max_features": None,   "class_weight": None},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 2, "max_features": None,   "class_weight": None},

        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": 20,   "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 2, "max_features": "sqrt", "class_weight": "balanced"},
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 1, "max_features": None,   "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 1, "max_features": None,   "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": 20,   "min_samples_leaf": 1, "max_features": None,   "class_weight": "balanced"},
        {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 2, "max_features": None,   "class_weight": "balanced"},
    ]

    search_results = []
    best = None
    best_selection_model = None

    for cfg in candidate_configs:
        clf = RandomForestClassifier(
            n_estimators=cfg["n_estimators"],
            max_depth=cfg["max_depth"],
            min_samples_leaf=cfg["min_samples_leaf"],
            max_features=cfg["max_features"],
            class_weight=cfg["class_weight"],
            n_jobs=-1,
            random_state=42,
        )

        clf.fit(X_train, y_train)

        val_pred = clf.predict(X_val)
        val_pred_labels = label_encoder.inverse_transform(val_pred)

        val_report = classification_report(
            y_val_labels,
            val_pred_labels,
            output_dict=True,
            zero_division=0,
        )

        val_accuracy = accuracy_score(y_val_labels, val_pred_labels)
        val_macro_f1 = float(val_report["macro avg"]["f1-score"])
        val_weighted_f1 = float(val_report["weighted avg"]["f1-score"])

        row = {
            "n_estimators": cfg["n_estimators"],
            "max_depth": cfg["max_depth"],
            "min_samples_leaf": cfg["min_samples_leaf"],
            "max_features": cfg["max_features"],
            "class_weight": cfg["class_weight"],
            "val_accuracy": float(val_accuracy),
            "val_macro_f1": val_macro_f1,
            "val_weighted_f1": val_weighted_f1,
        }
        search_results.append(row)

        if best is None:
            best = {
                "config": cfg,
                "val_accuracy": val_accuracy,
                "val_macro_f1": val_macro_f1,
                "val_weighted_f1": val_weighted_f1,
            }
            best_selection_model = clf
        else:
            if (
                val_macro_f1 > best["val_macro_f1"]
                or (
                    val_macro_f1 == best["val_macro_f1"]
                    and val_accuracy > best["val_accuracy"]
                )
            ):
                best = {
                    "config": cfg,
                    "val_accuracy": val_accuracy,
                    "val_macro_f1": val_macro_f1,
                    "val_weighted_f1": val_weighted_f1,
                }
                best_selection_model = clf

    # Validation metrics from selected model trained on train only
    selected_val_metrics = evaluate_split(
        "Validation",
        best_selection_model,
        X_val,
        y_val_labels,
        label_encoder,
    )

    # Final model: fit once on train + val, report final test only
    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_trainval = combined_df[FEATURE_COLUMNS].copy()
    y_trainval_labels = combined_df["risk_label"].tolist()
    y_trainval = label_encoder.transform(y_trainval_labels)

    final_clf = RandomForestClassifier(
        n_estimators=best["config"]["n_estimators"],
        max_depth=best["config"]["max_depth"],
        min_samples_leaf=best["config"]["min_samples_leaf"],
        max_features=best["config"]["max_features"],
        class_weight=best["config"]["class_weight"],
        n_jobs=-1,
        random_state=42,
    )

    final_clf.fit(X_trainval, y_trainval)

    final_test_metrics = evaluate_split(
        "Test",
        final_clf,
        X_test,
        y_test_labels,
        label_encoder,
    )

    joblib.dump(final_clf, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    importance_df = build_feature_importances_df(final_clf, FEATURE_COLUMNS)
    importance_df.to_csv(FEATURE_IMPORTANCES_PATH, index=False)

    metadata = {
        "model_name": "feature_random_forest_v1",
        "classifier_type": "RandomForestClassifier",
        "input_type": "engineered_feature_columns_only",
        "feature_columns": FEATURE_COLUMNS,
        "target_column": "risk_label",
        "excluded_columns": ["risk_score", "weak_score"],
        "selection_metric": "validation_macro_f1_then_accuracy",
        "selected_hyperparameters": make_json_safe(best["config"]),
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "train_plus_val_rows": int(len(combined_df)),
        "label_classes": label_encoder.classes_.tolist(),
        "classifier_params": make_json_safe(final_clf.get_params()),
    }

    train_report = {
        "hyperparameter_search_results": make_json_safe(search_results),
        "best_validation_selection": make_json_safe(best),
        "validation_selected_model": make_json_safe(selected_val_metrics),
        "test_final_model": make_json_safe(final_test_metrics),
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(TRAIN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    print(f"\n✅ Classifier saved to: {CLASSIFIER_PATH}")
    print(f"✅ Label encoder saved to: {LABEL_ENCODER_PATH}")
    print(f"✅ Metadata saved to: {METADATA_PATH}")
    print(f"✅ Training report saved to: {TRAIN_REPORT_PATH}")
    print(f"✅ Feature importances saved to: {FEATURE_IMPORTANCES_PATH}")


if __name__ == "__main__":
    main()