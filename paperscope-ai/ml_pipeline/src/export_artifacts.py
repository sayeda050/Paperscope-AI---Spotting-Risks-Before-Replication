from pathlib import Path
import shutil
import json
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent

SRC_MODEL_DIR = BASE_DIR / "outputs" / "models" / "tfidf_logreg_auto_v2"

BACKEND_DIR = BASE_DIR.parent / "backend"
ML_ASSETS_DIR = BACKEND_DIR / "ml_assets"
DEST_MODEL_DIR = ML_ASSETS_DIR / "models" / "tfidf_logreg_auto_v2"
REGISTRY_PATH = ML_ASSETS_DIR / "registry.json"


def main():
    if not SRC_MODEL_DIR.exists():
        raise FileNotFoundError(f"Source model directory not found: {SRC_MODEL_DIR}")

    DEST_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    ML_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        "vectorizer.joblib",
        "classifier.joblib",
        "label_encoder.joblib",
        "metadata.json",
        "train_report.json",
        "feature_coefficients.csv",
    ]

    for fname in files_to_copy:
        src_file = SRC_MODEL_DIR / fname
        if not src_file.exists():
            raise FileNotFoundError(f"Missing source file: {src_file}")
        shutil.copy2(src_file, DEST_MODEL_DIR / fname)

    registry = {
        "active_model": "tfidf_logreg_auto_v2",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "available_models": ["tfidf_logreg_auto_v2"],
        "model_path": str(DEST_MODEL_DIR),
    }

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(f"✅ Exported model files to: {DEST_MODEL_DIR}")
    print(f"✅ Registry updated at: {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
