from pathlib import Path
import json
import numpy as np
import pandas as pd


POSITIVE_FEATURES = [
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
]

NEGATIVE_FEATURES = [
    "review_missing_details",
    "review_repro_concern",
    "review_code_missing",
    "review_dataset_unclear",
    "review_hyperparams_unclear",
    "review_missing_ablation",
    "review_weak_baselines",
    "review_insufficient_experiments",
]

BASE_FEATURE_COLUMNS = POSITIVE_FEATURES + NEGATIVE_FEATURES


def safe_text_len(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.len().astype(float)


def normalize_binary_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in BASE_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)
    return df


def build_rich_features(df: pd.DataFrame):
    df = df.copy()
    df = normalize_binary_columns(df)

    # Ensure optional columns exist
    for col in ["title", "abstract", "model_text", "review_text", "decision_text", "venue", "year", "review_count"]:
        if col not in df.columns:
            df[col] = ""

    # Length-based features
    df["title_len"] = safe_text_len(df["title"])
    df["abstract_len"] = safe_text_len(df["abstract"])
    df["model_text_len"] = safe_text_len(df["model_text"])
    df["review_text_len"] = safe_text_len(df["review_text"])
    df["decision_text_len"] = safe_text_len(df["decision_text"])

    # Review count
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(float)

    # Count-style features
    df["num_positive_indicators"] = df[POSITIVE_FEATURES].sum(axis=1)
    df["num_negative_indicators"] = df[NEGATIVE_FEATURES].sum(axis=1)

    # Ratio / aggregate features
    df["positive_minus_negative"] = df["num_positive_indicators"] - df["num_negative_indicators"]
    df["positive_plus_negative"] = df["num_positive_indicators"] + df["num_negative_indicators"]
    df["positive_to_total_ratio"] = np.where(
        df["positive_plus_negative"] > 0,
        df["num_positive_indicators"] / df["positive_plus_negative"],
        0.0,
    )

    # Interaction features requested / useful
    df["has_code_and_data"] = (df["has_code_link"] * df["has_data_link"]).astype(float)
    df["has_hyperparams_and_seed"] = (df["has_hyperparams"] * df["has_seed"]).astype(float)
    df["repro_concern_and_missing_details"] = (
        df["review_repro_concern"] * df["review_missing_details"]
    ).astype(float)
    df["baselines_and_ablation"] = (df["has_baselines"] * df["has_ablation"]).astype(float)
    df["metrics_and_stats"] = (df["has_metrics"] * df["has_statistical_tests"]).astype(float)

    # Density-style features
    df["positive_per_1000_model_chars"] = np.where(
        df["model_text_len"] > 0,
        1000.0 * df["num_positive_indicators"] / df["model_text_len"],
        0.0,
    )
    df["negative_per_1000_review_chars"] = np.where(
        df["review_text_len"] > 0,
        1000.0 * df["num_negative_indicators"] / df["review_text_len"],
        0.0,
    )

    # Metadata features (legitimate if available at inference time)
    df["year_num"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(float)

    venue_series = df["venue"].fillna("").astype(str)
    df["venue_iclr_2025"] = (venue_series == "ICLR.cc/2025/Conference").astype(float)
    df["venue_iclr_2024"] = (venue_series == "ICLR.cc/2024/Conference").astype(float)
    df["venue_neurips_2024"] = (venue_series == "NeurIPS.cc/2024/Conference").astype(float)

    feature_columns = (
        BASE_FEATURE_COLUMNS
        + [
            "title_len",
            "abstract_len",
            "model_text_len",
            "review_text_len",
            "decision_text_len",
            "review_count",
            "num_positive_indicators",
            "num_negative_indicators",
            "positive_minus_negative",
            "positive_plus_negative",
            "positive_to_total_ratio",
            "has_code_and_data",
            "has_hyperparams_and_seed",
            "repro_concern_and_missing_details",
            "baselines_and_ablation",
            "metrics_and_stats",
            "positive_per_1000_model_chars",
            "negative_per_1000_review_chars",
            "year_num",
            "venue_iclr_2025",
            "venue_iclr_2024",
            "venue_neurips_2024",
        ]
    )

    X = df[feature_columns].copy()

    # Final clean numeric matrix
    for col in feature_columns:
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0).astype(float)

    return X, feature_columns


def save_feature_columns(path: Path, feature_columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feature_columns, indent=2), encoding="utf-8")