import sys
from pathlib import Path
import re
import pandas as pd
from sklearn.model_selection import train_test_split

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import read_jsonl, clamp, ensure_dir, clean_text

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_CSV = PIPELINE_DIR / "data" / "processed" / "labeled_dataset.csv"
TRAIN_CSV = PIPELINE_DIR / "data" / "processed" / "train.csv"
VAL_CSV = PIPELINE_DIR / "data" / "processed" / "val.csv"
TEST_CSV = PIPELINE_DIR / "data" / "processed" / "test.csv"
REPORT_DIR = PIPELINE_DIR / "outputs" / "reports"


POSITIVE_PATTERNS = {
    "has_code_link": [
        r"github\.com", r"gitlab\.com", r"bitbucket\.org",
        r"\bsource code\b", r"\bcode available\b", r"\bimplementation is available\b"
    ],
    "has_data_link": [
        r"\bdataset available\b", r"\bdata available\b", r"\bwe release the dataset\b",
        r"\bkaggle\b", r"\bzenodo\b", r"\bhuggingface\b", r"\bdatasets can be found\b"
    ],
    "has_hyperparams": [
        r"\blearning rate\b", r"\bbatch size\b", r"\bepochs?\b",
        r"\bdropout\b", r"\boptimizer\b", r"\bweight decay\b", r"\bhidden size\b"
    ],
    "has_seed": [
        r"\brandom seed\b", r"\bseed\s*=\s*\d+\b", r"\bwe use seed\b"
    ],
    "has_env_details": [
        r"\bgpu\b", r"\bcuda\b", r"\bpytorch\b", r"\btensorflow\b",
        r"\bubuntu\b", r"\bhardware\b", r"\bv100\b", r"\ba100\b"
    ],
    "has_metrics": [
        r"\baccuracy\b", r"\bf1\b", r"\bprecision\b", r"\brecall\b",
        r"\bauc\b", r"\bbleu\b", r"\brouge\b", r"\bmse\b", r"\bmae\b", r"\bperplexity\b"
    ],
    "has_baselines": [
        r"\bbaseline\b", r"\bcompared with\b", r"\bcompare against\b",
        r"\bstate[- ]of[- ]the[- ]art\b", r"\bsota\b"
    ],
    "has_ablation": [
        r"\bablation\b", r"\bablative\b", r"\bremove each component\b"
    ],
    "has_limitations": [
        r"\blimitations?\b", r"\bthreats to validity\b", r"\bfuture work\b"
    ],
    "has_statistical_tests": [
        r"\bp[- ]value\b", r"\bconfidence interval\b", r"\bstandard deviation\b",
        r"\bstd\.?\b", r"\bvariance\b"
    ],
}

NEGATIVE_PATTERNS = {
    "review_missing_details": [
        r"\bmissing details\b", r"\bnot enough details\b", r"\bunclear details\b",
        r"\binsufficient detail\b", r"\bunder[- ]specified\b"
    ],
    "review_repro_concern": [
        r"\breproducibility\b", r"\bhard to reproduce\b", r"\bdifficult to reproduce\b",
        r"\bnot reproducible\b"
    ],
    "review_code_missing": [
        r"\bno code\b", r"\bcode not provided\b", r"\bimplementation not available\b"
    ],
    "review_dataset_unclear": [
        r"\bdataset unclear\b", r"\bdata preprocessing unclear\b", r"\bdata split unclear\b"
    ],
    "review_hyperparams_unclear": [
        r"\bhyperparameters? (are )?unclear\b", r"\btraining details missing\b"
    ],
    "review_missing_ablation": [
        r"\bno ablation\b", r"\blacks ablation\b", r"\bmissing ablation\b"
    ],
    "review_weak_baselines": [
        r"\bweak baselines\b", r"\bmissing baseline\b", r"\binsufficient baseline\b"
    ],
    "review_insufficient_experiments": [
        r"\binsufficient experiments\b", r"\bmore experiments needed\b", r"\blimited evaluation\b"
    ],
}

POSITIVE_WEIGHTS = {
    "has_code_link": 1.5,
    "has_data_link": 1.5,
    "has_hyperparams": 1.0,
    "has_seed": 1.0,
    "has_env_details": 1.0,
    "has_metrics": 1.0,
    "has_baselines": 1.0,
    "has_ablation": 1.0,
    "has_limitations": 1.0,
    "has_statistical_tests": 1.0,
}

NEGATIVE_WEIGHTS = {
    "review_missing_details": 2.0,
    "review_repro_concern": 2.0,
    "review_code_missing": 1.5,
    "review_dataset_unclear": 1.0,
    "review_hyperparams_unclear": 1.0,
    "review_missing_ablation": 1.0,
    "review_weak_baselines": 1.0,
    "review_insufficient_experiments": 1.0,
}


def has_any_pattern(text: str, patterns):
    text = text or ""
    for p in patterns:
        if re.search(p, text, flags=re.I):
            return 1
    return 0


def compute_features(row):
    model_text = clean_text(row.get("model_text", ""))
    review_text = clean_text(row.get("review_text", ""))

    feats = {}
    for key, patterns in POSITIVE_PATTERNS.items():
        feats[key] = has_any_pattern(model_text, patterns)

    for key, patterns in NEGATIVE_PATTERNS.items():
        feats[key] = has_any_pattern(review_text, patterns)

    return feats


def score_and_label(feats):
    pos = sum(feats[k] * POSITIVE_WEIGHTS[k] for k in POSITIVE_WEIGHTS)
    neg = sum(feats[k] * NEGATIVE_WEIGHTS[k] for k in NEGATIVE_WEIGHTS)

    risk_score = 65 - (5 * pos) + (6 * neg)
    risk_score = round(clamp(risk_score, 0, 100), 2)

    if risk_score < 40:
        label = "LOW"
    elif risk_score < 70:
        label = "MEDIUM"
    else:
        label = "HIGH"

    weak_score = round(pos - neg, 2)
    return weak_score, risk_score, label


def split_and_save(df: pd.DataFrame):
    ensure_dir(TRAIN_CSV.parent)

    # Safety: if model_text is missing, stop with clear message
    if "model_text" not in df.columns:
        raise RuntimeError(
            "Column 'model_text' not found. "
            "You must run extract_text.py successfully before build_labels.py."
        )

    # Remove empty / tiny texts
    df = df[df["model_text"].fillna("").astype(str).str.len() > 300].copy()

    if len(df) == 0:
        raise RuntimeError(
            "No usable rows left after filtering. "
            "Check extracted_text.jsonl and make sure PDFs were downloaded and text was extracted."
        )

    # If too small, save all in train
    if len(df) < 20:
        df.to_csv(TRAIN_CSV, index=False)
        pd.DataFrame(columns=df.columns).to_csv(VAL_CSV, index=False)
        pd.DataFrame(columns=df.columns).to_csv(TEST_CSV, index=False)
        return

    stratify = df["risk_label"] if df["risk_label"].nunique() > 1 else None

    train_df, temp_df = train_test_split(
        df,
        test_size=0.30,
        random_state=42,
        stratify=stratify,
    )

    temp_stratify = temp_df["risk_label"] if temp_df["risk_label"].nunique() > 1 else None

    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=42,
        stratify=temp_stratify,
    )

    train_df.to_csv(TRAIN_CSV, index=False)
    val_df.to_csv(VAL_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)


def main():
    ensure_dir(REPORT_DIR)

    if not IN_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {IN_FILE}\n"
            f"Run these first:\n"
            f"1. python src\\collect_openreview.py\n"
            f"2. python src\\link_arxiv.py\n"
            f"3. python src\\download_arxiv_pdfs.py\n"
            f"4. python src\\extract_text.py"
        )

    rows = read_jsonl(IN_FILE)

    if not rows:
        raise RuntimeError(
            f"{IN_FILE} is empty.\n"
            f"That means extract_text.py did not produce any extracted rows."
        )

    out_rows = []
    for row in rows:
        # fallback if model_text missing
        model_text = clean_text(row.get("model_text", ""))

        if not model_text:
            title = clean_text(row.get("title", ""))
            abstract = clean_text(row.get("abstract", ""))
            raw_text = clean_text(row.get("raw_text", ""))
            model_text = clean_text(f"{title}. {abstract}. {raw_text}")

        enriched_row = dict(row)
        enriched_row["model_text"] = model_text

        feats = compute_features(enriched_row)
        weak_score, risk_score, risk_label = score_and_label(feats)

        out_rows.append({
            "paper_uid": row.get("paper_uid", ""),
            "source": row.get("source", ""),
            "venue": row.get("venue", ""),
            "year": row.get("year", ""),
            "openreview_id": row.get("openreview_id", ""),
            "forum_id": row.get("forum_id", ""),
            "arxiv_id": row.get("arxiv_id", ""),
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "review_text": row.get("review_text", ""),
            "model_text": model_text,
            **feats,
            "weak_score": weak_score,
            "risk_score": risk_score,
            "risk_label": risk_label,
        })

    df = pd.DataFrame(out_rows)

    if df.empty:
        raise RuntimeError("No rows available to build labels.")

    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    ensure_dir(OUT_CSV.parent)
    df.to_csv(OUT_CSV, index=False)

    split_and_save(df)

    label_dist = (
        df["risk_label"]
        .value_counts(dropna=False)
        .rename_axis("risk_label")
        .reset_index(name="count")
    )
    label_dist.to_csv(REPORT_DIR / "label_distribution.csv", index=False)

    feature_cols = list(POSITIVE_PATTERNS.keys()) + list(NEGATIVE_PATTERNS.keys())
    feature_sums = pd.DataFrame({
        "feature": feature_cols,
        "count": [int(df[c].sum()) for c in feature_cols]
    })
    feature_sums.to_csv(REPORT_DIR / "feature_counts.csv", index=False)

    print(f"✅ Labeled dataset saved to: {OUT_CSV}")
    print(f"✅ Train split saved to: {TRAIN_CSV}")
    print(f"✅ Val split saved to: {VAL_CSV}")
    print(f"✅ Test split saved to: {TEST_CSV}")
    print(f"✅ Label distribution report saved to: {REPORT_DIR / 'label_distribution.csv'}")


if __name__ == "__main__":
    main()