from pathlib import Path
import json
import shutil
from datetime import datetime

from feature_engineering_rich import build_rich_features


ML_PIPELINE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = ML_PIPELINE_DIR.parent
BACKEND_DIR = REPO_DIR / "backend"

SOURCE_MODELS_DIR = ML_PIPELINE_DIR / "outputs" / "models"
BACKEND_MODELS_DIR = BACKEND_DIR / "ml_assets" / "models"
REGISTRY_PATH = BACKEND_DIR / "ml_assets" / "registry.json"

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

MODEL_SPECS = [
    {
        "id": "text_tfidf_lr_v1",
        "name": "Text TF-IDF Baseline v1.0",
        "modelType": "Text TF-IDF Baseline",
        "pipelineType": "text_input_v1",
        "artifactSubdir": "tfidf_lr_v1",
        "description": "Text-only baseline model.",
    },
    {
        "id": "feature_lr_v1",
        "name": "Feature Logistic Regression v1.0",
        "modelType": "Feature Logistic Regression",
        "pipelineType": "feature_base_v1",
        "artifactSubdir": "feature_lr_v1",
        "description": "Base feature model using the 18 engineered indicators.",
    },
    {
        "id": "feature_random_forest_v1",
        "name": "Feature Random Forest v1.0",
        "modelType": "Feature Random Forest",
        "pipelineType": "feature_base_v1",
        "artifactSubdir": "feature_random_forest_v1",
        "description": "Base feature model using Random Forest.",
    },
    {
        "id": "feature_extra_trees_v1",
        "name": "Feature Extra Trees v1.0",
        "modelType": "Feature Extra Trees",
        "pipelineType": "feature_base_v1",
        "artifactSubdir": "feature_extra_trees_v1",
        "description": "Base feature model using Extra Trees.",
    },
    {
        "id": "feature_decision_tree_v1",
        "name": "Feature Decision Tree v1.0",
        "modelType": "Feature Decision Tree",
        "pipelineType": "feature_base_v1",
        "artifactSubdir": "feature_decision_tree_v1",
        "description": "Base feature model using Decision Tree.",
    },
    {
        "id": "feature_hist_gradient_boosting_rich_v1",
        "name": "Rich Feature HistGradientBoosting v1.0",
        "modelType": "Rich Feature HistGradientBoosting",
        "pipelineType": "feature_rich_v1",
        "artifactSubdir": "feature_hist_gradient_boosting_rich_v1",
        "description": "Rich feature model with derived engineered features.",
    },
    {
        "id": "feature_hist_gradient_boosting_rich_tuned_v1",
        "name": "Tuned Rich Feature HistGradientBoosting v1.1",
        "modelType": "Tuned Rich Feature HistGradientBoosting",
        "pipelineType": "feature_rich_v1",
        "artifactSubdir": "feature_hist_gradient_boosting_rich_tuned_v1",
        "description": "Best-performing tuned rich feature model.",
    },
]


def safe_read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def extract_metrics(model_dir: Path):
    train_report = safe_read_json(model_dir / "train_report.json", {})
    metrics = {"testAccuracy": None, "macroF1": None}

    test_block = None
    if isinstance(train_report, dict):
        test_block = (
            train_report.get("test_final_model")
            or train_report.get("test")
        )

    if isinstance(test_block, dict):
        metrics["testAccuracy"] = test_block.get("accuracy")
        report = test_block.get("classification_report", {})
        if isinstance(report, dict):
            metrics["macroF1"] = (
                report.get("macro avg", {}).get("f1-score")
                if isinstance(report.get("macro avg", {}), dict)
                else None
            )

    return metrics


def copy_model_dir(src: Path, dst: Path):
    if not src.exists():
        raise FileNotFoundError(f"Model source directory not found: {src}")

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


def ensure_feature_columns_json(pipeline_type: str, model_dir: Path):
    feature_columns_path = model_dir / "feature_columns.json"
    if feature_columns_path.exists():
        return

    if pipeline_type == "feature_base_v1":
        feature_columns = BASE_FEATURE_COLUMNS
    elif pipeline_type == "feature_rich_v1":
        import pandas as pd

        dummy = pd.DataFrame(
            [
                {
                    "title": "",
                    "abstract": "",
                    "model_text": "",
                    "review_text": "",
                    "decision_text": "",
                    "venue": "",
                    "year": 0,
                    "review_count": 0,
                }
            ]
        )
        _, feature_columns = build_rich_features(dummy)
    else:
        return

    feature_columns_path.write_text(
        json.dumps(feature_columns, indent=2),
        encoding="utf-8",
    )


def main():
    BACKEND_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    missing = []
    for spec in MODEL_SPECS:
        src = SOURCE_MODELS_DIR / spec["artifactSubdir"]
        if not src.exists():
            missing.append(str(src))

    if missing:
        missing_text = "\n".join(missing)
        raise FileNotFoundError(
            "The following model artifact directories are missing locally:\n"
            f"{missing_text}\n\n"
            "Bring the model code into the integration branch and rerun any missing training scripts first."
        )

    registry_models = []

    for spec in MODEL_SPECS:
        src = SOURCE_MODELS_DIR / spec["artifactSubdir"]
        dst = BACKEND_MODELS_DIR / spec["artifactSubdir"]

        copy_model_dir(src, dst)
        ensure_feature_columns_json(spec["pipelineType"], dst)

        metadata_path = dst / "metadata.json"
        created_at = (
            datetime.fromtimestamp(metadata_path.stat().st_mtime).strftime("%m/%d/%Y")
            if metadata_path.exists()
            else datetime.now().strftime("%m/%d/%Y")
        )

        metrics = extract_metrics(dst)

        registry_models.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "modelType": spec["modelType"],
                "pipelineType": spec["pipelineType"],
                "artifactSubdir": spec["artifactSubdir"],
                "createdAt": created_at,
                "active": spec["id"] == "feature_hist_gradient_boosting_rich_tuned_v1",
                "status": "ready",
                "description": spec["description"],
                "metrics": metrics,
            }
        )

    registry = {
        "activeModelId": "feature_hist_gradient_boosting_rich_tuned_v1",
        "models": registry_models,
    }

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    print(f"✅ Exported all models to: {BACKEND_MODELS_DIR}")
    print(f"✅ Wrote registry to: {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
