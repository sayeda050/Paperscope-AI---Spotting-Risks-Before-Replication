from pathlib import Path
import json
import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DATA = Path("data/processed/train.jsonl")
OUT_DIR = Path("outputs/model_artifacts/tfidf_lr_v1")

def load_data():
    texts, labels = [], []
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(int(row["label"]))
    return texts, np.array(labels)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    X, y = load_data()
    if len(X) < 4:
        raise RuntimeError("Need at least 4 rows to train. Add more samples.")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        lowercase=True,
        stop_words="english",
    )

    clf = LogisticRegression(max_iter=200, n_jobs=None)

    pipe = Pipeline([
        ("vectorizer", vectorizer),
        ("clf", clf),
    ])

    pipe.fit(X_train, y_train)

    # Save separate files to match backend expectation
    joblib.dump(pipe.named_steps["vectorizer"], OUT_DIR / "vectorizer.joblib")
    joblib.dump(pipe.named_steps["clf"], OUT_DIR / "classifier.joblib")

    metadata = {
        "model_name": "tfidf_lr_v1",
        "task": "binary_relevance",
        "labels": {"0": "not_relevant", "1": "relevant"},
        "vectorizer": {
            "max_features": 5000,
            "ngram_range": [1, 2],
            "stop_words": "english",
        },
        "classifier": {
            "type": "LogisticRegression",
            "max_iter": 200,
        },
        "train_size": len(X_train),
        "val_size": len(X_val),
    }

    (OUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"✅ Model trained & saved at: {OUT_DIR}")

if __name__ == "__main__":
    main()