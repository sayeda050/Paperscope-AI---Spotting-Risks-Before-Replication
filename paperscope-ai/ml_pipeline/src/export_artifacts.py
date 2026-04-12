from pathlib import Path
import shutil
import json
import argparse
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR.parent / "backend"
ML_ASSETS_DIR = BACKEND_DIR / "ml_assets"
MODELS_DIR = ML_ASSETS_DIR / "models"
REGISTRY_PATH = ML_ASSETS_DIR / "registry.json"


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


def main():
    parser = argparse.ArgumentParser(description="Export a trained model directory into backend/ml_assets.")
    parser.add_argument("--model-name", default="tfidf_logreg_auto_v2")
    args = parser.parse_args()

    src_model_dir = BASE_DIR / "outputs" / "models" / args.model_name
    dest_model_dir = MODELS_DIR / args.model_name

    if not src_model_dir.exists():
        raise FileNotFoundError(f"Source model directory not found: {src_model_dir}")

    dest_model_dir.mkdir(parents=True, exist_ok=True)
    ML_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    required_files = [
        "classifier.joblib",
        "label_encoder.joblib",
        "metadata.json",
        "train_report.json",
    ]
    optional_files = [
        "vectorizer.joblib",
        "feature_coefficients.csv",
        "feature_columns.json",
        "score_calibrator.joblib",
        "score_feature_columns.json",
        "score_calibrator_report.json",
    ]

    for fname in required_files:
        src_file = src_model_dir / fname
        if not src_file.exists():
            raise FileNotFoundError(f"Missing required source file: {src_file}")
        shutil.copy2(src_file, dest_model_dir / fname)

    for fname in optional_files:
        src_file = src_model_dir / fname
        if src_file.exists():
            shutil.copy2(src_file, dest_model_dir / fname)

    registry = safe_read_json(REGISTRY_PATH, {})
    models = registry.get("models", [])
    if not isinstance(models, list):
        models = []

    active_id = registry.get("activeModelId") or registry.get("active_model") or args.model_name
    known_ids = {m.get("id") for m in models if isinstance(m, dict)}
    if args.model_name not in known_ids:
        models.append({"id": args.model_name})

    payload = {
        "active_model": active_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "available_models": sorted({args.model_name, *[m.get("id") for m in models if isinstance(m, dict) and m.get("id")]}),
        "model_path": str(MODELS_DIR / active_id) if active_id else "",
        "activeModelId": active_id,
        "models": models,
    }
    write_json(REGISTRY_PATH, payload)

    print(f"✅ Exported model files to: {dest_model_dir}")
    print(f"✅ Registry updated at: {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
