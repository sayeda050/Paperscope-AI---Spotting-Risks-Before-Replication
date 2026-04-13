"""
evaluate_score_calibrator.py — Honest evaluation of the score calibrator.

CRITICAL FIX vs previous version:
  The old script loaded ALL of gold_score_dataset.csv and ran predictions on it.
  But the model was trained on 85% of that data — so metrics were inflated by
  in-sample predictions. MAE 10.65 / Spearman 0.822 were FAKE.

  This version reads directly from score_calibrator_holdout.csv which contains
  ONLY the 15% of data the model never saw during training or model selection.
  That is the only honest estimate of real-world performance.

  It also re-runs predictions fresh from the saved model to catch any drift.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from discover_pdf_features import extract_feature_record
from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_text,
    read_latest_model_dir,
    risk_label_from_score,
    write_json,
    ensure_dir,
)

PIPELINE_DIR = SRC_DIR.parent
DATA_FILE    = PIPELINE_DIR / "data" / "processed" / "gold_score_dataset.csv"
MODELS_BASE  = PIPELINE_DIR / "outputs" / "models"
REPORT_DIR   = PIPELINE_DIR / "outputs" / "reports"


def score_to_band(score: float) -> str:
    return risk_label_from_score(score)


def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    mae  = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    y_ts = pd.Series(y_true.tolist())
    y_ps = pd.Series(y_pred.tolist())
    sp_r = float(y_ts.corr(y_ps, method="spearman")) if len(y_ts) > 1 else 0.0
    ba   = float((y_ts.map(score_to_band) == y_ps.map(score_to_band)).mean())
    return {
        "mae":           mae,
        "rmse":          rmse,
        "spearman":      0.0 if math.isnan(sp_r) else sp_r,
        "band_accuracy": ba,
    }


def get_domain_onehot(domain: str) -> list[float]:
    return [1.0 if d == domain else 0.0 for d in SUPPORTED_DOMAINS]


def build_feature_row_from_holdout(row: pd.Series, feature_columns: list[str]) -> dict:
    """
    Build a feature dict from a holdout row.
    All needed values (rubric_score, llm_label_binary, etc.) are already
    stored in the holdout CSV — no re-extraction needed for them.
    For the attribute features we call extract_feature_record on model_text.
    """
    domain = str(row.get("domain", "ml") or "ml")
    record = extract_feature_record(
        {
            "paper_uid": row.get("paper_uid", ""),
            "domain":    domain,
            "title":     clean_text(str(row.get("title", "") or "")),
            "abstract":  clean_text(str(row.get("abstract", "") or "")),
            "keywords":  clean_text(str(row.get("keywords", "") or "")),
            "raw_text":  str(row.get("model_text", "") or ""),
        },
        domain=domain,
    )
    attr_map  = {a["name"]: a for a in record["attributes"]}
    supported = sum(1 for a in record["attributes"] if a["state"] == "SUPPORTED")
    partial   = sum(1 for a in record["attributes"] if a["state"] == "PARTIAL")
    missing_n = sum(1 for a in record["attributes"] if a["state"] == "NOT_FOUND")

    out = {name: float(attr_map[name]["value"]) for name in ATTRIBUTE_ORDER}
    out.update({
        "supported_count":     float(supported),
        "partial_count":       float(partial),
        "missing_count":       float(missing_n),
        "classifier_prob_yes": 0.0,   # filled below if classifier available
        "classifier_prob_no":  0.0,
        "model_text_chars":    float(len(str(row.get("model_text", "") or ""))),
        "page_count":          float(row.get("page_count", 0) or 0),
        "rubric_score":        float(row.get("rubric_score", 50.0) or 50.0),
        "llm_label_binary":    float(row.get("llm_label_binary", 0.0) or 0.0),
    })
    for k, v in zip([f"dom_{d}" for d in SUPPORTED_DOMAINS], get_domain_onehot(domain)):
        out[k] = v
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Honest evaluation of the score calibrator on held-out data only."
    )
    parser.add_argument("--domain", default="all")
    args = parser.parse_args()

    domain_tag = validate_domain(args.domain) if args.domain not in ("", "all") else "all"

    try:
        model_dir = read_latest_model_dir(MODELS_BASE, domain_tag)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    calibrator_path = model_dir / "score_calibrator.joblib"
    feat_cols_path  = model_dir / "score_feature_columns.json"
    holdout_path    = model_dir / "score_calibrator_holdout.csv"

    if not calibrator_path.exists():
        raise FileNotFoundError(f"Missing score calibrator: {calibrator_path}")
    if not feat_cols_path.exists():
        raise FileNotFoundError(f"Missing feature columns: {feat_cols_path}")
    if not holdout_path.exists():
        raise FileNotFoundError(
            f"Missing holdout CSV: {holdout_path}\n"
            "Re-train with: python train_score_calibrator.py --domain {domain_tag}"
        )

    calibrator      = joblib.load(calibrator_path)
    feature_columns = json.loads(feat_cols_path.read_text(encoding="utf-8"))

    # Load classifier for predict_proba (optional enhancement)
    vectorizer = clf = label_encoder = None
    vp = model_dir / "vectorizer.joblib"
    cp = model_dir / "classifier.joblib"
    lp = model_dir / "label_encoder.joblib"
    if vp.exists() and cp.exists() and lp.exists():
        vectorizer    = joblib.load(vp)
        clf           = joblib.load(cp)
        label_encoder = joblib.load(lp)

    # Load the true holdout — these rows were NEVER seen during training
    holdout_df = pd.read_csv(holdout_path)
    if "target_score" not in holdout_df.columns:
        raise ValueError("holdout CSV missing 'target_score' column.")

    holdout_df["target_score"] = pd.to_numeric(holdout_df["target_score"], errors="coerce")
    holdout_df = holdout_df[holdout_df["target_score"].notna()].copy()
    holdout_df["model_text"]      = holdout_df.get("model_text", pd.Series([""] * len(holdout_df))).fillna("").astype(str)
    holdout_df["rubric_score"]    = pd.to_numeric(holdout_df.get("rubric_score", pd.Series([50.0] * len(holdout_df))), errors="coerce").fillna(50.0)
    holdout_df["llm_label_binary"]= pd.to_numeric(holdout_df.get("llm_label_binary", pd.Series([0.0] * len(holdout_df))), errors="coerce").fillna(0.0)

    if holdout_df.empty:
        print("❌ Holdout CSV has no usable rows.")
        sys.exit(1)

    n = len(holdout_df)
    print(f"Evaluating on {n} true holdout rows (model never saw these during training).")

    # Re-build features fresh to catch any feature drift
    feat_rows = []
    for _, row in holdout_df.iterrows():
        feat_rows.append(build_feature_row_from_holdout(row, feature_columns))

    # Fill classifier proba if available
    if vectorizer is not None and clf is not None and label_encoder is not None:
        texts   = [str(r.get("model_text", "")) for _, r in holdout_df.iterrows()]
        expl_df = pd.DataFrame([{a: fr.get(a, 0.0) for a in ATTRIBUTE_ORDER} for fr in feat_rows])
        for col in ATTRIBUTE_ORDER:
            if col not in expl_df.columns:
                expl_df[col] = 0.0
        X_text  = vectorizer.transform(texts)
        X_num   = sp.csr_matrix(expl_df[ATTRIBUTE_ORDER].astype(float).to_numpy())
        X_cls   = sp.hstack([X_text, X_num], format="csr")
        for i in range(X_cls.shape[0]):
            try:
                if hasattr(clf, "predict_proba"):
                    proba   = clf.predict_proba(X_cls[i])[0]
                    classes = label_encoder.classes_.tolist()
                    feat_rows[i]["classifier_prob_yes"] = float(proba[classes.index("YES")] if "YES" in classes else 0.0)
                    feat_rows[i]["classifier_prob_no"]  = float(proba[classes.index("NO")]  if "NO"  in classes else 0.0)
            except Exception:
                pass

    X_score = pd.DataFrame(feat_rows)
    for col in feature_columns:
        if col not in X_score.columns:
            X_score[col] = 0.0
        X_score[col] = pd.to_numeric(X_score[col], errors="coerce").fillna(0.0).astype(float)
    X_score = X_score[feature_columns].copy()

    y_true = holdout_df["target_score"].astype(float).to_numpy()
    y_pred = np.clip(calibrator.predict(X_score), 0.0, 100.0)

    metrics = evaluate_regression(y_true, y_pred)

    # Save updated predictions CSV
    out_df = holdout_df.copy()
    out_df["predicted_score"] = np.round(y_pred, 2)
    out_df["true_band"]       = out_df["target_score"].map(score_to_band)
    out_df["predicted_band"]  = out_df["predicted_score"].map(score_to_band)

    ensure_dir(REPORT_DIR)
    pred_path    = model_dir / "score_calibrator_full_eval_predictions.csv"
    summary_path = model_dir / "score_calibrator_full_eval.json"
    out_df.to_csv(pred_path, index=False)

    summary = {
        "schema_version":   PIPELINE_SCHEMA_VERSION,
        "domain":           domain_tag,
        "evaluation_note":  (
            "Metrics computed on true holdout only (rows never seen during training). "
            "The previous version incorrectly included training rows, producing "
            "inflated metrics. These numbers are honest."
        ),
        "rows":             int(n),
        "mae":              metrics["mae"],
        "rmse":             metrics["rmse"],
        "spearman":         metrics["spearman"],
        "band_accuracy":    metrics["band_accuracy"],
        "predictions_csv":  str(pred_path),
    }
    write_json(summary_path, summary)

    print(f"\n✅ Predictions → {pred_path}")
    print(f"✅ Summary     → {summary_path}")
    print(f"\nCalibrator evaluation ({domain_tag}) — TRUE HOLDOUT ONLY:")
    print(f"  MAE:           {metrics['mae']:.2f}   (old script showed inflated 10.65)")
    print(f"  RMSE:          {metrics['rmse']:.2f}")
    print(f"  Spearman r:    {metrics['spearman']:.3f}  (old script showed inflated 0.822)")
    print(f"  Band accuracy: {metrics['band_accuracy']:.3f}  (old script showed inflated 0.732)")
    print(f"\n  ⚠  Compare these to the old script's numbers.")
    print(f"     A drop in apparent performance is EXPECTED and CORRECT.")
    print(f"     These are your real numbers. Improve them by getting more labels.")


if __name__ == "__main__":
    main()
