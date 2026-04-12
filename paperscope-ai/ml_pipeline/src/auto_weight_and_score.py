from __future__ import annotations

import sys
from pathlib import Path
import argparse
import json

import joblib
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from utils import ensure_dir, read_jsonl, risk_label_from_score, write_json
from discover_pdf_features import ATTRIBUTE_ORDER, ATTRIBUTE_WEIGHTS

PIPELINE_DIR = SRC_DIR.parent
IN_FEATURES_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_features.joblib"
IN_RECORDS_PATH = PIPELINE_DIR / "data" / "processed" / "discovered_feature_records.jsonl"
IN_TEXT_FILE = PIPELINE_DIR / "data" / "processed" / "extracted_text.jsonl"
OUT_SCORED_CSV = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers.csv"
OUT_EVIDENCE_JSONL = PIPELINE_DIR / "data" / "processed" / "auto_scored_papers_evidence.jsonl"
OUT_WEIGHTS_CSV = PIPELINE_DIR / "data" / "processed" / "feature_weights.csv"
OUT_REPORT = PIPELINE_DIR / "outputs" / "reports" / "auto_scoring_report.json"


SECTION_MAP = {
    "artifacts_and_data": [
        "code_artifact",
        "data_artifact",
        "availability_statement",
        "execution_instructions",
    ],
    "implementation_detail": [
        "hyperparams_detail",
        "seed_disclosed",
        "compute_detail",
        "software_versions",
    ],
    "evaluation_rigor": [
        "evaluation_protocol",
        "ablation",
        "baseline_comparison",
        "statistical_rigor",
        "limitations",
    ],
}

# Verify section map covers every attribute exactly once.
_section_attrs = [a for attrs in SECTION_MAP.values() for a in attrs]
assert sorted(_section_attrs) == sorted(ATTRIBUTE_ORDER), (
    f"SECTION_MAP attrs {sorted(_section_attrs)} do not match ATTRIBUTE_ORDER {sorted(ATTRIBUTE_ORDER)}"
)


def load_artifact():
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
        raise FileNotFoundError(f"Missing extracted text file: {IN_TEXT_FILE}")
    return pd.DataFrame(rows)


def score_sections(attr_map: dict) -> dict:
    out = {}
    for section_name, attrs in SECTION_MAP.items():
        weights = [ATTRIBUTE_WEIGHTS[a] for a in attrs]
        raw = sum(
            float(attr_map[a]["value"]) * ATTRIBUTE_WEIGHTS[a] for a in attrs
        )
        section_repro = 100.0 * raw / max(sum(weights), 1e-9)
        out[section_name] = {
            "reproducibility_score": round(section_repro, 2),
            "risk_score": round(100.0 - section_repro, 2),
        }
    return out


# ---------------------------------------------------------------------------
# BUG FIX 4 — build_summary_bullets
# ---------------------------------------------------------------------------
# The original function only covered 9 of the 13 ATTRIBUTE_ORDER entries.
# ablation, baseline_comparison, statistical_rigor, and limitations had no
# templates and were never emitted.  The fix adds all four missing attributes
# and iterates over the full ATTRIBUTE_ORDER so adding new attributes in the
# future automatically gets picked up.
# ---------------------------------------------------------------------------
_BULLET_TEMPLATES: dict[str, dict[str, str]] = {
    "code_artifact": {
        "SUPPORTED": "A public code or artifact link was detected.",
        "PARTIAL": "A code/artifact availability statement was detected, but the artifact is not clearly available right now.",
        "NOT_FOUND": "No clear public code or artifact link was detected.",
    },
    "data_artifact": {
        "SUPPORTED": "A public data or dataset access signal was detected.",
        "PARTIAL": "A public-data statement was detected, but an exact released dataset artifact was not clearly identified.",
        "NOT_FOUND": "No clear public data artifact or dataset link was detected.",
    },
    "availability_statement": {
        "SUPPORTED": "The paper includes a confirmed, explicit availability statement with a direct artifact or repository link.",
        "PARTIAL": "The paper includes a partial or future availability statement.",
        "NOT_FOUND": "No explicit availability statement was detected.",
    },
    "execution_instructions": {
        "SUPPORTED": "Concrete execution or reproduction instructions were detected.",
        "PARTIAL": "Some reproduction-package wording was detected, but step-by-step execution instructions were limited.",
        "NOT_FOUND": "No reproducibility package or clear execution instructions were detected.",
    },
    "hyperparams_detail": {
        "SUPPORTED": "The paper reports concrete hyperparameter settings.",
        "PARTIAL": "The paper reports some hyperparameter details, but coverage is incomplete.",
        "NOT_FOUND": "Hyperparameter details were not clearly reported.",
    },
    "seed_disclosed": {
        "SUPPORTED": "The paper reports explicit random-seed information.",
        "PARTIAL": "The paper contains a partial seed-related statement.",
        "NOT_FOUND": "No explicit random-seed information was detected.",
    },
    "compute_detail": {
        "SUPPORTED": "The paper reports concrete compute or hardware details.",
        "PARTIAL": "The paper includes limited compute/environment detail.",
        "NOT_FOUND": "Compute or hardware details were not clearly reported.",
    },
    "software_versions": {
        "SUPPORTED": "The paper includes software/toolchain details with useful version specificity.",
        "PARTIAL": "The paper names software/tooling, but version specificity is limited.",
        "NOT_FOUND": "Software or toolchain version details were not clearly reported.",
    },
    "evaluation_protocol": {
        "SUPPORTED": "The validation and evaluation protocol is clearly described.",
        "PARTIAL": "The paper reports some evaluation details, but the protocol is only partially specified.",
        "NOT_FOUND": "Validation or test protocol details are limited.",
    },
    # Previously missing — now included:
    "ablation": {
        "SUPPORTED": "An ablation study or ablation experiments were detected.",
        "PARTIAL": "Some ablation-related language was found, but a full study was not clearly described.",
        "NOT_FOUND": "No ablation study was detected.",
    },
    "baseline_comparison": {
        "SUPPORTED": "Explicit baseline comparisons or state-of-the-art benchmarking was detected.",
        "PARTIAL": "Baseline-related language was found, but comparisons are limited.",
        "NOT_FOUND": "No explicit baseline or comparative evaluation was detected.",
    },
    "statistical_rigor": {
        "SUPPORTED": "Statistical rigor signals (confidence intervals, multiple runs, p-values, etc.) were detected.",
        "PARTIAL": "Some statistical reporting language was found, but full rigor indicators are limited.",
        "NOT_FOUND": "No statistical rigor signals (confidence intervals, variance, etc.) were detected.",
    },
    "limitations": {
        "SUPPORTED": "A limitations section or threats-to-validity discussion was detected.",
        "PARTIAL": "Some limitations language was found, but a dedicated discussion appears limited.",
        "NOT_FOUND": "No limitations discussion was detected.",
    },
}

# Guard: every attribute in ATTRIBUTE_ORDER must have a bullet template.
_missing_templates = set(ATTRIBUTE_ORDER) - set(_BULLET_TEMPLATES.keys())
assert not _missing_templates, (
    f"_BULLET_TEMPLATES is missing entries for: {_missing_templates}"
)


def build_summary_bullets(attr_map: dict) -> list[str]:
    """Return one bullet per attribute in ATTRIBUTE_ORDER (all 13)."""
    bullets: list[str] = []
    for name in ATTRIBUTE_ORDER:
        state = attr_map[name]["state"]
        template = _BULLET_TEMPLATES[name]
        # Normalise the state key to the three canonical values used in templates.
        if state not in template:
            state = "NOT_FOUND"
        bullets.append(template[state])
    return bullets


def main():
    parser = argparse.ArgumentParser(
        description="Create transparent reproducibility and risk scores from discovered features."
    )
    _ = parser.parse_args()

    ensure_dir(OUT_SCORED_CSV.parent)
    ensure_dir(OUT_REPORT.parent)

    artifact = load_artifact()
    records = load_records()
    text_df = load_text_rows()

    weights_df = pd.DataFrame(
        [{"feature": name, "weight": ATTRIBUTE_WEIGHTS[name]} for name in ATTRIBUTE_ORDER]
    ).sort_values(by="weight", ascending=False)
    weights_df.to_csv(OUT_WEIGHTS_CSV, index=False)

    record_rows = []
    evidence_rows = []
    for record in records:
        attr_map = {item["name"]: item for item in record["attributes"]}

        # Guard: every expected attribute must be present in this record.
        missing = set(ATTRIBUTE_ORDER) - set(attr_map.keys())
        if missing:
            raise ValueError(
                f"Record {record.get('paper_uid', '?')} is missing attributes: {missing}"
            )

        section_scores = score_sections(attr_map)
        repro_score = float(record["reproducibility_score"])
        risk_score = float(record["risk_score"])
        summary_bullets = build_summary_bullets(attr_map)

        row = {
            "paper_uid": record["paper_uid"],
            "reproducibility_score": round(repro_score, 2),
            "risk_score": round(risk_score, 2),
            "risk_label": risk_label_from_score(risk_score),
            "summary_bullets": " || ".join(summary_bullets),
            "artifacts_and_data_risk": section_scores["artifacts_and_data"]["risk_score"],
            "implementation_detail_risk": section_scores["implementation_detail"]["risk_score"],
            "evaluation_rigor_risk": section_scores["evaluation_rigor"]["risk_score"],
        }
        for name in ATTRIBUTE_ORDER:
            row[name] = float(attr_map[name]["value"])
            row[f"{name}_state"] = attr_map[name]["state"]
        record_rows.append(row)

        evidence_rows.append(
            {
                "paper_uid": record["paper_uid"],
                "risk_score": round(risk_score, 2),
                "risk_label": risk_label_from_score(risk_score),
                "attributes": record["attributes"],
                "section_scores": section_scores,
                "summary_bullets": summary_bullets,
            }
        )

    feature_df = pd.DataFrame(record_rows)
    merged = text_df.merge(feature_df, on="paper_uid", how="inner")
    merged = merged.drop_duplicates(subset=["paper_uid"]).reset_index(drop=True)
    merged.to_csv(OUT_SCORED_CSV, index=False)

    with OUT_EVIDENCE_JSONL.open("w", encoding="utf-8") as f:
        for row in evidence_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "rows_scored": int(len(merged)),
        "feature_count": int(len(artifact.get("feature_columns", []))),
        "avg_reproducibility_score": float(merged["reproducibility_score"].mean()),
        "avg_risk_score": float(merged["risk_score"].mean()),
        "weights_csv": str(OUT_WEIGHTS_CSV),
        "scored_csv": str(OUT_SCORED_CSV),
        "evidence_jsonl": str(OUT_EVIDENCE_JSONL),
        "scoring_method": "transparent_weighted_attribute_rubric_v3",
    }
    write_json(OUT_REPORT, report)

    print(f"✅ Auto-scored CSV saved to: {OUT_SCORED_CSV}")
    print(f"✅ Evidence JSONL saved to: {OUT_EVIDENCE_JSONL}")
    print(f"✅ Report saved to: {OUT_REPORT}")


if __name__ == "__main__":
    main()