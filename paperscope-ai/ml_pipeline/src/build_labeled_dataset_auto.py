"""
build_labeled_dataset_auto.py — Domain-aware labeled dataset builder.

Labeling priority:
  1. Reviewer text (OpenReview papers only — highest precision)
  2. Editorial decision text (OpenReview papers only)
  3. LLM-as-judge (if API key available and --use-llm flag set)
  4. Feature-based fallback with domain-specific rules

No leakage: train_text_input = model_text (paper body only, never review text).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import (
    ATTRIBUTE_ORDER,
    SUPPORTED_DOMAINS,
    get_domain_labeling_weights,
    get_domain_llm_prompt,
    validate_domain,
)
from utils import ensure_dir, write_json, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
RESERVED_UIDS_FILE = PIPELINE_DIR / "data" / "gold_eval" / "reserved_uids.txt"

# Output paths (domain-specific)
PROCESSED_DIR = PIPELINE_DIR / "data" / "processed"
REPORT_DIR = PIPELINE_DIR / "outputs" / "reports"

POS_PATTERNS_RAW = [
    r"\bcode (?:is|was|has been)?\s*(?:available|released|shared|provided)\b",
    r"\bsource code (?:is|was|has been)?\s*(?:available|released|shared|provided)\b",
    r"\bartifact(?:s)? (?:are|is|were)?\s*(?:available|released|shared|provided)\b",
    r"\breproducib(?:ility|le) (?:is )?(?:good|strong|excellent|verified)\b",
    r"\bwell[- ]documented implementation\b",
    r"\bthe paper is reproducible\b",
    r"\bthe experiments are reproducible\b",
]

NEG_PATTERNS_RAW = [
    r"\bno (?:public )?(?:code|implementation|artifact)\b",
    r"\bwithout (?:code|implementation|artifact)\b",
    r"\breproducib(?:ility )?(?:concern|issue|problem|unclear)\b",
    r"\bmissing (?:detail|details|hyperparameter|hyperparameters|training details|implementation details)\b",
    r"\black(?:s|ing)? (?:code|detail|details|reproducibility|implementation)\b",
    r"\bnot reproducible\b",
    r"\bcannot be reproduced\b",
    r"\bcould not be reproduced\b",
    r"\bno clear (?:code|artifact|implementation)\b",
]

import re
POS_PATTERNS = [re.compile(p, re.I) for p in POS_PATTERNS_RAW]
NEG_PATTERNS = [re.compile(p, re.I) for p in POS_PATTERNS_RAW]
NEG_PATTERNS = [re.compile(p, re.I) for p in NEG_PATTERNS_RAW]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_val(row: pd.Series, key: str, default: float = 0.0) -> float:
    return safe_float(row.get(key, default), default)


def get_state(row: pd.Series, key: str) -> str:
    return str(row.get(f"{key}_state", "") or "").strip().upper()


def load_reserved_uids() -> set[str]:
    if not RESERVED_UIDS_FILE.exists():
        return set()
    return {
        line.strip()
        for line in RESERVED_UIDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


# ---------------------------------------------------------------------------
# Text labeling (review/decision text only — NOT model_text)
# ---------------------------------------------------------------------------
def label_from_text(text: str):
    text = str(text or "").strip()
    if not text:
        return None, 0.0, 0, 0
    pos_hits = sum(1 for p in POS_PATTERNS if p.search(text))
    neg_hits = sum(1 for p in NEG_PATTERNS if p.search(text))
    if pos_hits > 0 and neg_hits == 0:
        return "YES", (0.97 if pos_hits >= 2 else 0.95), pos_hits, neg_hits
    if neg_hits > 0 and pos_hits == 0:
        return "NO", (0.97 if neg_hits >= 2 else 0.95), pos_hits, neg_hits
    return None, 0.0, pos_hits, neg_hits


# ---------------------------------------------------------------------------
# LLM quick-label (lightweight version, called per-row when no review text)
# ---------------------------------------------------------------------------
def llm_quick_label(
    model_text: str,
    domain: str,
    provider: str,
    model_name: str,
) -> tuple[str | None, float, str]:
    """
    Call LLM for a quick YES/NO label with confidence.
    Returns (label, confidence, reason).
    """
    system_prompt = get_domain_llm_prompt(domain)
    raw: dict | None = None

    if provider == "openai":
        try:
            import openai
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return None, 0.0, "no_api_key"
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": model_text[:40_000]},
                ],
                temperature=0.1,
                max_tokens=128,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content or "{}")
        except Exception as e:
            return None, 0.0, f"openai_error: {e}"
    elif provider == "gemini":
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GOOGLE_API_KEY", "")
            if not api_key:
                return None, 0.0, "no_api_key"
            genai.configure(api_key=api_key)
            gem = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1, max_output_tokens=128,
                    response_mime_type="application/json",
                ),
            )
            resp = gem.generate_content(model_text[:30_000])
            raw = json.loads(resp.text)
        except Exception as e:
            return None, 0.0, f"gemini_error: {e}"
    else:
        return None, 0.0, "unknown_provider"

    if raw is None:
        return None, 0.0, "null_response"

    label_raw = str(raw.get("label", "")).strip().upper()
    score_raw = raw.get("score", raw.get("reproducibility_score", None))
    reason = str(raw.get("reason", "llm_label"))[:200]

    if label_raw in ("YES", "NO"):
        return label_raw, 0.88, reason

    if score_raw is not None:
        try:
            score = float(score_raw)
            label = "YES" if score >= 60 else "NO"
            return label, 0.85, reason
        except Exception:
            pass

    return None, 0.0, "unparseable_response"


# ---------------------------------------------------------------------------
# Feature-based fallback (domain-aware)
# ---------------------------------------------------------------------------
CORE_POSITIVE_ATTRS = [
    "code_artifact", "data_artifact", "execution_instructions",
    "hyperparams_detail", "evaluation_protocol", "software_versions",
]
CORE_NEGATIVE_ATTRS = [
    "code_artifact", "execution_instructions",
    "hyperparams_detail", "evaluation_protocol", "software_versions",
]
SUPPORTING_ATTRS = [
    "availability_statement", "seed_disclosed", "compute_detail",
    "ablation", "baseline_comparison", "statistical_rigor", "limitations",
]


def weighted_positive_support(row: pd.Series, labeling_weights: dict) -> float:
    score = 0.0
    for attr, weight in labeling_weights.items():
        v = get_val(row, attr, 0.0)
        if v >= 1.0:
            score += weight
        elif v >= 0.5:
            score += weight * 0.5
    return score


def count_core_supported(row: pd.Series) -> int:
    return sum(1 for a in CORE_POSITIVE_ATTRS if get_val(row, a, 0.0) >= 0.5)


def count_core_missing(row: pd.Series) -> int:
    return sum(1 for a in CORE_NEGATIVE_ATTRS if get_val(row, a, 0.0) <= 0.0)


def count_partial_core_missing(row: pd.Series) -> int:
    return sum(1 for a in CORE_NEGATIVE_ATTRS if get_val(row, a, 0.0) < 0.5)


def decide_feature_fallback(
    row: pd.Series,
    domain: str,
    labeling_weights: dict,
) -> tuple[str | None, float, str]:
    rs = get_val(row, "reproducibility_score", 0.0)
    pw = weighted_positive_support(row, labeling_weights)
    cs = count_core_supported(row)
    cm = count_core_missing(row)
    pm = count_partial_core_missing(row)

    co = get_val(row, "code_artifact", 0.0)
    da = get_val(row, "data_artifact", 0.0)
    ex = get_val(row, "execution_instructions", 0.0)
    hy = get_val(row, "hyperparams_detail", 0.0)
    ev = get_val(row, "evaluation_protocol", 0.0)
    sw = get_val(row, "software_versions", 0.0)
    se = get_val(row, "seed_disclosed", 0.0)
    av = get_val(row, "availability_statement", 0.0)
    st = get_val(row, "statistical_rigor", 0.0)

    code_state = get_state(row, "code_artifact")
    data_state = get_state(row, "data_artifact")
    avail_state = get_state(row, "availability_statement")

    # --- Domain-specific anchor signals ---
    # For biomed/finance, data_artifact matters MORE than code_artifact
    # For physics, statistical_rigor + compute are key
    # For math, statistical_rigor + evaluation matter most
    # For hardware, code + execution are the main signals

    primary_artifact = co  # default: code
    if domain in ("biomed", "finance"):
        primary_artifact = max(co, da)   # data is equally important
    elif domain == "math":
        primary_artifact = max(co, st)   # proofs or stat rigor

    # =========================================================================
    # YES RULES
    # =========================================================================
    if rs >= 90.0 and cm <= 1:
        return "YES", 0.87, "yes_extreme_high_score"

    if rs >= 82.0 and cs >= 3 and pw >= 6.0 and ev >= 0.5:
        return "YES", 0.83, "yes_strong_high_score_consensus"

    if rs >= 74.0 and cs >= 4 and pw >= 7.0:
        return "YES", 0.80, "yes_strong_broad_consensus"

    if rs >= 70.0 and primary_artifact >= 0.5 and hy >= 0.5 and ev >= 0.5 and (ex >= 0.5 or sw >= 0.5 or da >= 0.5) and pw >= 6.0:
        return "YES", 0.78, "yes_core_reproducibility_signals"

    if rs >= 68.0 and cs >= 3 and sum(1 for a in SUPPORTING_ATTRS if get_val(row, a, 0.0) >= 0.5) >= 2 and pw >= 6.2 and cm <= 1:
        return "YES", 0.75, "yes_moderate_consensus"

    if rs >= 72.0 and (code_state == "SUPPORTED" or co >= 1.0) and hy >= 0.5 and ev >= 0.5 and (av >= 0.5 or ex >= 0.5 or da >= 0.5):
        return "YES", 0.79, "yes_artifact_plus_method_detail"

    # Expanded YES tier
    if rs >= 63.0 and primary_artifact >= 0.5 and hy >= 0.5 and ev >= 0.5 and cm <= 2:
        return "YES", 0.74, "yes_artifact_with_method_detail"

    if rs >= 60.0 and da >= 1.0 and ex >= 0.5 and hy >= 0.5 and ev >= 0.5:
        return "YES", 0.73, "yes_data_release_with_exec_instructions"

    if rs >= 60.0 and code_state == "SUPPORTED" and cs >= 3 and pw >= 5.0:
        return "YES", 0.73, "yes_confirmed_code_multi_signal"

    # Biomed-specific: registered protocol + data deposition = YES
    if domain == "biomed" and rs >= 55.0 and da >= 1.0 and st >= 1.0 and av >= 1.0:
        return "YES", 0.76, "yes_biomed_registered_protocol_with_data"

    # Physics-specific: simulation code + data + stats = YES
    if domain == "physics" and rs >= 58.0 and (co >= 0.5 or ex >= 0.5) and st >= 1.0 and da >= 0.5:
        return "YES", 0.74, "yes_physics_simulation_with_data_and_stats"

    # Finance-specific: data source + methodology + stats = YES
    if domain == "finance" and rs >= 58.0 and da >= 1.0 and st >= 1.0 and hy >= 0.5:
        return "YES", 0.74, "yes_finance_data_with_methodology"

    # =========================================================================
    # NO RULES
    # =========================================================================
    if rs <= 12.0:
        return "NO", 0.88, "no_extreme_low_score"

    if rs <= 18.0 and cm >= 4:
        return "NO", 0.86, "no_very_low_score_extreme_missing"

    if rs <= 24.0 and cm >= 3 and pw <= 1.5:
        return "NO", 0.83, "no_low_score_high_missing_low_support"

    if rs <= 30.0 and co == 0 and ex == 0 and hy < 0.5 and ev < 0.5 and pm >= 4:
        return "NO", 0.79, "no_missing_core_signals"

    if rs <= 34.0 and cm >= 3 and pw <= 2.0 and av == 0 and se == 0:
        return "NO", 0.75, "no_moderate_consensus_no_artifacts"

    if rs <= 38.0 and code_state == "NOT_FOUND" and data_state == "NOT_FOUND" and ex == 0 and ev < 0.5 and hy < 0.5:
        return "NO", 0.72, "no_artifact_and_method_sparse_original"

    # Expanded NO: the dead zone (38–60%)
    # Anchored on: no primary artifact AND no execution instructions
    # Domain-specific: for biomed/finance, no data is the anchor
    primary_missing = (co == 0.0) if domain not in ("biomed", "finance") else (co == 0.0 and da <= 0.5)

    if rs <= 60.0 and primary_missing and ex == 0 and av <= 0.5 and se == 0 and cm >= 2:
        return "NO", 0.73, "no_expanded_primary_artifact_gap"

    if rs <= 55.0 and co == 0 and ex == 0 and cm >= 2 and hy <= 0.5 and pw <= 7.5:
        return "NO", 0.72, "no_expanded_no_code_limited_detail"

    if rs <= 48.0 and co == 0 and ex == 0 and se == 0 and hy <= 0.5 and cm >= 2:
        return "NO", 0.71, "no_expanded_low_score_sparse_detail"

    if rs <= 50.0 and co == 0 and ex == 0 and se == 0 and sw <= 0.5 and cm >= 2:
        return "NO", 0.70, "no_expanded_no_code_exec_seed"

    if rs <= 45.0 and co == 0 and ex == 0 and cm >= 2 and pw <= 5.0:
        return "NO", 0.70, "no_expanded_sparse_middle_zone"

    # Physics: no simulation, no data, no stats = NO
    if domain == "physics" and rs <= 55.0 and co == 0 and da <= 0.5 and st <= 0.5:
        return "NO", 0.71, "no_physics_no_simulation_data_or_stats"

    # Biomed: no data accession AND no protocol = NO
    if domain == "biomed" and rs <= 55.0 and da == 0 and av <= 0.5 and st <= 0.5:
        return "NO", 0.71, "no_biomed_no_data_no_protocol"

    # Finance: no data source AND no methodology = NO
    if domain == "finance" and rs <= 50.0 and da <= 0.5 and hy <= 0.5 and st <= 0.5:
        return "NO", 0.71, "no_finance_no_data_no_methodology"

    # =========================================================================
    # GUARDRAILS
    # =========================================================================
    if rs >= 68.0 and cs <= 2 and co == 0 and ex == 0:
        return None, 0.0, "guardrail_high_score_no_code_no_exec"

    if rs <= 42.0 and pw >= 5.0 and cs >= 3:
        return None, 0.0, "guardrail_low_score_with_strong_positive_support"

    if (
        rs < 60.0
        and get_state(row, "seed_disclosed") == "PARTIAL"
        and cs < 2
        and co == 0
        and ex == 0
    ):
        return None, 0.0, "guardrail_seed_partial_near_only_signal"

    return None, 0.0, "ambiguous"


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------
def split_and_save(
    df: pd.DataFrame,
    out_dir: Path,
    domain: str,
    val_ratio: float,
    test_ratio: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        raise ValueError("Cannot split an empty labeled dataset.")

    label_counts = df["repro_label"].value_counts()
    if len(label_counts) < 2 or int(label_counts.min()) < 3:
        raise RuntimeError(
            f"Need at least 2 classes with ≥3 rows each. "
            f"Got: {label_counts.to_dict()}"
        )

    holdout = val_ratio + test_ratio
    train_df, holdout_df = train_test_split(
        df, test_size=holdout, random_state=random_state, stratify=df["repro_label"]
    )
    test_share = test_ratio / holdout
    val_df, test_df = train_test_split(
        holdout_df, test_size=test_share, random_state=random_state, stratify=holdout_df["repro_label"]
    )

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if len(split_df) < 10:
            raise RuntimeError(f"Split {split_name!r} has only {len(split_df)} rows.")
        if not {"YES", "NO"}.issubset(set(split_df["repro_label"].unique())):
            raise RuntimeError(f"Split {split_name!r} is missing a class.")

    train_df = train_df.reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    ensure_dir(out_dir)
    train_df.to_csv(out_dir / "train.csv", index=False)
    val_df.to_csv(out_dir / "val.csv", index=False)
    test_df.to_csv(out_dir / "test.csv", index=False)

    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Domain-aware labeled dataset builder with LLM integration."
    )
    parser.add_argument("--domain", default="", help="Filter to a specific domain (empty = all domains).")
    parser.add_argument("--min-rows", type=int, default=50)
    parser.add_argument("--enable-feature-fallback", action="store_true", default=True)
    parser.add_argument("--use-llm", action="store_true", default=False, help="Use LLM for papers without review text.")
    parser.add_argument("--llm-provider", choices=["openai", "gemini"], default="openai")
    parser.add_argument("--llm-model", default="", help="LLM model override.")
    parser.add_argument("--llm-max-papers", type=int, default=500, help="Max papers to send to LLM.")
    parser.add_argument("--llm-sleep", type=float, default=1.5, help="Sleep between LLM calls.")
    parser.add_argument("--min-label-confidence", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    ensure_dir(PROCESSED_DIR)
    ensure_dir(REPORT_DIR)

    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing: {IN_FILE}\nRun auto_weight_and_score.py first.")

    df = pd.read_csv(IN_FILE)
    required_cols = {"paper_uid", "model_text", "reproducibility_score", "risk_score"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"auto_scored_papers.csv missing columns: {sorted(missing_cols)}")

    df = df.copy()
    df["paper_uid"] = df["paper_uid"].fillna("").astype(str)
    df["model_text"] = df["model_text"].fillna("").astype(str)
    if "review_text" not in df.columns:
        df["review_text"] = ""
    if "decision_text" not in df.columns:
        df["decision_text"] = ""
    df["review_text"] = df["review_text"].fillna("").astype(str)
    df["decision_text"] = df["decision_text"].fillna("").astype(str)
    if "domain" not in df.columns:
        df["domain"] = "ml"
    df["domain"] = df["domain"].fillna("ml").astype(str)

    # Filter by domain if specified
    if args.domain:
        domain_filter = validate_domain(args.domain)
        df = df[df["domain"] == domain_filter].copy()
        if df.empty:
            raise RuntimeError(f"No rows found for domain {domain_filter!r}")

    # Drop reserved gold-eval UIDs
    reserved = load_reserved_uids()
    if reserved:
        before = len(df)
        df = df[~df["paper_uid"].isin(reserved)].copy()
        print(f"📋 Reserved UIDs excluded: {before - len(df)} rows")

    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    llm_model = args.llm_model or ("gpt-4o" if args.llm_provider == "openai" else "gemini-1.5-pro")
    llm_calls_made = 0

    stats = {
        "input_rows": int(len(df)),
        "labeled_from_reviewer_text": 0,
        "labeled_from_decision_text": 0,
        "labeled_from_llm": 0,
        "labeled_from_feature_fallback": 0,
        "dropped_ambiguous": 0,
        "dropped_below_confidence": 0,
    }

    labels: list[str | None] = []
    sources: list[str] = []
    confidences: list[float] = []
    reasons: list[str] = []
    r_pos_list: list[int] = []
    r_neg_list: list[int] = []
    d_pos_list: list[int] = []
    d_neg_list: list[int] = []

    for _, row in df.iterrows():
        row_domain = str(row.get("domain", "ml") or "ml")
        if row_domain not in SUPPORTED_DOMAINS:
            row_domain = "ml"
        labeling_weights = get_domain_labeling_weights(row_domain)

        review_text = str(row.get("review_text", "") or "")
        decision_text = str(row.get("decision_text", "") or "")

        # Step 1: reviewer text
        label, conf, r_pos, r_neg = label_from_text(review_text)
        r_pos_list.append(r_pos); r_neg_list.append(r_neg)

        if label is not None:
            labels.append(label); sources.append("review_text")
            confidences.append(conf); reasons.append("review_text_high_precision")
            d_pos_list.append(0); d_neg_list.append(0)
            stats["labeled_from_reviewer_text"] += 1
            continue

        # Step 2: decision text
        label, conf, d_pos, d_neg = label_from_text(decision_text)
        d_pos_list.append(d_pos); d_neg_list.append(d_neg)

        if label is not None:
            labels.append(label); sources.append("decision_text")
            confidences.append(conf); reasons.append("decision_text_high_precision")
            stats["labeled_from_decision_text"] += 1
            continue

        # Step 3: LLM (optional)
        if args.use_llm and llm_calls_made < args.llm_max_papers:
            model_text = str(row.get("model_text", ""))
            if len(model_text) >= 1200:
                lbl, conf, rsn = llm_quick_label(model_text, row_domain, args.llm_provider, llm_model)
                llm_calls_made += 1
                time.sleep(args.llm_sleep)
                if lbl is not None and conf >= args.min_label_confidence:
                    labels.append(lbl); sources.append("llm")
                    confidences.append(conf); reasons.append(f"llm_{rsn[:80]}")
                    stats["labeled_from_llm"] += 1
                    continue

        # Step 4: feature fallback
        label, conf, reason = None, 0.0, "ambiguous"
        if args.enable_feature_fallback:
            label, conf, reason = decide_feature_fallback(row, row_domain, labeling_weights)

        if label is not None and conf >= args.min_label_confidence:
            labels.append(label); sources.append("feature_consensus")
            confidences.append(conf); reasons.append(reason)
            stats["labeled_from_feature_fallback"] += 1
            continue

        if label is not None:
            stats["dropped_below_confidence"] += 1

        labels.append(None); sources.append("dropped")
        confidences.append(0.0); reasons.append(reason)
        stats["dropped_ambiguous"] += 1

    df["repro_label"] = labels
    df["label_source"] = sources
    df["label_confidence"] = confidences
    df["label_reason"] = reasons
    df["review_pos_hits"] = r_pos_list
    df["review_neg_hits"] = r_neg_list
    df["decision_pos_hits"] = d_pos_list
    df["decision_neg_hits"] = d_neg_list

    # LEAKAGE GUARD: training text is always model_text only
    df["train_text_input"] = df["model_text"]
    df["training_text_source"] = "model_text_only"
    df["schema_version"] = PIPELINE_SCHEMA_VERSION

    labeled_df = df[df["repro_label"].notna()].copy().reset_index(drop=True)

    if len(labeled_df) < args.min_rows:
        raise RuntimeError(
            f"Only {len(labeled_df)} rows labeled (minimum={args.min_rows}). "
            "Try --use-llm to label more papers."
        )

    # Save per-domain split files and combined labeled dataset
    # Combined output
    out_csv = PROCESSED_DIR / "labeled_dataset.csv"
    labeled_df.to_csv(out_csv, index=False)

    # Unified splits (train_tfidf_logreg.py reads these)
    train_df, val_df, test_df = split_and_save(
        labeled_df,
        out_dir=PROCESSED_DIR,
        domain=args.domain or "all",
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        random_state=args.random_state,
    )

    report = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "input_rows": stats["input_rows"],
        "rows_labeled": int(len(labeled_df)),
        "domain_filter": args.domain or "all",
        "dropped_ambiguous": stats["dropped_ambiguous"],
        "dropped_below_confidence": stats["dropped_below_confidence"],
        "labeled_from_reviewer_text": stats["labeled_from_reviewer_text"],
        "labeled_from_decision_text": stats["labeled_from_decision_text"],
        "labeled_from_llm": stats["labeled_from_llm"],
        "labeled_from_feature_fallback": stats["labeled_from_feature_fallback"],
        "llm_calls_made": llm_calls_made,
        "label_counts": {str(k): int(v) for k, v in labeled_df["repro_label"].value_counts().to_dict().items()},
        "label_source_counts": {str(k): int(v) for k, v in labeled_df["label_source"].value_counts().to_dict().items()},
        "domain_label_counts": {
            dom: {str(k): int(v) for k, v in grp["repro_label"].value_counts().to_dict().items()}
            for dom, grp in labeled_df.groupby("domain")
        },
        "split": {
            "train_rows": int(len(train_df)),
            "val_rows": int(len(val_df)),
            "test_rows": int(len(test_df)),
            "stratified": True,
        },
        "leakage_guard": "train_text_input == model_text (review/decision text EXCLUDED from training)",
    }
    write_json(REPORT_DIR / "labeling_summary.json", report)

    print(f"✅ Labeled dataset ({len(labeled_df)} rows) → {out_csv}")
    print(f"✅ Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
    print(f"   Labels: {dict(labeled_df['repro_label'].value_counts())}")
    print(f"   Sources: {dict(labeled_df['label_source'].value_counts())}")


if __name__ == "__main__":
    main()
