
"""
Prepare Dataset V2 for an Isolation Forest baseline.

Input:
    data/wallet_features.csv

Outputs:
    data/model/
        model_features.csv             # wallet + transformed model features
        selected_features_raw.csv      # selected raw features, before transforms
        eligible_wallets.csv           # wallet list included in baseline
        excluded_wallets.csv           # wallets excluded by activity threshold
        feature_metadata.json          # reproducible preprocessing configuration
        preparation_report.json        # summary report
        feature_distribution.csv        # transformed feature distributions
        feature_correlation.csv         # Spearman correlation on prepared features
        high_correlation_pairs.csv      # high correlation pairs

Run from dataset_v2:
    python .\\prepare_dataset.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_FILE = DATA_DIR / "wallet_features.csv"
OUTPUT_DIR = DATA_DIR / "model"

MIN_TX_COUNT = 20

# Features selected for the initial Isolation Forest baseline.
# Asset-specific features, directional transfer-record counts,
# outgoing_ratio, and transfer_per_active_day are intentionally omitted.
RAW_FEATURES = [
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

# log1p is used to reduce skew for count, rate, and interval features.
LOG1P_FEATURES = [
    "tx_count",
    "incoming_tx_count",
    "outgoing_tx_count",
    "transfer_count",
    "unique_counterparties",
    "unique_assets",
    "avg_interval_minutes",
    "median_interval_minutes",
    "tx_per_active_day",
]

# Keep these features on their original scale for the initial baseline.
KEEP_AS_IS_FEATURES = [
    "active_days",
    "active_span_hours",
]

# Audit-only metadata, never used as model input.
AUDIT_COLUMNS = [
    "collection_complete",
    "incoming_complete",
    "outgoing_complete",
    "incoming_pages",
    "outgoing_pages",
    "raw_incoming_records",
    "raw_outgoing_records",
    "collection_error",
]

WALLET_COLUMN = "wallet"
ACTIVITY_COLUMN = "tx_count"


# ============================================================
# HELPERS
# ============================================================

def fail(message: str) -> None:
    raise SystemExit(f"\nERROR: {message}\n")


def json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def save_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=json_safe)


def make_distribution_report(
    df: pd.DataFrame,
    feature_columns: list[str]
) -> pd.DataFrame:
    rows = []
    percentiles = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]

    for feature in feature_columns:
        series = pd.to_numeric(df[feature], errors="coerce")
        row = {
            "feature": feature,
            "count": int(series.count()),
            "mean": series.mean(),
            "std": series.std(),
            "min": series.min(),
            "max": series.max(),
        }

        for p in percentiles:
            row[f"p{int(p * 100)}"] = series.quantile(p)

        rows.append(row)

    return pd.DataFrame(rows)


def calculate_spearman(
    df: pd.DataFrame,
    feature_columns: list[str]
) -> pd.DataFrame:
    corr = df[feature_columns].corr(method="spearman")
    rows = []

    for i, feature_a in enumerate(feature_columns):
        for j in range(i + 1, len(feature_columns)):
            feature_b = feature_columns[j]
            value = corr.loc[feature_a, feature_b]

            if pd.notna(value):
                rows.append({
                    "feature_a": feature_a,
                    "feature_b": feature_b,
                    "spearman_correlation": float(value),
                    "absolute_spearman": float(abs(value)),
                })

    result = pd.DataFrame(rows)

    if not result.empty:
        result = result.sort_values(
            "absolute_spearman",
            ascending=False
        ).reset_index(drop=True)

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 70)
    print("PREPARE DATASET V2 - ISOLATION FOREST BASELINE")
    print("=" * 70)

    if not INPUT_FILE.exists():
        fail(f"Input file not found: {INPUT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_FILE)

    print(f"Input: {INPUT_FILE}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    # --------------------------------------------------------
    # 1. Schema validation
    # --------------------------------------------------------

    required_columns = [WALLET_COLUMN, ACTIVITY_COLUMN] + RAW_FEATURES

    missing_columns = sorted(
        set(required_columns) - set(df.columns)
    )

    if missing_columns:
        fail(f"Missing required columns: {missing_columns}")

    if df[WALLET_COLUMN].isna().any():
        fail("Wallet column contains missing values.")

    df[WALLET_COLUMN] = (
        df[WALLET_COLUMN]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    duplicate_wallets = df[
        df[WALLET_COLUMN].duplicated(keep=False)
    ]

    if not duplicate_wallets.empty:
        fail(
            "Duplicate wallet rows detected. Resolve duplicates before "
            "preparing the dataset. Duplicate rows: "
            f"{len(duplicate_wallets)}"
        )

    # Convert selected features to numeric and validate.
    for feature in RAW_FEATURES:
        df[feature] = pd.to_numeric(
            df[feature],
            errors="coerce"
        )

    missing_feature_values = df[RAW_FEATURES].isna().sum()
    missing_feature_values = missing_feature_values[
        missing_feature_values > 0
    ]

    if not missing_feature_values.empty:
        fail(
            "Missing/non-numeric values in selected features:\n"
            + missing_feature_values.to_string()
        )

    if not np.isfinite(
        df[RAW_FEATURES].to_numpy(dtype=float)
    ).all():
        fail("Infinite values detected in selected feature columns.")

    negative_values = {}

    for feature in RAW_FEATURES:
        count = int((df[feature] < 0).sum())

        if count > 0:
            negative_values[feature] = count

    if negative_values:
        fail(
            "Negative values found in selected features. "
            "Review feature definitions:\n"
            + json.dumps(negative_values, indent=2)
        )

    if (df[ACTIVITY_COLUMN] < 0).any():
        fail("tx_count cannot be negative.")

    # --------------------------------------------------------
    # 2. Population selection
    # --------------------------------------------------------

    eligible = df[
        df[ACTIVITY_COLUMN] >= MIN_TX_COUNT
    ].copy()

    excluded = df[
        df[ACTIVITY_COLUMN] < MIN_TX_COUNT
    ].copy()

    eligible = eligible.sort_values(
        ACTIVITY_COLUMN,
        ascending=False
    ).reset_index(drop=True)

    excluded = excluded.sort_values(
        ACTIVITY_COLUMN,
        ascending=True
    ).reset_index(drop=True)

    print("\nPOPULATION")
    print(f"Total wallets: {len(df)}")
    print(
        f"Eligible (tx_count >= {MIN_TX_COUNT}): "
        f"{len(eligible)}"
    )
    print(
        f"Excluded (tx_count < {MIN_TX_COUNT}): "
        f"{len(excluded)}"
    )

    if eligible.empty:
        fail("No eligible wallets after activity filtering.")

    if len(eligible) < 30:
        print(
            "WARNING: Eligible population is very small "
            "for an initial unsupervised baseline."
        )

    # --------------------------------------------------------
    # 3. Raw feature selection
    # --------------------------------------------------------

    raw_selected = eligible[
        [WALLET_COLUMN] + RAW_FEATURES
    ].copy()

    raw_feature_matrix = raw_selected[RAW_FEATURES].copy()

    # --------------------------------------------------------
    # 4. Transform features
    # --------------------------------------------------------

    transformed = raw_feature_matrix.copy()

    for feature in LOG1P_FEATURES:
        if feature not in transformed.columns:
            fail(
                f"Configured transformation feature not found: "
                f"{feature}"
            )

        # Negative values were already checked, so log1p is safe.
        transformed[feature] = np.log1p(
            transformed[feature]
        )

    # Keep selected features on original scale.
    for feature in KEEP_AS_IS_FEATURES:
        if feature not in transformed.columns:
            fail(
                f"Keep-as-is feature not found: {feature}"
            )

    # Stable column order.
    transformed = transformed[RAW_FEATURES]

    if transformed.isna().any().any():
        fail("Missing values found after transformations.")

    if not np.isfinite(
        transformed.to_numpy(dtype=float)
    ).all():
        fail("Infinite values found after transformations.")

    # --------------------------------------------------------
    # 5. Output tables
    # --------------------------------------------------------

    model_features = pd.concat(
        [
            eligible[[WALLET_COLUMN]].reset_index(drop=True),
            transformed.reset_index(drop=True),
        ],
        axis=1,
    )

    raw_selected.to_csv(
        OUTPUT_DIR / "selected_features_raw.csv",
        index=False
    )

    model_features.to_csv(
        OUTPUT_DIR / "model_features.csv",
        index=False
    )

    eligible[
        [WALLET_COLUMN, ACTIVITY_COLUMN]
    ].to_csv(
        OUTPUT_DIR / "eligible_wallets.csv",
        index=False
    )

    excluded.to_csv(
        OUTPUT_DIR / "excluded_wallets.csv",
        index=False
    )

    # --------------------------------------------------------
    # 6. Reports
    # --------------------------------------------------------

    distribution = make_distribution_report(
        transformed,
        RAW_FEATURES
    )

    distribution.to_csv(
        OUTPUT_DIR / "feature_distribution.csv",
        index=False
    )

    correlations = calculate_spearman(
        transformed,
        RAW_FEATURES
    )

    correlations.to_csv(
        OUTPUT_DIR / "feature_correlation.csv",
        index=False
    )

    high_corr = correlations[
        correlations["absolute_spearman"] >= 0.90
    ].copy()

    high_corr.to_csv(
        OUTPUT_DIR / "high_correlation_pairs.csv",
        index=False
    )

    zero_counts = {
        feature: int((transformed[feature] == 0).sum())
        for feature in RAW_FEATURES
    }

    zero_rates = {
        feature: float(
            (transformed[feature] == 0).mean()
        )
        for feature in RAW_FEATURES
    }

    feature_config = {
        "wallet_column": WALLET_COLUMN,
        "activity_filter": {
            "column": ACTIVITY_COLUMN,
            "minimum_inclusive": MIN_TX_COUNT,
        },
        "selected_raw_features": RAW_FEATURES,
        "log1p_features": LOG1P_FEATURES,
        "keep_as_is_features": KEEP_AS_IS_FEATURES,
        "excluded_feature_groups": [
            "incoming_transfer_count",
            "outgoing_transfer_count",
            "outgoing_ratio",
            "transfer_per_active_day",
            "asset-specific volume and count features",
            "collection/audit metadata",
        ],
        "transformations": {
            "log1p": LOG1P_FEATURES,
            "no_scaling": True,
            "no_clipping": True,
        },
        "note": (
            "This configuration is a baseline experiment, not a "
            "final feature set. Fit and inference must use the same "
            "feature order and transformations."
        ),
    }

    save_json(
        OUTPUT_DIR / "feature_metadata.json",
        feature_config
    )

    report = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "input_file": str(INPUT_FILE),
        "output_dir": str(OUTPUT_DIR),
        "total_wallets": int(len(df)),
        "eligible_wallets": int(len(eligible)),
        "excluded_wallets": int(len(excluded)),
        "minimum_tx_count": MIN_TX_COUNT,
        "selected_feature_count": int(len(RAW_FEATURES)),
        "selected_features": RAW_FEATURES,
        "log1p_features": LOG1P_FEATURES,
        "keep_as_is_features": KEEP_AS_IS_FEATURES,
        "high_correlation_pairs_threshold": 0.90,
        "high_correlation_pairs_count": int(
            len(high_corr)
        ),
        "zero_counts_after_transform": zero_counts,
        "zero_rates_after_transform": zero_rates,
        "outputs": [
            "model_features.csv",
            "selected_features_raw.csv",
            "eligible_wallets.csv",
            "excluded_wallets.csv",
            "feature_metadata.json",
            "preparation_report.json",
            "feature_distribution.csv",
            "feature_correlation.csv",
            "high_correlation_pairs.csv",
        ],
    }

    save_json(
        OUTPUT_DIR / "preparation_report.json",
        report
    )

    # --------------------------------------------------------
    # 7. Console summary
    # --------------------------------------------------------

    print("\nFEATURE PREPARATION SUMMARY")
    print("-" * 70)

    print(f"Eligible wallets: {len(eligible)}")
    print(f"Excluded wallets: {len(excluded)}")
    print(f"Features: {len(RAW_FEATURES)}")
    print(f"Log1p transformed: {len(LOG1P_FEATURES)}")
    print(f"Kept as-is: {len(KEEP_AS_IS_FEATURES)}")

    print(
        "High correlation pairs "
        "(|Spearman| >= 0.90): "
        f"{len(high_corr)}"
    )

    print("\nSelected features:")

    for feature in RAW_FEATURES:
        transformation = (
            "log1p"
            if feature in LOG1P_FEATURES
            else "unchanged"
        )

        print(f"  - {feature}: {transformation}")

    print("\nHigh correlation pairs:")

    if high_corr.empty:
        print("  None at threshold >= 0.90")
    else:
        print(high_corr.to_string(index=False))

    print("\nOutput files:")

    for filename in report["outputs"]:
        print(f"  - {OUTPUT_DIR / filename}")

    print("\n" + "=" * 70)
    print("PREPARATION COMPLETE")
    print("=" * 70)

    print(
        "No model was trained. Dataset is prepared "
        "for baseline review."
    )


if __name__ == "__main__":
    main()

