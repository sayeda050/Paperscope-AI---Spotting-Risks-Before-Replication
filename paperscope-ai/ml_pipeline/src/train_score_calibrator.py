"""
train_score_calibrator.py — Domain-aware score calibrator training.

Requires: data/processed/gold_score_dataset.csv with target_score filled.
         Use llm_auto_label.py to auto-populate target_score.

FIXES APPLIED vs previous version:
  - FIX 1: rubric_score added as feature (was in CSV, completely ignored before)
  - FIX 2: llm_label_binary added as feature (was in CSV, completely ignored before)
  - FIX 3: Stratified train/test split by score band (prevents band imbalance)
  - FIX 4: 5-fold stratified CV for model selection (replaces unreliable single val split)
  - FIX 5: Final model is a FRESH instance refit on all train+val (not the search object)
  - FIX 6: Honest holdout metrics printed and saved (no in-sample contamination)
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
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from discover_pdf_features import extract_feature_record
from domain_config import ATTRIBUTE_ORDER, SUPPORTED_DOMAINS, validate_domain
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_text,
    ensure_dir,
    get_run_id,
    risk_label_from_score,
    write_json,
    write_latest_pointer,
)

PIPELINE_DIR        = SRC_DIR.parent
DATA_FILE           = PIPELINE_DIR / "data" / "processed" / "gold_score_dataset.csv"
MODELS_BASE         = PIPELINE_DIR / "outputs" / "models"
MIN_ROWS_PER_DOMAIN = 30

# FIX 1 & 2: rubric_score + llm_label_binary were in gold_score_dataset.csv
# the entire time but were never passed as features. Adding them now.
SCORE_FEATURE_COLUMNS = (
    ATTRIBUTE_ORDER
    + [
        "supported_count",
        "partial_count",
        "missing_count",
        "classifier_prob_yes",
        "classifier_prob_no",
        "model_text_chars",
        "page_count",
        "rubric_score",      # FIX 1: the weighted rubric score 0-100
        "llm_label_binary",  # FIX 2: 1.0=YES / 0.0=NO from LLM
    ]
    + [f"dom_{d}" for d in SUPPORTED_DOMAINS]
)

# FIX 5: Store constructors so we can create FRESH instances for the final refit.
# The old code reused already-fitted objects, which works but is fragile.
CANDIDATE_CONFIGS: list[tuple[str, object]] = [
    (
        "rf_400",
        lambda: RandomForestRegressor(
            n_estimators=400, max_depth=None, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        ),
    ),
    (
        "rf_600_d12",
        lambda: RandomForestRegressor(
            n_estimators=600, max_depth=12, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        ),
    ),
    (
        "gbr_250_lr005",
        lambda: GradientBoostingRegressor(
            n_estimators=250, learning_rate=0.05, max_depth=3,
            subsample=0.9, random_state=42
        ),
    ),
    (
        "gbr_400_lr003",
        lambda: GradientBoostingRegressor(
            n_estimators=400, learning_rate=0.03, max_depth=3,
            subsample=0.9, random_state=42
        ),
    ),
]


def load_gold_dataset(path: Path, domain_filter: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Gold score dataset not found: {path}\n"
            "Run llm_auto_label.py first to create it."
        )
    df = pd.read_csv(path)
    required = {"title", "abstract", "model_text", "target_score"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"gold_score_dataset.csv missing columns: {sorted(missing)}")

    df = df.copy()
    df["title"]        = df["title"].fillna("").astype(str).map(clean_text)
    df["abstract"]     = df["abstract"].fillna("").astype(str).map(clean_text)
    df["model_text"]   = df["model_text"].fillna("").astype(str)
    df["target_score"] = pd.to_numeric(df["target_score"], errors="coerce")

    if "page_count" not in df.columns:
        df["page_count"] = 0
    df["page_count"] = pd.to_numeric(df["page_count"], errors="coerce").fillna(0).astype(int)

    if "domain" not in df.columns:
        df["domain"] = "ml"
    df["domain"] = df["domain"].fillna("ml").astype(str)

    # FIX 1: load rubric_score (0-100 weighted attribute score, already computed)
    if "rubric_score" in df.columns:
        df["rubric_score"] = (
            pd.to_numeric(df["rubric_score"], errors="coerce").fillna(50.0)
        )
    else:
        df["rubric_score"] = 50.0

    # FIX 2: load llm_label and binarize it
    if "llm_label" in df.columns:
        df["llm_label_binary"] = (
            df["llm_label"]
            .fillna("NO").astype(str).str.upper().str.strip()
            .map({"YES": 1.0, "NO": 0.0})
            .fillna(0.0)
        )
    else:
        df["llm_label_binary"] = 0.0

    df = df[df["target_score"].notna()].copy()
    df = df[(df["target_score"] >= 0.0) & (df["target_score"] <= 100.0)].copy()
    df = df[df["model_text"].str.len() > 0].copy()
    uid_col = "paper_uid" if "paper_uid" in df.columns else df.columns[0]
    df = df.drop_duplicates(subset=[uid_col]).copy()

    if domain_filter:
        df = df[df["domain"] == domain_filter].copy()

    return df.reset_index(drop=True)


def get_domain_onehot(domain: str) -> list[float]:
    return [1.0 if d == domain else 0.0 for d in SUPPORTED_DOMAINS]


def build_classifier_matrix(
    vectorizer, texts: list[str], explicit_df: pd.DataFrame
) -> sp.csr_matrix:
    X_text = vectorizer.transform(texts)
    X_num  = sp.csr_matrix(explicit_df[ATTRIBUTE_ORDER].astype(float).to_numpy())
    return sp.hstack([X_text, X_num], format="csr")


def safe_predict_proba(classifier, X, label_encoder) -> dict[str, float]:
    try:
        if hasattr(classifier, "predict_proba"):
            proba   = classifier.predict_proba(X)[0]
            classes = label_encoder.classes_.tolist()
            return {classes[i]: float(proba[i]) for i in range(len(classes))}
    except Exception:
        pass
    return {}


def build_score_feature_row(row: pd.Series, pred_probs: dict) -> dict:
    domain = str(row.get("domain", "ml") or "ml")
    record = extract_feature_record(
        {
            "paper_uid": row.get("paper_uid", ""),
            "domain":    domain,
            "title":     row.get("title", ""),
            "abstract":  row.get("abstract", ""),
            "keywords":  row.get("keywords", ""),
            "raw_text":  row.get("model_text", ""),
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
        "classifier_prob_yes": float(pred_probs.get("YES", 0.0)),
        "classifier_prob_no":  float(pred_probs.get("NO",  0.0)),
        "model_text_chars":    float(len(str(row.get("model_text", "") or ""))),
        "page_count":          float(row.get("page_count", 0) or 0),
        # FIX 1 & 2: pull the free signals directly from the dataset row
        "rubric_score":        float(row.get("rubric_score", 50.0) or 50.0),
        "llm_label_binary":    float(row.get("llm_label_binary", 0.0) or 0.0),
    })
    for k, v in zip([f"dom_{d}" for d in SUPPORTED_DOMAINS], get_domain_onehot(domain)):
        out[k] = v
    return out


def score_to_band(score: float) -> str:
    return risk_label_from_score(score)


def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
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


def build_feature_matrix(
    rows_df: pd.DataFrame,
    vectorizer,
    classifier,
    label_encoder,
) -> pd.DataFrame:
    """Build the full feature DataFrame for a set of rows."""
    texts     = [str(r.get("model_text", "")) for _, r in rows_df.iterrows()]
    expl_rows = []
    for _, row in rows_df.iterrows():
        dom_r  = str(row.get("domain", "ml") or "ml")
        record = extract_feature_record(
            {
                "paper_uid": row.get("paper_uid", ""),
                "domain":    dom_r,
                "title":     row.get("title", ""),
                "abstract":  row.get("abstract", ""),
                "keywords":  row.get("keywords", ""),
                "raw_text":  row.get("model_text", ""),
            },
            domain=dom_r,
        )
        expl_rows.append({a["name"]: a["value"] for a in record["attributes"]})

    prob_rows: list[dict] = []
    if vectorizer is not None and classifier is not None and label_encoder is not None:
        expl_tmp = pd.DataFrame(expl_rows)
        for col in ATTRIBUTE_ORDER:
            if col not in expl_tmp.columns:
                expl_tmp[col] = 0.0
        X_cls = build_classifier_matrix(vectorizer, texts, expl_tmp)
        for i in range(X_cls.shape[0]):
            prob_rows.append(safe_predict_proba(classifier, X_cls[i], label_encoder))
    else:
        prob_rows = [{} for _ in range(len(rows_df))]

    feat_rows = []
    for (_, row_series), probs in zip(rows_df.iterrows(), prob_rows):
        feat_rows.append(build_score_feature_row(row_series, probs))

    X = pd.DataFrame(feat_rows)
    for col in SCORE_FEATURE_COLUMNS:
        if col not in X.columns:
            X[col] = 0.0
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0.0).astype(float)
    return X[SCORE_FEATURE_COLUMNS].copy()


def stratified_cv_select(
    X: pd.DataFrame, y: np.ndarray, n_splits: int = 5
) -> tuple[str, dict]:
    """
    FIX 4: Stratified 5-fold CV for model selection.
    Stratification is by score band (LOW/MEDIUM/HIGH) so every fold
    has representative coverage of all difficulty levels.
    """
    bands = np.array([score_to_band(s) for s in y])
    unique_bands = np.unique(bands)

    # Assign fold indices within each band to spread them evenly
    fold_ids = np.zeros(len(y), dtype=int)
    rng = np.random.default_rng(42)
    for band in unique_bands:
        idx = np.where(bands == band)[0]
        shuffled = rng.permutation(idx)
        for rank, orig_idx in enumerate(shuffled):
            fold_ids[orig_idx] = rank % n_splits

    cv_scores: dict[str, list[float]] = {name: [] for name, _ in CANDIDATE_CONFIGS}

    for fold in range(n_splits):
        val_mask   = fold_ids == fold
        train_mask = ~val_mask
        if val_mask.sum() == 0:
            continue
        X_tr, y_tr = X.iloc[train_mask].reset_index(drop=True), y[train_mask]
        X_vl, y_vl = X.iloc[val_mask].reset_index(drop=True),  y[val_mask]

        for name, constructor in CANDIDATE_CONFIGS:
            m    = constructor()
            m.fit(X_tr, y_tr)
            pred = np.clip(m.predict(X_vl), 0.0, 100.0)
            cv_scores[name].append(float(mean_absolute_error(y_vl, pred)))

    cv_mean = {
        name: float(np.mean(scores)) if scores else 999.0
        for name, scores in cv_scores.items()
    }
    best_name = min(cv_mean, key=cv_mean.__getitem__)
    return best_name, {
        name: {
            "cv_mae_per_fold": scores,
            "cv_mae_mean":     cv_mean[name],
        }
        for name, scores in cv_scores.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train domain-aware score calibrator (all fixes applied)."
    )
    parser.add_argument("--domain", default="")
    parser.add_argument("--min-rows", type=int, default=MIN_ROWS_PER_DOMAIN)
    args = parser.parse_args()

    domain_filter = validate_domain(args.domain) if (args.domain and args.domain.lower() != "all") else ""
    domain_tag    = domain_filter or "all"
    run_id        = get_run_id()

    # Load classifier for predict_proba features (optional enhancement)
    from utils import read_latest_model_dir
    vectorizer = classifier = label_encoder = None
    for tag in [domain_tag, "all"]:
        try:
            clf_dir = read_latest_model_dir(PIPELINE_DIR / "outputs" / "models", tag)
            vp, cp, lp = (
                clf_dir / "vectorizer.joblib",
                clf_dir / "classifier.joblib",
                clf_dir / "label_encoder.joblib",
            )
            if vp.exists() and cp.exists() and lp.exists():
                vectorizer    = joblib.load(vp)
                classifier    = joblib.load(cp)
                label_encoder = joblib.load(lp)
                print(f"Loaded classifier from: {clf_dir.name}")
            break
        except FileNotFoundError:
            continue

    df = load_gold_dataset(DATA_FILE, domain_filter)
    print(f"Loaded {len(df)} labeled rows for domain={domain_tag!r}")
    print(f"  rubric_score range: {df['rubric_score'].min():.1f} – {df['rubric_score'].max():.1f}")
    print(f"  llm_label YES rate: {df['llm_label_binary'].mean():.2f}")

    if len(df) < args.min_rows:
        raise RuntimeError(
            f"Only {len(df)} labeled rows (minimum={args.min_rows}). "
            "Run llm_auto_label.py to generate more gold labels."
        )

    # FIX 3: Stratified train/test split by score band
    band_labels = [score_to_band(s) for s in df["target_score"]]
    try:
        train_val_df, test_df = train_test_split(
            df, test_size=0.15, random_state=42, stratify=band_labels
        )
    except ValueError:
        print("⚠ Too few samples per band for stratified split — using random split.")
        train_val_df, test_df = train_test_split(df, test_size=0.15, random_state=42)

    train_val_df = train_val_df.reset_index(drop=True)
    test_df      = test_df.reset_index(drop=True)
    print(f"\nSplit: {len(train_val_df)} train+val | {len(test_df)} holdout")

    # Build feature matrices
    print("Building features for train+val...")
    X_tv = build_feature_matrix(train_val_df, vectorizer, classifier, label_encoder)
    y_tv = train_val_df["target_score"].astype(float).to_numpy()

    print("Building features for holdout...")
    X_test = build_feature_matrix(test_df, vectorizer, classifier, label_encoder)
    y_test = test_df["target_score"].astype(float).to_numpy()

    # FIX 4: 5-fold CV model selection
    print(f"\nRunning 5-fold stratified CV on {len(train_val_df)} rows...")
    best_name, cv_results = stratified_cv_select(X_tv, y_tv, n_splits=5)
    print("\nCV model selection results:")
    for name, res in cv_results.items():
        marker = " ← SELECTED" if name == best_name else ""
        folds  = [f"{m:.2f}" for m in res["cv_mae_per_fold"]]
        print(f"  {name:20s}  mean={res['cv_mae_mean']:.2f}  folds=[{', '.join(folds)}]{marker}")

    # FIX 5: Fresh instance of best model, refit on ALL train+val data
    best_constructor = next(ctor for n, ctor in CANDIDATE_CONFIGS if n == best_name)
    final_model = best_constructor()
    print(f"\nRefitting fresh {best_name} on all {len(train_val_df)} train+val rows...")
    final_model.fit(X_tv, y_tv)

    # FIX 6: Evaluate on true holdout (never touched during training or selection)
    test_pred    = np.clip(final_model.predict(X_test), 0.0, 100.0)
    test_metrics = evaluate_regression(y_test, test_pred)

    print(f"\n{'='*55}")
    print(f"TRUE HOLDOUT METRICS (n={len(test_df)}, never seen during training):")
    print(f"  MAE:           {test_metrics['mae']:.2f}")
    print(f"  RMSE:          {test_metrics['rmse']:.2f}")
    print(f"  Spearman r:    {test_metrics['spearman']:.3f}")
    print(f"  Band accuracy: {test_metrics['band_accuracy']:.3f}")
    print(f"{'='*55}\n")

    # Save artifacts
    out_dir = MODELS_BASE / domain_tag / run_id
    ensure_dir(out_dir)

    calibrator_path = out_dir / "score_calibrator.joblib"
    feat_cols_path  = out_dir / "score_feature_columns.json"
    report_path     = out_dir / "score_calibrator_report.json"
    holdout_path    = out_dir / "score_calibrator_holdout.csv"

    joblib.dump(final_model, calibrator_path)
    feat_cols_path.write_text(json.dumps(SCORE_FEATURE_COLUMNS, indent=2), encoding="utf-8")

    holdout_out = test_df.copy().reset_index(drop=True)
    holdout_out["predicted_score"] = np.round(test_pred, 2)
    holdout_out["true_band"]       = holdout_out["target_score"].map(score_to_band)
    holdout_out["predicted_band"]  = holdout_out["predicted_score"].map(score_to_band)
    holdout_out.to_csv(holdout_path, index=False)

    report = {
        "schema_version":        PIPELINE_SCHEMA_VERSION,
        "run_id":                run_id,
        "domain":                domain_tag,
        "gold_rows_total":       int(len(df)),
        "train_val_rows":        int(len(train_val_df)),
        "holdout_rows":          int(len(test_df)),
        "selected_model":        best_name,
        "feature_count":         len(SCORE_FEATURE_COLUMNS),
        "new_features_added":    ["rubric_score", "llm_label_binary"],
        "cv_results":            cv_results,
        "holdout_metrics":       test_metrics,
        "artifacts": {
            "score_calibrator":      str(calibrator_path),
            "score_feature_columns": str(feat_cols_path),
            "holdout_predictions":   str(holdout_path),
        },
    }
    write_json(report_path, report)
    write_latest_pointer(MODELS_BASE, domain_tag, run_id, out_dir)

    meta_path = out_dir / "metadata.json"
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    meta["score_calibrator"] = {
        "selected_model":        best_name,
        "feature_columns_path":  str(feat_cols_path),
        "calibrator_path":       str(calibrator_path),
        "report_path":           str(report_path),
        "new_features":          ["rubric_score", "llm_label_binary"],
        "cv_folds":              5,
    }
    write_json(meta_path, meta)

    print(f"✅ Score calibrator → {calibrator_path}")
    print(f"✅ Holdout CSV      → {holdout_path}")
    print(f"✅ Report           → {report_path}")
    print(f"   Selected model:    {best_name}")
    print(f"   True holdout MAE:  {test_metrics['mae']:.2f}")
    print(f"   True band acc:     {test_metrics['band_accuracy']:.3f}")


if __name__ == "__main__":
    main()
