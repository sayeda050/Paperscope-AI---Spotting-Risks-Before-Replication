from __future__ import annotations

import json
import math
import re
from pathlib import Path
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd


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
        or _extract_metric(train_report, ["validation", "accuracy"])
        or _extract_metric(train_report, ["validation_selected_model", "accuracy"])
    )

    test_f1 = (
        _extract_metric(train_report, ["test", "macro_f1"])
        or _extract_metric(train_report, ["test_final_model", "macro_f1"])
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
    active_model_path = ""
    if active_id:
        active_model_path = str(MODELS_DIR / active_id)

    payload = {
        # backward-compatible simple keys
        "active_model": active_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "available_models": [m["id"] for m in models],
        "model_path": active_model_path,
        # richer keys for admin model UI/service
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
    }

    if pipeline_type == "text_input_v1":
        bundle["vectorizer"] = joblib.load(model_dir / "vectorizer.joblib")
    else:
        feature_columns = safe_read_json(model_dir / "feature_columns.json", [])
        if not feature_columns and pipeline_type == "feature_base_v1":
            feature_columns = BASE_FEATURE_COLUMNS
        bundle["feature_columns"] = feature_columns

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


def predict_with_active_model(payload):
    model_spec = get_active_model()
    if not model_spec:
        raise RuntimeError("No active model is configured.")

    bundle = _load_model_bundle(model_spec)
    classifier = bundle["classifier"]
    label_encoder = bundle["label_encoder"]

    if bundle["pipelineType"] == "text_input_v1":
        text_input = build_text_input(payload, bundle["metadata"])
        X = bundle["vectorizer"].transform([text_input])

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