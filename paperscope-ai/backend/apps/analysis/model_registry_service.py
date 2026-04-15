"""
model_registry_service.py — ML model registry and prediction service.

Fully backward-compatible with both:
  - Old models (tfidf_logreg_auto_v2): 18 BASE_FEATURE_COLUMNS, 5-domain one-hot
  - New models (tfidf_logreg_*_YYYYMMDD): 13 ATTRIBUTE_ORDER features, 7-domain one-hot,
    CalibratedClassifierCV (isotonic), versioned latest.json routing

The explicit feature columns and domain one-hot columns are read from each
model's metadata.json at runtime, so the same code works for any model version.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR   = Path(__file__).resolve().parents[2]
ML_ASSETS_DIR = BACKEND_DIR / "ml_assets"
MODELS_DIR    = ML_ASSETS_DIR / "models"
REGISTRY_PATH = ML_ASSETS_DIR / "registry.json"

_MODEL_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Feature column definitions
# ---------------------------------------------------------------------------

# Legacy 18 features (used by old models like tfidf_logreg_auto_v2).
# Kept here so backward-compatible discovery still works.
_LEGACY_BASE_FEATURE_COLUMNS: list[str] = [
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

# New 13 attributes — match ATTRIBUTE_ORDER in domain_config.py / train_tfidf_logreg.py
NEW_ATTRIBUTE_ORDER: list[str] = [
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

# The 7 supported domains in the new pipeline (used for sorted one-hot columns)
_NEW_SUPPORTED_DOMAINS: list[str] = [
    "ml", "physics", "biomed", "nlp", "finance", "hardware", "math",
]
_NEW_DOMAIN_ONEHOT_COLS: list[str] = sorted(
    f"dom_{d}" for d in _NEW_SUPPORTED_DOMAINS
)
# = ["dom_biomed", "dom_finance", "dom_hardware", "dom_math", "dom_ml", "dom_nlp", "dom_physics"]

# Legacy 5-domain one-hot (sorted) — for old models
_LEGACY_DOMAIN_ONEHOT_COLS: list[str] = sorted(
    f"dom_{d}" for d in ["biomed", "econ", "finance", "math", "ml"]
)

LABEL_MAP = {
    "NO":     "HIGH",
    "YES":    "LOW",
    "HIGH":   "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW":    "LOW",
}
LABEL_ORDER = ["LOW", "MEDIUM", "HIGH"]


# ---------------------------------------------------------------------------
# Regex patterns — kept identical to original for all services.py usage
# ---------------------------------------------------------------------------
POSITIVE_PATTERNS: dict[str, list[str]] = {
    "has_code_link": [
        r"github\.com", r"gitlab\.com", r"bitbucket\.org",
        r"\bsource code\b", r"\bcode available\b", r"\bimplementation is available\b",
    ],
    "has_data_link": [
        r"\bdataset available\b", r"\bdata available\b", r"\bwe release the dataset\b",
        r"\bkaggle\b", r"\bzenodo\b", r"\bhuggingface\b", r"\bdatasets can be found\b",
    ],
    "has_hyperparams": [
        r"\blearning rate\b", r"\bbatch size\b", r"\bepochs?\b",
        r"\bdropout\b", r"\boptimizer\b", r"\bweight decay\b", r"\bhidden size\b",
    ],
    "has_seed": [
        r"\brandom seed\b", r"\bseed\s*=\s*\d+\b", r"\bwe use seed\b",
    ],
    "has_env_details": [
        r"\bgpu\b", r"\bcuda\b", r"\bpytorch\b", r"\btensorflow\b",
        r"\bubuntu\b", r"\bhardware\b", r"\bv100\b", r"\ba100\b",
    ],
    "has_metrics": [
        r"\baccuracy\b", r"\bf1\b", r"\bprecision\b", r"\brecall\b",
        r"\bauc\b", r"\bbleu\b", r"\brouge\b", r"\bmse\b", r"\bmae\b", r"\bperplexity\b",
    ],
    "has_baselines": [
        r"\bbaseline\b", r"\bcompared with\b", r"\bcompare against\b",
        r"\bstate[- ]of[- ]the[- ]art\b", r"\bsota\b",
    ],
    "has_ablation": [
        r"\bablation\b", r"\bablative\b", r"\bremove each component\b",
    ],
    "has_limitations": [
        r"\blimitations?\b", r"\bthreats to validity\b", r"\bfuture work\b",
    ],
    "has_statistical_tests": [
        r"\bp[- ]value\b", r"\bconfidence interval\b", r"\bstandard deviation\b",
        r"\bstd\.\b", r"\bstatistical significance\b",
    ],
}

NEGATIVE_PATTERNS: dict[str, list[str]] = {
    "review_missing_details":            [r"\bdetails are missing\b", r"\black of detail\b", r"\bnot enough detail\b"],
    "review_repro_concern":              [r"\breproducibility\b", r"\bdifficult to reproduce\b", r"\bnot reproducible\b"],
    "review_code_missing":               [r"\bcode is not available\b", r"\bno code\b", r"\bmissing implementation\b"],
    "review_dataset_unclear":            [r"\bdataset is unclear\b", r"\bdata source is unclear\b", r"\bunclear dataset\b"],
    "review_hyperparams_unclear":        [r"\bhyperparameters are unclear\b", r"\bmissing hyperparameters\b", r"\btraining details are unclear\b"],
    "review_missing_ablation":           [r"\bno ablation\b", r"\bmissing ablation\b"],
    "review_weak_baselines":             [r"\bweak baselines\b", r"\binsufficient baselines\b"],
    "review_insufficient_experiments":   [r"\binsufficient experiments\b", r"\bmore experiments are needed\b"],
}

# Extra patterns for new attribute features
_EXECUTION_RE = re.compile(
    r"\bpip install\b|\bconda install\b|\brequirements\.txt\b|"
    r"\bDockerfile\b|\bdocker\b|\bhow to run\b|\bto reproduce\b|"
    r"\breproduc.*package\b|\bREADME\b|\binstall.*instructions\b|"
    r"\bSnakefile\b|\bNextflow\b|\bSnakemake\b|"
    r"\brun\.sh\b|\btrain\.sh\b|\bscript.*available\b",
    re.I,
)
_SOFTWARE_VERSIONS_RE = re.compile(
    r"\bPython\s+\d+\.\d+\b|\bPyTorch\s+\d+\.\d+\b|\bTensorFlow\s+\d+\.\d+\b|"
    r"\bscikit[- ]learn\s+\d+\.\d+\b|\bCUDA\s+\d+\.\d+\b|"
    r"\bR\s+version\s+\d+\.\d+\b|\bMatlab\s+R?\d{4}\b|"
    r"\bGeant4\b|\bROOT\s+\d+\b|\bPythia\s+\d+\b|"
    r"\brequirements\.txt\b|\bDockerfile\b",
    re.I,
)
_AVAILABILITY_CONFIRMED_RE = re.compile(
    r"github\.com/|gitlab\.com/|zenodo\.org/|figshare\.com/|"
    r"huggingface\.co/|osf\.io/|codeocean\.com/|"
    r"\bcode (?:is|has been|was)\s*(?:available|released|shared|provided)\b|"
    r"\bdata (?:is|are|has been|was)\s*(?:available|released|shared|provided)\b|"
    r"\bartifact(?:s)? (?:are|is)\s*(?:available|released|shared|provided)\b|"
    r"\bGEO accession\b|\bSRA accession\b|\bPDB ID\b|\bhepdata\.net\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_text(value) -> str:
    return str(value or "").strip()


def _normalize_label(value: str) -> str:
    text = _coerce_text(value).upper()
    return LABEL_MAP.get(text, text or "MEDIUM")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _clip_score(value) -> float:
    return float(max(0.0, min(100.0, _safe_float(value, 50.0))))


def label_from_score(score: float) -> str:
    score = _clip_score(score)
    if score >= 70:
        return "LOW"
    if score >= 40:
        return "MEDIUM"
    return "HIGH"


def _extract_probability_map(model, matrix, class_labels: list[str]) -> dict[str, float]:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(matrix)[0]
        return {
            str(class_labels[i]): float(probs[i])
            for i in range(min(len(class_labels), len(probs)))
        }
    predicted      = model.predict(matrix)[0]
    predicted_label = _normalize_label(predicted)
    return {label: (1.0 if label == predicted_label else 0.0) for label in class_labels}


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    _ensure_directory(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Registry I/O — handles both old (dict) and new (list) models formats
# ---------------------------------------------------------------------------
def _registry_template() -> dict:
    return {
        "active_model":       None,
        "models":             {},
        "last_refreshed_at":  None,
    }


def _read_registry() -> dict:
    """
    Read registry.json and normalize to internal format:
      {"active_model": str, "models": {model_key: entry_dict}, ...}

    New pipeline writes models as a list; old pipeline wrote a dict.
    Both are handled transparently.
    """
    payload = _read_json(REGISTRY_PATH, _registry_template())
    if not isinstance(payload, dict):
        payload = _registry_template()

    # Normalize active_model key (new format uses "activeModelId" as alias)
    if not payload.get("active_model"):
        payload["active_model"] = (
            payload.get("activeModelId")
            or payload.get("active_model")
        )

    # Normalize models: new format is a list, old is a dict
    raw_models = payload.get("models", {})
    if isinstance(raw_models, list):
        models_dict: dict = {}
        for m in raw_models:
            if isinstance(m, dict) and m.get("id"):
                models_dict[m["id"]] = m
        payload["models"] = models_dict

    payload.setdefault("active_model",      None)
    payload.setdefault("models",            {})
    payload.setdefault("last_refreshed_at", None)
    return payload


def _write_registry(payload: dict) -> dict:
    payload["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(REGISTRY_PATH, payload)
    return payload


# ---------------------------------------------------------------------------
# Model discovery — works for both versioned and non-versioned dirs
# ---------------------------------------------------------------------------
def _discover_model_entry(model_dir: Path) -> dict | None:
    """
    Discover a model from a directory. Returns None if the directory is not
    a valid model (e.g., domain sub-folder like ml/ or all/).
    """
    if not model_dir.is_dir():
        return None

    # New versioned structure: outputs/models/{domain}/{run_id}/
    # The ML pipeline exports flat into ml_assets/models/{model_id}/
    # So we only need to check direct children of MODELS_DIR.

    metadata_path              = model_dir / "metadata.json"
    vectorizer_path            = model_dir / "vectorizer.joblib"
    classifier_path            = model_dir / "classifier.joblib"
    label_encoder_path         = model_dir / "label_encoder.joblib"
    score_calibrator_path      = model_dir / "score_calibrator.joblib"
    score_feature_columns_path = model_dir / "score_feature_columns.json"

    if not vectorizer_path.exists() or not classifier_path.exists():
        return None

    metadata     = _read_json(metadata_path, {})
    model_key    = model_dir.name
    display_name = metadata.get("display_name") or model_key
    created_at   = metadata.get("created_at") or metadata.get("run_id")

    return {
        "model_key":                  model_key,
        "display_name":               display_name,
        "domain":                     metadata.get("domain", "ml"),
        "run_id":                     metadata.get("run_id", ""),
        "model_dir":                  str(model_dir),
        "vectorizer_path":            str(vectorizer_path),
        "classifier_path":            str(classifier_path),
        "label_encoder_path":         str(label_encoder_path) if label_encoder_path.exists() else None,
        "score_calibrator_path":      str(score_calibrator_path) if score_calibrator_path.exists() else None,
        "score_feature_columns_path": str(score_feature_columns_path) if score_feature_columns_path.exists() else None,
        "metadata_path":              str(metadata_path) if metadata_path.exists() else None,
        "created_at":                 created_at,
        "metadata":                   metadata,
    }


def refresh_registry_from_disk() -> dict:
    """Scan MODELS_DIR, discover valid models, update registry.json."""
    registry   = _read_registry()
    discovered: dict = {}

    _ensure_directory(MODELS_DIR)

    for child in sorted(MODELS_DIR.iterdir()):
        entry = _discover_model_entry(child)
        if entry is not None:
            discovered[entry["model_key"]] = entry

    registry["models"] = discovered

    active_key = registry.get("active_model")
    if active_key not in discovered:
        registry["active_model"] = next(iter(discovered.keys()), None)

    return _write_registry(registry)


def list_models() -> list[dict]:
    registry   = refresh_registry_from_disk()
    active_key = registry.get("active_model")
    models     = []
    for key, entry in registry.get("models", {}).items():
        item            = dict(entry)
        item["is_active"] = (key == active_key)
        models.append(item)
    return models


def get_active_model() -> dict | None:
    registry   = refresh_registry_from_disk()
    active_key = registry.get("active_model")
    if not active_key:
        return None
    return registry.get("models", {}).get(active_key)


def set_active_model(model_key: str) -> dict:
    model_key = _coerce_text(model_key)
    if not model_key:
        raise ValueError("model_key is required.")
    registry = refresh_registry_from_disk()
    if model_key not in registry.get("models", {}):
        raise ValueError(f"Model '{model_key}' was not found in backend/ml_assets/models.")
    registry["active_model"] = model_key
    return _write_registry(registry)


# ---------------------------------------------------------------------------
# Model / artifact caching
# ---------------------------------------------------------------------------
def _cache_key(model_key: str, suffix: str) -> str:
    return f"{model_key}::{suffix}"


def _load_joblib_cached(path: str | None, cache_key: str):
    if not path:
        return None
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    obj = joblib.load(path)
    _MODEL_CACHE[cache_key] = obj
    return obj


def _load_json_cached(path: str | None, cache_key: str, default):
    if not path:
        return default
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    payload = _read_json(Path(path), default)
    _MODEL_CACHE[cache_key] = payload
    return payload


# ---------------------------------------------------------------------------
# Per-model feature metadata helpers
# ---------------------------------------------------------------------------

def _get_classifier_n_features(active_model: dict) -> int | None:
    """
    Return the total number of input features the classifier expects.
    Works for both LogisticRegression and CalibratedClassifierCV wrappers.
    Returns None if the value cannot be determined.
    """
    model_key = active_model["model_key"]
    clf       = _load_joblib_cached(
        active_model.get("classifier_path"),
        _cache_key(model_key, "classifier"),
    )
    if clf is None:
        return None
    # Direct attribute (sklearn >= 1.0 sets this on every estimator)
    if hasattr(clf, "n_features_in_"):
        return int(clf.n_features_in_)
    # CalibratedClassifierCV wraps the base estimator
    if hasattr(clf, "estimator") and hasattr(clf.estimator, "n_features_in_"):
        return int(clf.estimator.n_features_in_)
    # calibrated_classifiers_ list (sklearn internal)
    calibrated = getattr(clf, "calibrated_classifiers_", None)
    if calibrated:
        base = getattr(calibrated[0], "base_estimator", None) or getattr(calibrated[0], "estimator", None)
        if base is not None and hasattr(base, "n_features_in_"):
            return int(base.n_features_in_)
    return None


def _get_vectorizer_vocab_size(active_model: dict) -> int:
    """Return the number of TF-IDF vocabulary features."""
    model_key  = active_model["model_key"]
    vectorizer = _load_joblib_cached(
        active_model.get("vectorizer_path"),
        _cache_key(model_key, "vectorizer"),
    )
    if vectorizer is None:
        return 100_000  # safe default
    vocab = getattr(vectorizer, "vocabulary_", {})
    return len(vocab) if vocab else 100_000


def _resolve_feature_layout(active_model: dict) -> tuple[list[str], list[str]]:
    """
    Determine (explicit_feature_cols, domain_onehot_cols) for this model.

    Priority:
    1. metadata.json keys  explicit_feature_names / domain_onehot_features
    2. Auto-detection from classifier.n_features_in_ - vectorizer vocab size
       — handles models whose metadata.json was written before these keys existed

    The auto-detection logic:
      extra = n_features_in - vocab_size
      We know the new pipeline always uses NEW_ATTRIBUTE_ORDER (13 items).
      If extra == 20  → 13 new attributes + 7 new domain one-hot
      If extra == 18  → 13 new attributes + 5 legacy domain one-hot
      If extra == 23  → 18 legacy attrs + 5 legacy domain  (old pipeline)
      Anything else   → best-effort guess
    """
    model_key = active_model["model_key"]
    metadata  = _load_json_cached(
        active_model.get("metadata_path"),
        _cache_key(model_key, "metadata"),
        {},
    )

    # ── Step 1: try metadata keys ─────────────────────────────────────────
    explicit_from_meta = (
        metadata.get("explicit_feature_names")
        or metadata.get("explicit_feature_columns")
    )
    domain_from_meta = metadata.get("domain_onehot_features")

    if (
        explicit_from_meta
        and isinstance(explicit_from_meta, list)
        and len(explicit_from_meta) > 0
        and domain_from_meta
        and isinstance(domain_from_meta, list)
        and len(domain_from_meta) > 0
    ):
        # Both keys present — trust metadata completely
        return list(explicit_from_meta), sorted(list(domain_from_meta))

    # ── Step 2: auto-detect from model artifacts ──────────────────────────
    n_total  = _get_classifier_n_features(active_model)
    n_vocab  = _get_vectorizer_vocab_size(active_model)

    if n_total is not None and n_vocab > 0:
        extra = n_total - n_vocab

        if extra == 20:
            # New pipeline: 13 ATTRIBUTE_ORDER + 7 new domain one-hot
            explicit_cols = list(NEW_ATTRIBUTE_ORDER)
            domain_cols   = list(_NEW_DOMAIN_ONEHOT_COLS)
        elif extra == 18:
            # New attributes + legacy 5-domain one-hot
            explicit_cols = list(NEW_ATTRIBUTE_ORDER)
            domain_cols   = list(_LEGACY_DOMAIN_ONEHOT_COLS)
        elif extra == 23:
            # Full legacy: 18 base features + 5 old domain one-hot
            explicit_cols = list(_LEGACY_BASE_FEATURE_COLUMNS)
            domain_cols   = list(_LEGACY_DOMAIN_ONEHOT_COLS)
        elif extra == 13:
            # New attributes only, no domain one-hot
            explicit_cols = list(NEW_ATTRIBUTE_ORDER)
            domain_cols   = []
        elif extra == 18 and explicit_from_meta:
            # metadata had explicit but not domain
            explicit_cols = list(explicit_from_meta)
            n_dom = extra - len(explicit_cols)
            domain_cols   = list(_NEW_DOMAIN_ONEHOT_COLS) if n_dom == 7 else list(_LEGACY_DOMAIN_ONEHOT_COLS)
        else:
            # Unknown layout — produce exactly the right total by adjusting domain
            # Use new attributes; pad/trim domain cols to match
            explicit_cols = list(NEW_ATTRIBUTE_ORDER)
            n_dom         = max(0, extra - len(explicit_cols))
            all_dom_cols  = list(_NEW_DOMAIN_ONEHOT_COLS)
            domain_cols   = all_dom_cols[:n_dom]

        return explicit_cols, domain_cols

    # ── Step 3: conservative fallback (metadata-only, best effort) ─────────
    explicit_cols = (
        list(explicit_from_meta)
        if explicit_from_meta and isinstance(explicit_from_meta, list)
        else list(NEW_ATTRIBUTE_ORDER)
    )
    domain_cols = (
        sorted(list(domain_from_meta))
        if domain_from_meta and isinstance(domain_from_meta, list)
        else list(_NEW_DOMAIN_ONEHOT_COLS)
    )
    return explicit_cols, domain_cols


def _get_explicit_feature_columns(active_model: dict) -> list[str]:
    explicit, _ = _resolve_feature_layout(active_model)
    return explicit


def _get_domain_onehot_cols(active_model: dict) -> list[str]:
    _, domain = _resolve_feature_layout(active_model)
    return domain


def _load_label_encoder_classes(active_model: dict) -> list[str]:
    """Load class labels and normalize to LABEL_MAP values."""
    model_key = active_model["model_key"]
    encoder   = _load_joblib_cached(
        active_model.get("label_encoder_path"),
        _cache_key(model_key, "label_encoder"),
    )
    if encoder is not None and hasattr(encoder, "classes_"):
        return [_normalize_label(label) for label in list(encoder.classes_)]

    metadata = _load_json_cached(
        active_model.get("metadata_path"),
        _cache_key(model_key, "metadata"),
        {},
    )
    raw_labels = (
        metadata.get("class_labels")
        or metadata.get("class_names")
        or metadata.get("labels")
        or LABEL_ORDER
    )
    labels  = [_normalize_label(label) for label in raw_labels]
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return deduped or LABEL_ORDER


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------
def _extract_domain(value) -> str:
    raw = _coerce_text(value).lower()
    # Map aliases to canonical names used in domain_config.SUPPORTED_DOMAINS
    _alias_map = {
        "machine learning":  "ml",
        "deep learning":     "ml",
        "artificial intelligence": "ml",
        "biomedical":        "biomed",
        "biology":           "biomed",
        "economics":         "finance",
        "econ":              "finance",
        "hardware":          "hardware",
        "computer architecture": "hardware",
        "natural language":  "nlp",
        "computational linguistics": "nlp",
        "mathematics":       "math",
    }
    return _alias_map.get(raw, raw) or "ml"


def _domain_onehot_matrix(domain: str, domain_cols: list[str]) -> sp.csr_matrix:
    """Build domain one-hot matrix matching the column list from model metadata."""
    canonical = _extract_domain(domain)
    target    = f"dom_{canonical}"
    vector    = [1.0 if col == target else 0.0 for col in domain_cols]
    return sp.csr_matrix(np.asarray([vector], dtype=float))


# ---------------------------------------------------------------------------
# Feature flag computation
# ---------------------------------------------------------------------------
def compute_base_feature_flags(payload: dict) -> dict[str, float]:
    """
    Compute all reproducibility feature flags from paper text.

    Returns a union of:
    - Legacy flags (has_code_link, has_data_link, ...) — for services.py signals
    - New 13 attribute flags (code_artifact, data_artifact, ...) — for new ML classifier
    """
    model_text    = _compose_model_text(payload).lower()
    review_text   = _coerce_text(payload.get("review_text")).lower()
    decision_text = _coerce_text(payload.get("decision_text")).lower()
    review_bundle = f"{review_text}\n{decision_text}".strip()

    flags: dict[str, float] = {}

    # ── Legacy positive flags (services.py uses these) ──────────────────────
    for feature_name, patterns in POSITIVE_PATTERNS.items():
        flags[feature_name] = (
            1.0 if any(re.search(p, model_text, re.I) for p in patterns) else 0.0
        )

    # ── Legacy negative flags (services.py uses these) ──────────────────────
    for feature_name, patterns in NEGATIVE_PATTERNS.items():
        flags[feature_name] = (
            1.0 if any(re.search(p, review_bundle, re.I) for p in patterns) else 0.0
        )

    # ── New 13 ATTRIBUTE_ORDER flags (new ML classifier uses these) ──────────
    # code_artifact: confirmed code URL or "code available" statement
    code_url_hit = bool(re.search(
        r"github\.com/|gitlab\.com/|bitbucket\.org/|"
        r"anonymous\.4open\.science|codeocean\.com/|"
        r"\bcode (?:is|was|has been)\s*(?:available|released|shared|provided)\b|"
        r"\bsource code (?:is|was|has been)\s*(?:available|released|shared|provided)\b|"
        r"\bwe release (?:the )?code\b|\bopen[- ]?source\b",
        model_text, re.I,
    ))
    code_future  = bool(re.search(
        r"\bcode will be available\b|\bcode will be released\b|"
        r"\bavailable upon acceptance\b",
        model_text, re.I,
    ))
    flags["code_artifact"] = (
        1.0 if code_url_hit
        else (0.5 if code_future else 0.0)
    )

    # data_artifact: confirmed dataset URL or accession number
    data_url_hit = bool(re.search(
        r"zenodo\.org/|figshare\.com/|osf\.io/|huggingface\.co/datasets/|"
        r"kaggle\.com/|dataverse\.|"
        r"\bGEO accession\b|\bSRA accession\b|\bdbGaP\b|\bPDB ID\b|"
        r"\bhepdata\.net\b|\bICPSR\b|\bWRDS\b|"
        r"\bwe release (?:the )?(?:dataset|data)\b|"
        r"\bdataset (?:is|was|has been)\s*(?:available|released|shared|provided)\b",
        model_text, re.I,
    ))
    data_public  = bool(flags.get("has_data_link", 0.0))
    data_future  = bool(re.search(
        r"\bdata will be available\b|\bdataset will be released\b",
        model_text, re.I,
    ))
    flags["data_artifact"] = (
        1.0 if data_url_hit
        else (0.5 if (data_public or data_future) else 0.0)
    )

    # availability_statement: any confirmed availability link/statement
    avail_confirmed = bool(_AVAILABILITY_CONFIRMED_RE.search(model_text))
    avail_partial   = bool(re.search(
        r"\bsupplementary material\b|\bartifact(?:s)? will be (?:available|released)\b",
        model_text, re.I,
    ))
    flags["availability_statement"] = (
        1.0 if avail_confirmed
        else (0.5 if avail_partial else 0.0)
    )

    # execution_instructions: pip/conda/docker/README/how-to-run
    exec_strong = bool(re.search(
        r"\bpip install\b|\bconda install\b|\brequirements\.txt\b|"
        r"\bDockerfile\b|\bStep[- ]by[- ]step\b|\bhow to run\b|"
        r"\bSnakemake\b|\bNextflow\b|\brun\.sh\b",
        model_text, re.I,
    ))
    exec_partial = bool(_EXECUTION_RE.search(model_text))
    flags["execution_instructions"] = (
        1.0 if exec_strong
        else (0.5 if exec_partial else 0.0)
    )

    # hyperparams_detail: learning rate, batch size, epochs, etc.
    hyper_hits = sum(
        1 for p in POSITIVE_PATTERNS["has_hyperparams"]
        if re.search(p, model_text, re.I)
    )
    extra_hyper = bool(re.search(
        r"\bsample size\b|\bconvergence criterion\b|\btime step\b|"
        r"\bhyperparameter\b|\bgrid search\b|\brandom search\b",
        model_text, re.I,
    ))
    if hyper_hits >= 3 or (hyper_hits >= 2 and extra_hyper):
        flags["hyperparams_detail"] = 1.0
    elif hyper_hits >= 1 or extra_hyper:
        flags["hyperparams_detail"] = 0.5
    else:
        flags["hyperparams_detail"] = 0.0

    # seed_disclosed: explicit random seed disclosure
    seed_strict = bool(re.search(
        r"\brandom seed\b|\bseed\s*=\s*\d+\b|\bseeded with \d+\b|"
        r"\brandom_state\s*=\s*\d+\b|\bwe set (?:the )?seed\b",
        model_text, re.I,
    ))
    seed_partial = bool(re.search(r"\bseed\b|\bseeded\b|\brng\b", model_text, re.I))
    flags["seed_disclosed"] = (
        1.0 if seed_strict
        else (0.5 if seed_partial else 0.0)
    )

    # compute_detail: GPU/hardware/training time
    compute_strong = bool(re.search(
        r"\bNVIDIA\b|\bH100\b|\bA100\b|\bV100\b|\bRTX\b|\bTPU\b|"
        r"\bGPU(?:s)?\b|\btraining time\b|\bwall[- ]clock\b|"
        r"\bCERN\b|\bLHC\b|\bGeant4\b|\bcomputing cluster\b",
        model_text, re.I,
    ))
    compute_partial = bool(re.search(
        r"\bCUDA\b|\bcompute\b|\bhardware\b|\bCPU\b",
        model_text, re.I,
    ))
    flags["compute_detail"] = (
        1.0 if compute_strong
        else (0.5 if compute_partial else 0.0)
    )

    # software_versions: versioned software names or tool configs
    sw_strong = bool(_SOFTWARE_VERSIONS_RE.search(model_text))
    sw_partial = bool(re.search(
        r"\bPyTorch\b|\bTensorFlow\b|\bscikit[- ]learn\b|\bR package\b|"
        r"\bMATLAB\b|\bStata\b|\bGeant\b|\bROOT\b",
        model_text, re.I,
    ))
    flags["software_versions"] = (
        1.0 if sw_strong
        else (0.5 if sw_partial else 0.0)
    )

    # evaluation_protocol: benchmarks + metrics present
    bench_hits  = sum(1 for p in POSITIVE_PATTERNS["has_metrics"] if re.search(p, model_text, re.I))
    metric_extra = bool(re.search(
        r"\bROC curve\b|\bAUROC\b|\bhazard ratio\b|\bSharpe ratio\b|"
        r"\bCONSORT\b|\bSPEC\b|\bMLPerf\b|\bcross[- ]validation\b|"
        r"\btest set\b|\bevaluation protocol\b|\bvalidation set\b|\bbenchmark\b",
        model_text, re.I,
    ))
    flags["evaluation_protocol"] = (
        1.0 if (bench_hits >= 2 and metric_extra)
        else (0.5 if (bench_hits >= 1 or metric_extra) else 0.0)
    )

    # ablation: ablation study detected
    ablation_hit = any(
        re.search(p, model_text, re.I) for p in POSITIVE_PATTERNS["has_ablation"]
    )
    flags["ablation"] = 1.0 if ablation_hit else 0.0

    # baseline_comparison: explicit comparison to baselines / SOTA
    baseline_hit = any(
        re.search(p, model_text, re.I) for p in POSITIVE_PATTERNS["has_baselines"]
    )
    flags["baseline_comparison"] = 1.0 if baseline_hit else 0.0

    # statistical_rigor: confidence intervals, p-values, multiple runs, etc.
    stat_hits = sum(
        1 for p in POSITIVE_PATTERNS["has_statistical_tests"]
        if re.search(p, model_text, re.I)
    )
    stat_extra = bool(re.search(
        r"\bmultiple runs?\b|\bstd(?:ev)?\b|\bbootstrap\b|"
        r"\bWilcoxon\b|\bt[- ]test\b|\bANOVA\b|\bFDR\b|"
        r"\bsystematic uncertainty\b|\bluminosity\b",
        model_text, re.I,
    ))
    flags["statistical_rigor"] = (
        1.0 if (stat_hits >= 2 or (stat_hits >= 1 and stat_extra))
        else (0.5 if (stat_hits == 1 or stat_extra) else 0.0)
    )

    # limitations: limitations section or threats-to-validity
    limitations_hit = any(
        re.search(p, model_text, re.I) for p in POSITIVE_PATTERNS["has_limitations"]
    )
    flags["limitations"] = 1.0 if limitations_hit else 0.0

    return flags


# ---------------------------------------------------------------------------
# Text composition
# ---------------------------------------------------------------------------
def _compose_model_text(payload: dict) -> str:
    title      = _coerce_text(payload.get("title"))
    abstract   = _coerce_text(payload.get("abstract"))
    model_text = _coerce_text(payload.get("model_text"))
    raw_text   = _coerce_text(payload.get("raw_text"))
    keywords   = payload.get("keywords") or []

    keyword_text = ""
    if isinstance(keywords, (list, tuple)):
        keyword_text = " ".join(_coerce_text(item) for item in keywords if _coerce_text(item))

    pieces = [title, abstract, keyword_text, model_text, raw_text]
    return "\n\n".join(piece for piece in pieces if piece).strip()


# ---------------------------------------------------------------------------
# Feature row builders (used for classifier and calibrator matrices)
# ---------------------------------------------------------------------------
def _merge_payload_with_auto_flags(payload: dict) -> dict:
    """Auto-compute feature flags and merge into payload (only fills missing keys)."""
    merged     = dict(payload or {})
    auto_flags = compute_base_feature_flags(merged)
    for key, value in auto_flags.items():
        if key not in merged or merged.get(key) in (None, "", []):
            merged[key] = value
    return merged


def _build_explicit_feature_row(payload: dict, feature_columns: list[str]) -> pd.DataFrame:
    """Build the explicit feature row for the given column list."""
    row = {col: _safe_float(payload.get(col), 0.0) for col in feature_columns}
    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Classifier matrix builder (TF-IDF + explicit features + domain one-hot)
# ---------------------------------------------------------------------------
def _build_classifier_matrix(active_model: dict, payload: dict):
    """
    Build the sparse feature matrix for the active model.

    Matrix = [TF-IDF | explicit features | domain one-hot]

    The column dimensions of explicit features and domain one-hot are read
    from the model's metadata.json so old and new models both work.
    """
    model_key   = active_model["model_key"]
    vectorizer  = _load_joblib_cached(
        active_model["vectorizer_path"],
        _cache_key(model_key, "vectorizer"),
    )
    classifier  = _load_joblib_cached(
        active_model["classifier_path"],
        _cache_key(model_key, "classifier"),
    )

    model_text = _compose_model_text(payload)
    if not model_text:
        raise ValueError("No input text was provided for prediction.")

    explicit_cols   = _get_explicit_feature_columns(active_model)
    domain_cols     = _get_domain_onehot_cols(active_model)
    domain          = _extract_domain(payload.get("domain"))

    text_matrix     = vectorizer.transform([model_text])
    explicit_df     = _build_explicit_feature_row(payload, explicit_cols)
    explicit_matrix = sp.csr_matrix(explicit_df.to_numpy(dtype=float))
    domain_matrix   = _domain_onehot_matrix(domain, domain_cols)

    parts = [text_matrix, explicit_matrix]
    if domain_matrix.shape[1] > 0:
        parts.append(domain_matrix)

    matrix = sp.hstack(parts, format="csr")
    return classifier, matrix, model_text


# ---------------------------------------------------------------------------
# Main prediction entry points
# ---------------------------------------------------------------------------
def predict_with_active_model(payload: dict) -> dict:
    active_model = get_active_model()
    if active_model is None:
        raise FileNotFoundError("No active model is available in backend/ml_assets/models.")

    payload = _merge_payload_with_auto_flags(payload)

    classifier, matrix, model_text = _build_classifier_matrix(active_model, payload)
    class_labels  = _load_label_encoder_classes(active_model)

    predicted_raw   = classifier.predict(matrix)[0]
    predicted_label = _normalize_label(predicted_raw)
    probabilities   = _extract_probability_map(classifier, matrix, class_labels)

    # Normalize probabilities to LABEL_ORDER keys
    normalized_probabilities: dict[str, float] = {}
    for label in LABEL_ORDER:
        normalized_probabilities[label] = float(probabilities.get(label, 0.0))

    if sum(normalized_probabilities.values()) <= 0:
        normalized_probabilities[predicted_label] = 1.0

    total = sum(normalized_probabilities.values()) or 1.0
    normalized_probabilities = {
        label: float(value / total)
        for label, value in normalized_probabilities.items()
    }

    confidence = float(max(normalized_probabilities.values())) if normalized_probabilities else 0.0

    # Build normalized probabilities keyed by YES/NO for services.py compatibility.
    # New classifier labels: NO→HIGH, YES→LOW after _normalize_label.
    # services.py calls score_from_prediction(prediction["prediction"], prediction["probabilities"])
    # and build_explanation reads prediction["prediction"] — so we must provide both
    # the new canonical keys AND the legacy aliases.
    yes_prob = normalized_probabilities.get("LOW", 0.0)
    no_prob  = normalized_probabilities.get("HIGH", 0.0)
    legacy_probabilities = {"YES": yes_prob, "NO": no_prob}

    return {
        # ── New canonical keys ──────────────────────────────────────────────
        "model_key":             active_model["model_key"],
        "model_dir":             active_model["model_dir"],
        "predicted_label":       predicted_label,
        "class_probabilities":   normalized_probabilities,
        "confidence":            confidence,
        "model_text_chars":      len(model_text),
        "domain":                _extract_domain(payload.get("domain")),
        "used_score_calibrator": bool(active_model.get("score_calibrator_path")),
        # ── Legacy aliases expected by services.py ──────────────────────────
        # services.py reads prediction.get("prediction") and prediction.get("probabilities")
        # These must match so score_from_prediction() and build_explanation() work correctly.
        "prediction":            "YES" if predicted_label == "LOW" else ("NO" if predicted_label == "HIGH" else predicted_label),
        "probabilities":         legacy_probabilities,
        "model": {
            "model_key": active_model["model_key"],
            "domain":    _extract_domain(payload.get("domain")),
        },
    }


def _safe_probability(probabilities: dict, key: str) -> float:
    return _safe_float(probabilities.get(key), 0.0)


def _build_score_feature_frame(active_model: dict, payload: dict, classification_result: dict) -> pd.DataFrame:
    """
    Build the feature frame for the score calibrator.

    Produces ALL possible feature columns (legacy + new) so that
    score_feature_columns.json can select exactly what the model needs.
    """
    model_key       = active_model["model_key"]
    feature_columns = _load_json_cached(
        active_model.get("score_feature_columns_path"),
        _cache_key(model_key, "score_feature_columns"),
        [],
    )
    if not feature_columns:
        raise FileNotFoundError("score_feature_columns.json is missing for the active model.")

    flags = compute_base_feature_flags(payload)

    # ── Count states ─────────────────────────────────────────────────────────
    # Using new 13 attributes if available; fallback to legacy positives
    explicit_cols = _get_explicit_feature_columns(active_model)
    attr_vals     = [_safe_float(flags.get(col), 0.0) for col in explicit_cols]
    supported_count = float(sum(1 for v in attr_vals if v >= 0.99))
    partial_count   = float(sum(1 for v in attr_vals if 0.49 <= v < 0.99))
    missing_count   = float(sum(1 for v in attr_vals if v < 0.49))

    # ── Probabilities ─────────────────────────────────────────────────────────
    probabilities = classification_result.get("class_probabilities", {})

    # New binary models: YES→LOW, NO→HIGH after _normalize_label
    # So P(YES reproducible) is stored as probabilities["LOW"]
    classifier_prob_yes = _safe_probability(probabilities, "LOW")
    classifier_prob_no  = _safe_probability(probabilities, "HIGH")

    # Also keep legacy yes_proxy / no_proxy for old calibrators
    yes_proxy = _safe_probability(probabilities, "LOW")  + 0.5 * _safe_probability(probabilities, "MEDIUM")
    no_proxy  = _safe_probability(probabilities, "HIGH") + 0.5 * _safe_probability(probabilities, "MEDIUM")

    # ── Other scalar features ─────────────────────────────────────────────────
    page_count    = _safe_float(payload.get("page_count"), 0.0)
    rubric_score  = _safe_float(payload.get("rubric_score"), 0.0)
    llm_label     = _normalize_label(payload.get("llm_label", ""))
    llm_label_bin = 1.0 if llm_label == "LOW" else 0.0

    # ── Domain one-hot for new 7-domain structure ────────────────────────────
    domain      = _extract_domain(payload.get("domain"))
    domain_row  = {col: (1.0 if col == f"dom_{domain}" else 0.0) for col in _NEW_DOMAIN_ONEHOT_COLS}

    # ── Also produce legacy 5-domain one-hot for old calibrators ─────────────
    for col in _LEGACY_DOMAIN_ONEHOT_COLS:
        domain_row[col] = 1.0 if col == f"dom_{domain}" else 0.0

    # ── Build comprehensive row ───────────────────────────────────────────────
    row: dict = {
        # New 13 attribute flags
        **{attr: _safe_float(flags.get(attr), 0.0) for attr in NEW_ATTRIBUTE_ORDER},
        # Legacy 18 feature flags
        **{col: _safe_float(flags.get(col), 0.0) for col in _LEGACY_BASE_FEATURE_COLUMNS},
        # Count-based features
        "supported_count":        supported_count,
        "partial_count":          partial_count,
        "missing_count":          missing_count,
        # Probability features (new names)
        "classifier_prob_yes":    classifier_prob_yes,
        "classifier_prob_no":     classifier_prob_no,
        # Probability features (legacy names)
        "yes_proxy":              yes_proxy,
        "no_proxy":               no_proxy,
        # Scalar features
        "model_text_chars":       float(classification_result.get("model_text_chars", 0.0)),
        "page_count":             page_count,
        "rubric_score":           rubric_score,          # legacy
        "llm_label_binary":       llm_label_bin,         # legacy
        # Domain one-hot (both new 7-domain and legacy 5-domain)
        **domain_row,
    }

    # ── Build frame and reindex to exactly what the calibrator expects ────────
    frame = pd.DataFrame([row])
    for column in feature_columns:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0).astype(float)

    frame = frame[feature_columns]
    return frame


def predict_score_with_active_model(payload: dict) -> dict:
    active_model = get_active_model()
    if active_model is None:
        raise FileNotFoundError("No active model is available in backend/ml_assets/models.")

    score_calibrator_path = active_model.get("score_calibrator_path")
    if not score_calibrator_path:
        raise FileNotFoundError("score_calibrator.joblib is missing for the active model.")

    payload = _merge_payload_with_auto_flags(payload)
    classification_result = predict_with_active_model(payload)

    model_key  = active_model["model_key"]
    calibrator = _load_joblib_cached(
        score_calibrator_path,
        _cache_key(model_key, "score_calibrator"),
    )

    feature_frame    = _build_score_feature_frame(active_model, payload, classification_result)
    predicted_score  = float(calibrator.predict(feature_frame)[0])
    predicted_score  = _clip_score(predicted_score)
    predicted_label  = label_from_score(predicted_score)

    return {
        "model_key":       active_model["model_key"],
        "predicted_score": round(predicted_score, 2),
        "score":           round(predicted_score, 2),  # legacy alias so old callers still work
        "predicted_label": predicted_label,
        "band":            predicted_label,
        "features_used":   list(feature_frame.columns),
        "classification":  classification_result,
    }
