from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "feature_lr_v1"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"
COEFFICIENTS_PATH = OUT_DIR / "feature_coefficients.csv"

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


def build_coefficients_df(clf, feature_names, class_names):
    coef = clf.coef_

    rows = []
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
        by=["class_name", "abs_coefficient"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return coef_df


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
    y_val = label_encoder.transform(y_val_labels)

    # Small, legitimate validation search over C and class_weight.
    # We select by validation macro-F1 first, then accuracy.
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
    best = None

    for cfg in candidate_configs:
        clf = LogisticRegression(
            C=cfg["C"],
            class_weight=cfg["class_weight"],
            max_iter=5000,
            solver="lbfgs",
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
            "C": cfg["C"],
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

    # Train once more on train + val using the selected hyperparameters.
    combined_df = pd.concat([train_df, val_df], axis=0, ignore_index=True)
    X_trainval = combined_df[FEATURE_COLUMNS].copy()
    y_trainval_labels = combined_df["risk_label"].tolist()
    y_trainval = label_encoder.fit_transform(y_trainval_labels)

    best_clf = LogisticRegression(
        C=best["config"]["C"],
        class_weight=best["config"]["class_weight"],
        max_iter=5000,
        solver="lbfgs",
        random_state=42,
    )

    best_clf.fit(X_trainval, y_trainval)

    # Re-evaluate on val with the final selected setup for visibility
    final_val_metrics = evaluate_split(
        "Validation",
        best_clf,
        X_val,
        y_val_labels,
        label_encoder,
    )

    final_test_metrics = evaluate_split(
        "Test",
        best_clf,
        X_test,
        y_test_labels,
        label_encoder,
    )

    joblib.dump(best_clf, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    coef_df = build_coefficients_df(
        best_clf,
        FEATURE_COLUMNS,
        label_encoder.classes_.tolist(),
    )
    coef_df.to_csv(COEFFICIENTS_PATH, index=False)

    metadata = {
        "model_name": "feature_lr_v1",
        "classifier_type": "LogisticRegression",
        "input_type": "engineered_feature_columns_only",
        "feature_columns": FEATURE_COLUMNS,
        "target_column": "risk_label",
        "excluded_columns": ["risk_score", "weak_score"],
        "selection_metric": "validation_macro_f1_then_accuracy",
        "selected_hyperparameters": {
            "C": best["config"]["C"],
            "class_weight": best["config"]["class_weight"],
        },
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "train_plus_val_rows": int(len(combined_df)),
        "label_classes": label_encoder.classes_.tolist(),
        "classifier_params": make_json_safe(best_clf.get_params()),
    }

    train_report = {
        "hyperparameter_search_results": make_json_safe(search_results),
        "best_validation_selection": make_json_safe(best),
        "validation": make_json_safe(final_val_metrics),
        "test": make_json_safe(final_test_metrics),
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(TRAIN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    print(f"\n✅ Classifier saved to: {CLASSIFIER_PATH}")
    print(f"✅ Label encoder saved to: {LABEL_ENCODER_PATH}")
    print(f"✅ Metadata saved to: {METADATA_PATH}")
    print(f"✅ Training report saved to: {TRAIN_REPORT_PATH}")
    print(f"✅ Feature coefficients saved to: {COEFFICIENTS_PATH}")


if __name__ == "__main__":
    main()