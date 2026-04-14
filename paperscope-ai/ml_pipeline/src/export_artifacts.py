"""
export_artifacts.py — Export the latest trained model for a domain to backend/ml_assets.

Reads from outputs/models/{domain}/latest.json, copies all artifacts,
and updates backend/ml_assets/registry.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from domain_config import SUPPORTED_DOMAINS, validate_domain
from utils import ensure_dir, read_latest_model_dir, write_json, PIPELINE_SCHEMA_VERSION

PIPELINE_DIR = SRC_DIR.parent
BACKEND_DIR  = PIPELINE_DIR.parent / "backend"
ML_ASSETS    = BACKEND_DIR / "ml_assets"
MODELS_OUT   = ML_ASSETS / "models"
REGISTRY     = ML_ASSETS / "registry.json"

# Only metadata.json is truly required — it is written by every training script.
REQUIRED_FILES = [
    "metadata.json",
]

# All model artifacts are optional individually; the guard below ensures at
# least one real model file is present before the export proceeds.
OPTIONAL_FILES = [
    # Classifier artifacts (from train_tfidf_logreg.py)
    "classifier.joblib",
    "label_encoder.joblib",
    "vectorizer.joblib",
    "train_report.json",
    "feature_coefficients.csv",
    "confusion_matrix_test.csv",
    # Calibrator artifacts (from train_score_calibrator.py)
    "score_calibrator.joblib",
    "score_feature_columns.json",
    "score_calibrator_report.json",
]

# At least one of these must be present — otherwise there is nothing useful to export.
MUST_HAVE_ONE_OF = [
    "classifier.joblib",
    "score_calibrator.joblib",
]


def load_registry() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"models": [], "domains": {}}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the latest trained model artifacts to backend/ml_assets."
    )
    parser.add_argument(
        "--domain", required=True,
        choices=SUPPORTED_DOMAINS + ["all"],
        help="Domain whose latest model to export.",
    )
    parser.add_argument(
        "--model-name", default="",
        help="Override model directory name in ml_assets (default: auto-named).",
    )
    args = parser.parse_args()

    domain_tag = validate_domain(args.domain) if args.domain != "all" else "all"

    try:
        src_dir = read_latest_model_dir(PIPELINE_DIR / "outputs" / "models", domain_tag)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Read run_id from metadata
    run_id = "unknown"
    meta_path = src_dir / "metadata.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            run_id = meta.get("run_id", src_dir.name)
        except Exception:
            run_id = src_dir.name

    model_name = args.model_name or f"tfidf_logreg_{domain_tag}_{run_id}"
    dest_dir   = MODELS_OUT / model_name
    ensure_dir(dest_dir)
    ensure_dir(ML_ASSETS)

    # Copy required files
    for fname in REQUIRED_FILES:
        src_file = src_dir / fname
        if not src_file.exists():
            raise FileNotFoundError(
                f"Required artifact missing: {src_file}\n"
                f"Re-train with: python train_tfidf_logreg.py --domain {domain_tag}"
            )
        shutil.copy2(src_file, dest_dir / fname)
        print(f"  ✅ {fname}")

    # Guard: at least one real model artifact must be present before we proceed
    present_models = [f for f in MUST_HAVE_ONE_OF if (src_dir / f).exists()]
    if not present_models:
        raise FileNotFoundError(
            f"No usable model artifact found in {src_dir}\n"
            f"Expected at least one of: {MUST_HAVE_ONE_OF}\n"
            f"Run one or both of:\n"
            f"  python train_tfidf_logreg.py --domain {domain_tag}\n"
            f"  python train_score_calibrator.py --domain {domain_tag}"
        )

    # Copy optional files (silently skip any that don't exist)
    for fname in OPTIONAL_FILES:
        src_file = src_dir / fname
        if src_file.exists():
            shutil.copy2(src_file, dest_dir / fname)
            print(f"  📋 {fname} (optional)")

    # Update registry.json
    registry = load_registry()
    models: list[dict] = registry.get("models", [])
    domains: dict       = registry.get("domains", {})

    # Update or add this model
    existing_ids = {m.get("id") for m in models}
    if model_name not in existing_ids:
        models.append({
            "id":          model_name,
            "domain":      domain_tag,
            "run_id":      run_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        })

    # Set as active model for this domain
    domains[domain_tag] = {
        "active_model_id": model_name,
        "model_path":      str(dest_dir),
    }

    registry_payload = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "updated_at":     datetime.now(timezone.utc).isoformat(),
        "models":         models,
        "domains":        domains,
        # Legacy fields for backward compatibility
        "active_model":   model_name,
        "activeModelId":  model_name,
        "model_path":     str(dest_dir),
    }
    write_json(REGISTRY, registry_payload)

    print(f"\n✅ Exported {domain_tag} model → {dest_dir}")
    print(f"✅ Registry updated → {REGISTRY}")
    print(f"   Model name:  {model_name}")
    print(f"   Domain:      {domain_tag}")
    print(f"   Run ID:      {run_id}")


if __name__ == "__main__":
    main()
