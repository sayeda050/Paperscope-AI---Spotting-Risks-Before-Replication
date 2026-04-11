from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from feature_engineering_rich import build_rich_features


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "outputs" / "models" / "feature_hist_gradient_boosting_rich_tuned_v1"
REPORT_DIR = BASE_DIR / "outputs" / "reports"

TEST_CSV = DATA_DIR / "test.csv"

CLASSIFIER_PATH = MODEL_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = MODEL_DIR / "label_encoder.joblib"
METADATA_PATH = MODEL_DIR / "metadata.json"

EVAL_TXT_PATH = REPORT_DIR / "feature_hist_gradient_boosting_rich_tuned_evaluation.txt"
CONF_MATRIX_PATH = REPORT_DIR / "feature_hist_gradient_boosting_rich_tuned_confusion_matrix.csv"
EVAL_JSON_PATH = REPORT_DIR / "feature_hist_gradient_boosting_rich_tuned_evaluation_summary.json"


def load_test_data():
    if not TEST_CSV.exists():
        raise FileNotFoundError(f"Missing file: {TEST_CSV}")

    df = pd.read_csv(TEST_CSV)

    if "risk_label" not in df.columns:
        raise ValueError(f"{TEST_CSV.name} is missing column: risk_label")

    df = df.copy()
    df["risk_label"] = df["risk_label"].fillna("").astype(str)
    df = df[df["risk_label"].str.len() > 0]

    if df.empty:
        raise ValueError("Test set is empty after cleaning.")

    return df


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    test_df = load_test_data()
    X_test, feature_columns = build_rich_features(test_df)
    y_test = test_df["risk_label"].tolist()

    if not CLASSIFIER_PATH.exists():
        raise FileNotFoundError(f"Missing classifier: {CLASSIFIER_PATH}")
    if not LABEL_ENCODER_PATH.exists():
        raise FileNotFoundError(f"Missing label encoder: {LABEL_ENCODER_PATH}")

    clf = joblib.load(CLASSIFIER_PATH)
    label_encoder = joblib.load(LABEL_ENCODER_PATH)

    y_pred_numeric = clf.predict(X_test)
    y_pred = label_encoder.inverse_transform(y_pred_numeric)

    acc = accuracy_score(y_test, y_pred)
    report_text = classification_report(y_test, y_pred, digits=4, zero_division=0)
    report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    labels = list(label_encoder.classes_)
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    cm_df = pd.DataFrame(
        cm,
        index=[f"true_{x}" for x in labels],
        columns=[f"pred_{x}" for x in labels],
    )

    EVAL_TXT_PATH.write_text(
        f"Test accuracy: {acc:.4f}\n\n{report_text}",
        encoding="utf-8",
    )
    cm_df.to_csv(CONF_MATRIX_PATH, index=True)

    summary = {
        "model_name": "feature_hist_gradient_boosting_rich_tuned_v1",
        "test_accuracy": float(acc),
        "labels": labels,
        "classification_report": report_dict,
        "test_rows": int(len(test_df)),
        "feature_columns_count": int(len(feature_columns)),
        "metadata_path": str(METADATA_PATH),
        "model_dir": str(MODEL_DIR),
    }

    with open(EVAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"✅ Evaluation text report saved to: {EVAL_TXT_PATH}")
    print(f"✅ Confusion matrix saved to: {CONF_MATRIX_PATH}")
    print(f"✅ Evaluation summary saved to: {EVAL_JSON_PATH}")
    print("\nTest accuracy:", round(acc, 4))
    print(report_text)


if __name__ == "__main__":
    main()