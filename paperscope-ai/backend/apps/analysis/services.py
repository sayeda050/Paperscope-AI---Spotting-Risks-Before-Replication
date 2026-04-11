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

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
WS_RE = re.compile(r"\s+")

# Artifact / code / availability
ARTIFACT_LINK_RE = re.compile(
    r"(github\.com|gitlab\.com|bitbucket\.org|huggingface\.co|zenodo|figshare|osf\.io|code\.ocean|anonymous\.4open\.science)",
    re.I,
)
AVAILABILITY_SECTION_RE = re.compile(
    r"\b(data and source code availability|data availability|code availability|availability of data and materials|software availability)\b",
    re.I,
)
PUBLIC_DATA_RE = re.compile(
    r"\b(tcga|geo|sra|dbgap|uk biobank|seer|physionet|mimic|kaggle|uci|openml|yahoo finance|public dataset|public repository|public repositories)\b",
    re.I,
)
ARTIFACT_PACKAGE_RE = re.compile(
    r"\b(docker|requirements\.txt|conda|environment\.yml|replication package|artifact package|supplementary artifact|supplementary material)\b",
    re.I,
)
EXECUTION_RE = re.compile(
    r"\b(readme|installation|install(ation)? instructions|how to run|run the code|command line|cli|scripts are available|reproducible workflow|implementation available)\b",
    re.I,
)

# Method / params / environment
SEED_RE = re.compile(r"\b(seed|random seed|seeded|rng)\b", re.I)
VERSION_RE = re.compile(
    r"\b("
    r"python\s*\d+(\.\d+){0,2}|"
    r"pytorch\s*\d+(\.\d+){0,2}|"
    r"tensorflow\s*\d+(\.\d+){0,2}|"
    r"scikit[- ]learn\s*\d+(\.\d+){0,2}|"
    r"sklearn\s*\d+(\.\d+){0,2}|"
    r"cuda\s*\d+(\.\d+){0,2}|"
    r"ubuntu\s*\d+(\.\d+){0,2}|"
    r"r\s*version\s*\d+(\.\d+){0,2}|"
    r"matlab\s*r?\d{4}[ab]?|"
    r"package version|software version|library version"
    r")\b",
    re.I,
)
ENV_RE = re.compile(
    r"\b(gpu|cpu|cuda|ubuntu|linux|hardware|software version|library version|package version|server|cluster)\b",
    re.I,
)
PARAM_DETAIL_RE = re.compile(
    r"\b(learning rate|batch size|epochs?|dropout|optimizer|weight decay|hidden size|population size|number of simulation|time step|risk[- ]free rate|garch\(1,1\)|l-bfgs-b|hyperparameter|parameter setting|grid search|concordance index|root-leanness)\b",
    re.I,
)
ALGORITHM_RE = re.compile(r"\balgorithm\s+\d+\b", re.I)
TABLE_RE = re.compile(r"\btable\s+[ivxlcdm]+\b", re.I)
EQUATION_ID_RE = re.compile(r"\(\d+\)")

# Evaluation rigor
METRIC_RE = re.compile(
    r"\b(accuracy|f1|precision|recall|auc|auroc|concordance index|c-index|bleu|rouge|mse|mae|rmse|hazard ratio|success rate|mean error|hypervolume|pareto delta|price error)\b",
    re.I,
)
BASELINE_RE = re.compile(
    r"\b(baseline|compared with|comparison|clinical-only|versus|vs\.?|benchmark against|outperform)\b",
    re.I,
)
ABLATION_RE = re.compile(r"\b(ablation|ablation study|w/o|without)\b", re.I)
CV_RE = re.compile(r"\b(cross-validation|k-fold|5-fold|10-fold|holdout|held-out|train-test split)\b", re.I)
NESTED_CV_RE = re.compile(r"\b(nested validation|nested cross-validation)\b", re.I)
EXTERNAL_VALIDATION_RE = re.compile(r"\b(external validation|independent cohort|left-out sets|testing performance)\b", re.I)
STAT_TEST_RE = re.compile(
    r"\b(p-value|confidence interval|statistical significance|variance|standard deviation|std\.?|wilcoxon|t-test|anova)\b",
    re.I,
)

# Scientific writing quality indicators
LIMITATIONS_RE = re.compile(
    r"\b(limitations?|future work|overestimation|challenge|cohort-dependent|generalization gap|bias|scope)\b",
    re.I,
)
SUPPLEMENTARY_RE = re.compile(r"\b(supplementary|appendix|supplementary section|supplementary fig|supplementary table)\b", re.I)

# Domain detectors
ML_RE = re.compile(
    r"\b(machine learning|deep learning|neural network|transformer|classifier|regression|feature selection|genetic algorithm|optimization)\b",
    re.I,
)
LLM_RE = re.compile(
    r"\b(llm|large language model|large language models|gpt-4|gpt-3\.5|claude|llama|gemini|mistral)\b",
    re.I,
)
HDL_RE = re.compile(
    r"\b(verilog|rtl|hdl|hardware|synthesis|testbench|compiler|simulator|simulation toolchain)\b",
    re.I,
)
BIOMED_RE = re.compile(
    r"\b(omics|multi-omic|multi-omics|gene|genomic|transcriptomic|mirna|mrna|biomarker|cancer|patient|cohort|survival analysis|clinical)\b",
    re.I,
)
FINANCE_RE = re.compile(
    r"\b(option pricing|black[- ]scholes|heston|garch|jump diffusion|merton|strike price|implied volatility|financial market|call option|put option)\b",
    re.I,
)

# Theory / conceptual detectors
THEOREM_RE = re.compile(r"\b(theorem|lemma|corollary|proposition|claim|proof)\b", re.I)
THEORY_KEYWORD_RE = re.compile(
    r"\b(local limit theorem|poisson convergence|normal convergence|asymptotic normality|stein'?s method|exchangeable pairs|method of moments|galton[-– ]watson|quality-ladder framework|comparative statics|equilibrium)\b",
    re.I,
)
APPENDIX_MATH_RE = re.compile(
    r"\b(appendix|supplementary material|supplementary section|for completeness|we prove|proof of theorem|proof of lemma)\b",
    re.I,
)
EMPIRICAL_PROTOCOL_RE = re.compile(
    r"\b(dataset|datasets|cohort|cohorts|benchmark|cross-validation|held-out|train-test|ablation|baseline|external validation|survey|participant|participants|experiment|experiments|evaluation protocol)\b",
    re.I,
)
CONCEPTUAL_MODEL_RE = re.compile(
    r"\b(framework|model|equilibrium|comparative statics|innovation|firms|welfare|policy|distance|knowledge recombination|quality-ladder|creative destruction|recombinant innovation|random trees|probability distribution)\b",
    re.I,
)
LIVE_DATA_RE = re.compile(
    r"\b(live market data|fetched at the time of execution|obtained .* at the time of execution|live data)\b",
    re.I,
)
ASSUMPTION_RE = re.compile(r"\b(assume|assumption|assumptions)\b", re.I)
JEL_RE = re.compile(r"\bjel classification\b", re.I)


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


def label_from_score(score: float) -> str:
    if score < 35:
        return "Low"
    if score < 65:
        return "Med"
    return "High"


def score_from_prediction(label: str, probabilities: Dict[str, float] | None) -> float:
    probabilities = probabilities or {}
    upper_probs = {str(k).upper(): float(v) for k, v in probabilities.items()}

    if "YES" in upper_probs or "NO" in upper_probs:
        yes = upper_probs.get("YES")
        no = upper_probs.get("NO")

        if yes is None and no is not None:
            yes = 1.0 - no
        if no is None and yes is not None:
            no = 1.0 - yes

        if no is not None:
            return round(float(no) * 100.0, 2)

    if {"LOW", "MEDIUM", "HIGH"} & set(upper_probs.keys()):
        low = upper_probs.get("LOW", 0.0)
        med = upper_probs.get("MEDIUM", upper_probs.get("MED", 0.0))
        high = upper_probs.get("HIGH", 0.0)
        return round((low * 20.0) + (med * 55.0) + (high * 85.0), 2)

    raw = str(label or "").strip().upper()
    if raw == "YES":
        return 25.0
    if raw == "NO":
        return 75.0
    if raw == "LOW":
        return 25.0
    if raw in {"MEDIUM", "MED"}:
        return 55.0
    if raw == "HIGH":
        return 82.0
    return 55.0


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
    text = text.lower()
    start_idx = len(text) // 5
    body_text = text[start_idx:]

    llm_mentions_total = len(LLM_RE.findall(text))
    llm_mentions_body = len(LLM_RE.findall(body_text))
    prompt_hits = len(re.findall(r"\b(prompt|template|instruction|few-shot|zero-shot|chain-of-thought|in-context|agent)\b", body_text, re.I))
    method_hits = len(re.findall(r"\b(we use|we employ|our method|our framework|our approach|uses|leverages|based on|built on)\b", body_text, re.I))

    if llm_mentions_body >= 2 and (prompt_hits >= 1 or method_hits >= 1):
        return True
    if llm_mentions_total <= 2:
        return False
    return llm_mentions_body >= 3


def _paper_type_scores(title: str, abstract: str, cleaned_text: str, signals: dict) -> dict:
    combined = f"{title} {abstract} {cleaned_text}".lower()

    theory_score = 0
    conceptual_score = 0
    empirical_score = 0

    if signals["theorem_count"] >= 2:
        theory_score += 3
    if signals["equation_count"] >= 3:
        theory_score += 1
    if signals["appendix_math_hits"] >= 1:
        theory_score += 1
    theory_keyword_hits = len(THEORY_KEYWORD_RE.findall(combined))
    if theory_keyword_hits >= 2:
        theory_score += 3
    elif theory_keyword_hits == 1:
        theory_score += 2

    conceptual_hits = len(CONCEPTUAL_MODEL_RE.findall(combined))
    if conceptual_hits >= 2:
        conceptual_score += 3
    elif conceptual_hits == 1:
        conceptual_score += 2
    if ASSUMPTION_RE.search(combined):
        conceptual_score += 1
    if JEL_RE.search(combined):
        conceptual_score += 2
    if signals["equation_count"] >= 2:
        conceptual_score += 1
    if signals["has_limitations"]:
        conceptual_score += 1

    empirical_score += signals["strong_empirical_evidence_count"]
    if signals["has_metrics"]:
        empirical_score += 1
    if signals["table_count"] >= 2:
        empirical_score += 1

    is_theory_heavy = theory_score >= 4 and empirical_score <= 1
    is_conceptual = not is_theory_heavy and conceptual_score >= 3 and empirical_score <= 1
    is_empirical = not is_theory_heavy and not is_conceptual

    return {
        "theory_score": theory_score,
        "conceptual_score": conceptual_score,
        "empirical_score": empirical_score,
        "is_theory_heavy": is_theory_heavy,
        "is_conceptual": is_conceptual,
        "is_empirical": is_empirical,
    }


def _extract_repro_signals(title: str, abstract: str, cleaned_text: str, base_flags: dict) -> dict:
    title = title or ""
    abstract = abstract or ""
    cleaned_text = cleaned_text or ""
    combined = f"{title}\n{abstract}\n{cleaned_text}"
    text = combined.lower()

    equation_count = len(EQUATION_ID_RE.findall(text))
    algorithm_count = len(ALGORITHM_RE.findall(text))
    table_count = len(TABLE_RE.findall(text))
    theorem_count = len(THEOREM_RE.findall(text))
    appendix_math_hits = len(APPENDIX_MATH_RE.findall(text))
    conceptual_hits = len(CONCEPTUAL_MODEL_RE.findall(text))
    empirical_hits = len(EMPIRICAL_PROTOCOL_RE.findall(text))

    has_public_code = bool(ARTIFACT_LINK_RE.search(text))
    has_availability_section = bool(AVAILABILITY_SECTION_RE.search(text))
    has_public_data = bool(PUBLIC_DATA_RE.search(text))
    has_artifact_package = bool(ARTIFACT_PACKAGE_RE.search(text))
    has_execution_instructions = bool(EXECUTION_RE.search(text))
    has_live_runtime_data = bool(LIVE_DATA_RE.search(text))

    has_seed_mentions = bool(SEED_RE.search(text)) or bool(base_flags.get("has_seed"))
    has_version_details = bool(VERSION_RE.search(text))
    has_env_details = bool(ENV_RE.search(text)) or bool(base_flags.get("has_env_details"))
    has_parameter_details = bool(PARAM_DETAIL_RE.search(text)) or bool(base_flags.get("has_hyperparams"))

    has_metrics = bool(METRIC_RE.search(text)) or bool(base_flags.get("has_metrics"))
    has_baselines = bool(BASELINE_RE.search(text)) or bool(base_flags.get("has_baselines"))
    has_ablation = bool(ABLATION_RE.search(text)) or bool(base_flags.get("has_ablation"))
    has_cv = bool(CV_RE.search(text))
    has_nested_cv = bool(NESTED_CV_RE.search(text))
    has_external_validation = bool(EXTERNAL_VALIDATION_RE.search(text))
    has_stat_tests = bool(STAT_TEST_RE.search(text)) or bool(base_flags.get("has_statistical_tests"))

    has_limitations = bool(LIMITATIONS_RE.search(text)) or bool(base_flags.get("has_limitations"))
    has_supplementary = bool(SUPPLEMENTARY_RE.search(text))

    has_validation_design = has_cv or has_nested_cv or has_external_validation

    is_ml = bool(ML_RE.search(text))
    is_biomed = bool(BIOMED_RE.search(text))
    is_finance = bool(FINANCE_RE.search(text))
    is_hdl = bool(HDL_RE.search(text))
    is_llm_method = _detect_actual_llm_method_paper(text)

    strong_empirical_evidence_count = sum(
        [
            1 if has_public_data else 0,
            1 if has_validation_design else 0,
            1 if has_baselines else 0,
            1 if has_ablation else 0,
            1 if (has_metrics and table_count >= 2) else 0,
            1 if empirical_hits >= 2 else 0,
        ]
    )

    has_strong_theory_detail = (
        theorem_count >= 5
        or appendix_math_hits >= 1
        or len(THEORY_KEYWORD_RE.findall(text)) >= 2
    )

    has_strong_method_detail = (
        has_strong_theory_detail
        or (
            (equation_count >= 3 or algorithm_count >= 1 or has_parameter_details)
            and (table_count >= 2 or has_validation_design or has_public_data)
        )
    )

    strong_eval = sum(
        [
            1 if has_metrics else 0,
            1 if has_baselines else 0,
            1 if has_ablation else 0,
            1 if has_validation_design else 0,
            1 if has_stat_tests else 0,
        ]
    ) >= 3

    code_heavy_domain = is_ml or is_llm_method or is_hdl or is_finance or (is_biomed and strong_empirical_evidence_count >= 2)

    signals = {
        "has_public_code": has_public_code,
        "has_availability_section": has_availability_section,
        "has_public_data": has_public_data,
        "has_artifact_package": has_artifact_package,
        "has_execution_instructions": has_execution_instructions,
        "has_live_runtime_data": has_live_runtime_data,
        "has_seed_mentions": has_seed_mentions,
        "has_version_details": has_version_details,
        "has_env_details": has_env_details,
        "has_parameter_details": has_parameter_details,
        "has_metrics": has_metrics,
        "has_baselines": has_baselines,
        "has_ablation": has_ablation,
        "has_cv": has_cv,
        "has_nested_cv": has_nested_cv,
        "has_external_validation": has_external_validation,
        "has_stat_tests": has_stat_tests,
        "has_limitations": has_limitations,
        "has_supplementary": has_supplementary,
        "has_validation_design": has_validation_design,
        "has_strong_method_detail": has_strong_method_detail,
        "has_strong_theory_detail": has_strong_theory_detail,
        "strong_eval": strong_eval,
        "equation_count": equation_count,
        "algorithm_count": algorithm_count,
        "table_count": table_count,
        "theorem_count": theorem_count,
        "appendix_math_hits": appendix_math_hits,
        "conceptual_hits": conceptual_hits,
        "empirical_hits": empirical_hits,
        "strong_empirical_evidence_count": strong_empirical_evidence_count,
        "is_ml": is_ml,
        "is_biomed": is_biomed,
        "is_finance": is_finance,
        "is_hdl": is_hdl,
        "is_llm_method": is_llm_method,
        "code_heavy_domain": code_heavy_domain,
    }
    signals.update(_paper_type_scores(title, abstract, cleaned_text, signals))
    return signals


def _apply_general_floor(score: float, signals: dict) -> float:
    floor_score = 0.0

    if signals["is_theory_heavy"]:
        floor_score = max(floor_score, 16.0)

    if signals["is_conceptual"]:
        floor_score = max(floor_score, 26.0)

    if signals["is_empirical"] and not signals["has_public_code"] and not signals["has_public_data"]:
        floor_score = max(floor_score, 28.0)

    if (
        signals["is_empirical"]
        and signals["code_heavy_domain"]
        and not signals["has_public_code"]
        and not signals["has_artifact_package"]
    ):
        floor_score = max(floor_score, 32.0)

    if (
        signals["is_empirical"]
        and signals["has_public_code"]
        and signals["has_public_data"]
        and signals["strong_eval"]
        and not signals["has_seed_mentions"]
    ):
        floor_score = max(floor_score, 22.0)

    if signals["is_finance"] and signals["has_live_runtime_data"]:
        floor_score = max(floor_score, 34.0)

    return max(score, floor_score)


def _calibrate_score(title: str, abstract: str, cleaned_text: str, prediction: dict) -> dict:
    text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)
    base_flags = compute_base_feature_flags({"model_text": text})

    raw_base_score = score_from_prediction(prediction.get("prediction"), prediction.get("probabilities"))
    tempered_base_score = 55.0 + 0.45 * (raw_base_score - 55.0)
    signals = _extract_repro_signals(title or "", abstract or "", text, base_flags)

    negatives: List[str] = []
    positives: List[str] = []

    # THEORY-HEAVY PAPERS
    if signals["is_theory_heavy"]:
        score = 31.0 + 0.08 * (tempered_base_score - 50.0)

        if signals["theorem_count"] >= 2:
            score -= 5
            positives.append("The paper is structured around explicit theorems, lemmas, or proofs.")

        if signals["equation_count"] >= 5:
            score -= 2
            positives.append("The paper provides substantial mathematical derivations.")

        if signals["appendix_math_hits"] >= 1 or signals["has_supplementary"]:
            score -= 3
            positives.append("The paper includes appendix or supplementary proof material.")

        if signals["has_strong_theory_detail"]:
            score -= 3
            positives.append("The theoretical development is comparatively detailed and complete.")

        if signals["has_limitations"]:
            score -= 1
            positives.append("The paper explicitly discusses limitations or scope conditions.")

        if signals["has_public_code"]:
            score -= 1
            positives.append("A public code or artifact link was detected.")

        if signals["has_availability_section"]:
            score -= 1
            positives.append("The paper includes an explicit availability or supplementary statement.")

        if signals["theorem_count"] < 2 and signals["equation_count"] < 3:
            score += 3
            negatives.append("Theoretical justification is limited or lightly documented.")

        score = clamp_score(score)
        score = _apply_general_floor(score, signals)
        score = round(score, 2)
        db_label = label_from_score(score)

        return {
            "raw_base_score": raw_base_score,
            "tempered_base_score": round(tempered_base_score, 2),
            "calibrated_score": score,
            "db_label": db_label,
            "base_flags": base_flags,
            "signals": signals,
            "negatives": negatives,
            "positives": positives,
        }

    # CONCEPTUAL / MODEL PAPERS
    if signals["is_conceptual"]:
        score = 41.0 + 0.10 * (tempered_base_score - 50.0)

        if not signals["has_public_code"]:
            score += 2
            negatives.append("No clear public code or artifact link was detected.")

        if not signals["has_public_data"]:
            score += 1
            negatives.append("No explicit public data or repository access statement was detected.")

        if not signals["has_artifact_package"] and not signals["has_execution_instructions"]:
            score += 1
            negatives.append("No reproducibility package or clear execution instructions were detected.")

        if signals["equation_count"] >= 3:
            score -= 3
            positives.append("The paper provides a substantial mathematical formulation.")

        if signals["algorithm_count"] >= 1:
            score -= 2
            positives.append("The paper includes explicit algorithmic steps or pseudocode.")

        if signals["has_limitations"]:
            score -= 1
            positives.append("The paper explicitly discusses limitations or scope conditions.")

        if signals["has_supplementary"]:
            score -= 1
            positives.append("The paper references supplementary material.")

        if signals["has_availability_section"]:
            score -= 2
            positives.append("The paper includes an explicit availability statement.")

        if signals["has_public_code"]:
            score -= 2
            positives.append("A public code or artifact link was detected.")

        if signals["has_public_data"]:
            score -= 2
            positives.append("The paper clearly discloses a public dataset, cohort, or data source.")

        score = clamp_score(score)
        score = _apply_general_floor(score, signals)
        score = round(score, 2)
        db_label = label_from_score(score)

        return {
            "raw_base_score": raw_base_score,
            "tempered_base_score": round(tempered_base_score, 2),
            "calibrated_score": score,
            "db_label": db_label,
            "base_flags": base_flags,
            "signals": signals,
            "negatives": negatives,
            "positives": positives,
        }

    # EMPIRICAL / ARTIFACT-DRIVEN PAPERS
    score = 52.0 + 0.35 * (tempered_base_score - 52.0)

    if not signals["has_public_code"]:
        score += 5 if signals["code_heavy_domain"] else 3
        negatives.append("No clear public code or artifact link was detected.")

    if not signals["has_public_data"]:
        score += 3
        negatives.append("No explicit public data or repository access statement was detected.")

    if not signals["has_artifact_package"] and not signals["has_execution_instructions"]:
        score += 3
        negatives.append("No reproducibility package or clear execution instructions were detected.")

    if not signals["has_seed_mentions"]:
        score += 2 if signals["code_heavy_domain"] else 1
        negatives.append("Random seed information is missing or unclear.")

    if not (signals["has_env_details"] or signals["has_version_details"]):
        score += 2 if signals["code_heavy_domain"] else 1
        negatives.append("Exact environment or software-version details are limited.")

    if not signals["has_validation_design"]:
        score += 4
        negatives.append("Validation or test protocol details are limited.")

    if not signals["has_metrics"]:
        score += 4
        negatives.append("Evaluation metrics are not clearly specified.")

    combined_for_checks = f"{title} {abstract} {text}"

    if signals["is_llm_method"] and not re.search(r"\b(prompt|template|instruction|few-shot|zero-shot)\b", combined_for_checks, re.I):
        score += 3
        negatives.append("Prompt or instruction details for the LLM workflow are not clearly disclosed.")

    if signals["is_hdl"] and not re.search(r"\b(verilator|iverilog|yosys|vivado|quartus|compiler|simulator)\b", combined_for_checks, re.I):
        score += 3
        negatives.append("Hardware toolchain details are not fully specified.")

    if signals["has_live_runtime_data"]:
        score += 4
        negatives.append("The results depend on live or time-varying market data, which makes exact reruns harder.")

    if signals["has_public_code"]:
        score -= 6
        positives.append("A public code or artifact link was detected.")

    if signals["has_availability_section"]:
        score -= 3
        positives.append("The paper includes an explicit availability statement.")

    if signals["has_public_data"]:
        score -= 2 if signals["has_live_runtime_data"] else 5
        positives.append("The paper clearly discloses a public dataset, cohort, or data source.")

    if signals["has_artifact_package"]:
        score -= 2
        positives.append("The paper mentions an artifact or reproducibility package.")

    if signals["has_execution_instructions"]:
        score -= 2
        positives.append("The paper or artifact indicates how the work can be executed or reproduced.")

    if signals["has_seed_mentions"]:
        score -= 2
        positives.append("The paper reports random seed information.")

    if signals["has_env_details"] or signals["has_version_details"]:
        score -= 2
        positives.append("The paper includes environment or software-version details.")

    if signals["has_parameter_details"]:
        score -= 3
        positives.append("The paper reports concrete modeling or hyperparameter settings.")

    if signals["equation_count"] >= 3:
        score -= 1.5
        positives.append("The paper provides a substantial mathematical formulation.")

    if signals["algorithm_count"] >= 1:
        score -= 2
        positives.append("The paper includes explicit algorithmic steps or pseudocode.")

    if signals["table_count"] >= 3:
        score -= 1.5
        positives.append("The paper reports multiple result tables for comparison.")

    if signals["has_metrics"]:
        score -= 2
        positives.append("The paper clearly specifies evaluation metrics.")

    if signals["has_baselines"]:
        score -= 1.5
        positives.append("The paper includes baseline comparisons.")

    if signals["has_ablation"]:
        score -= 1.5
        positives.append("The paper includes ablation-style evidence.")

    if signals["has_cv"]:
        score -= 2
        positives.append("The paper reports cross-validation or held-out evaluation.")

    if signals["has_nested_cv"]:
        score -= 1.5
        positives.append("The paper reports nested validation.")

    if signals["has_external_validation"]:
        score -= 1.5
        positives.append("The paper includes external or left-out testing evidence.")

    if signals["has_stat_tests"]:
        score -= 1.5
        positives.append("The paper reports statistical uncertainty or significance information.")

    if signals["has_limitations"]:
        score -= 1
        positives.append("The paper explicitly discusses limitations or generalization issues.")

    if signals["has_supplementary"]:
        score -= 1
        positives.append("The paper references supplementary material.")

    if signals["has_strong_method_detail"]:
        score -= 3
        positives.append("The paper provides comparatively detailed methodological disclosure.")

    if signals["strong_eval"]:
        score -= 1.5
        positives.append("The evaluation protocol is comparatively strong and well specified.")

    score = clamp_score(score)
    score = _apply_general_floor(score, signals)
    score = round(score, 2)
    db_label = label_from_score(score)

    return {
        "raw_base_score": raw_base_score,
        "tempered_base_score": round(tempered_base_score, 2),
        "calibrated_score": score,
        "db_label": db_label,
        "base_flags": base_flags,
        "signals": signals,
        "negatives": negatives,
        "positives": positives,
    }


def _build_section_scores(calibration: dict) -> List[dict]:
    s = calibration["signals"]

    if s["is_theory_heavy"]:
        methodology = 30
        if s["theorem_count"] >= 2:
            methodology -= 5
        if s["equation_count"] >= 5:
            methodology -= 3
        if s["has_strong_theory_detail"]:
            methodology -= 4
        if s["appendix_math_hits"] >= 1 or s["has_supplementary"]:
            methodology -= 3

        data_availability = 28
        if s["has_availability_section"]:
            data_availability -= 2
        if s["has_public_code"]:
            data_availability -= 2

        statistical_rigor = 29
        if s["theorem_count"] >= 2:
            statistical_rigor -= 4
        if s["has_limitations"]:
            statistical_rigor -= 1
        if s["equation_count"] >= 5:
            statistical_rigor -= 2

        code_availability = 30
        if s["has_public_code"]:
            code_availability -= 3
        if s["has_execution_instructions"]:
            code_availability -= 2

    elif s["is_conceptual"]:
        methodology = 39
        if s["equation_count"] >= 3:
            methodology -= 3
        if s["algorithm_count"] >= 1:
            methodology -= 2
        if s["has_supplementary"]:
            methodology -= 1

        data_availability = 37
        if s["has_availability_section"]:
            data_availability -= 2
        if s["has_public_code"]:
            data_availability -= 2
        if s["has_public_data"]:
            data_availability -= 2

        statistical_rigor = 37
        if s["has_metrics"]:
            statistical_rigor -= 2
        if s["has_limitations"]:
            statistical_rigor -= 1

        code_availability = 39
        if s["has_public_code"]:
            code_availability -= 3
        if s["has_execution_instructions"]:
            code_availability -= 2

    else:
        methodology = 45
        if s["has_parameter_details"]:
            methodology -= 7
        if s["equation_count"] >= 3:
            methodology -= 5
        if s["algorithm_count"] >= 1:
            methodology -= 6
        if s["has_strong_method_detail"]:
            methodology -= 6
        if s["has_limitations"]:
            methodology -= 2
        if not s["has_parameter_details"]:
            methodology += 4

        data_availability = 45
        if s["has_availability_section"]:
            data_availability -= 5
        if s["has_public_data"]:
            data_availability -= 5
        if s["has_live_runtime_data"]:
            data_availability += 3
        if s["has_public_code"]:
            data_availability -= 4
        if s["table_count"] >= 3:
            data_availability -= 2
        if not s["has_public_data"]:
            data_availability += 4
        if not s["has_public_code"]:
            data_availability += 3

        statistical_rigor = 45
        if s["has_metrics"]:
            statistical_rigor -= 5
        if s["has_baselines"]:
            statistical_rigor -= 4
        if s["has_ablation"]:
            statistical_rigor -= 3
        if s["has_cv"]:
            statistical_rigor -= 5
        if s["has_nested_cv"]:
            statistical_rigor -= 3
        if s["has_external_validation"]:
            statistical_rigor -= 2
        if s["has_stat_tests"]:
            statistical_rigor -= 3
        if s["table_count"] >= 3:
            statistical_rigor -= 2
        if not s["has_validation_design"]:
            statistical_rigor += 6
        if not s["has_metrics"]:
            statistical_rigor += 6

        code_availability = 50
        if s["has_public_code"]:
            code_availability -= 10
        if s["has_artifact_package"]:
            code_availability -= 6
        if s["has_execution_instructions"]:
            code_availability -= 6
        if s["has_seed_mentions"]:
            code_availability -= 3
        if s["has_env_details"] or s["has_version_details"]:
            code_availability -= 3
        if not s["has_public_code"]:
            code_availability += 6
        if not s["has_artifact_package"] and not s["has_execution_instructions"]:
            code_availability += 5

    def clamp_section(v: int) -> int:
        return max(10, min(95, v))

    return [
        {
            "name": "Methodology",
            "score": clamp_section(int(round(methodology))),
            "detail": "Lower is better. This score reflects implementation specificity and methodological transparency.",
        },
        {
            "name": "Data Availability",
            "score": clamp_section(int(round(data_availability))),
            "detail": "Lower is better. This score reflects data-source transparency and artifact discoverability.",
        },
        {
            "name": "Statistical Rigor",
            "score": clamp_section(int(round(statistical_rigor))),
            "detail": "Lower is better. This score reflects metrics, validation design, comparisons, and evaluation depth.",
        },
        {
            "name": "Code Availability",
            "score": clamp_section(int(round(code_availability))),
            "detail": "Lower is better. This score reflects whether code, packages, instructions, and execution details are directly available.",
        },
    ]


def build_explanation(title: str, abstract: str, cleaned_text: str, prediction: dict) -> dict:
    title = sanitize_text_for_db(title, collapse_whitespace=True)
    abstract = sanitize_text_for_db(abstract, collapse_whitespace=True)
    cleaned_text = sanitize_text_for_db(cleaned_text, collapse_whitespace=True)

    calibration = _calibrate_score(title, abstract, cleaned_text, prediction)
    keywords = [word for word, _ in extract_keywords(cleaned_text)]

    score = int(round(calibration["calibrated_score"]))
    top_factors = calibration["negatives"] + calibration["positives"]
    if not top_factors:
        top_factors = ["The paper contains a balanced mix of reproducibility indicators."]

    model_pred = str(prediction.get("prediction", "")).strip().upper()
    if model_pred == "YES":
        pred_phrase = "more reproducible"
    elif model_pred == "NO":
        pred_phrase = "not clearly reproducible"
    else:
        pred_phrase = model_pred.lower() if model_pred else "uncertain"

    if calibration["signals"]["is_theory_heavy"]:
        summary = (
            f"The active model predicts the paper is {pred_phrase}. "
            f"That prediction is then converted into a reproducibility risk score of {score}/100. "
            f"For theory-heavy papers, the final score reflects proof structure, mathematical completeness, "
            f"appendix detail, and artifact availability only when relevant."
        )
    elif calibration["signals"]["is_conceptual"]:
        summary = (
            f"The active model predicts the paper is {pred_phrase}. "
            f"That prediction is then converted into a reproducibility risk score of {score}/100. "
            f"For conceptual or model-driven papers, the final score reflects model clarity, mathematical detail, "
            f"scope transparency, and artifact availability when relevant."
        )
    else:
        summary = (
            f"The active model predicts the paper is {pred_phrase}. "
            f"That prediction is then converted into a reproducibility risk score of {score}/100. "
            f"The final score reflects artifact/data availability, method completeness, execution detail, "
            f"and evaluation rigor."
        )

    return sanitize_json_for_db({
        "summary": summary,
        "topFactors": top_factors[:8],
        "sections": _build_section_scores(calibration),
        "keywords": keywords,
        "model": prediction.get("model", {}),
        "rawPrediction": prediction,
        "calibration": {
            "rawBaseScore": calibration["raw_base_score"],
            "temperedBaseScore": calibration["tempered_base_score"],
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

        explanation = build_explanation(title, abstract, cleaned_text, prediction)
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