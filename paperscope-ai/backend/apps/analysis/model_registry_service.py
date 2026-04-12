from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp


BACKEND_DIR = Path(__file__).resolve().parents[2]
ML_ASSETS_DIR = BACKEND_DIR / "ml_assets"
MODELS_DIR = ML_ASSETS_DIR / "models"
REGISTRY_PATH = ML_ASSETS_DIR / "registry.json"

_MODEL_CACHE = {}


BASE_FEATURE_COLUMNS = [
    "has_code_link",
    "has_data_link",
    "has_hyperparams",
    "has_seed",
    "has_env_details",
    "has_metrics",
    "has_baselines",
    "has_ablation",
    "has_limitations",
    "has_statistical_tests",
    "review_missing_details",
    "review_repro_concern",
    "review_code_missing",
    "review_dataset_unclear",
    "review_hyperparams_unclear",
    "review_missing_ablation",
    "review_weak_baselines",
    "review_insufficient_experiments",
]

POSITIVE_FEATURES = BASE_FEATURE_COLUMNS[:10]
NEGATIVE_FEATURES = BASE_FEATURE_COLUMNS[10:]


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

# Must match the corrected train_tfidf_logreg.py keyword flags exactly.
TEXT_KEYWORD_FLAG_PATTERNS = {
    "kw_code_link": re.compile(
        r"github\.com/|gitlab\.com/|code\s+available|we\s+release\s+(?:the\s+)?code|open[- ]?source",
        re.I,
    ),
    "kw_data_link": re.compile(
        r"dataset\s+available|we\s+release\s+(?:the\s+)?data|huggingface\.co/|zenodo\.org/",
        re.I,
    ),
    "kw_hyperparams": re.compile(
        r"learning\s+rate|batch\s+size|epochs?|weight\s+decay|dropout|hyperparameter",
        re.I,
    ),
    "kw_seed": re.compile(
        r"random\s+seed|seed\s*=\s*\d+|seeded",
        re.I,
    ),
    "kw_uncertainty": re.compile(
        r"standard\s+deviation|confidence\s+interval|error\s+bar|±|\u00b1|p[- ]value",
        re.I,
    ),
    "kw_compute": re.compile(
        r"\bgpu\b|v100|a100|cuda|training\s+time|compute\s+(?:budget|hours?)",
        re.I,
    ),
    "kw_ablation": re.compile(
        r"ablation\s+stud(?:y|ies)|we\s+ablate",
        re.I,
    ),
    "kw_baselines": re.compile(
        r"baseline|compared\s+(?:with|to|against)|state[- ]of[- ]the[- ]art|sota",
        re.I,
    ),
    "kw_limitations": re.compile(
        r"limitations?|threats\s+to\s+validity|future\s+work|bias",
        re.I,
    ),
    "kw_stat_tests": re.compile(
        r"wilcoxon|t-test|anova|bootstrap|significance|confidence\s+interval",
        re.I,
    ),
}

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
LIVE_DATA_RE = re.compile(
    r"\b(live market data|fetched at the time of execution|obtained .* at the time of execution|live data)\b",
    re.I,
)
THEOREM_RE = re.compile(r"\b(theorem|lemma|corollary|proposition|claim|proof)\b", re.I)
ALGORITHM_RE = re.compile(r"\balgorithm\s+\d+\b", re.I)
TABLE_RE = re.compile(r"\btable\s+[ivxlcdm0-9]+\b", re.I)
EQUATION_ID_RE = re.compile(r"\(\d+\)")
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

DEFAULT_SCORE_FEATURE_COLUMNS = [
    "prob_yes",
    "prob_no",
    "top_class_probability",
    "prediction_is_yes",
    "prediction_is_no",
    "has_code_link",
    "has_data_link",
    "has_hyperparams",
    "has_seed",
    "has_env_details",
    "has_metrics",
    "has_baselines",
    "has_ablation",
    "has_limitations",
    "has_statistical_tests",
    "title_len",
    "abstract_len",
    "model_text_len",
    "model_text_len_k",
    "num_positive_indicators",
    "positive_per_1000_model_chars",
    "has_code_and_data",
    "has_hyperparams_and_seed",
    "baselines_and_ablation",
    "metrics_and_stats",
    "has_availability_section",
    "has_public_data",
    "has_artifact_package",
    "has_execution_instructions",
    "has_live_runtime_data",
    "equation_count",
    "algorithm_count",
    "table_count",
    "theorem_count",
    "is_ml",
    "is_llm",
    "is_hdl",
    "is_biomed",
    "is_finance",
]


def safe_read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_model_cache():
    _MODEL_CACHE.clear()


def clean_text(text):
    return " ".join(str(text or "").split()).strip()


def has_any_pattern(text: str, patterns):
    text = text or ""
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            return 1.0
    return 0.0


def build_default_model_text(payload):
    model_text = clean_text(payload.get("model_text", ""))
    if model_text:
        return model_text

    title = clean_text(payload.get("title", ""))
    abstract = clean_text(payload.get("abstract", ""))
    return clean_text(f"{title}. {abstract}")


def build_text_input(payload, metadata):
    base_text = build_default_model_text(payload)
    review_text = clean_text(payload.get("review_text", ""))
    decision_text = clean_text(payload.get("decision_text", ""))

    input_hint = str(metadata.get("input_text", "")).lower()
    if "review_text" in input_hint or "decision_text" in input_hint:
        return clean_text(f"{base_text} [REVIEW] {review_text} [DECISION] {decision_text}")

    return base_text


def _build_text_keyword_flags(texts: list[str]) -> np.ndarray:
    n = len(texts)
    k = len(TEXT_KEYWORD_FLAG_PATTERNS)
    X = np.zeros((n, k), dtype=np.float32)
    for j, pattern in enumerate(TEXT_KEYWORD_FLAG_PATTERNS.values()):
        for i, text in enumerate(texts):
            X[i, j] = 1.0 if pattern.search(text or "") else 0.0
    return X


def build_text_model_matrix(texts: list[str], vectorizer, metadata: dict):
    X_tfidf = vectorizer.transform(texts)

    feature_engineering = str(metadata.get("feature_engineering", "")).lower()
    keyword_names = metadata.get("keyword_flag_names") or metadata.get("keyword_flags") or []

    uses_keyword_flags = ("keyword" in feature_engineering) or bool(keyword_names)
    if not uses_keyword_flags:
        return X_tfidf

    X_kw = _build_text_keyword_flags(texts)
    return sp.hstack([X_tfidf, sp.csr_matrix(X_kw)], format="csr")


def compute_base_feature_flags(payload):
    model_text = build_default_model_text(payload)
    review_text = clean_text(payload.get("review_text", ""))
    decision_text = clean_text(payload.get("decision_text", ""))
    reviewer_signal_text = clean_text(f"{review_text} {decision_text}")

    feats = {}
    for key, patterns in POSITIVE_PATTERNS.items():
        feats[key] = has_any_pattern(model_text, patterns)
    for key, patterns in NEGATIVE_PATTERNS.items():
        feats[key] = has_any_pattern(reviewer_signal_text, patterns)
    return feats


def build_base_feature_frame(payload, feature_columns):
    row = compute_base_feature_flags(payload)
    df = pd.DataFrame([row])

    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0

    df = df[feature_columns].copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    return df


def safe_text_len(value):
    return float(len(str(value or "")))


def build_rich_feature_frame(payload, feature_columns):
    row = compute_base_feature_flags(payload)

    title = payload.get("title", "")
    abstract = payload.get("abstract", "")
    model_text = build_default_model_text(payload)
    review_text = payload.get("review_text", "")
    decision_text = payload.get("decision_text", "")
    venue = str(payload.get("venue", "") or "")
    year_raw = payload.get("year", 0)
    review_count_raw = payload.get("review_count", 0)

    try:
        year_num = float(year_raw)
    except Exception:
        year_num = 0.0

    try:
        review_count = float(review_count_raw)
    except Exception:
        review_count = 0.0

    row["title_len"] = safe_text_len(title)
    row["abstract_len"] = safe_text_len(abstract)
    row["model_text_len"] = safe_text_len(model_text)
    row["review_text_len"] = safe_text_len(review_text)
    row["decision_text_len"] = safe_text_len(decision_text)
    row["review_count"] = review_count

    row["num_positive_indicators"] = float(sum(row.get(k, 0.0) for k in POSITIVE_FEATURES))
    row["num_negative_indicators"] = float(sum(row.get(k, 0.0) for k in NEGATIVE_FEATURES))
    row["positive_minus_negative"] = row["num_positive_indicators"] - row["num_negative_indicators"]
    row["positive_plus_negative"] = row["num_positive_indicators"] + row["num_negative_indicators"]
    row["positive_to_total_ratio"] = (
        row["num_positive_indicators"] / row["positive_plus_negative"]
        if row["positive_plus_negative"] > 0 else 0.0
    )

    row["has_code_and_data"] = row.get("has_code_link", 0.0) * row.get("has_data_link", 0.0)
    row["has_hyperparams_and_seed"] = row.get("has_hyperparams", 0.0) * row.get("has_seed", 0.0)
    row["repro_concern_and_missing_details"] = (
        row.get("review_repro_concern", 0.0) * row.get("review_missing_details", 0.0)
    )
    row["baselines_and_ablation"] = row.get("has_baselines", 0.0) * row.get("has_ablation", 0.0)
    row["metrics_and_stats"] = row.get("has_metrics", 0.0) * row.get("has_statistical_tests", 0.0)

    row["positive_per_1000_model_chars"] = (
        1000.0 * row["num_positive_indicators"] / row["model_text_len"]
        if row["model_text_len"] > 0 else 0.0
    )
    row["negative_per_1000_review_chars"] = (
        1000.0 * row["num_negative_indicators"] / row["review_text_len"]
        if row["review_text_len"] > 0 else 0.0
    )

    row["year_num"] = year_num
    row["venue_iclr_2025"] = 1.0 if venue == "ICLR.cc/2025/Conference" else 0.0
    row["venue_iclr_2024"] = 1.0 if venue == "ICLR.cc/2024/Conference" else 0.0
    row["venue_neurips_2024"] = 1.0 if venue == "NeurIPS.cc/2024/Conference" else 0.0

    df = pd.DataFrame([row])

    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0

    df = df[feature_columns].copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    return df


def _count_pattern_matches(text: str, pattern) -> float:
    text = text or ""
    return float(len(pattern.findall(text)))


def _normalize_probabilities(probabilities: dict | None):
    probabilities = probabilities or {}
    upper_probs = {str(k).upper(): float(v) for k, v in probabilities.items()}

    yes = upper_probs.get("YES")
    no = upper_probs.get("NO")

    if yes is None and no is not None:
        yes = 1.0 - no
    if no is None and yes is not None:
        no = 1.0 - yes

    if yes is None:
        yes = 0.0
    if no is None:
        no = 0.0

    top_class_probability = max(upper_probs.values()) if upper_probs else 0.0
    return yes, no, float(top_class_probability)


def build_score_feature_row(payload, prediction):
    payload = payload or {}
    prediction = prediction or {}

    row = compute_base_feature_flags(payload)

    title = clean_text(payload.get("title", ""))
    abstract = clean_text(payload.get("abstract", ""))
    model_text = build_default_model_text(payload)
    combined = clean_text(f"{title} {abstract} {model_text}")

    prob_yes, prob_no, top_class_probability = _normalize_probabilities(prediction.get("probabilities"))
    pred_label = str(prediction.get("prediction", "")).strip().upper()

    row["prob_yes"] = float(prob_yes)
    row["prob_no"] = float(prob_no)
    row["top_class_probability"] = float(top_class_probability)
    row["prediction_is_yes"] = 1.0 if pred_label == "YES" else 0.0
    row["prediction_is_no"] = 1.0 if pred_label == "NO" else 0.0

    row["title_len"] = safe_text_len(title)
    row["abstract_len"] = safe_text_len(abstract)
    row["model_text_len"] = safe_text_len(model_text)
    row["model_text_len_k"] = row["model_text_len"] / 1000.0 if row["model_text_len"] > 0 else 0.0

    row["num_positive_indicators"] = float(sum(row.get(k, 0.0) for k in POSITIVE_FEATURES))
    row["positive_per_1000_model_chars"] = (
        1000.0 * row["num_positive_indicators"] / row["model_text_len"]
        if row["model_text_len"] > 0 else 0.0
    )

    row["has_code_and_data"] = row.get("has_code_link", 0.0) * row.get("has_data_link", 0.0)
    row["has_hyperparams_and_seed"] = row.get("has_hyperparams", 0.0) * row.get("has_seed", 0.0)
    row["baselines_and_ablation"] = row.get("has_baselines", 0.0) * row.get("has_ablation", 0.0)
    row["metrics_and_stats"] = row.get("has_metrics", 0.0) * row.get("has_statistical_tests", 0.0)

    row["has_availability_section"] = 1.0 if AVAILABILITY_SECTION_RE.search(combined) else 0.0
    row["has_public_data"] = 1.0 if PUBLIC_DATA_RE.search(combined) else 0.0
    row["has_artifact_package"] = 1.0 if ARTIFACT_PACKAGE_RE.search(combined) else 0.0
    row["has_execution_instructions"] = 1.0 if EXECUTION_RE.search(combined) else 0.0
    row["has_live_runtime_data"] = 1.0 if LIVE_DATA_RE.search(combined) else 0.0

    row["equation_count"] = _count_pattern_matches(combined, EQUATION_ID_RE)
    row["algorithm_count"] = _count_pattern_matches(combined, ALGORITHM_RE)
    row["table_count"] = _count_pattern_matches(combined, TABLE_RE)
    row["theorem_count"] = _count_pattern_matches(combined, THEOREM_RE)

    row["is_ml"] = 1.0 if ML_RE.search(combined) else 0.0
    row["is_llm"] = 1.0 if LLM_RE.search(combined) else 0.0
    row["is_hdl"] = 1.0 if HDL_RE.search(combined) else 0.0
    row["is_biomed"] = 1.0 if BIOMED_RE.search(combined) else 0.0
    row["is_finance"] = 1.0 if FINANCE_RE.search(combined) else 0.0

    return row


def build_score_feature_frame(payload, prediction, feature_columns=None):
    if not feature_columns:
        feature_columns = DEFAULT_SCORE_FEATURE_COLUMNS

    row = build_score_feature_row(payload, prediction)
    df = pd.DataFrame([row])

    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0

    df = df[list(feature_columns)].copy()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    return df


def _patch_classifier_for_runtime_compatibility(classifier):
    class_name = classifier.__class__.__name__

    if class_name == "LogisticRegression":
        if not hasattr(classifier, "multi_class"):
            classifier.multi_class = "auto"
        if not hasattr(classifier, "n_jobs"):
            classifier.n_jobs = None
        if not hasattr(classifier, "l1_ratio"):
            classifier.l1_ratio = None

    elif class_name in {"LinearSVC", "SVC"}:
        if not hasattr(classifier, "break_ties"):
            classifier.break_ties = False

    return classifier


def _guess_pipeline_type(model_dir: Path, metadata: dict) -> str:
    if (model_dir / "vectorizer.joblib").exists():
        return "text_input_v1"

    input_type = str(metadata.get("input_type", "")).lower()
    if "rich" in input_type:
        return "feature_rich_v1"

    return "feature_base_v1"


def _extract_metric(train_report: dict, key_path):
    cur = train_report
    for key in key_path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    try:
        return float(cur)
    except Exception:
        return None


def _extract_metrics(model_dir: Path):
    train_report = safe_read_json(model_dir / "train_report.json", {})

    test_acc = (
        _extract_metric(train_report, ["test", "accuracy"])
        or _extract_metric(train_report, ["test_final_model", "accuracy"])
        or _extract_metric(train_report, ["best_validation_selection", "val_accuracy"])
        or _extract_metric(train_report, ["validation", "accuracy"])
        or _extract_metric(train_report, ["validation_selected_model", "accuracy"])
    )

    test_f1 = (
        _extract_metric(train_report, ["test", "macro_f1"])
        or _extract_metric(train_report, ["test_final_model", "macro_f1"])
        or _extract_metric(train_report, ["best_validation_selection", "val_macro_f1"])
        or _extract_metric(train_report, ["validation", "macro_f1"])
        or _extract_metric(train_report, ["validation_selected_model", "macro_f1"])
    )

    return {
        "testAccuracy": test_acc,
        "macroF1": test_f1,
    }


def _format_created_at(model_dir: Path, metadata: dict):
    value = metadata.get("created_at")
    if value:
        return str(value)

    try:
        ts = model_dir.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _discover_models_from_disk():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    models = []
    for child in MODELS_DIR.iterdir():
        if not child.is_dir():
            continue

        metadata = safe_read_json(child / "metadata.json", {})
        pipeline_type = _guess_pipeline_type(child, metadata)

        model_name = metadata.get("model_name") or child.name
        classifier_type = metadata.get("classifier_type", "")
        vectorizer_type = metadata.get("vectorizer_type", "")
        model_type = " + ".join([x for x in [vectorizer_type, classifier_type] if x]) or child.name

        status = "ready"
        if not (child / "classifier.joblib").exists() or not (child / "label_encoder.joblib").exists():
            status = "missing_artifacts"

        if pipeline_type == "text_input_v1" and not (child / "vectorizer.joblib").exists():
            status = "missing_artifacts"

        models.append(
            {
                "id": child.name,
                "name": model_name,
                "artifactSubdir": child.name,
                "modelType": model_type,
                "pipelineType": pipeline_type,
                "createdAt": _format_created_at(child, metadata),
                "metrics": _extract_metrics(child),
                "status": status,
                "active": False,
            }
        )

    models.sort(key=lambda x: x["name"].lower())
    return models


def load_registry():
    registry = safe_read_json(REGISTRY_PATH, {})
    active_id = registry.get("activeModelId") or registry.get("active_model")
    return {
        "activeModelId": active_id,
        "raw": registry,
    }


def save_registry(active_id: str, models: list[dict]):
    active_model_path = str(MODELS_DIR / active_id) if active_id else ""

    payload = {
        "active_model": active_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "available_models": [m["id"] for m in models],
        "model_path": active_model_path,
        "activeModelId": active_id,
        "models": models,
    }
    write_json(REGISTRY_PATH, payload)


def list_models():
    registry = load_registry()
    active_id = registry["activeModelId"]

    models = _discover_models_from_disk()
    for model in models:
        model["active"] = model["id"] == active_id

    if not active_id and models:
        models[0]["active"] = True
        active_id = models[0]["id"]
        save_registry(active_id, models)

    models.sort(key=lambda x: (not x.get("active", False), x.get("name", "").lower()))
    return models


def refresh_registry_from_disk():
    clear_model_cache()
    models = list_models()
    active = next((m["id"] for m in models if m.get("active")), None)
    save_registry(active, models)
    return models


def get_model_by_id(model_id):
    for model in list_models():
        if model.get("id") == model_id:
            return model
    return None


def get_active_model():
    models = list_models()
    for model in models:
        if model.get("active"):
            return model
    return None


def set_active_model(model_id: str):
    models = list_models()
    found = False

    for model in models:
        is_active = model["id"] == model_id
        model["active"] = is_active
        if is_active:
            found = True
            model_dir = MODELS_DIR / model["artifactSubdir"]
            if not model_dir.exists():
                raise FileNotFoundError(f"Artifact folder missing for model: {model_id}")
            if model.get("status") != "ready":
                raise FileNotFoundError(f"Artifacts are incomplete for model: {model_id}")

    if not found:
        raise ValueError(f"Model id not found: {model_id}")

    save_registry(model_id, models)
    clear_model_cache()


def _load_model_bundle(model_spec):
    model_id = model_spec["id"]
    if model_id in _MODEL_CACHE:
        return _MODEL_CACHE[model_id]

    model_dir = MODELS_DIR / model_spec["artifactSubdir"]
    if not model_dir.exists():
        raise FileNotFoundError(f"Model artifact directory not found: {model_dir}")

    metadata = safe_read_json(model_dir / "metadata.json", {})
    pipeline_type = model_spec["pipelineType"]

    classifier = joblib.load(model_dir / "classifier.joblib")
    classifier = _patch_classifier_for_runtime_compatibility(classifier)

    bundle = {
        "pipelineType": pipeline_type,
        "classifier": classifier,
        "label_encoder": joblib.load(model_dir / "label_encoder.joblib"),
        "metadata": metadata,
        "score_calibrator": None,
        "score_feature_columns": DEFAULT_SCORE_FEATURE_COLUMNS,
    }

    if pipeline_type == "text_input_v1":
        bundle["vectorizer"] = joblib.load(model_dir / "vectorizer.joblib")
    else:
        feature_columns = safe_read_json(model_dir / "feature_columns.json", [])
        if not feature_columns and pipeline_type == "feature_base_v1":
            feature_columns = BASE_FEATURE_COLUMNS
        bundle["feature_columns"] = feature_columns

    score_calibrator_path = model_dir / "score_calibrator.joblib"
    if score_calibrator_path.exists():
        bundle["score_calibrator"] = joblib.load(score_calibrator_path)
        feature_columns = safe_read_json(model_dir / "score_feature_columns.json", [])
        if feature_columns:
            bundle["score_feature_columns"] = feature_columns

    _MODEL_CACHE[model_id] = bundle
    return bundle


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _softmax(arr):
    arr = np.asarray(arr, dtype=float)
    arr = arr - np.max(arr)
    exp = np.exp(arr)
    denom = np.sum(exp)
    if denom == 0:
        return np.ones_like(arr) / len(arr)
    return exp / denom


def _safe_predict_proba(classifier, X, label_encoder):
    try:
        if hasattr(classifier, "predict_proba"):
            proba = classifier.predict_proba(X)[0]
            class_names = label_encoder.classes_.tolist()
            return {class_names[i]: float(proba[i]) for i in range(len(class_names))}
    except Exception:
        pass

    try:
        if hasattr(classifier, "decision_function"):
            scores = classifier.decision_function(X)
            class_names = label_encoder.classes_.tolist()

            if np.ndim(scores) == 1:
                pos = float(_sigmoid(scores[0]))
                neg = 1.0 - pos
                if len(class_names) == 2:
                    return {
                        class_names[0]: neg,
                        class_names[1]: pos,
                    }

            scores = np.asarray(scores[0], dtype=float)
            probs = _softmax(scores)
            return {class_names[i]: float(probs[i]) for i in range(len(class_names))}
    except Exception:
        pass

    return {}


def _predict_score_from_bundle(bundle, payload, prediction):
    calibrator = bundle.get("score_calibrator")
    if calibrator is None:
        return {
            "used_trained_calibrator": False,
            "score": None,
            "label": None,
        }

    feature_columns = bundle.get("score_feature_columns") or DEFAULT_SCORE_FEATURE_COLUMNS
    X_score = build_score_feature_frame(payload, prediction, feature_columns)

    raw_score = calibrator.predict(X_score)[0]
    score = float(np.clip(raw_score, 0.0, 100.0))

    if score < 35.0:
        label = "Low"
    elif score < 65.0:
        label = "Med"
    else:
        label = "High"

    return {
        "used_trained_calibrator": True,
        "score": round(score, 2),
        "label": label,
    }


def predict_score_with_active_model(payload, prediction=None):
    model_spec = get_active_model()
    if not model_spec:
        raise RuntimeError("No active model is configured.")

    bundle = _load_model_bundle(model_spec)

    if prediction is None:
        prediction = predict_with_active_model(payload)

    score_result = _predict_score_from_bundle(bundle, payload, prediction)
    score_result["model"] = {
        "id": model_spec["id"],
        "name": model_spec["name"],
        "modelType": model_spec["modelType"],
        "pipelineType": model_spec["pipelineType"],
        "active": True,
    }
    return score_result


def predict_with_active_model(payload):
    model_spec = get_active_model()
    if not model_spec:
        raise RuntimeError("No active model is configured.")

    bundle = _load_model_bundle(model_spec)
    classifier = bundle["classifier"]
    label_encoder = bundle["label_encoder"]

    if bundle["pipelineType"] == "text_input_v1":
        text_input = build_text_input(payload, bundle["metadata"])
        X = build_text_model_matrix([text_input], bundle["vectorizer"], bundle["metadata"])
    elif bundle["pipelineType"] == "feature_base_v1":
        X = build_base_feature_frame(payload, bundle["feature_columns"])
    elif bundle["pipelineType"] == "feature_rich_v1":
        X = build_rich_feature_frame(payload, bundle["feature_columns"])
    else:
        raise ValueError(f"Unsupported pipelineType: {bundle['pipelineType']}")

    try:
        pred_numeric = classifier.predict(X)[0]
    except AttributeError as exc:
        raise RuntimeError(
            f"Active model '{model_spec['name']}' could not run prediction because its "
            f"saved sklearn artifact is incompatible with the current runtime: {exc}"
        ) from exc

    pred_label = label_encoder.inverse_transform([pred_numeric])[0]
    probabilities = _safe_predict_proba(classifier, X, label_encoder)

    return {
        "model": {
            "id": model_spec["id"],
            "name": model_spec["name"],
            "modelType": model_spec["modelType"],
            "pipelineType": model_spec["pipelineType"],
            "active": True,
        },
        "prediction": pred_label,
        "probabilities": probabilities,
    }