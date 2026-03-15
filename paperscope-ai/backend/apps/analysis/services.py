from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Dict, List, Tuple

from django.db import transaction
from django.utils import timezone

from apps.logs_app.utils import log_error
from apps.papers.models import Keyword, PaperKeyword, Paper, PaperText
from .models import AnalysisJob, AnalysisResult, ModelVersion
from .model_registry_service import (
    list_models,
    get_active_model,
    predict_with_active_model,
    compute_base_feature_flags,
)


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "their", "there", "where", "which", "when",
    "have", "were", "been", "being", "using", "used", "use", "also", "than", "then", "into", "our", "your",
    "can", "could", "should", "would", "will", "may", "might", "not", "but", "are", "was", "were", "has", "had",
    "model", "paper", "results", "result", "method", "methods", "data", "dataset", "datasets", "study", "based",
    "approach", "analysis", "learning", "research", "show", "shows", "shown", "new", "high", "low", "medium",
}

LABEL_TO_DB = {
    "LOW": "Low",
    "MEDIUM": "Med",
    "MED": "Med",
    "HIGH": "High",
    "Low": "Low",
    "Medium": "Med",
    "Med": "Med",
    "High": "High",
}

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
WS_RE = re.compile(r"\s+")

# Real public artifact/code hosts only
ARTIFACT_LINK_RE = re.compile(
    r"(github\.com|gitlab\.com|huggingface\.co|zenodo|figshare|osf\.io|code\.ocean|anonymous\.4open\.science)",
    re.I,
)

VERSION_RE = re.compile(
    r"\b(v?\d+(\.\d+){0,3}|gpt-4|gpt-3\.5|claude|llama|gemini|mistral|verilator|iverilog|yosys|quartus|vivado)\b",
    re.I,
)
SEED_RE = re.compile(r"\b(seed|random seed|seeded|rng)\b", re.I)

PROMPT_RE = re.compile(
    r"\b(prompt|template|instruction|system prompt|few-shot|zero-shot|debug prompt|coverage prompt|fix prompt|feedback prompt|repair prompt|trace-aware)\b",
    re.I,
)

ARTIFACT_RE = re.compile(
    r"\b(docker|requirements\.txt|conda|environment\.yml|artifact evaluation|replication package|supplementary material|supplementary artifact|reproduce|reproducibility)\b",
    re.I,
)

TOOLCHAIN_RE = re.compile(
    r"\b(verilator|iverilog|yosys|vivado|quartus|vcs|questa|modelsim|myhdl|soda|synthesis|linter|compiler|smt|solver|testbench|golden model|parallel checking|simulation)\b",
    re.I,
)

BENCHMARK_RE = re.compile(
    r"\b(benchmark|public benchmark|open-source benchmark|verilogeval|rtllm|humaneval|mbpp|mnist|celeba|fifa|white wine|wine)\b",
    re.I,
)
METRIC_RE = re.compile(
    r"\b(pass@1|pass@10|accuracy|f1|precision|recall|coverage|branch coverage|false positive|fpr|area|gate count|success rate)\b",
    re.I,
)
ABLATION_RE = re.compile(r"\b(ablation|ablation study|w/o|without)\b", re.I)
BASELINE_RE = re.compile(r"\b(baseline|compared with|comparison|state-of-the-art|outperforms)\b", re.I)

LLM_TERM_RE = re.compile(
    r"\b(llm|large language model|large language models|gpt-4|gpt-3\.5|claude|llama|gemini|mistral)\b",
    re.I,
)

LLM_METHOD_CONTEXT_RE = re.compile(
    r"""
    (
        \b(llm|large\ language\ model|large\ language\ models|gpt-4|gpt-3\.5|claude|llama|gemini|mistral)\b
        .{0,120}
        \b(prompt|template|instruction|few-shot|zero-shot|chain-of-thought|in-context|generate|generation|repair|feedback|trace-aware|agent)\b
    )
    |
    (
        \b(prompt|template|instruction|few-shot|zero-shot|chain-of-thought|in-context|generate|generation|repair|feedback|trace-aware|agent)\b
        .{0,120}
        \b(llm|large\ language\ model|large\ language\ models|gpt-4|gpt-3\.5|claude|llama|gemini|mistral)\b
    )
    """,
    re.I | re.S | re.X,
)

LLM_METHOD_SECTION_RE = re.compile(
    r"""
    \b(we\ use|we\ employ|our\ method|our\ framework|our\ approach|uses|leverages|based\ on|built\ on)\b
    .{0,100}
    \b(llm|large\ language\ model|large\ language\ models|gpt-4|gpt-3\.5|claude|llama|gemini|mistral)\b
    """,
    re.I | re.S | re.X,
)

HDL_TERM_RE = re.compile(
    r"\b(verilog|rtl|hdl|hardware|synthesis|testbench|gate-level|logic design|circuit)\b",
    re.I,
)


def sanitize_text_for_db(value, *, collapse_whitespace: bool = False) -> str:
    text = str(value or "")
    text = text.replace("\x00", " ")
    text = CONTROL_RE.sub(" ", text)
    if collapse_whitespace:
        text = WS_RE.sub(" ", text).strip()
    return text


def sanitize_json_for_db(value):
    if isinstance(value, dict):
        return {
            sanitize_text_for_db(k, collapse_whitespace=True): sanitize_json_for_db(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json_for_db(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_json_for_db(v) for v in value]
    if isinstance(value, str):
        return sanitize_text_for_db(value, collapse_whitespace=False)
    return value


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def is_admin_user(user) -> bool:
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", None) == "ADMIN")


def sync_model_versions_from_registry() -> List[ModelVersion]:
    registry_models = list_models()
    active_spec = get_active_model()
    active_name = active_spec["name"] if active_spec else None

    existing = {mv.model_name: mv for mv in ModelVersion.objects.all()}
    ordered = []

    with transaction.atomic():
        if active_name:
            ModelVersion.objects.filter(active_flag=True).exclude(model_name=active_name).update(active_flag=False)

        for spec in registry_models:
            model_dir = f"backend/ml_assets/models/{spec['artifactSubdir']}"
            vectorizer_path = f"{model_dir}/vectorizer.joblib"
            classifier_path = f"{model_dir}/classifier.joblib"

            if spec.get("pipelineType") != "text_input_v1":
                vectorizer_path = f"{model_dir}/feature_columns.json"

            obj = existing.get(spec["name"])
            if obj is None:
                obj = ModelVersion.objects.create(
                    model_name=spec["name"],
                    artifact_path_vectorizer=vectorizer_path,
                    artifact_path_classifier=classifier_path,
                    active_flag=bool(spec.get("active")),
                )
            else:
                obj.artifact_path_vectorizer = vectorizer_path
                obj.artifact_path_classifier = classifier_path
                obj.active_flag = bool(spec.get("active"))
                obj.save(update_fields=["artifact_path_vectorizer", "artifact_path_classifier", "active_flag"])
            ordered.append(obj)

    return ordered


def get_active_model_version() -> ModelVersion:
    sync_model_versions_from_registry()
    active = ModelVersion.objects.filter(active_flag=True).first()
    if not active:
        raise RuntimeError("No active model version found in database.")
    return active


def normalize_db_label(label: str) -> str:
    return LABEL_TO_DB.get(str(label or "").strip(), "Med")


def label_from_score(score: float) -> str:
    if score < 35:
        return "Low"
    if score < 65:
        return "Med"
    return "High"


def score_from_prediction(label: str, probabilities: Dict[str, float] | None) -> float:
    probabilities = probabilities or {}
    if probabilities:
        low = probabilities.get("LOW", probabilities.get("Low", 0.0))
        med = probabilities.get("MEDIUM", probabilities.get("Med", probabilities.get("Medium", 0.0)))
        high = probabilities.get("HIGH", probabilities.get("High", 0.0))
        score = (low * 20.0) + (med * 55.0) + (high * 85.0)
    else:
        score = {"LOW": 25.0, "MEDIUM": 55.0, "HIGH": 82.0}.get(str(label or "").upper(), 55.0)
    return round(score, 2)


def extract_keywords(cleaned_text: str, limit: int = 8) -> List[Tuple[str, float]]:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-+]{2,}", cleaned_text.lower())
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    items = counts.most_common(limit)
    return [(word, round(freq / total, 6)) for word, freq in items]


def save_keywords_for_paper(paper: Paper, cleaned_text: str) -> None:
    cleaned_text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)
    PaperKeyword.objects.filter(paper=paper).delete()
    for word, weight in extract_keywords(cleaned_text):
        keyword, _ = Keyword.objects.get_or_create(keyword_text=word)
        PaperKeyword.objects.create(paper=paper, keyword=keyword, weight=weight)


def _detect_actual_llm_method_paper(text: str) -> bool:
    """
    True only when the paper itself appears to USE an LLM in its method/workflow.
    A background mention of 'large language models' should not trigger this.
    """
    text = text.lower()

    # Skip the earliest part to reduce false positives from intro/background mentions.
    start_idx = len(text) // 5
    body_text = text[start_idx:]

    llm_mentions_total = len(LLM_TERM_RE.findall(text))
    llm_mentions_body = len(LLM_TERM_RE.findall(body_text))
    llm_context_hits = len(LLM_METHOD_CONTEXT_RE.findall(body_text))
    llm_section_hits = len(LLM_METHOD_SECTION_RE.findall(body_text))
    prompt_hits = len(PROMPT_RE.findall(body_text))

    if llm_context_hits >= 1:
        return True

    if llm_section_hits >= 1:
        return True

    if llm_mentions_body >= 3 and prompt_hits >= 1:
        return True

    # If it only mentions LLM once or twice in the whole paper, treat that as likely background.
    if llm_mentions_total <= 2:
        return False

    return False


def _extract_calibration_signals(cleaned_text: str, base_flags: dict) -> dict:
    text = cleaned_text.lower()

    has_artifact_link = bool(ARTIFACT_LINK_RE.search(text))
    has_public_benchmark = bool(BENCHMARK_RE.search(text))
    has_version_details = bool(VERSION_RE.search(text))
    has_seed_mentions = bool(SEED_RE.search(text)) or bool(base_flags.get("has_seed"))
    has_prompt_details = bool(PROMPT_RE.search(text))
    has_artifact_package = bool(ARTIFACT_RE.search(text))

    toolchain_hits = {m.group(0).lower() for m in TOOLCHAIN_RE.finditer(text)}
    has_toolchain_details = len(toolchain_hits) >= 1

    has_metrics = bool(METRIC_RE.search(text)) or bool(base_flags.get("has_metrics"))
    has_ablation = bool(ABLATION_RE.search(text)) or bool(base_flags.get("has_ablation"))
    has_baselines = bool(BASELINE_RE.search(text)) or bool(base_flags.get("has_baselines"))
    has_env_details = bool(base_flags.get("has_env_details")) or has_toolchain_details or has_version_details

    is_hdl_paper = bool(HDL_TERM_RE.search(text))
    is_llm_method_paper = _detect_actual_llm_method_paper(text)

    strong_empirical = sum(
        [
            1 if has_metrics else 0,
            1 if has_ablation else 0,
            1 if has_baselines else 0,
            1 if has_public_benchmark else 0,
        ]
    ) >= 3

    return {
        "has_public_benchmark": has_public_benchmark,
        "has_artifact_link": has_artifact_link,
        "has_version_details": has_version_details,
        "has_seed_mentions": has_seed_mentions,
        "has_prompt_details": has_prompt_details,
        "has_artifact_package": has_artifact_package,
        "has_toolchain_details": has_toolchain_details,
        "has_metrics": has_metrics,
        "has_ablation": has_ablation,
        "has_baselines": has_baselines,
        "has_env_details": has_env_details,
        "is_hdl_paper": is_hdl_paper,
        "is_llm_method_paper": is_llm_method_paper,
        "strong_empirical": strong_empirical,
    }


def _apply_score_floors(score: float, signals: dict) -> float:
    floor_score = 0.0

    if not signals["has_artifact_link"] and not signals["has_artifact_package"]:
        floor_score = max(floor_score, 28.0)

    if (signals["is_hdl_paper"] or signals["is_llm_method_paper"]) and not signals["has_artifact_link"] and not signals["has_artifact_package"]:
        floor_score = max(floor_score, 30.0)

    if (
        (signals["is_hdl_paper"] or signals["is_llm_method_paper"])
        and not signals["has_artifact_link"]
        and (
            (signals["is_llm_method_paper"] and not signals["has_prompt_details"])
            or (signals["is_hdl_paper"] and not signals["has_toolchain_details"])
        )
    ):
        floor_score = max(floor_score, 32.0)

    return max(score, floor_score)


def _calibrate_score(cleaned_text: str, prediction: dict) -> dict:
    text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)
    base_flags = compute_base_feature_flags({"model_text": text})
    base_score = score_from_prediction(prediction.get("prediction"), prediction.get("probabilities"))
    signals = _extract_calibration_signals(text, base_flags)

    score = base_score
    negatives = []
    positives = []

    if not signals["has_artifact_link"]:
        score += 10
        negatives.append("No clear public code or artifact link was detected.")

    if not signals["has_artifact_package"]:
        score += 8
        negatives.append("No replication package, Docker/requirements, or supplementary artifact package was detected.")

    if not signals["has_seed_mentions"]:
        score += 2
        negatives.append("Random seed information is missing or unclear.")

    if not signals["has_env_details"]:
        score += 2
        negatives.append("Exact environment or version details are limited.")

    # Only apply prompt penalty to actual LLM-method papers
    if signals["is_llm_method_paper"] and not signals["has_prompt_details"]:
        score += 6
        negatives.append("Prompt/template details for the LLM-driven workflow are not clearly disclosed.")

    # Only apply toolchain penalty to actual HDL/hardware papers
    if signals["is_hdl_paper"] and not signals["has_toolchain_details"]:
        score += 5
        negatives.append("Hardware or verification toolchain details are not fully specified.")

    if signals["has_public_benchmark"]:
        score -= 2
        positives.append("Named public benchmarks are reported.")

    if signals["has_baselines"]:
        score -= 2
        positives.append("The paper includes baseline comparisons.")

    if signals["has_ablation"]:
        score -= 2
        positives.append("The paper includes ablation-style evidence.")

    if signals["strong_empirical"]:
        score -= 2
        positives.append("The evaluation is comparatively strong and benchmark-driven.")

    score = clamp_score(score)
    score = _apply_score_floors(score, signals)
    score = round(score, 2)
    db_label = label_from_score(score)

    return {
        "base_score": base_score,
        "calibrated_score": score,
        "db_label": db_label,
        "base_flags": base_flags,
        "signals": signals,
        "negatives": negatives,
        "positives": positives,
    }


def _build_section_scores(calibration: dict) -> List[dict]:
    signals = calibration["signals"]

    methodology = 34
    if signals["has_ablation"]:
        methodology -= 4
    if signals["has_baselines"]:
        methodology -= 3

    if signals["is_llm_method_paper"]:
        if signals["has_prompt_details"]:
            methodology -= 5
        else:
            methodology += 8

    if signals["is_hdl_paper"]:
        if signals["has_toolchain_details"]:
            methodology -= 3
        else:
            methodology += 7

    data_availability = 36
    if signals["has_public_benchmark"]:
        data_availability -= 7
    else:
        data_availability += 10
    if signals["has_artifact_link"]:
        data_availability -= 4
    else:
        data_availability += 6

    statistical_rigor = 33
    if signals["has_metrics"]:
        statistical_rigor -= 4
    else:
        statistical_rigor += 8
    if signals["has_ablation"]:
        statistical_rigor -= 4
    if signals["strong_empirical"]:
        statistical_rigor -= 3

    code_availability = 45
    if signals["has_artifact_link"]:
        code_availability -= 10
    else:
        code_availability += 10
    if signals["has_artifact_package"]:
        code_availability -= 8
    else:
        code_availability += 10

    def clamp_section(v: int) -> int:
        return max(10, min(95, v))

    return [
        {
            "name": "Methodology",
            "score": clamp_section(methodology),
            "detail": "Lower is better. This score reflects implementation specificity, prompt disclosure, and toolchain clarity.",
        },
        {
            "name": "Data Availability",
            "score": clamp_section(data_availability),
            "detail": "Lower is better. This score reflects benchmark/data transparency and artifact discoverability.",
        },
        {
            "name": "Statistical Rigor",
            "score": clamp_section(statistical_rigor),
            "detail": "Lower is better. This score reflects metrics, ablations, comparisons, and evaluation depth.",
        },
        {
            "name": "Code Availability",
            "score": clamp_section(code_availability),
            "detail": "Lower is better. This score reflects whether code/artifacts or reproducibility packages are directly available.",
        },
    ]


def build_explanation(cleaned_text: str, prediction: dict) -> dict:
    cleaned_text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)
    calibration = _calibrate_score(cleaned_text, prediction)
    keywords = [word for word, _ in extract_keywords(cleaned_text)]

    score = int(round(calibration["calibrated_score"]))
    db_label = calibration["db_label"]

    top_factors = calibration["negatives"] + calibration["positives"]
    if not top_factors:
        top_factors = ["The paper contains a balanced mix of reproducibility indicators."]

    summary = (
        f"The active model predicts {db_label} reproducibility risk after rule-based calibration. "
        f"The final risk score is {score}/100. "
        f"This score starts from the model prediction and is then adjusted using artifact availability, "
        f"toolchain/version disclosure, prompt transparency, and benchmark/evaluation strength."
    )

    return sanitize_json_for_db({
        "summary": summary,
        "topFactors": top_factors[:8],
        "sections": _build_section_scores(calibration),
        "keywords": keywords,
        "model": prediction.get("model", {}),
        "rawPrediction": prediction,
        "calibration": {
            "baseScore": calibration["base_score"],
            "finalScore": calibration["calibrated_score"],
            "signals": calibration["signals"],
        },
    })


def run_analysis_for_paper(*, paper: Paper, user, title: str, cleaned_text: str, raw_text: str, abstract: str = "") -> AnalysisJob:
    title = sanitize_text_for_db(title, collapse_whitespace=True)
    cleaned_text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)
    raw_text = sanitize_text_for_db(raw_text, collapse_whitespace=False)
    abstract = sanitize_text_for_db(abstract, collapse_whitespace=True)

    job = AnalysisJob.objects.create(
        paper=paper,
        user=user,
        status=AnalysisJob.Status.QUEUED,
    )

    try:
        job.status = AnalysisJob.Status.PROCESSING
        job.save(update_fields=["status"])

        PaperText.objects.update_or_create(
            paper=paper,
            defaults={
                "raw_text": raw_text,
                "cleaned_text": cleaned_text,
            },
        )

        save_keywords_for_paper(paper, cleaned_text)

        active_model_version = get_active_model_version()
        prediction = predict_with_active_model({
            "title": title,
            "abstract": abstract,
            "model_text": cleaned_text,
            "review_text": "",
            "decision_text": "",
            "venue": "",
            "year": 0,
            "review_count": 0,
        })

        explanation = build_explanation(cleaned_text, prediction)
        final_score = float(explanation["calibration"]["finalScore"])
        db_label = label_from_score(final_score)
        now = timezone.now()

        AnalysisResult.objects.update_or_create(
            job=job,
            defaults={
                "model_version": active_model_version,
                "risk_score": Decimal(str(round(final_score, 2))),
                "risk_label": db_label,
                "explanation_json": explanation,
                "completed_at": now,
            },
        )

        job.status = AnalysisJob.Status.DONE
        job.completed_at = now
        job.error_message = None
        job.save(update_fields=["status", "completed_at", "error_message"])
        return job

    except Exception as exc:
        now = timezone.now()
        safe_error = sanitize_text_for_db(str(exc), collapse_whitespace=True)
        job.status = AnalysisJob.Status.FAILED
        job.completed_at = now
        job.error_message = safe_error
        job.save(update_fields=["status", "completed_at", "error_message"])
        log_error(module_name="analysis_pipeline", message=safe_error, user=user, paper=paper)
        raise


def retry_analysis_job(job: AnalysisJob, *, requested_by) -> AnalysisJob:
    paper = job.paper
    text_obj = getattr(paper, "text", None)
    if text_obj is None:
        raise ValueError("Paper text is missing, so this job cannot be retried.")

    return run_analysis_for_paper(
        paper=paper,
        user=job.user,
        title=paper.title,
        cleaned_text=text_obj.cleaned_text,
        raw_text=text_obj.raw_text,
        abstract="",
    )