
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

FEATURE_FILE = DATA_DIR / "wallet_features.csv"

AUDIT_DIR = DATA_DIR / "audit"

AUDIT_DIR.mkdir(exist_ok=True)


# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(FEATURE_FILE)

print("=" * 70)
print("DATASET V2 AUDIT")
print("=" * 70)

print("Rows:", len(df))
print("Columns:", len(df.columns))


# ============================================================
# DUPLICATE WALLETS
# ============================================================

print("\n" + "=" * 70)
print("DUPLICATE WALLET AUDIT")
print("=" * 70)

duplicate_wallets = df[
    df["wallet"].duplicated(keep=False)
]

print(
    "Duplicate wallet rows:",
    len(duplicate_wallets),
)

if len(duplicate_wallets):
    duplicate_wallets.to_csv(
        AUDIT_DIR / "duplicate_wallets.csv",
        index=False,
    )


# ============================================================
# ACTIVITY DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("ACTIVITY DISTRIBUTION")
print("=" * 70)

activity_metrics = [
    "tx_count",
    "transfer_count",
    "incoming_tx_count",
    "outgoing_tx_count",
    "incoming_transfer_count",
    "outgoing_transfer_count",
    "unique_counterparties",
    "unique_assets",
    "active_days",
    "tx_per_active_day",
    "transfer_per_active_day",
    "active_span_hours",
    "avg_interval_minutes",
    "median_interval_minutes",
]

existing_metrics = [
    col
    for col in activity_metrics
    if col in df.columns
]

summary = df[
    existing_metrics
].describe(
    percentiles=[
        0.01,
        0.05,
        0.25,
        0.50,
        0.75,
        0.95,
        0.99,
    ]
).T

summary.to_csv(
    AUDIT_DIR / "feature_distribution.csv"
)

print(summary.to_string())


# ============================================================
# ACTIVITY GROUPS
# ============================================================

print("\n" + "=" * 70)
print("WALLET ACTIVITY GROUPS")
print("=" * 70)

tx = df["tx_count"]

groups = {
    "0 transactions": tx == 0,
    "1-4 transactions": tx.between(1, 4),
    "5-19 transactions": tx.between(5, 19),
    "20-99 transactions": tx.between(20, 99),
    "100-499 transactions": tx.between(100, 499),
    "500-999 transactions": tx.between(500, 999),
    "1000+ transactions": tx >= 1000,
}

group_rows = []

for name, mask in groups.items():
    count = int(mask.sum())

    percentage = (
        count / len(df) * 100
        if len(df)
        else 0
    )

    group_rows.append({
        "group": name,
        "wallet_count": count,
        "percentage": percentage,
    })

    print(
        f"{name:25} "
        f"{count:5} "
        f"({percentage:.2f}%)"
    )

group_df = pd.DataFrame(group_rows)

group_df.to_csv(
    AUDIT_DIR / "activity_groups.csv",
    index=False,
)


# ============================================================
# INSUFFICIENT ACTIVITY
# ============================================================

print("\n" + "=" * 70)
print("INSUFFICIENT ACTIVITY")
print("=" * 70)

insufficient = df[
    df["tx_count"] < 5
]

print(
    "Wallets < 5 transactions:",
    len(insufficient),
)

insufficient.to_csv(
    AUDIT_DIR / "insufficient_activity.csv",
    index=False,
)


# ============================================================
# MISSING VALUES
# ============================================================

print("\n" + "=" * 70)
print("MISSING VALUE AUDIT")
print("=" * 70)

missing = df.isna().sum()

missing_df = pd.DataFrame({
    "column": missing.index,
    "missing_count": missing.values,
    "missing_percentage": (
        missing.values / len(df) * 100
        if len(df)
        else 0
    ),
})

missing_df = missing_df.sort_values(
    "missing_count",
    ascending=False,
)

missing_df.to_csv(
    AUDIT_DIR / "missing_values.csv",
    index=False,
)

print(
    missing_df.to_string(index=False)
)


# ============================================================
# INFINITE VALUES
# ============================================================

print("\n" + "=" * 70)
print("INFINITE VALUE AUDIT")
print("=" * 70)

numeric_df = df.select_dtypes(
    include=[np.number]
)

infinite_counts = pd.Series(
    np.isinf(numeric_df).sum(),
    index=numeric_df.columns,
)

infinite_df = pd.DataFrame({
    "column": infinite_counts.index,
    "infinite_count": infinite_counts.values,
})

infinite_df = infinite_df[
    infinite_df["infinite_count"] > 0
]

infinite_df.to_csv(
    AUDIT_DIR / "infinite_values.csv",
    index=False,
)

print(
    infinite_df.to_string(index=False)
    if len(infinite_df)
    else "No infinite values found."
)


# ============================================================
# FEATURE CORRELATION
# ============================================================

print("\n" + "=" * 70)
print("FEATURE CORRELATION")
print("=" * 70)

exclude_cols = [
    "wallet",
    "collection_complete",
    "collection_error",
    "incoming_complete",
    "outgoing_complete",
    "tx_count",
    "transfer_count",
    "raw_incoming_records",
    "raw_outgoing_records",
    "incoming_pages",
    "outgoing_pages",
]

correlation_features = [
    col
    for col in numeric_df.columns
    if col not in exclude_cols
]

correlation_df = df[
    correlation_features
].corr(
    method="spearman",
)

correlation_df.to_csv(
    AUDIT_DIR / "feature_correlation.csv"
)

# Identify highly correlated feature pairs
high_corr_pairs = []

for i, col_a in enumerate(correlation_df.columns):
    for col_b in correlation_df.columns[i + 1:]:
        correlation = correlation_df.loc[
            col_a,
            col_b,
        ]

        if pd.notna(correlation) and abs(
            correlation
        ) >= 0.90:
            high_corr_pairs.append({
                "feature_a": col_a,
                "feature_b": col_b,
                "spearman_correlation": correlation,
            })

high_corr_df = pd.DataFrame(
    high_corr_pairs
)

high_corr_df.to_csv(
    AUDIT_DIR / "high_correlation_pairs.csv",
    index=False,
)

print(
    "Pairs with |Spearman correlation| >= 0.90:",
    len(high_corr_df),
)

if len(high_corr_df):
    print(
        high_corr_df.to_string(index=False)
    )


# ============================================================
# COLLECTION STATUS
# ============================================================

print("\n" + "=" * 70)
print("COLLECTION STATUS")
print("=" * 70)

if "collection_complete" in df.columns:
    print(
        "Complete:",
        int(
            df["collection_complete"].fillna(
                False
            ).astype(bool).sum()
        ),
    )

if "incoming_complete" in df.columns:
    print(
        "Incoming complete:",
        int(
            df["incoming_complete"].fillna(
                False
            ).astype(bool).sum()
        ),
    )

if "outgoing_complete" in df.columns:
    print(
        "Outgoing complete:",
        int(
            df["outgoing_complete"].fillna(
                False
            ).astype(bool).sum()
        ),
    )


# ============================================================
# TOP WALLETS
# ============================================================

print("\n" + "=" * 70)
print("TOP 20 WALLETS")
print("=" * 70)

top_wallets = df.sort_values(
    "tx_count",
    ascending=False,
).head(20)

top_wallets.to_csv(
    AUDIT_DIR / "top_wallets.csv",
    index=False,
)

display_cols = [
    "wallet",
    "tx_count",
    "transfer_count",
    "unique_counterparties",
    "unique_assets",
    "active_days",
]

display_cols = [
    col
    for col in display_cols
    if col in top_wallets.columns
]

print(
    top_wallets[
        display_cols
    ].to_string(index=False)
)


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 70)
print("AUDIT COMPLETE")
print("=" * 70)

print("Audit output:", AUDIT_DIR)

