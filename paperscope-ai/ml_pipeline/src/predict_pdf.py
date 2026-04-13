"""
predict_pdf.py — Domain-aware reproducibility risk prediction for a single PDF.

USAGE:
  python predict_pdf.py --pdf-path paper.pdf --domain ml
  python predict_pdf.py --pdf-path paper.pdf --domain physics --title "My Paper" --abstract "..."

Routes to the latest trained model for the specified domain via latest.json.
Falls back to rubric-only scoring if no model is trained yet.
"""
from __future__ import annotations

import argparse
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

from discover_pdf_features import extract_feature_record
from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import (
    clean_text,
    clean_multiline_text,
    read_latest_model_dir,
    risk_label_from_score,
)

PIPELINE_DIR = SRC_DIR.parent
MODELS_BASE = PIPELINE_DIR / "outputs" / "models"
DEFAULT_DOMAIN = "ml"


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------
def extract_with_pymupdf(pdf_path: Path, max_pages: int = 60) -> tuple[str, int]:
    parts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            parts.append(page.get_text("text") or "")
        page_count = len(doc)
    finally:
        doc.close()
    return "\n".join(parts), page_count


def extract_with_pdfplumber(pdf_path: Path, max_pages: int = 60) -> tuple[str, int]:
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            parts.append(page.extract_text() or "")
        page_count = len(pdf.pages)
    return "\n".join(parts), page_count


def build_model_text(
    title: str, abstract: str, keywords: str, raw_text: str, max_chars: int = 80_000
) -> str:
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


# ---------------------------------------------------------------------------
# Feature matrix
# ---------------------------------------------------------------------------
def build_classifier_matrix(
    vectorizer, text: str, explicit_features: dict, domain: str
) -> sp.csr_matrix:
    X_text = vectorizer.transform([text])
    explicit_row = pd.DataFrame(
        [{name: float(explicit_features.get(name, 0.0)) for name in ATTRIBUTE_ORDER}]
    )
    X_num = sp.csr_matrix(explicit_row[ATTRIBUTE_ORDER].astype(float).to_numpy())
    # Domain one-hot
    dom_cols = {f"dom_{d}": (1.0 if d == domain else 0.0) for d in SUPPORTED_DOMAINS}
    X_dom = sp.csr_matrix([[dom_cols.get(f"dom_{d}", 0.0) for d in SUPPORTED_DOMAINS]])
    return sp.hstack([X_text, X_num, X_dom], format="csr")


def build_score_feature_row(
    record: dict, pred_probs: dict, model_text: str, page_count: int
) -> dict:
    supported = sum(1 for a in record["attributes"] if a["state"] == "SUPPORTED")
    partial   = sum(1 for a in record["attributes"] if a["state"] == "PARTIAL")
    missing   = sum(1 for a in record["attributes"] if a["state"] == "NOT_FOUND")
    attr_map  = {a["name"]: a for a in record["attributes"]}
    out = {name: float(attr_map[name]["value"]) for name in ATTRIBUTE_ORDER}
    out.update({
        "supported_count":      float(supported),
        "partial_count":        float(partial),
        "missing_count":        float(missing),
        "classifier_prob_yes":  float(pred_probs.get("YES", 0.0)),
        "classifier_prob_no":   float(pred_probs.get("NO", 0.0)),
        "model_text_chars":     float(len(model_text)),
        "page_count":           float(page_count),
    })
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict reproducibility risk for a single PDF."
    )
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument(
        "--domain", default=DEFAULT_DOMAIN,
        choices=SUPPORTED_DOMAINS,
        help=f"Paper domain (default: {DEFAULT_DOMAIN}).",
    )
    parser.add_argument("--title", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--max-pages", type=int, default=60)
    args = parser.parse_args()

    domain = validate_domain(args.domain)
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Extract text
    try:
        raw_text, page_count = extract_with_pymupdf(pdf_path, max_pages=args.max_pages)
    except Exception:
        raw_text, page_count = extract_with_pdfplumber(pdf_path, max_pages=args.max_pages)
    raw_text = clean_multiline_text(raw_text)

    title    = clean_text(args.title)
    abstract = clean_text(args.abstract)
    keywords = clean_text(args.keywords)

    row = {
        "paper_uid": pdf_path.stem,
        "domain": domain,
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "raw_text": raw_text,
    }

    # Rubric-based scoring
    record = extract_feature_record(row, domain=domain)

    output: dict = {
        "pdf_path":                  str(pdf_path),
        "domain":                    domain,
        "page_count":                int(page_count),
        "rubric_reproducibility_score": float(record["reproducibility_score"]),
        "rubric_risk_score":         float(record["risk_score"]),
        "rubric_risk_label":         risk_label_from_score(float(record["risk_score"])),
        "attributes":                record["attributes"],
    }

    # Classifier path — only if model exists
    try:
        model_dir = read_latest_model_dir(MODELS_BASE, domain)
    except FileNotFoundError:
        # Try fallback to "all" domain model
        try:
            model_dir = read_latest_model_dir(MODELS_BASE, "all")
        except FileNotFoundError:
            model_dir = None

    if model_dir is not None:
        vectorizer_path    = model_dir / "vectorizer.joblib"
        classifier_path    = model_dir / "classifier.joblib"
        label_encoder_path = model_dir / "label_encoder.joblib"
        metadata_path      = model_dir / "metadata.json"

        if all(p.exists() for p in [vectorizer_path, classifier_path, label_encoder_path]):
            vectorizer    = joblib.load(vectorizer_path)
            clf           = joblib.load(classifier_path)
            label_encoder = joblib.load(label_encoder_path)

            metadata: dict = {}
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            model_text = build_model_text(title, abstract, keywords, raw_text)
            explicit_map = {a["name"]: a["value"] for a in record["attributes"]}
            X = build_classifier_matrix(vectorizer, model_text, explicit_map, domain)

            pred_num   = clf.predict(X)[0]
            pred_label = label_encoder.inverse_transform([pred_num])[0]

            pred_probs: dict[str, float] = {}
            if hasattr(clf, "predict_proba"):
                proba = clf.predict_proba(X)[0]
                pred_probs = {
                    label_encoder.classes_[i]: float(proba[i])
                    for i in range(len(label_encoder.classes_))
                }

            output["classifier_prediction"]     = pred_label
            output["class_probabilities"]        = pred_probs
            output["model_dir"]                  = str(model_dir)
            output["calibration"]                = metadata.get("calibration", "unknown")

            # Score calibrator
            calibrator_path    = model_dir / "score_calibrator.joblib"
            score_feat_path    = model_dir / "score_feature_columns.json"

            if calibrator_path.exists() and score_feat_path.exists():
                calibrator      = joblib.load(calibrator_path)
                feature_columns = json.loads(score_feat_path.read_text(encoding="utf-8"))
                score_row       = build_score_feature_row(record, pred_probs, model_text, page_count)
                X_score         = pd.DataFrame([score_row])
                for col in feature_columns:
                    if col not in X_score.columns:
                        X_score[col] = 0.0
                    X_score[col] = pd.to_numeric(X_score[col], errors="coerce").fillna(0.0)
                pred_score = float(
                    max(0.0, min(100.0, calibrator.predict(X_score[feature_columns])[0]))
                )
                output["predicted_risk_score"] = round(pred_score, 2)
                output["predicted_risk_label"] = risk_label_from_score(pred_score)
            else:
                output["predicted_risk_score"] = round(float(record["risk_score"]), 2)
                output["predicted_risk_label"] = risk_label_from_score(float(record["risk_score"]))

    else:
        # No model — fall back to rubric
        output["predicted_risk_score"] = round(float(record["risk_score"]), 2)
        output["predicted_risk_label"] = risk_label_from_score(float(record["risk_score"]))
        output["classifier_prediction"] = None
        output["note"] = f"No trained model found for domain {domain!r}. Run train_tfidf_logreg.py first."

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
