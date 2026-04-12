import sys
from pathlib import Path
import json
import argparse
import re

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, ensure_dir, clean_text

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_FEATURES_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_features.joblib"
OUT_TERMS_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_feature_terms.json"
OUT_MATRIX_CSV = PIPELINE_DIR / "data" / "processed" / "discovered_feature_matrix.csv"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "feature_discovery_report.json"

# Only paper-accessible signals. Reviewer/decision signals are intentionally
# excluded from this feature block so pseudo-scores stay aligned with runtime
# inference, where user-uploaded PDFs do not come with reviews/decisions.
CONTENT_PATTERNS = {
    "has_code_link": re.compile(
        r"github\.com/|gitlab\.com/|bitbucket\.org/|code\s+(?:is\s+)?available|"
        r"implementation\s+(?:is\s+)?available|source\s+code|we\s+release\s+(?:the\s+)?code|"
        r"open[- ]?source",
        re.I,
    ),
    "has_data_link": re.compile(
        r"dataset\s+(?:is\s+)?available|data\s+available|we\s+release\s+(?:the\s+)?data(?:set)?|"
        r"publicly\s+available\s+(?:data|dataset)|huggingface\.co/|zenodo\.org/|"
        r"figshare\.com/|osf\.io/|kaggle\.com/",
        re.I,
    ),
    "reports_hyperparams": re.compile(
        r"learning\s+rate|batch\s+size|(?:number\s+of\s+)?epochs?|weight\s+decay|"
        r"dropout|optimizer|momentum|hyperparameter",
        re.I,
    ),
    "reports_seed": re.compile(r"random\s+seed|seed\s*=\s*\d+|seeded", re.I),
    "reports_uncertainty": re.compile(
        r"standard\s+deviation|standard\s+error|confidence\s+interval|"
        r"error\s+bar|±|\u00b1|p[- ]value|multiple\s+run",
        re.I,
    ),
    "reports_compute": re.compile(
        r"gpu|tpu|cuda|v100|a100|rtx|computing\s+infrastructure|"
        r"compute\s+(?:budget|cost|hours?)|training\s+time|wall[- ]?clock",
        re.I,
    ),
    "has_ablation": re.compile(
        r"ablation\s+stud(?:y|ies)|ablate|we\s+ablate|ablation\s+experiment",
        re.I,
    ),
    "compares_baselines": re.compile(
        r"baseline|we\s+compare|compared\s+(?:with|to|against)|"
        r"outperform|state[- ]of[- ]the[- ]art|sota",
        re.I,
    ),
    "has_limitations": re.compile(
        r"limitations?|threats\s+to\s+validity|future\s+work|scope|bias",
        re.I,
    ),
    "has_statistical_tests": re.compile(
        r"wilcoxon|t-test|anova|bootstrap|confidence\s+interval|p[- ]value|significance",
        re.I,
    ),
}


def extract_content_features(row: dict) -> dict:
    raw_text = (row.get("raw_text") or "")[:60000]
    abstract = row.get("abstract") or ""
    keywords = row.get("keywords") or ""
    title = row.get("title") or ""
    full_text = clean_text(" ".join([title, abstract, keywords, raw_text]))
    return {name: 1.0 if pattern.search(full_text) else 0.0 for name, pattern in CONTENT_PATTERNS.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Discover paper-content reproducibility features plus a small SVD block."
    )
    parser.add_argument("--min-model-chars", type=int, default=500)
    parser.add_argument("--max-tfidf-features", type=int, default=20000)
    parser.add_argument("--n-svd-components", type=int, default=16)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--max-df", type=float, default=0.95)
    args = parser.parse_args()

    ensure_dir(OUT_FEATURES_PATH.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Input missing or empty: {IN_FILE}")

    df = pd.DataFrame(rows)
    required = {"paper_uid", "model_text"}
    if not required.issubset(df.columns):
        raise ValueError(f"extracted_text.jsonl must contain: {required}")

    df["model_text"] = df["model_text"].fillna("").astype(str).map(clean_text)
    df = df[df["model_text"].str.len() >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    if len(df) < 20:
        raise RuntimeError("Too few usable rows. Lower --min-model-chars or extract more PDFs.")

    paper_uids = df["paper_uid"].tolist()
    row_by_uid = {str(row.get("paper_uid", "")): row for row in rows}

    explicit_cols = list(CONTENT_PATTERNS.keys())
    explicit_matrix = np.array(
        [
            [extract_content_features(row_by_uid.get(uid, {})).get(col, 0.0) for col in explicit_cols]
            for uid in paper_uids
        ],
        dtype=float,
    )

    texts = df["model_text"].tolist()
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=args.min_df,
        max_df=args.max_df,
        max_features=args.max_tfidf_features,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(texts)

    n_components = min(args.n_svd_components, max(2, X.shape[0] - 1), max(2, X.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    Z_svd = svd.fit_transform(X)
    svd_cols = [f"svd_feature_{i:02d}" for i in range(Z_svd.shape[1])]

    Z = np.hstack([explicit_matrix, Z_svd])
    feature_cols = explicit_cols + svd_cols

    feature_df = pd.DataFrame(Z, columns=feature_cols)
    feature_df.insert(0, "paper_uid", paper_uids)
    feature_df.to_csv(OUT_MATRIX_CSV, index=False)

    terms = np.array(vectorizer.get_feature_names_out())
    discovered_terms = {}
    for i, comp in enumerate(svd.components_):
        top_idx = np.argsort(comp)[-15:][::-1]
        discovered_terms[f"svd_feature_{i:02d}"] = terms[top_idx].tolist()

    joblib.dump(
        {
            "paper_uids": paper_uids,
            "feature_columns": feature_cols,
            "explicit_feature_columns": explicit_cols,
            "svd_feature_columns": svd_cols,
            "matrix": Z,
            "explicit_matrix": explicit_matrix,
            "vectorizer": vectorizer,
            "svd": svd,
            "content_pattern_names": explicit_cols,
        },
        OUT_FEATURES_PATH,
    )

    OUT_TERMS_PATH.write_text(json.dumps(discovered_terms, indent=2), encoding="utf-8")

    explicit_hit_rates = {col: float(explicit_matrix[:, i].mean()) for i, col in enumerate(explicit_cols)}
    report = {
        "input_rows_after_filtering": int(len(df)),
        "explicit_features": len(explicit_cols),
        "svd_components": int(n_components),
        "tfidf_vocab_size": int(len(vectorizer.get_feature_names_out())),
        "total_features": len(feature_cols),
        "svd_explained_variance_ratio_sum": float(svd.explained_variance_ratio_.sum()),
        "explicit_feature_hit_rates": explicit_hit_rates,
        "feature_matrix_csv": str(OUT_MATRIX_CSV),
        "feature_terms_json": str(OUT_TERMS_PATH),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Feature artifact saved to: {OUT_FEATURES_PATH}")
    print(f"✅ Feature matrix CSV saved to: {OUT_MATRIX_CSV}")
    print(f"✅ Feature term summary saved to: {OUT_TERMS_PATH}")
    print(f"✅ Explicit features: {len(explicit_cols)}, SVD features: {n_components}")


if __name__ == "__main__":
    main()