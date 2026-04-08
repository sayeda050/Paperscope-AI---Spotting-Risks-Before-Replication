import sys
from pathlib import Path
import json
import argparse

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


def main():
    parser = argparse.ArgumentParser(description="Automatically discover latent PDF features using TF-IDF + TruncatedSVD.")
    parser.add_argument("--min-model-chars", type=int, default=1000)
    parser.add_argument("--max-features", type=int, default=80000)
    parser.add_argument("--n-components", type=int, default=32)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--max-df", type=float, default=0.95)
    args = parser.parse_args()

    ensure_dir(OUT_FEATURES_PATH.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Input missing or empty: {IN_FILE}")

    df = pd.DataFrame(rows)
    if "model_text" not in df.columns or "paper_uid" not in df.columns:
        raise ValueError("extracted_text.jsonl must contain 'paper_uid' and 'model_text'.")

    df["model_text"] = df["model_text"].fillna("").astype(str).map(clean_text)
    df = df[df["model_text"].str.len() >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    if len(df) < 50:
        raise RuntimeError("Too few usable rows after filtering. Lower --min-model-chars or extract more PDFs.")

    texts = df["model_text"].tolist()
    paper_uids = df["paper_uid"].tolist()

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=args.min_df,
        max_df=args.max_df,
        max_features=args.max_features,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(texts)

    n_components = min(args.n_components, max(2, X.shape[0] - 1), max(2, X.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    Z = svd.fit_transform(X)

    feature_cols = [f"latent_feature_{i:02d}" for i in range(Z.shape[1])]
    feature_df = pd.DataFrame(Z, columns=feature_cols)
    feature_df.insert(0, "paper_uid", paper_uids)
    feature_df.to_csv(OUT_MATRIX_CSV, index=False)

    terms = np.array(vectorizer.get_feature_names_out())
    discovered_terms = {}
    for i, comp in enumerate(svd.components_):
        top_idx = np.argsort(comp)[-15:][::-1]
        discovered_terms[f"latent_feature_{i:02d}"] = terms[top_idx].tolist()

    joblib.dump({
        "paper_uids": paper_uids,
        "feature_columns": feature_cols,
        "matrix": Z,
        "vectorizer": vectorizer,
        "svd": svd,
    }, OUT_FEATURES_PATH)

    OUT_TERMS_PATH.write_text(json.dumps(discovered_terms, indent=2), encoding="utf-8")

    report = {
        "input_rows_after_filtering": int(len(df)),
        "tfidf_vocab_size": int(len(vectorizer.get_feature_names_out())),
        "n_components": int(n_components),
        "explained_variance_ratio_sum": float(svd.explained_variance_ratio_.sum()),
        "feature_matrix_csv": str(OUT_MATRIX_CSV),
        "feature_terms_json": str(OUT_TERMS_PATH),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"✅ Discovered feature artifact saved to: {OUT_FEATURES_PATH}")
    print(f"✅ Feature matrix CSV saved to: {OUT_MATRIX_CSV}")
    print(f"✅ Feature term summary saved to: {OUT_TERMS_PATH}")
    print(f"✅ Discovery report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
