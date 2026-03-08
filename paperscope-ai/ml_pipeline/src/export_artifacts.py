#Copies artifacts to backend ml_assets/ and writes registry.json.


from pathlib import Path
import shutil
import json
from datetime import datetime, timezone

MODEL_NAME = "tfidf_lr_v1"

SRC_DIR = Path("outputs/model_artifacts") / MODEL_NAME

# IMPORTANT: points to your backend folder
BACKEND_ASSETS = Path("..") / "backend" / "ml_assets"
DEST_DIR = BACKEND_ASSETS / "models" / MODEL_NAME
REGISTRY = BACKEND_ASSETS / "registry.json"

def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_ASSETS.mkdir(parents=True, exist_ok=True)

    for fname in ["vectorizer.joblib", "classifier.joblib", "metadata.json"]:
        shutil.copyfile(SRC_DIR / fname, DEST_DIR / fname)

    registry = {
        "active_model": MODEL_NAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "available_models": [MODEL_NAME],
    }
    REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    print("✅ Export complete!")
    print("   ->", DEST_DIR)
    print("   ->", REGISTRY)

if __name__ == "__main__":
    main()