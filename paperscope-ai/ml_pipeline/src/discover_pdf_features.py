from __future__ import annotations

import sys
from pathlib import Path
import argparse
import json
import re
from typing import Iterable

import joblib
import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import (
    clean_text,
    clean_multiline_text,
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
OUT_TERMS_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_feature_terms.json"
REPORT_FILE = PIPELINE_DIR / "outputs" / "reports" / "feature_discovery_report.json"


def rc(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


PATTERNS = {
    "code_url": [
        rc(r"github\.com/"),
        rc(r"gitlab\.com/"),
        rc(r"bitbucket\.org/"),
        rc(r"anonymous\.4open\.science"),
        rc(r"codeocean\.com/"),
    ],
    "code_claim": [
        rc(r"\bsource code\b"),
        rc(r"\bcode (?:is|will be|has been)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bimplementation (?:is|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:the )?code\b"),
        rc(r"\bopen[- ]source\b"),
    ],
    "code_future": [
        rc(r"\bcode will be available upon acceptance\b"),
        rc(r"\bcode will be released\b"),
        rc(r"\bcode will be made available\b"),
        rc(r"\bavailable upon acceptance\b"),
    ],
    "code_negative": [
        rc(r"\bno (?:public )?(?:code|implementation|artifact)\b"),
        rc(r"\bwithout (?:code|implementation|artifact)\b"),
        rc(r"\black(?:s|ing)? (?:code|implementation|artifact)\b"),
    ],
    "data_url": [
        rc(r"huggingface\.co/"),
        rc(r"zenodo\.org/"),
        rc(r"figshare\.com/"),
        rc(r"osf\.io/"),
        rc(r"kaggle\.com/"),
    ],
    "data_claim": [
        rc(r"\bdataset (?:is|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bdata (?:is|are|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:the )?(?:dataset|data)\b"),
        rc(r"\bpublicly available (?:benchmark|benchmarks|dataset|datasets|data)\b"),
        rc(r"\bderived from previously published, publicly available benchmarks\b"),
    ],
    "data_future": [
        rc(r"\bdata will be available upon acceptance\b"),
        rc(r"\bdataset will be released\b"),
        rc(r"\bdata will be released\b"),
    ],
    # BUG FIX 3 — availability_statement patterns now separated into two tiers so
    # scoring logic can distinguish confirmed releases from generic/future statements.
    "availability_confirmed": [
        rc(r"\bartifact(?:s)? (?:are|is)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bcode (?:is|has been)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bdata (?:is|are|has been)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:all )?(?:code|data|models|artifacts)\b"),
        rc(r"github\.com/"),
        rc(r"zenodo\.org/"),
        rc(r"figshare\.com/"),
        rc(r"huggingface\.co/"),
        rc(r"osf\.io/"),
    ],
    "availability_partial": [
        rc(r"\bcode will be available upon acceptance\b"),
        rc(r"\bartifact(?:s)? will be (?:available|released|shared|provided)\b"),
        rc(r"\ball training and evaluation data .* publicly available benchmarks\b"),
        rc(r"\bsupplementary material\b"),
        rc(r"\bwe do not collect any private user data\b"),
    ],
    "execution_instruction": [
        rc(r"\bpip install\b"),
        rc(r"\bconda install\b"),
        rc(r"\brequirements\.txt\b"),
        rc(r"\bdocker(?:file)?\b"),
        rc(r"\bto reproduce\b"),
        rc(r"\breproduc(?:e|ing|ibility) package\b"),
        rc(r"\brun the following command\b"),
        rc(r"\bscript(?:s)? (?:are|is)? available\b"),
        rc(r"\btraining script\b"),
    ],
    "hyperparams": [
        rc(r"\blearning rate\b"),
        rc(r"\bbatch size\b"),
        rc(r"\bepochs?\b"),
        rc(r"\bweight decay\b"),
        rc(r"\bdropout\b"),
        rc(r"\boptimizer\b"),
        rc(r"\bwarmup ratio\b"),
        rc(r"\bglobal batch size\b"),
        rc(r"\bmicro-batch size\b"),
        rc(r"\bmax prompt length\b"),
        rc(r"\bmax completion length\b"),
        rc(r"\bsampling temperature\b"),
        rc(r"\bnumber of rollouts\b"),
        rc(r"\bKL penalty\b"),
        rc(r"\bhyperparameter(?:s)?\b"),
    ],
    "seed_strict": [
        rc(r"\brandom seed\b"),
        rc(r"\bseed\s*=\s*\d+\b"),
        rc(r"\bseed(?:ed)? with \d+\b"),
        rc(r"\bwe set (?:the )?seed to \d+\b"),
        rc(r"\brandom_state\s*=\s*\d+\b"),
    ],
    "compute_strong": [
        rc(r"\bNVIDIA\b"),
        rc(r"\bH100\b"),
        rc(r"\bH200\b"),
        rc(r"\bA100\b"),
        rc(r"\bV100\b"),
        rc(r"\bRTX\b"),
        rc(r"\bTPU\b"),
        rc(r"\bGPU(?:s)?\b"),
        rc(r"\btraining time\b"),
        rc(r"\bwall[- ]clock\b"),
        rc(r"\bcompute budget\b"),
        rc(r"\bGB of memory\b"),
    ],
    "compute_partial": [
        rc(r"\bCUDA\b"),
        rc(r"\bcompute\b"),
        rc(r"\bhardware\b"),
    ],
    "software_strong": [
        rc(r"\bPyTorch\s*\d+(?:\.\d+)+\b"),
        rc(r"\bTensorFlow\s*\d+(?:\.\d+)+\b"),
        rc(r"\bvLLM\b"),
        rc(r"\bverl\b"),
        rc(r"\btransformers\s*\d+(?:\.\d+)+\b"),
        rc(r"\bPython\s*\d+(?:\.\d+)+\b"),
        rc(r"\brequirements\.txt\b"),
        rc(r"\bDocker(?:file)?\b"),
    ],
    "software_partial": [
        rc(r"\bPyTorch\b"),
        rc(r"\bTensorFlow\b"),
        rc(r"\bvLLM\b"),
        rc(r"\bverl\b"),
        rc(r"\btransformers\b"),
        rc(r"\bscikit-learn\b"),
        rc(r"\bCUDA\b"),
    ],
    "benchmarks": [
        rc(r"\bbenchmark(?:s)?\b"),
        rc(r"\bMMLU\b"),
        rc(r"\bCyberMetric\b"),
        rc(r"\bCSEBenchmark\b"),
        rc(r"\bASBench\b"),
        rc(r"\btest set\b"),
        rc(r"\bevaluation protocol\b"),
    ],
    "metrics": [
        rc(r"\baccuracy\b"),
        rc(r"\bF1\b"),
        rc(r"\bprecision\b"),
        rc(r"\brecall\b"),
        rc(r"\bRMSE\b"),
        rc(r"\bMAE\b"),
        rc(r"\bSpearman\b"),
        rc(r"\bband accuracy\b"),
        rc(r"\binvalid ratio\b"),
        rc(r"\bconfidence faithfulness\b"),
    ],
    "inference_detail": [
        rc(r"\bgreedy decoding\b"),
        rc(r"\bsampling temperature\b"),
        rc(r"\bvLLM inference engine\b"),
        rc(r"\bdeterministic\b"),
        rc(r"\bdecoding\b"),
    ],
    "ablation": [
        rc(r"\bablation (?:study|studies|experiment|experiments)\b"),
        rc(r"\bwe ablate\b"),
        rc(r"\bablation variant(?:s)?\b"),
    ],
    "baseline": [
        rc(r"\bbaseline(?:s)?\b"),
        rc(r"\bcompare(?:d)? (?:with|to|against)\b"),
        rc(r"\bperformance comparison\b"),
        rc(r"\boutperform(?:s|ed|ing)?\b"),
        rc(r"\bstate[- ]of[- ]the[- ]art\b"),
    ],
    "stat_rigor": [
        rc(r"\bconfidence interval(?:s)?\b"),
        rc(r"\bstandard deviation\b"),
        rc(r"\bstandard error\b"),
        rc(r"\bmultiple runs?\b"),
        rc(r"\bp[- ]value\b"),
        rc(r"\bsignificance\b"),
        rc(r"\bbootstrap\b"),
        rc(r"\bvariance\b"),
        rc(r"\btop-100 samples\b"),
    ],
    "limitations": [
        rc(r"\blimitations?\b"),
        rc(r"\bthreats to validity\b"),
        rc(r"\bfuture work\b"),
        rc(r"\bimpact statement\b"),
        rc(r"\bmay suffer\b"),
        rc(r"\bdoes not remove the need\b"),
    ],
}


ATTRIBUTE_ORDER = [
    "code_artifact",
    "data_artifact",
    "availability_statement",
    "execution_instructions",
    "hyperparams_detail",
    "seed_disclosed",
    "compute_detail",
    "software_versions",
    "evaluation_protocol",
    "ablation",
    "baseline_comparison",
    "statistical_rigor",
    "limitations",
]

ATTRIBUTE_WEIGHTS = {
    "code_artifact": 0.16,
    "data_artifact": 0.10,
    "availability_statement": 0.05,
    "execution_instructions": 0.10,
    "hyperparams_detail": 0.12,
    "seed_disclosed": 0.08,
    "compute_detail": 0.08,
    "software_versions": 0.08,
    "evaluation_protocol": 0.10,
    "ablation": 0.05,
    "baseline_comparison": 0.04,
    "statistical_rigor": 0.02,
    "limitations": 0.02,
}

# Sanity-check that weights are defined for every attribute and sum to 1.0.
assert set(ATTRIBUTE_WEIGHTS.keys()) == set(ATTRIBUTE_ORDER), (
    "ATTRIBUTE_WEIGHTS keys must match ATTRIBUTE_ORDER exactly."
)
assert abs(sum(ATTRIBUTE_WEIGHTS.values()) - 1.0) < 1e-6, (
    f"ATTRIBUTE_WEIGHTS must sum to 1.0, got {sum(ATTRIBUTE_WEIGHTS.values()):.6f}"
)


# ---------------------------------------------------------------------------
# BUG FIX 1 — combine_text
# ---------------------------------------------------------------------------
# Original code built parts as:
#   f"Title: {clean_text(row.get('title', ''))}"
# then filtered with `if clean_text(p)`.
# `clean_text("Title: ")` → "Title:" which is truthy, so an empty title still
# contributed the useless stub "Title:" to the combined text.  The fix builds
# each section only when the payload is non-empty.
# ---------------------------------------------------------------------------
def combine_text(row: dict) -> str:
    parts: list[str] = []
    title = clean_text(row.get("title", ""))
    abstract = clean_text(row.get("abstract", ""))
    keywords = clean_text(row.get("keywords", ""))
    raw = clean_multiline_text(row.get("raw_text", ""))
    if title:
        parts.append(f"Title: {title}")
    if abstract:
        parts.append(f"Abstract: {abstract}")
    if keywords:
        parts.append(f"Keywords: {keywords}")
    if raw:
        parts.append(raw)
    return "\n\n".join(parts)


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


def evaluate_code_artifact(text: str) -> dict:
    pos = find_pattern_snippets(text, PATTERNS["code_url"] + PATTERNS["code_claim"])
    neg = find_pattern_snippets(text, PATTERNS["code_negative"])
    partial = find_pattern_snippets(text, PATTERNS["code_future"])
    if pos:
        # If strong positive evidence coexists with strong negative evidence, reduce
        # to PARTIAL rather than blindly claiming SUPPORTED.  This guards against a
        # paper that says "the baseline has no code" while releasing its own.
        if neg:
            return state_record(
                "code_artifact",
                0.5,
                pos,
                neg,
                "Code availability claim found alongside negative signals; manual review recommended.",
            )
        return state_record("code_artifact", 1.0, pos, neg)
    if partial:
        return state_record(
            "code_artifact",
            0.5,
            partial,
            neg,
            "Future or deferred code-release statement found.",
        )
    return state_record("code_artifact", 0.0, [], neg)


# ---------------------------------------------------------------------------
# BUG FIX 2 — evaluate_data_artifact
# ---------------------------------------------------------------------------
# Original logic:
#   if strong or any("publicly available benchmark" in s for s in pos):  → 1.0 or 0.5
#   if partial:  → 0.5
#   return 0.0
#
# The gap: if `pos` has a data_claim that does NOT mention "publicly available
# benchmark" (e.g. "our dataset is available at …") AND there is no data_url,
# the condition fails, we fall through to `partial`, find nothing, and return
# 0.0 — silently discarding a real data claim.
#
# Fix: add an explicit `elif pos:` branch that returns 0.5.
# ---------------------------------------------------------------------------
def evaluate_data_artifact(text: str) -> dict:
    strong = find_pattern_snippets(text, PATTERNS["data_url"])
    pos = find_pattern_snippets(text, PATTERNS["data_claim"])
    partial = find_pattern_snippets(text, PATTERNS["data_future"])

    if strong:
        # Direct URL to a data repository — best signal.
        return state_record("data_artifact", 1.0, strong, [])

    if pos:
        # Data availability claim exists.  Distinguish between a claim backed by a
        # direct URL-level confidence vs. a generic "publicly available benchmarks"
        # statement (which merely means the paper used standard benchmarks, not that
        # it released its own data).
        has_benchmark_only = all(
            "publicly available benchmark" in s.lower() for s in pos
        )
        if has_benchmark_only:
            return state_record(
                "data_artifact",
                0.5,
                pos,
                [],
                "Paper references publicly available benchmarks but no direct dataset URL was detected.",
            )
        # At least one claim is a genuine data-release statement.
        return state_record(
            "data_artifact",
            0.5,
            pos,
            [],
            "Data availability claim found; no direct repository URL detected.",
        )

    if partial:
        return state_record(
            "data_artifact",
            0.5,
            partial,
            [],
            "Future or deferred data-release statement found.",
        )

    return state_record("data_artifact", 0.0, [], [])


# ---------------------------------------------------------------------------
# BUG FIX 3 — evaluate_availability_statement
# ---------------------------------------------------------------------------
# Original scoring:
#   value = 1.0 if any("publicly available benchmarks" in s for s in pos) else 0.5
#
# This gave 1.0 for papers that merely used standard benchmarks (MMLU etc.)
# while giving only 0.5 to papers that explicitly said "our artifacts are
# available at <URL>".  The scoring was inverted.
#
# Fix: use two separate pattern lists (availability_confirmed vs
# availability_partial).  Confirmed = explicit present-tense release or known
# repository URL → 1.0.  Partial = future/conditional/generic → 0.5.
# ---------------------------------------------------------------------------
def evaluate_availability_statement(text: str) -> dict:
    confirmed = find_pattern_snippets(text, PATTERNS["availability_confirmed"])
    partial = find_pattern_snippets(text, PATTERNS["availability_partial"])

    if confirmed:
        return state_record(
            "availability_statement",
            1.0,
            confirmed,
            [],
            "Explicit confirmed availability statement or repository URL detected.",
        )
    if partial:
        return state_record(
            "availability_statement",
            0.5,
            partial,
            [],
            "Availability statement found, but it is future/conditional or references standard benchmarks only.",
        )
    return state_record("availability_statement", 0.0, [], [])


def evaluate_execution_instructions(text: str) -> dict:
    pos = find_pattern_snippets(text, PATTERNS["execution_instruction"])
    if not pos:
        return state_record("execution_instructions", 0.0, [], [])
    value = (
        1.0
        if any(
            x.lower().find("pip install") >= 0
            or x.lower().find("requirements.txt") >= 0
            or x.lower().find("docker") >= 0
            for x in pos
        )
        else 0.5
    )
    note = (
        ""
        if value == 1.0
        else "Some reproducibility-package wording found, but no concrete install/run command."
    )
    return state_record("execution_instructions", value, pos, [], note)


def evaluate_hyperparams(text: str) -> dict:
    found: set[str] = set()
    evidence: list[str] = []
    for sentence in sentence_split(text, max_sentences=1500):
        local_hits = []
        for pat in PATTERNS["hyperparams"]:
            if pat.search(sentence):
                local_hits.append(clean_text(pat.pattern))
        if local_hits:
            evidence.append(sentence)
            for item in local_hits:
                found.add(item)
    if len(found) >= 4:
        return state_record(
            "hyperparams_detail",
            1.0,
            evidence[:3],
            [],
            f"Distinct hyperparameter signals: {len(found)}",
        )
    if len(found) >= 2:
        return state_record(
            "hyperparams_detail",
            0.5,
            evidence[:3],
            [],
            f"Distinct hyperparameter signals: {len(found)}",
        )
    return state_record("hyperparams_detail", 0.0, [], [], "Too few hyperparameter signals found.")


def evaluate_seed(text: str) -> dict:
    pos = find_pattern_snippets(text, PATTERNS["seed_strict"])
    if pos:
        return state_record("seed_disclosed", 1.0, pos, [])
    return state_record("seed_disclosed", 0.0, [], [], "No explicit reproducibility seed statement found.")


def evaluate_compute(text: str) -> dict:
    strong = find_pattern_snippets(text, PATTERNS["compute_strong"])
    partial = find_pattern_snippets(text, PATTERNS["compute_partial"])
    if strong:
        return state_record("compute_detail", 1.0, strong, [])
    if partial:
        return state_record(
            "compute_detail",
            0.5,
            partial,
            [],
            "Generic compute/environment mentions without strong hardware detail.",
        )
    return state_record("compute_detail", 0.0, [], [])


def evaluate_software_versions(text: str) -> dict:
    strong = find_pattern_snippets(text, PATTERNS["software_strong"])
    partial = find_pattern_snippets(text, PATTERNS["software_partial"])
    if strong:
        has_version = any(re.search(r"\d+\.\d+", s) for s in strong)
        value = 1.0 if has_version else 0.5
        note = (
            ""
            if value == 1.0
            else "Framework/tooling named, but explicit version information is limited."
        )
        return state_record("software_versions", value, strong, [], note)
    if partial:
        return state_record(
            "software_versions",
            0.5,
            partial,
            [],
            "Framework/tooling named, but explicit version information is limited.",
        )
    return state_record("software_versions", 0.0, [], [])


def evaluate_eval_protocol(text: str) -> dict:
    bench_hits = count_pattern_hits(text, PATTERNS["benchmarks"])
    metric_hits = count_pattern_hits(text, PATTERNS["metrics"])
    infer_hits = count_pattern_hits(text, PATTERNS["inference_detail"])
    pos = dedupe_snippets(
        find_pattern_snippets(text, PATTERNS["benchmarks"])
        + find_pattern_snippets(text, PATTERNS["metrics"])
        + find_pattern_snippets(text, PATTERNS["inference_detail"])
    )
    score = 0.0
    if (bench_hits >= 1 and metric_hits >= 2) or (
        bench_hits >= 2 and metric_hits >= 1 and infer_hits >= 1
    ):
        score = 1.0
    elif bench_hits >= 1 or metric_hits >= 1:
        score = 0.5
    note = f"benchmark_hits={bench_hits}, metric_hits={metric_hits}, inference_detail_hits={infer_hits}"
    return state_record("evaluation_protocol", score, pos, [], note)


def evaluate_simple_flag(
    name: str,
    text: str,
    patterns: list[re.Pattern],
    strong_note: str = "",
) -> dict:
    pos = find_pattern_snippets(text, patterns)
    return state_record(name, 1.0 if pos else 0.0, pos, [], strong_note if pos else "")


def extract_feature_record(row: dict) -> dict:
    text = combine_text(row)
    attributes = [
        evaluate_code_artifact(text),
        evaluate_data_artifact(text),
        evaluate_availability_statement(text),
        evaluate_execution_instructions(text),
        evaluate_hyperparams(text),
        evaluate_seed(text),
        evaluate_compute(text),
        evaluate_software_versions(text),
        evaluate_eval_protocol(text),
        evaluate_simple_flag("ablation", text, PATTERNS["ablation"]),
        evaluate_simple_flag("baseline_comparison", text, PATTERNS["baseline"]),
        evaluate_simple_flag("statistical_rigor", text, PATTERNS["stat_rigor"]),
        evaluate_simple_flag("limitations", text, PATTERNS["limitations"]),
    ]

    # Guard: every attribute in ATTRIBUTE_ORDER must have been produced.
    produced = {a["name"] for a in attributes}
    missing_attrs = set(ATTRIBUTE_ORDER) - produced
    if missing_attrs:
        raise RuntimeError(
            f"extract_feature_record produced attributes {produced} but "
            f"ATTRIBUTE_ORDER expects {set(ATTRIBUTE_ORDER)}. Missing: {missing_attrs}"
        )

    attr_map = {item["name"]: item for item in attributes}
    weighted_sum = 0.0
    weight_total = 0.0
    for name in ATTRIBUTE_ORDER:
        weight = ATTRIBUTE_WEIGHTS[name]
        weight_total += weight
        weighted_sum += weight * float(attr_map[name]["value"])
    reproducibility_score = 100.0 * weighted_sum / max(weight_total, 1e-9)
    risk_score = 100.0 - reproducibility_score

    return {
        "paper_uid": clean_text(row.get("paper_uid", "")),
        "title": clean_text(row.get("title", "")),
        "attributes": attributes,
        "reproducibility_score": round(reproducibility_score, 4),
        "risk_score": round(risk_score, 4),
    }


def feature_row_from_record(record: dict) -> dict:
    row = {"paper_uid": record["paper_uid"]}
    for attr in record["attributes"]:
        row[attr["name"]] = float(attr["value"])
    row["reproducibility_score"] = float(record["reproducibility_score"])
    row["risk_score"] = float(record["risk_score"])
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Extract explanation-ready reproducibility attributes from PDF text."
    )
    parser.add_argument("--min-model-chars", type=int, default=400)
    args = parser.parse_args()

    ensure_dir(OUT_FEATURES_PATH.parent)
    ensure_dir(REPORT_FILE.parent)

    rows = read_jsonl(IN_FILE)
    if not rows:
        raise FileNotFoundError(f"Missing input file: {IN_FILE}")

    df = pd.DataFrame(rows)
    if "paper_uid" not in df.columns or "model_text" not in df.columns:
        raise ValueError("extracted_text.jsonl must contain paper_uid and model_text.")

    df["model_text"] = df["model_text"].fillna("").astype(str)
    df = df[df["model_text"].str.len() >= args.min_model_chars].copy()
    df = df.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)

    if len(df) < 10:
        raise RuntimeError(
            "Too few usable rows found. Lower --min-model-chars or extract more PDFs."
        )

    records = []
    for _, row in df.iterrows():
        record = extract_feature_record(row.to_dict())
        records.append(record)

    feature_df = pd.DataFrame([feature_row_from_record(r) for r in records])
    feature_cols = ATTRIBUTE_ORDER
    matrix = feature_df[feature_cols].astype(float).to_numpy()

    feature_df.to_csv(OUT_MATRIX_CSV, index=False)
    write_jsonl(OUT_RECORDS_JSONL, records)
    write_json(
        OUT_TERMS_PATH,
        {"feature_terms": {name: {"weight": ATTRIBUTE_WEIGHTS[name]} for name in ATTRIBUTE_ORDER}},
    )

    joblib.dump(
        {
            "paper_uids": feature_df["paper_uid"].tolist(),
            "feature_columns": feature_cols,
            "explicit_feature_columns": feature_cols,
            "svd_feature_columns": [],
            "matrix": matrix,
            "content_pattern_names": feature_cols,
            "records_path": str(OUT_RECORDS_JSONL),
            "attribute_weights": ATTRIBUTE_WEIGHTS,
        },
        OUT_FEATURES_PATH,
    )

    hit_rates = {col: float(feature_df[col].mean()) for col in feature_cols}
    report = {
        "input_rows_after_filtering": int(len(df)),
        "total_features": len(feature_cols),
        "feature_hit_rates": hit_rates,
        "avg_reproducibility_score": float(feature_df["reproducibility_score"].mean()),
        "avg_risk_score": float(feature_df["risk_score"].mean()),
        "records_jsonl": str(OUT_RECORDS_JSONL),
        "matrix_csv": str(OUT_MATRIX_CSV),
        "artifact_path": str(OUT_FEATURES_PATH),
    }
    write_json(REPORT_FILE, report)

    print(f"✅ Features artifact saved to: {OUT_FEATURES_PATH}")
    print(f"✅ Feature matrix saved to: {OUT_MATRIX_CSV}")
    print(f"✅ Feature records saved to: {OUT_RECORDS_JSONL}")
    print(f"✅ Report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()