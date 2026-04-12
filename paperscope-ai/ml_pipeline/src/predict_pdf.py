from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import joblib
import pandas as pd
import pdfplumber
import scipy.sparse as sp

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from discover_pdf_features import ATTRIBUTE_ORDER, extract_feature_record
from utils import clean_text, clean_multiline_text, risk_label_from_score

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v3"


# ---------------------------------------------------------------------------
# PDF text extraction helpers
# ---------------------------------------------------------------------------

def extract_with_pymupdf(pdf_path: Path, max_pages: int = 60) -> tuple[str, int]:
    text_parts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            text_parts.append(page.get_text("text") or "")
        page_count = len(doc)
    finally:
        doc.close()
    return "\n".join(text_parts), page_count


def extract_with_pdfplumber(pdf_path: Path, max_pages: int = 60) -> tuple[str, int]:
    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            text_parts.append(page.extract_text() or "")
        page_count = len(pdf.pages)
    return "\n".join(text_parts), page_count


# ---------------------------------------------------------------------------
# BUG FIX 8 — model_text construction
# ---------------------------------------------------------------------------
# Original code:
#   model_text = str(row["raw_text"])
#   if row["title"]:
#       model_text = f"Title: {row['title']}\n\n{model_text}"
#   if row["abstract"]:
#       model_text = f"Title: {row['title']}\n\nAbstract: {row['abstract']}\n\n{row['raw_text']}"
#
# Problems:
#   1. If only abstract is present (no title), the second branch produces
#      "Title: \n\nAbstract: ..." with an empty Title prefix.
#   2. Keywords are silently ignored even though extract_text.py includes
#      them in the model_text that the classifier was trained on.
#   3. text_col_name was fetched from metadata but then never used —
#      the construction always operated on raw_text directly, creating a
#      potential train/inference text mismatch.
#
# Fix: replicate extract_text.py's build_model_text logic exactly, including
# keywords, and respect the text column name stored in metadata.
# ---------------------------------------------------------------------------
def build_model_text(
    title: str,
    abstract: str,
    keywords: str,
    raw_text: str,
    max_chars: int = 80_000,
) -> str:
    """
    Exact replica of extract_text.build_model_text so inference text always
    matches what the TF-IDF vectorizer was trained on.
    """
    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    if keywords:
        parts.append(f"Keywords: {keywords}")
    if raw_text:
        parts.append(raw_text[:max_chars])
    return "\n\n".join(parts).strip()


def build_classifier_matrix(vectorizer, text: str, explicit_features: dict):
    X_text = vectorizer.transform([text])
    explicit_row = pd.DataFrame(
        [{name: float(explicit_features.get(name, 0.0)) for name in ATTRIBUTE_ORDER}]
    )
    X_num = sp.csr_matrix(explicit_row[ATTRIBUTE_ORDER].astype(float).to_numpy())
    return sp.hstack([X_text, X_num], format="csr")


def build_score_feature_row(
    record: dict,
    pred_probs: dict,
    model_text: str,
    page_count: int,
) -> dict:
    supported = sum(1 for a in record["attributes"] if a["state"] == "SUPPORTED")
    partial = sum(1 for a in record["attributes"] if a["state"] == "PARTIAL")
    missing = sum(1 for a in record["attributes"] if a["state"] == "NOT_FOUND")
    attr_map = {a["name"]: a for a in record["attributes"]}
    out = {name: float(attr_map[name]["value"]) for name in ATTRIBUTE_ORDER}
    out.update(
        {
            "supported_count": float(supported),
            "partial_count": float(partial),
            "missing_count": float(missing),
            "classifier_prob_yes": float(pred_probs.get("YES", 0.0)),
            "classifier_prob_no": float(pred_probs.get("NO", 0.0)),
            "model_text_chars": float(len(model_text)),
            "page_count": float(page_count),
        }
    )
    return out


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Predict reproducibility risk for a single PDF with evidence-backed attributes."
    )
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--max-pages", type=int, default=60)
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Extract raw text.
    try:
        raw_text, page_count = extract_with_pymupdf(pdf_path, max_pages=args.max_pages)
    except Exception:
        raw_text, page_count = extract_with_pdfplumber(pdf_path, max_pages=args.max_pages)

    raw_text = clean_multiline_text(raw_text)

    title = clean_text(args.title)
    abstract = clean_text(args.abstract)
    keywords = clean_text(args.keywords)

    row = {
        "paper_uid": pdf_path.stem,
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "raw_text": raw_text,
    }

    # Extract evidence-backed attribute record (rubric path).
    record = extract_feature_record(row)

    output = {
        "pdf_path": str(pdf_path),
        "page_count": int(page_count),
        "rubric_reproducibility_score": float(record["reproducibility_score"]),
        "rubric_risk_score": float(record["risk_score"]),
        "rubric_risk_label": risk_label_from_score(float(record["risk_score"])),
        "attributes": record["attributes"],
    }

    # -----------------------------------------------------------------------
    # Classifier path — only runs when model artefacts are present.
    # -----------------------------------------------------------------------
    vectorizer_path = MODEL_DIR / "vectorizer.joblib"
    classifier_path = MODEL_DIR / "classifier.joblib"
    label_encoder_path = MODEL_DIR / "label_encoder.joblib"
    metadata_path = MODEL_DIR / "metadata.json"

    if vectorizer_path.exists() and classifier_path.exists() and label_encoder_path.exists():
        vectorizer = joblib.load(vectorizer_path)
        clf = joblib.load(classifier_path)
        label_encoder = joblib.load(label_encoder_path)

        metadata: dict = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}

        # -------------------------------------------------------------------
        # Build model_text that exactly mirrors what train_tfidf_logreg.py
        # fed into the vectorizer during training.
        #
        # The metadata stores which text column was used.  The two possible
        # values are:
        #   "train_text_input"  →  model_text as produced by extract_text.py
        #                          (Title + Abstract + Keywords + raw_text)
        #   "model_text"        →  same content, different column name
        #
        # In both cases the correct thing is to call build_model_text, which
        # replicates extract_text.build_model_text exactly, including keywords.
        # -------------------------------------------------------------------
        model_text = build_model_text(title, abstract, keywords, raw_text)

        explicit_map = {a["name"]: a["value"] for a in record["attributes"]}
        X = build_classifier_matrix(vectorizer, model_text, explicit_map)

        pred_num = clf.predict(X)[0]
        pred_label = label_encoder.inverse_transform([pred_num])[0]

        pred_probs: dict[str, float] = {}
        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(X)[0]
            class_names = label_encoder.classes_.tolist()
            pred_probs = {class_names[i]: float(proba[i]) for i in range(len(class_names))}

        output["classifier_prediction"] = pred_label
        output["class_probabilities"] = pred_probs

        # -------------------------------------------------------------------
        # Score calibrator path — runs when calibrator artefacts are present.
        # -------------------------------------------------------------------
        calibrator_path = MODEL_DIR / "score_calibrator.joblib"
        score_feature_columns_path = MODEL_DIR / "score_feature_columns.json"

        if calibrator_path.exists() and score_feature_columns_path.exists():
            calibrator = joblib.load(calibrator_path)
            feature_columns: list[str] = json.loads(
                score_feature_columns_path.read_text(encoding="utf-8")
            )
            score_row = build_score_feature_row(record, pred_probs, model_text, page_count)
            X_score = pd.DataFrame([score_row])
            for col in feature_columns:
                if col not in X_score.columns:
                    X_score[col] = 0.0
                X_score[col] = (
                    pd.to_numeric(X_score[col], errors="coerce").fillna(0.0).astype(float)
                )
            pred_score = float(
                max(0.0, min(100.0, calibrator.predict(X_score[feature_columns])[0]))
            )
            output["predicted_risk_score"] = round(pred_score, 2)
            output["predicted_risk_label"] = risk_label_from_score(pred_score)
        else:
            # Fall back to rubric score when calibrator is not available.
            output["predicted_risk_score"] = round(float(record["risk_score"]), 2)
            output["predicted_risk_label"] = risk_label_from_score(float(record["risk_score"]))

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()