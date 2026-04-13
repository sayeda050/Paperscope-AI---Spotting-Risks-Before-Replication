"""
discover_pdf_features.py — Domain-aware feature extraction.

Reads extracted_text.jsonl, applies domain-specific regex patterns from
domain_config.py, and produces feature records for every paper.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import (
    ATTRIBUTE_ORDER,
    DOMAIN_ATTRIBUTE_WEIGHTS,
    get_domain_patterns,
    get_domain_weights,
    validate_domain,
)
from utils import (
    PIPELINE_SCHEMA_VERSION,
    clean_multiline_text,
    clean_text,
    count_pattern_hits,
    ensure_dir,
    find_pattern_snippets,
    read_jsonl,
    sentence_split,
    write_json,
    write_jsonl,
)

PIPELINE_DIR = SRC_DIR.parent
IN_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_FEATURES_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_features.joblib"
OUT_MATRIX_CSV = PIPELINE_DIR / "data" / "processed" / "discovered_feature_matrix.csv"
OUT_RECORDS_JSONL = PIPELINE_DIR / "data" / "processed" / "discovered_feature_records.jsonl"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "feature_discovery_report.json"

DEFAULT_DOMAIN = "ml"


# ---------------------------------------------------------------------------
# Text combination
# ---------------------------------------------------------------------------
def combine_text(row: dict) -> str:
    parts: list[str] = []
    title = clean_text(row.get("title", ""))
    abstract = clean_text(row.get("abstract", ""))
    keywords = clean_text(row.get("keywords", ""))
    raw = clean_multiline_text(row.get("raw_text", "") or row.get("model_text", ""))
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    if keywords:
        parts.append(f"Keywords: {keywords}")
    if raw:
        parts.append(raw)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def dedupe_snippets(snippets: Iterable[str], max_items: int = 3) -> list[str]:
    out: list[str] = []
    for s in snippets:
        s = clean_text(s)
        if not s or s in out:
            continue
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def state_record(
    name: str,
    value: float,
    positive: list[str],
    negative: list[str],
    notes: str = "",
) -> dict:
    if value >= 0.99:
        state = "SUPPORTED"
    elif value >= 0.49:
        state = "PARTIAL"
    else:
        state = "NOT_FOUND"
    return {
        "name": name,
        "value": float(value),
        "state": state,
        "positive_evidence": dedupe_snippets(positive),
        "negative_evidence": dedupe_snippets(negative),
        "notes": clean_text(notes),
    }


# ---------------------------------------------------------------------------
# Per-attribute evaluators (domain-aware)
# ---------------------------------------------------------------------------
def evaluate_code_artifact(text: str, patterns: dict) -> dict:
    pos = find_pattern_snippets(text, patterns.get("code_url", []) + patterns.get("code_claim", []))
    neg = find_pattern_snippets(text, patterns.get("code_negative", []))
    partial = find_pattern_snippets(text, patterns.get("code_future", []))
    # Domain-specific: hardware artifact, math artifact count as code
    extra_pos = find_pattern_snippets(
        text,
        patterns.get("hardware_artifact", []) + patterns.get("math_artifact", []),
    )
    all_pos = dedupe_snippets(pos + extra_pos)
    if all_pos:
        if neg:
            return state_record(
                "code_artifact", 0.5, all_pos, neg,
                "Code/artifact availability found alongside negative signals; review recommended.",
            )
        return state_record("code_artifact", 1.0, all_pos, neg)
    if partial:
        return state_record("code_artifact", 0.5, partial, neg, "Future/deferred release statement.")
    return state_record("code_artifact", 0.0, [], neg)


def evaluate_data_artifact(text: str, patterns: dict) -> dict:
    strong = find_pattern_snippets(text, patterns.get("data_url", []))
    pos = find_pattern_snippets(text, patterns.get("data_claim", []))
    biomed_pos = find_pattern_snippets(text, patterns.get("biomed_data", []))
    fin_pos = find_pattern_snippets(text, patterns.get("finance_data", []))
    partial = find_pattern_snippets(text, patterns.get("data_future", []))

    all_strong = dedupe_snippets(strong + biomed_pos + fin_pos)
    if all_strong:
        return state_record("data_artifact", 1.0, all_strong, [])
    if pos:
        has_benchmark_only = all("publicly available benchmark" in s.lower() for s in pos)
        note = (
            "Paper references public benchmarks but no direct dataset URL detected."
            if has_benchmark_only
            else "Data availability claim found; no direct repository URL detected."
        )
        return state_record("data_artifact", 0.5, pos, [], note)
    if partial:
        return state_record("data_artifact", 0.5, partial, [], "Future data release statement.")
    return state_record("data_artifact", 0.0, [], [])


def evaluate_availability_statement(text: str, patterns: dict) -> dict:
    confirmed = find_pattern_snippets(text, patterns.get("availability_confirmed", []))
    partial = find_pattern_snippets(text, patterns.get("availability_partial", []))
    # Biomed: reagent / protocol registration also count as confirmed
    biomed_confirmed = find_pattern_snippets(
        text,
        patterns.get("biomed_reagents", []) + patterns.get("biomed_protocol", []),
    )
    all_confirmed = dedupe_snippets(confirmed + biomed_confirmed)
    if all_confirmed:
        return state_record(
            "availability_statement", 1.0, all_confirmed, [],
            "Confirmed availability or registration statement detected.",
        )
    if partial:
        return state_record(
            "availability_statement", 0.5, partial, [],
            "Partial/conditional availability statement.",
        )
    return state_record("availability_statement", 0.0, [], [])


def evaluate_execution_instructions(text: str, patterns: dict) -> dict:
    pos = find_pattern_snippets(text, patterns.get("execution_instruction", []))
    if not pos:
        return state_record("execution_instructions", 0.0, [], [])
    strong_terms = {
        "pip install", "requirements.txt", "docker", "conda install",
        "step-by-step", "testbench", "synthesis script", "snakemake", "nextflow",
    }
    value = (
        1.0
        if any(any(t in x.lower() for t in strong_terms) for x in pos)
        else 0.5
    )
    note = "" if value == 1.0 else "Reproducibility wording found but no concrete install/run command."
    return state_record("execution_instructions", value, pos, [], note)


def evaluate_hyperparams(text: str, patterns: dict) -> dict:
    found: set[str] = set()
    evidence: list[str] = []
    for sentence in sentence_split(text, max_sentences=1500):
        local_hits = []
        for pat in patterns.get("hyperparams", []):
            if pat.search(sentence):
                local_hits.append(clean_text(pat.pattern))
        if local_hits:
            evidence.append(sentence)
            found.update(local_hits)
    if len(found) >= 4:
        return state_record(
            "hyperparams_detail", 1.0, evidence[:3], [],
            f"Distinct hyperparameter signals: {len(found)}",
        )
    if len(found) >= 2:
        return state_record(
            "hyperparams_detail", 0.5, evidence[:3], [],
            f"Distinct hyperparameter signals: {len(found)}",
        )
    return state_record("hyperparams_detail", 0.0, [], [], "Too few hyperparameter signals.")


def evaluate_seed(text: str, patterns: dict) -> dict:
    pos = find_pattern_snippets(text, patterns.get("seed_strict", []))
    if pos:
        return state_record("seed_disclosed", 1.0, pos, [])
    return state_record("seed_disclosed", 0.0, [], [], "No explicit seed statement found.")


def evaluate_compute(text: str, patterns: dict) -> dict:
    strong = find_pattern_snippets(text, patterns.get("compute_strong", []))
    partial = find_pattern_snippets(text, patterns.get("compute_partial", []))
    phys_compute = find_pattern_snippets(text, patterns.get("simulation", []))
    all_strong = dedupe_snippets(strong + phys_compute)
    if all_strong:
        return state_record("compute_detail", 1.0, all_strong, [])
    if partial:
        return state_record(
            "compute_detail", 0.5, partial, [],
            "Generic compute mention without strong hardware detail.",
        )
    return state_record("compute_detail", 0.0, [], [])


def evaluate_software_versions(text: str, patterns: dict) -> dict:
    strong = find_pattern_snippets(text, patterns.get("software_strong", []))
    partial = find_pattern_snippets(text, patterns.get("software_partial", []))
    if strong:
        import re
        has_version = any(re.search(r"\d+\.\d+", s) for s in strong)
        value = 1.0 if has_version else 0.5
        note = "" if value == 1.0 else "Framework named but version specificity is limited."
        return state_record("software_versions", value, strong, [], note)
    if partial:
        return state_record(
            "software_versions", 0.5, partial, [],
            "Software named but version specificity is limited.",
        )
    return state_record("software_versions", 0.0, [], [])


def evaluate_eval_protocol(text: str, patterns: dict) -> dict:
    bench_hits = count_pattern_hits(text, patterns.get("benchmarks", []))
    metric_hits = count_pattern_hits(text, patterns.get("metrics", []))
    infer_hits = count_pattern_hits(text, patterns.get("inference_detail", []))
    pos = dedupe_snippets(
        find_pattern_snippets(text, patterns.get("benchmarks", []))
        + find_pattern_snippets(text, patterns.get("metrics", []))
        + find_pattern_snippets(text, patterns.get("inference_detail", []))
    )
    score = 0.0
    if (bench_hits >= 1 and metric_hits >= 2) or (bench_hits >= 2 and metric_hits >= 1 and infer_hits >= 1):
        score = 1.0
    elif bench_hits >= 1 or metric_hits >= 1:
        score = 0.5
    note = f"benchmark_hits={bench_hits}, metric_hits={metric_hits}, infer_hits={infer_hits}"
    return state_record("evaluation_protocol", score, pos, [], note)


def evaluate_simple_flag(
    name: str,
    text: str,
    patterns: dict,
    pattern_keys: list[str],
    strong_note: str = "",
) -> dict:
    import itertools
    all_pats = list(itertools.chain.from_iterable(patterns.get(k, []) for k in pattern_keys))
    pos = find_pattern_snippets(text, all_pats)
    return state_record(name, 1.0 if pos else 0.0, pos, [], strong_note if pos else "")


def evaluate_statistical_rigor(text: str, patterns: dict) -> dict:
    """Statistical rigor gets domain-specific extra signals."""
    base_pats = patterns.get("stat_rigor", [])
    pos = find_pattern_snippets(text, base_pats)
    if pos:
        return state_record("statistical_rigor", 1.0, pos, [])
    return state_record("statistical_rigor", 0.0, [], [], "No statistical rigor signals detected.")


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------
def extract_feature_record(row: dict, domain: str = DEFAULT_DOMAIN) -> dict:
    patterns = get_domain_patterns(domain)
    weights = get_domain_weights(domain)
    text = combine_text(row)

    attributes = [
        evaluate_code_artifact(text, patterns),
        evaluate_data_artifact(text, patterns),
        evaluate_availability_statement(text, patterns),
        evaluate_execution_instructions(text, patterns),
        evaluate_hyperparams(text, patterns),
        evaluate_seed(text, patterns),
        evaluate_compute(text, patterns),
        evaluate_software_versions(text, patterns),
        evaluate_eval_protocol(text, patterns),
        evaluate_simple_flag("ablation", text, patterns, ["ablation"]),
        evaluate_simple_flag("baseline_comparison", text, patterns, ["baseline"]),
        evaluate_statistical_rigor(text, patterns),
        evaluate_simple_flag("limitations", text, patterns, ["limitations"]),
    ]

    # Guard: all 13 attributes must be produced
    produced = {a["name"] for a in attributes}
    missing_attrs = set(ATTRIBUTE_ORDER) - produced
    if missing_attrs:
        raise RuntimeError(
            f"extract_feature_record missing attributes: {missing_attrs}"
        )

    attr_map = {item["name"]: item for item in attributes}
    weighted_sum = sum(
        weights[name] * float(attr_map[name]["value"]) for name in ATTRIBUTE_ORDER
    )
    reproducibility_score = 100.0 * weighted_sum
    risk_score = 100.0 - reproducibility_score

    return {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "paper_uid": clean_text(row.get("paper_uid", "")),
        "domain": domain,
        "title": clean_text(row.get("title", "")),
        "attributes": attributes,
        "reproducibility_score": round(reproducibility_score, 4),
        "risk_score": round(risk_score, 4),
    }


def feature_row_from_record(record: dict) -> dict:
    row = {
        "paper_uid": record["paper_uid"],
        "domain": record.get("domain", DEFAULT_DOMAIN),
    }
    for attr in record["attributes"]:
        row[attr["name"]] = float(attr["value"])
    row["reproducibility_score"] = float(record["reproducibility_score"])
    row["risk_score"] = float(record["risk_score"])
    return row


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract domain-aware reproducibility attributes from extracted_text.jsonl."
    )
    parser.add_argument("--min-model-chars", type=int, default=400)
    parser.add_argument(
        "--default-domain",
        default=DEFAULT_DOMAIN,
        help="Domain to use when a row's domain field is missing (default: ml).",
    )
    args = parser.parse_args()

    ensure_dir(OUT_FEATURES_PATH.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Missing or empty input file: {IN_FILE}")

    df = pd.DataFrame(rows)
    if "paper_uid" not in df.columns or ("model_text" not in df.columns and "raw_text" not in df.columns):
        raise ValueError("extracted_text.jsonl must contain paper_uid and model_text/raw_text.")

    text_col = "model_text" if "model_text" in df.columns else "raw_text"
    df[text_col] = df[text_col].fillna("").astype(str)
    df = df[df[text_col].str.len() >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    if len(df) < 5:
        raise RuntimeError("Too few usable rows. Lower --min-model-chars or extract more PDFs.")

    records: list[dict] = []
    for _, row in df.iterrows():
        domain = str(row.get("domain", "") or args.default_domain).strip().lower()
        if domain not in DOMAIN_ATTRIBUTE_WEIGHTS:
            domain = args.default_domain
        record = extract_feature_record(row.to_dict(), domain=domain)
        records.append(record)

    feature_df = pd.DataFrame([feature_row_from_record(r) for r in records])
    feature_df.to_csv(OUT_MATRIX_CSV, index=False)
    write_jsonl(OUT_RECORDS_JSONL, records)

    matrix = feature_df[ATTRIBUTE_ORDER].astype(float).to_numpy()
    joblib.dump(
        {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "paper_uids": feature_df["paper_uid"].tolist(),
            "domains": feature_df["domain"].tolist(),
            "feature_columns": ATTRIBUTE_ORDER,
            "explicit_feature_columns": ATTRIBUTE_ORDER,
            "matrix": matrix,
            "records_path": str(OUT_RECORDS_JSONL),
        },
        OUT_FEATURES_PATH,
    )

    # Per-domain stats
    domain_stats: dict = {}
    for dom in feature_df["domain"].unique():
        sub = feature_df[feature_df["domain"] == dom]
        weights = DOMAIN_ATTRIBUTE_WEIGHTS.get(dom, DOMAIN_ATTRIBUTE_WEIGHTS["ml"])
        domain_stats[dom] = {
            "rows": int(len(sub)),
            "avg_reproducibility_score": float(sub["reproducibility_score"].mean()),
            "avg_risk_score": float(sub["risk_score"].mean()),
            "hit_rates": {col: float(sub[col].mean()) for col in ATTRIBUTE_ORDER},
        }

    write_json(
        REPORT_FILE,
        {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "input_rows_after_filtering": int(len(df)),
            "total_features": len(ATTRIBUTE_ORDER),
            "domain_stats": domain_stats,
            "records_jsonl": str(OUT_RECORDS_JSONL),
            "matrix_csv": str(OUT_MATRIX_CSV),
            "artifact_path": str(OUT_FEATURES_PATH),
        },
    )

    print(f"✅ Features artifact → {OUT_FEATURES_PATH}")
    print(f"✅ Feature matrix   → {OUT_MATRIX_CSV}")
    print(f"✅ Records JSONL    → {OUT_RECORDS_JSONL}")
    print(f"✅ Report           → {REPORT_FILE}")
    for dom, stats in domain_stats.items():
        print(f"   {dom:12s}: {stats['rows']:4d} rows, avg_repro={stats['avg_reproducibility_score']:.1f}%")


if __name__ == "__main__":
    main()
