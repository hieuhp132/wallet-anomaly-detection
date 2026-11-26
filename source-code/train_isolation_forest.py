
"""
Train Isolation Forest Baseline A.

Input:
    data/model/model_features.csv

Outputs:
    data/model/results/
        anomaly_scores.csv
        anomaly_summary.json
        model_config.json
        model.joblib
        feature_deviation_analysis.csv
        top_anomaly_wallets.csv

Run:
    python .\\train_isolation_forest.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_DATA_DIR = BASE_DIR / "data" / "model"
INPUT_FILE = MODEL_DATA_DIR / "model_features.csv"

RESULTS_DIR = MODEL_DATA_DIR / "results"

WALLET_COLUMN = "wallet"

FEATURES = [
    "tx_count",
    "incoming_tx_count",
    "outgoing_tx_count",
    "transfer_count",
    "unique_counterparties",
    "unique_assets",
    "active_days",
    "active_span_hours",
    "avg_interval_minutes",
    "median_interval_minutes",
    "tx_per_active_day",
]

CONFIG = {
    "model_name": "IsolationForest",
    "baseline": "A",
    "n_estimators": 300,
    "max_samples": "auto",
    "contamination": 0.05,
    "max_features": 1.0,
    "bootstrap": False,
    "random_state": 42,
    "n_jobs": -1,
}


# ============================================================
# HELPERS
# ============================================================

def fail(message: str) -> None:
    raise SystemExit(f"\nERROR: {message}\n")


def save_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )


def validate_dataset(df: pd.DataFrame) -> None:
    required = [WALLET_COLUMN] + FEATURES

    missing = sorted(set(required) - set(df.columns))

    if missing:
        fail(f"Missing columns: {missing}")

    if df[WALLET_COLUMN].isna().any():
        fail("Wallet column contains missing values.")

    if df[WALLET_COLUMN].duplicated().any():
        fail("Duplicate wallets detected.")

    for feature in FEATURES:
        df[feature] = pd.to_numeric(
            df[feature],
            errors="coerce",
        )

    if df[FEATURES].isna().any().any():
        fail("Missing or non-numeric feature values.")

    values = df[FEATURES].to_numpy(dtype=float)

    if not np.isfinite(values).all():
        fail("Infinite values detected.")

    if (values < 0).any():
        fail("Negative values detected.")

    if len(df) < 30:
        fail("Too few observations for this experiment.")


def calculate_feature_deviations(
    df: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate descriptive feature-level deviation information.

    This is NOT a model-native feature attribution method.
    It compares each wallet with the dataset distribution
    using percentile rank and distance from the median.
    """

    rows = []

    for _, wallet_row in scores.iterrows():
        wallet = wallet_row[WALLET_COLUMN]

        original_row = df.loc[
            df[WALLET_COLUMN] == wallet
        ].iloc[0]

        for feature in FEATURES:
            population = df[feature].astype(float)

            value = float(original_row[feature])
            median = float(population.median())

            percentile = float(
                population.rank(
                    method="average",
                    pct=True,
                ).loc[original_row.name]
            )

            # Descriptive deviation from median.
            # Not a causal/model attribution.
            deviation = value - median

            if deviation > 0:
                direction = "above_median"
            elif deviation < 0:
                direction = "below_median"
            else:
                direction = "at_median"

            rows.append({
                "wallet": wallet,
                "anomaly_score": wallet_row["anomaly_score"],
                "anomaly_rank": wallet_row["anomaly_rank"],
                "feature": feature,
                "feature_value": value,
                "population_median": median,
                "population_percentile": percentile,
                "deviation_from_median": deviation,
                "direction": direction,
            })

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 70)
    print("TRAIN ISOLATION FOREST - BASELINE A")
    print("=" * 70)

    if not INPUT_FILE.exists():
        fail(f"Input file not found: {INPUT_FILE}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1. LOAD DATA
    # --------------------------------------------------------

    df = pd.read_csv(INPUT_FILE)

    print(f"Input: {INPUT_FILE}")
    print(f"Wallets: {len(df)}")
    print(f"Features: {len(FEATURES)}")

    validate_dataset(df)

    wallets = df[WALLET_COLUMN].copy()

    X = df[FEATURES].copy()

    print("\nDataset validation passed.")

    # --------------------------------------------------------
    # 2. TRAIN MODEL
    # --------------------------------------------------------

    model = IsolationForest(
        n_estimators=CONFIG["n_estimators"],
        max_samples=CONFIG["max_samples"],
        contamination=CONFIG["contamination"],
        max_features=CONFIG["max_features"],
        bootstrap=CONFIG["bootstrap"],
        random_state=CONFIG["random_state"],
        n_jobs=CONFIG["n_jobs"],
    )

    print("\nTraining Isolation Forest...")

    model.fit(X)

    print("Training completed.")

    # --------------------------------------------------------
    # 3. CALCULATE SCORES
    # --------------------------------------------------------

    # sklearn:
    # decision_function: lower = more anomalous
    # score_samples: lower = more anomalous
    # predict: -1 = anomaly, 1 = normal

    decision_scores = model.decision_function(X)

    raw_scores = model.score_samples(X)

    predictions = model.predict(X)

    # Invert score direction for easier ranking:
    # higher anomaly_score = more anomalous
    anomaly_scores = -raw_scores

    results = pd.DataFrame({
        WALLET_COLUMN: wallets,
        "decision_score": decision_scores,
        "raw_score_samples": raw_scores,
        "anomaly_score": anomaly_scores,
        "prediction": predictions,
    })

    results["is_anomaly"] = (
        results["prediction"] == -1
    )

    results["status"] = results["prediction"].map({
        -1: "ANOMALY",
        1: "NORMAL",
    })

    # Higher anomaly_score = more anomalous.
    results = results.sort_values(
        "anomaly_score",
        ascending=False,
    ).reset_index(drop=True)

    results["anomaly_rank"] = (
        np.arange(1, len(results) + 1)
    )

    # --------------------------------------------------------
    # 4. SAVE SCORES
    # --------------------------------------------------------

    results.to_csv(
        RESULTS_DIR / "anomaly_scores.csv",
        index=False,
    )

    # --------------------------------------------------------
    # 5. SUMMARY
    # --------------------------------------------------------

    anomaly_count = int(
        results["is_anomaly"].sum()
    )

    normal_count = int(
        (~results["is_anomaly"]).sum()
    )

    anomaly_rate = (
        anomaly_count / len(results)
        if len(results) > 0
        else 0
    )

    summary = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_name": "IsolationForest",
        "baseline": "A",
        "dataset_size": int(len(results)),
        "feature_count": int(len(FEATURES)),
        "anomaly_count": anomaly_count,
        "normal_count": normal_count,
        "actual_anomaly_rate": anomaly_rate,
        "configured_contamination": CONFIG["contamination"],
        "note": (
            "Anomaly detection is not equivalent to fraud detection. "
            "Scores identify unusual behavior relative to the sampled "
            "dataset. No fraud labels or ground-truth evaluation "
            "are available in this experiment."
        ),
    }

    save_json(
        RESULTS_DIR / "anomaly_summary.json",
        summary,
    )

    # --------------------------------------------------------
    # 6. SAVE MODEL
    # --------------------------------------------------------

    model_path = RESULTS_DIR / "model.joblib"

    joblib.dump(model, model_path)

    # --------------------------------------------------------
    # 7. SAVE MODEL CONFIG
    # --------------------------------------------------------

    model_config = {
        **CONFIG,
        "features": FEATURES,
        "wallet_column": WALLET_COLUMN,
        "input_file": str(INPUT_FILE),
        "model_file": str(model_path),
        "score_interpretation": {
            "anomaly_score": (
                "Higher values indicate more anomalous observations "
                "relative to this fitted model."
            ),
            "decision_score": (
                "Negative decision_function values indicate "
                "observations classified as anomalies."
            ),
            "prediction": {
                "-1": "ANOMALY",
                "1": "NORMAL",
            },
        },
    }

    save_json(
        RESULTS_DIR / "model_config.json",
        model_config,
    )

    # --------------------------------------------------------
    # 8. FEATURE DEVIATION ANALYSIS
    # --------------------------------------------------------

    deviations = calculate_feature_deviations(
        df,
        results,
    )

    deviations.to_csv(
        RESULTS_DIR / "feature_deviation_analysis.csv",
        index=False,
    )

    # --------------------------------------------------------
    # 9. TOP ANOMALIES
    # --------------------------------------------------------

    top_anomalies = results[
        results["is_anomaly"]
    ].copy()

    top_anomalies.to_csv(
        RESULTS_DIR / "top_anomaly_wallets.csv",
        index=False,
    )

    # --------------------------------------------------------
    # 10. CONSOLE SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MODEL SUMMARY")
    print("=" * 70)

    print(f"Total wallets: {len(results)}")
    print(f"Anomalies: {anomaly_count}")
    print(f"Normal: {normal_count}")
    print(f"Actual anomaly rate: {anomaly_rate:.2%}")

    print("\nTOP 20 WALLETS BY ANOMALY SCORE")

    display_columns = [
        WALLET_COLUMN,
        "anomaly_rank",
        "anomaly_score",
        "decision_score",
        "status",
    ]

    print(
        results[display_columns]
        .head(20)
        .to_string(index=False)
    )

    print("\nANOMALY WALLETS")

    if top_anomalies.empty:
        print("No wallets classified as anomalies.")
    else:
        print(
            top_anomalies[
                display_columns
            ].to_string(index=False)
        )

    print("\nOUTPUT FILES")

    for filename in [
        "anomaly_scores.csv",
        "anomaly_summary.json",
        "model_config.json",
        "model.joblib",
        "feature_deviation_analysis.csv",
        "top_anomaly_wallets.csv",
    ]:
        print(RESULTS_DIR / filename)

    print("\n" + "=" * 70)
    print("BASELINE A TRAINING COMPLETE")
    print("=" * 70)

    print(
        "Reminder: anomaly scores are not fraud labels."
    )


if __name__ == "__main__":
    main()

