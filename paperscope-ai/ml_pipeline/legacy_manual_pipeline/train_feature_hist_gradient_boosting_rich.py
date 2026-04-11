from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder

from feature_engineering_rich import build_rich_features, save_feature_columns


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "feature_hist_gradient_boosting_rich_v1"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"
FEATURE_COLUMNS_PATH = OUT_DIR / "feature_columns.json"


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

    if "risk_label" not in df.columns:
        raise ValueError(f"{csv_path.name} is missing column: risk_label")

    df = df.copy()
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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_df = load_split(TRAIN_CSV)
    val_df = load_split(VAL_CSV)
    test_df = load_split(TEST_CSV)

    X_train, feature_columns = build_rich_features(train_df)
    X_val, _ = build_rich_features(val_df)
    X_test, _ = build_rich_features(test_df)

    y_train_labels = train_df["risk_label"].tolist()
    y_val_labels = val_df["risk_label"].tolist()
    y_test_labels = test_df["risk_label"].tolist()

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(y_train_labels)

    # Rich-feature validation search
    candidate_configs = [
        {"learning_rate": 0.03, "max_depth": 3,  "max_leaf_nodes": 15, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.05, "max_depth": 3,  "max_leaf_nodes": 15, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.10, "max_depth": 3,  "max_leaf_nodes": 15, "min_samples_leaf": 10, "l2_regularization": 0.0},

        {"learning_rate": 0.03, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.05, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.10, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 10, "l2_regularization": 0.0},

        {"learning_rate": 0.03, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.05, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 10, "l2_regularization": 0.0},
        {"learning_rate": 0.10, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 10, "l2_regularization": 0.0},

        {"learning_rate": 0.03, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"learning_rate": 0.05, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"learning_rate": 0.10, "max_depth": 5,  "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.1},

        {"learning_rate": 0.03, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"learning_rate": 0.05, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.1},
        {"learning_rate": 0.10, "max_depth": 8,  "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 0.1},
    ]

    search_results = []
    best = None
    best_selection_model = None

    for cfg in candidate_configs:
        clf = HistGradientBoostingClassifier(
            learning_rate=cfg["learning_rate"],
            max_depth=cfg["max_depth"],
            max_leaf_nodes=cfg["max_leaf_nodes"],
            min_samples_leaf=cfg["min_samples_leaf"],
            l2_regularization=cfg["l2_regularization"],
            max_iter=300,
            early_stopping=False,
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
            "learning_rate": cfg["learning_rate"],
            "max_depth": cfg["max_depth"],
            "max_leaf_nodes": cfg["max_leaf_nodes"],
            "min_samples_leaf": cfg["min_samples_leaf"],
            "l2_regularization": cfg["l2_regularization"],
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

    selected_val_metrics = evaluate_split(
        "Validation",
        best_selection_model,
        X_val,
        y_val_labels,
        label_encoder,
    )

    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_trainval, _ = build_rich_features(combined_df)
    y_trainval_labels = combined_df["risk_label"].tolist()
    y_trainval = label_encoder.transform(y_trainval_labels)

    final_clf = HistGradientBoostingClassifier(
        learning_rate=best["config"]["learning_rate"],
        max_depth=best["config"]["max_depth"],
        max_leaf_nodes=best["config"]["max_leaf_nodes"],
        min_samples_leaf=best["config"]["min_samples_leaf"],
        l2_regularization=best["config"]["l2_regularization"],
        max_iter=300,
        early_stopping=False,
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
    save_feature_columns(FEATURE_COLUMNS_PATH, feature_columns)

    metadata = {
        "model_name": "feature_hist_gradient_boosting_rich_v1",
        "classifier_type": "HistGradientBoostingClassifier",
        "input_type": "rich_engineered_feature_columns_only",
        "feature_columns_count": len(feature_columns),
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
    print(f"✅ Feature columns saved to: {FEATURE_COLUMNS_PATH}")


if __name__ == "__main__":
    main()