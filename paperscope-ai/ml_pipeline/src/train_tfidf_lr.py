from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "outputs" / "models" / "tfidf_lr_v1"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

VECTORIZER_PATH = OUT_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = OUT_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = OUT_DIR / "label_encoder.joblib"
METADATA_PATH = OUT_DIR / "metadata.json"
TRAIN_REPORT_PATH = OUT_DIR / "train_report.json"


def make_json_safe(obj):
    """
    Recursively convert Python / sklearn / numpy objects
    into JSON-serializable values.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(v) for v in obj]

    # numpy scalar support
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass

    # fallback for types / callables / other sklearn objects
    return str(obj)


def load_split(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing file: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {"model_text", "risk_label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path.name} is missing columns: {sorted(missing)}")

    df = df.copy()
    df["model_text"] = df["model_text"].fillna("").astype(str)
    df["risk_label"] = df["risk_label"].fillna("").astype(str)

    df = df[df["model_text"].str.len() > 0]
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
        "classification_report": report,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_df = load_split(TRAIN_CSV)
    val_df = load_split(VAL_CSV)
    test_df = load_split(TEST_CSV)

    X_train_text = train_df["model_text"].tolist()
    X_val_text = val_df["model_text"].tolist()
    X_test_text = test_df["model_text"].tolist()

    y_train_labels = train_df["risk_label"].tolist()
    y_val_labels = val_df["risk_label"].tolist()
    y_test_labels = test_df["risk_label"].tolist()

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(y_train_labels)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=50000,
        sublinear_tf=True,
    )

    X_train = vectorizer.fit_transform(X_train_text)
    X_val = vectorizer.transform(X_val_text)
    X_test = vectorizer.transform(X_test_text)

    clf = LogisticRegression(
        max_iter=2000,
        solver="lbfgs",
        class_weight="balanced",
        random_state=42,
    )

    clf.fit(X_train, y_train)

    val_metrics = evaluate_split("Validation", clf, X_val, y_val_labels, label_encoder)
    test_metrics = evaluate_split("Test", clf, X_test, y_test_labels, label_encoder)

    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(clf, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    metadata = {
        "model_name": "tfidf_lr_v1",
        "vectorizer_type": "TfidfVectorizer",
        "classifier_type": "LogisticRegression",
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "label_classes": label_encoder.classes_.tolist(),
        "vectorizer_params": make_json_safe(vectorizer.get_params()),
        "classifier_params": make_json_safe(clf.get_params()),
    }

    train_report = {
        "validation": make_json_safe(val_metrics),
        "test": make_json_safe(test_metrics),
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(TRAIN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(train_report, f, indent=2)

    print(f"\n✅ Vectorizer saved to: {VECTORIZER_PATH}")
    print(f"✅ Classifier saved to: {CLASSIFIER_PATH}")
    print(f"✅ Label encoder saved to: {LABEL_ENCODER_PATH}")
    print(f"✅ Metadata saved to: {METADATA_PATH}")
    print(f"✅ Training report saved to: {TRAIN_REPORT_PATH}")


if __name__ == "__main__":
    main()