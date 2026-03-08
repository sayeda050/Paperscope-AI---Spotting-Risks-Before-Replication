from pathlib import Path
import json
import joblib
import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

DATA = Path("data/processed/train.jsonl")
MODEL_DIR = Path("outputs/model_artifacts/tfidf_lr_v1")
REPORT = Path("outputs/reports/tfidf_lr_v1_report.txt")

def load_data():
    texts, labels = [], []
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(int(row["label"]))
    return texts, np.array(labels)

def main():
    X, y = load_data()
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    vec: TfidfVectorizer = joblib.load(MODEL_DIR / "vectorizer.joblib")
    clf: LogisticRegression = joblib.load(MODEL_DIR / "classifier.joblib")

    Xv = vec.transform(X_val)
    preds = clf.predict(Xv)

    rep = classification_report(y_val, preds, digits=4)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(rep, encoding="utf-8")

    print("✅ Evaluation report saved:", REPORT)
    print(rep)

if __name__ == "__main__":
    main()