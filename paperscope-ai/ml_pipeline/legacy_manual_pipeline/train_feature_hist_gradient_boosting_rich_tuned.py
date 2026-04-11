from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import PredefinedSplit, RandomizedSearchCV
from sklearn.preprocessing import LabelEncoder

from feature_engineering_rich import build_rich_features


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "feature_hist_gradient_boosting_rich_tuned_v1"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"
SEARCH_RESULTS_PATH = OUT_DIR / "search_results.csv"


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
    y_val = label_encoder.transform(y_val_labels)
    y_test = label_encoder.transform(y_test_labels)

    # Combine train + val only for hyperparameter search with a fixed validation fold.
    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_trainval, _ = build_rich_features(combined_df)
    y_trainval_labels = combined_df["risk_label"].tolist()
    y_trainval = label_encoder.transform(y_trainval_labels)

    # Predefined split: train rows are -1, val rows are 0
    test_fold = [-1] * len(train_df) + [0] * len(val_df)
    predefined_split = PredefinedSplit(test_fold=test_fold)

    base_model = HistGradientBoostingClassifier(
        early_stopping=False,
        random_state=42,
    )

    # Wider but still practical search
    param_distributions = {
        "learning_rate": [0.01, 0.02, 0.03, 0.05, 0.08, 0.10],
        "max_depth": [3, 4, 5, 6, 8, None],
        "max_leaf_nodes": [15, 31, 63, 127],
        "min_samples_leaf": [5, 10, 20, 30],
        "l2_regularization": [0.0, 0.01, 0.1, 1.0, 3.0],
        "max_iter": [200, 300, 500, 800],
    }

    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_distributions,
        n_iter=45,
        scoring="f1_macro",
        n_jobs=-1,
        cv=predefined_split,
        random_state=42,
        refit=False,
        verbose=1,
    )

    search.fit(X_trainval, y_trainval)

    search_results_df = pd.DataFrame(search.cv_results_)
    useful_cols = [
        "rank_test_score",
        "mean_test_score",
        "param_learning_rate",
        "param_max_depth",
        "param_max_leaf_nodes",
        "param_min_samples_leaf",
        "param_l2_regularization",
        "param_max_iter",
    ]
    useful_cols = [c for c in useful_cols if c in search_results_df.columns]
    search_results_df[useful_cols].sort_values(
        by=["rank_test_score", "mean_test_score"],
        ascending=[True, False],
    ).to_csv(SEARCH_RESULTS_PATH, index=False)

    best_params = search.best_params_
    best_val_macro_f1 = float(search.best_score_)

    # 1) Validation-selected model trained on train only for a clean val readout
    selected_model = HistGradientBoostingClassifier(
        early_stopping=False,
        random_state=42,
        **best_params,
    )
    selected_model.fit(X_train, y_train)

    selected_val_metrics = evaluate_split(
        "Validation",
        selected_model,
        X_val,
        y_val_labels,
        label_encoder,
    )

    # 2) Final model trained on train + val, evaluated once on test
    final_model = HistGradientBoostingClassifier(
        early_stopping=False,
        random_state=42,
        **best_params,
    )
    final_model.fit(X_trainval, y_trainval)

    final_test_metrics = evaluate_split(
        "Test",
        final_model,
        X_test,
        y_test_labels,
        label_encoder,
    )

    joblib.dump(final_model, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    metadata = {
        "model_name": "feature_hist_gradient_boosting_rich_tuned_v1",
        "classifier_type": "HistGradientBoostingClassifier",
        "input_type": "rich_engineered_feature_columns_only",
        "feature_columns_count": int(len(feature_columns)),
        "target_column": "risk_label",
        "excluded_columns": ["risk_score", "weak_score"],
        "selection_metric": "validation_macro_f1",
        "search_method": "RandomizedSearchCV_with_PredefinedSplit",
        "selected_hyperparameters": make_json_safe(best_params),
        "validation_macro_f1_from_search": best_val_macro_f1,
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "train_plus_val_rows": int(len(combined_df)),
        "label_classes": label_encoder.classes_.tolist(),
        "classifier_params": make_json_safe(final_model.get_params()),
    }

    train_report = {
        "best_validation_macro_f1_from_search": best_val_macro_f1,
        "best_params": make_json_safe(best_params),
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
    print(f"✅ Search results saved to: {SEARCH_RESULTS_PATH}")


if __name__ == "__main__":
    main()