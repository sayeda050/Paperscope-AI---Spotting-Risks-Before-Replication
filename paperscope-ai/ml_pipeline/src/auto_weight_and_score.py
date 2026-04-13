"""
auto_weight_and_score.py — Domain-aware reproducibility & risk scoring.

Reads: data/processed/discovered_feature_records.jsonl
       data/processed/extracted_text.jsonl
Writes: data/processed/auto_scored_papers.csv
        data/processed/auto_scored_papers_evidence.jsonl
        data/processed/feature_weights.csv  (per domain)
        outputs/reports/auto_scoring_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import (
    ATTRIBUTE_ORDER,
    DOMAIN_ATTRIBUTE_WEIGHTS,
    DOMAIN_SECTION_MAPS,
    get_domain_section_map,
    get_domain_weights,
)
from utils import (
    PIPELINE_SCHEMA_VERSION,
    ensure_dir,
    read_jsonl,
    risk_label_from_score,
    write_json,
)

PIPELINE_DIR = SRC_DIR.parent
IN_FEATURES_PATH  = PIPELINE_DIR / "data" / "processed" / "discovered_features.joblib"
IN_RECORDS_PATH   = PIPELINE_DIR / "data" / "processed" / "discovered_feature_records.jsonl"
IN_TEXT_FILE      = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_SCORED_CSV    = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_EVIDENCE_JSONL = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers_evidence.jsonl"
OUT_WEIGHTS_CSV   = PIPELINE_DIR / "data" / "processed" / "feature_weights.csv"
OUT_REPORT        = PIPELINE_DIR / "outputs" / "reports" / "auto_scoring_report.json"

DEFAULT_DOMAIN = "ml"


# ---------------------------------------------------------------------------
# Bullet templates (domain-generic; keys match ATTRIBUTE_ORDER exactly)
# ---------------------------------------------------------------------------
_BULLET_TEMPLATES: dict[str, dict[str, str]] = {
    "code_artifact": {
        "SUPPORTED": "A public code or artifact link was detected.",
        "PARTIAL":   "A code/artifact availability statement was detected, but the artifact is not clearly available right now.",
        "NOT_FOUND": "No clear public code or artifact link was detected.",
    },
    "data_artifact": {
        "SUPPORTED": "A public data or dataset access signal was detected.",
        "PARTIAL":   "A public-data statement was detected, but an exact released dataset artifact was not clearly identified.",
        "NOT_FOUND": "No clear public data artifact or dataset link was detected.",
    },
    "availability_statement": {
        "SUPPORTED": "The paper includes a confirmed, explicit availability statement with a direct artifact or repository link.",
        "PARTIAL":   "The paper includes a partial or future availability statement.",
        "NOT_FOUND": "No explicit availability statement was detected.",
    },
    "execution_instructions": {
        "SUPPORTED": "Concrete execution or reproduction instructions were detected.",
        "PARTIAL":   "Some reproduction-package wording was detected, but step-by-step instructions were limited.",
        "NOT_FOUND": "No reproducibility package or clear execution instructions were detected.",
    },
    "hyperparams_detail": {
        "SUPPORTED": "The paper reports concrete hyperparameter or study-design settings.",
        "PARTIAL":   "The paper reports some hyperparameter details, but coverage is incomplete.",
        "NOT_FOUND": "Hyperparameter or study-design details were not clearly reported.",
    },
    "seed_disclosed": {
        "SUPPORTED": "The paper reports explicit random-seed or randomization information.",
        "PARTIAL":   "The paper contains a partial seed or randomization-related statement.",
        "NOT_FOUND": "No explicit random-seed or randomization information was detected.",
    },
    "compute_detail": {
        "SUPPORTED": "The paper reports concrete compute, hardware, or simulation-environment details.",
        "PARTIAL":   "The paper includes limited compute/environment detail.",
        "NOT_FOUND": "Compute or hardware details were not clearly reported.",
    },
    "software_versions": {
        "SUPPORTED": "The paper includes software/toolchain details with useful version specificity.",
        "PARTIAL":   "The paper names software/tooling, but version specificity is limited.",
        "NOT_FOUND": "Software or toolchain version details were not clearly reported.",
    },
    "evaluation_protocol": {
        "SUPPORTED": "The validation and evaluation protocol is clearly described.",
        "PARTIAL":   "The paper reports some evaluation details, but the protocol is only partially specified.",
        "NOT_FOUND": "Validation or test protocol details are limited.",
    },
    "ablation": {
        "SUPPORTED": "An ablation study or ablation experiments were detected.",
        "PARTIAL":   "Some ablation-related language was found, but a full study was not clearly described.",
        "NOT_FOUND": "No ablation study was detected.",
    },
    "baseline_comparison": {
        "SUPPORTED": "Explicit baseline comparisons or state-of-the-art benchmarking was detected.",
        "PARTIAL":   "Baseline-related language was found, but comparisons are limited.",
        "NOT_FOUND": "No explicit baseline or comparative evaluation was detected.",
    },
    "statistical_rigor": {
        "SUPPORTED": "Statistical rigor signals (confidence intervals, multiple runs, p-values, etc.) were detected.",
        "PARTIAL":   "Some statistical reporting language was found, but full rigor indicators are limited.",
        "NOT_FOUND": "No statistical rigor signals (confidence intervals, variance, etc.) were detected.",
    },
    "limitations": {
        "SUPPORTED": "A limitations section or threats-to-validity discussion was detected.",
        "PARTIAL":   "Some limitations language was found, but a dedicated discussion appears limited.",
        "NOT_FOUND": "No limitations discussion was detected.",
    },
}

# Guard: every attribute must have a template
_missing = set(ATTRIBUTE_ORDER) - set(_BULLET_TEMPLATES.keys())
assert not _missing, f"_BULLET_TEMPLATES missing entries for: {_missing}"


def build_summary_bullets(attr_map: dict) -> list[str]:
    bullets: list[str] = []
    for name in ATTRIBUTE_ORDER:
        state = attr_map[name]["state"]
        tmpl  = _BULLET_TEMPLATES[name]
        if state not in tmpl:
            state = "NOT_FOUND"
        bullets.append(tmpl[state])
    return bullets


def score_sections(attr_map: dict, domain: str) -> dict:
    section_map = get_domain_section_map(domain)
    weights     = get_domain_weights(domain)
    out: dict   = {}
    for section_name, attrs in section_map.items():
        w_sum = sum(weights[a] for a in attrs)
        raw   = sum(float(attr_map[a]["value"]) * weights[a] for a in attrs)
        repro = 100.0 * raw / max(w_sum, 1e-9)
        out[section_name] = {
            "reproducibility_score": round(repro, 2),
            "risk_score":            round(100.0 - repro, 2),
        }
    return out


def load_artifact() -> dict:
    if not IN_FEATURES_PATH.exists():
        raise FileNotFoundError(f"Missing feature artifact: {IN_FEATURES_PATH}")
    return joblib.load(IN_FEATURES_PATH)


def load_records() -> list[dict]:
    if not IN_RECORDS_PATH.exists():
        raise FileNotFoundError(f"Missing feature records: {IN_RECORDS_PATH}")
    return read_jsonl(IN_RECORDS_PATH)


def load_text_rows() -> pd.DataFrame:
    rows = read_jsonl(IN_TEXT_FILE)
    if not rows:
        raise FileNotFoundError(f"Missing extracted text: {IN_TEXT_FILE}")
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create transparent reproducibility and risk scores from discovered features."
    )
    parser.add_argument(
        "--default-domain", default=DEFAULT_DOMAIN,
        help="Domain to use when a record's domain field is missing.",
    )
    _ = parser.parse_args()

    ensure_dir(OUT_SCORED_CSV.parent)
    ensure_dir(OUT_REPORT.parent)

    artifact = load_artifact()
    records  = load_records()
    text_df  = load_text_rows()

    # Build per-domain weight tables for reporting
    weights_rows: list[dict] = []
    for dom, w in DOMAIN_ATTRIBUTE_WEIGHTS.items():
        for attr in ATTRIBUTE_ORDER:
            weights_rows.append({"domain": dom, "feature": attr, "weight": w[attr]})
    pd.DataFrame(weights_rows).to_csv(OUT_WEIGHTS_CSV, index=False)

    record_rows:   list[dict] = []
    evidence_rows: list[dict] = []

    for record in records:
        attr_map = {item["name"]: item for item in record["attributes"]}

        # Validate all attributes present
        missing_attrs = set(ATTRIBUTE_ORDER) - set(attr_map.keys())
        if missing_attrs:
            raise ValueError(
                f"Record {record.get('paper_uid', '?')} is missing attributes: {missing_attrs}"
            )

        domain = str(record.get("domain", DEFAULT_DOMAIN) or DEFAULT_DOMAIN).strip().lower()
        if domain not in DOMAIN_ATTRIBUTE_WEIGHTS:
            domain = DEFAULT_DOMAIN

        section_scores  = score_sections(attr_map, domain)
        repro_score     = float(record["reproducibility_score"])
        risk_score_val  = float(record["risk_score"])
        summary_bullets = build_summary_bullets(attr_map)

        # Build section risk columns dynamically (domain-agnostic column names)
        section_risk_cols: dict = {}
        for sec_name, sec_data in section_scores.items():
            col = f"{sec_name}_risk"
            section_risk_cols[col] = sec_data["risk_score"]

        row: dict = {
            "schema_version":          PIPELINE_SCHEMA_VERSION,
            "paper_uid":               record["paper_uid"],
            "domain":                  domain,
            "reproducibility_score":   round(repro_score, 2),
            "risk_score":              round(risk_score_val, 2),
            "risk_label":              risk_label_from_score(risk_score_val),
            "summary_bullets":         " || ".join(summary_bullets),
            **section_risk_cols,
        }

        for name in ATTRIBUTE_ORDER:
            row[name]              = float(attr_map[name]["value"])
            row[f"{name}_state"]   = attr_map[name]["state"]

        record_rows.append(row)

        evidence_rows.append({
            "paper_uid":       record["paper_uid"],
            "domain":          domain,
            "risk_score":      round(risk_score_val, 2),
            "risk_label":      risk_label_from_score(risk_score_val),
            "attributes":      record["attributes"],
            "section_scores":  section_scores,
            "summary_bullets": summary_bullets,
        })

    feature_df = pd.DataFrame(record_rows)
    merged = (
        text_df
        .merge(feature_df, on="paper_uid", how="inner")
        .drop_duplicates(subset=["paper_uid"])
        .reset_index(drop=True)
    )

    # Resolve domain column conflict after merge (prefer feature_df's domain)
    if "domain_x" in merged.columns and "domain_y" in merged.columns:
        merged["domain"] = merged["domain_y"].fillna(merged["domain_x"])
        merged.drop(columns=["domain_x", "domain_y"], inplace=True)

    merged.to_csv(OUT_SCORED_CSV, index=False)

    with OUT_EVIDENCE_JSONL.open("w", encoding="utf-8") as f:
        for ev in evidence_rows:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # Per-domain stats
    domain_stats: dict = {}
    for dom, grp in merged.groupby("domain"):
        domain_stats[str(dom)] = {
            "rows":                     int(len(grp)),
            "avg_reproducibility_score": float(grp["reproducibility_score"].mean()),
            "avg_risk_score":            float(grp["risk_score"].mean()),
        }

    report = {
        "schema_version":            PIPELINE_SCHEMA_VERSION,
        "rows_scored":               int(len(merged)),
        "feature_count":             int(len(artifact.get("feature_columns", []))),
        "avg_reproducibility_score": float(merged["reproducibility_score"].mean()),
        "avg_risk_score":            float(merged["risk_score"].mean()),
        "domain_stats":              domain_stats,
        "weights_csv":               str(OUT_WEIGHTS_CSV),
        "scored_csv":                str(OUT_SCORED_CSV),
        "evidence_jsonl":            str(OUT_EVIDENCE_JSONL),
        "scoring_method":            "transparent_weighted_attribute_rubric_domain_aware_v3",
    }
    write_json(OUT_REPORT, report)

    print(f"✅ Auto-scored CSV       → {OUT_SCORED_CSV}")
    print(f"✅ Evidence JSONL        → {OUT_EVIDENCE_JSONL}")
    print(f"✅ Feature weights CSV   → {OUT_WEIGHTS_CSV}")
    print(f"✅ Report                → {OUT_REPORT}")
    for dom, stats in domain_stats.items():
        print(f"   {dom:12s}: {stats['rows']:4d} rows | "
              f"avg_repro={stats['avg_reproducibility_score']:.1f}% | "
              f"avg_risk={stats['avg_risk_score']:.1f}%")


if __name__ == "__main__":
    main()
