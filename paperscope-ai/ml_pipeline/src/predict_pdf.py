import sys
from pathlib import Path
import argparse
import json
import re

import fitz
import joblib
import pdfplumber

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import clean_text

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v2"

VECTORIZER_PATH = MODEL_DIR / "vectorizer.joblib"
CLASSIFIER_PATH = MODEL_DIR / "classifier.joblib"
LABEL_ENCODER_PATH = MODEL_DIR / "label_encoder.joblib"


def normalize_pdf_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return clean_text(text)


def extract_with_pymupdf(pdf_path: Path, max_pages=50):
    text_parts = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            txt = page.get_text("text")
            if txt:
                text_parts.append(txt)
    finally:
        doc.close()
    return "\n".join(text_parts)


def extract_with_pdfplumber(pdf_path: Path, max_pages=50):
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)


def main():
    parser = argparse.ArgumentParser(description="Predict reproducibility label for a single PDF.")
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        raw_text = extract_with_pymupdf(pdf_path, max_pages=args.max_pages)
    except Exception:
        raw_text = extract_with_pdfplumber(pdf_path, max_pages=args.max_pages)

    raw_text = normalize_pdf_text(raw_text)
    title = clean_text(args.title)
    abstract = clean_text(args.abstract)
    model_text = clean_text(". ".join([x for x in [title, abstract, raw_text[:60000]] if x]))

    vectorizer = joblib.load(VECTORIZER_PATH)
    clf = joblib.load(CLASSIFIER_PATH)
    label_encoder = joblib.load(LABEL_ENCODER_PATH)

    X = vectorizer.transform([model_text])
    pred_numeric = clf.predict(X)[0]
    pred_label = label_encoder.inverse_transform([pred_numeric])[0]

    output = {
        "pdf_path": str(pdf_path),
        "predicted_label": pred_label,
        "model_text_chars": len(model_text),
    }

    if hasattr(clf, "predict_proba"):
        proba = clf.predict_proba(X)[0]
        class_names = label_encoder.classes_.tolist()
        output["class_probabilities"] = {class_names[i]: float(proba[i]) for i in range(len(class_names))}

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
