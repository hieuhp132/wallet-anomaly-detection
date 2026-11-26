
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

SELECTED_FILE = DATA_DIR / "selected_wallets.json"
RAW_FILE = DATA_DIR / "raw_transfers.json"
REPORT_FILE = DATA_DIR / "collection_report.json"
OUTPUT_FILE = DATA_DIR / "wallet_features.csv"

TRACKED_ASSETS = [
    "ETH",
    "WETH",
    "USDC",
    "USDT",
    "DAI",
    "WBTC",
    "USDE",
    "UNI",
    "AAVE",
]


# ============================================================
# HELPERS
# ============================================================

def load_json(path, default=None):
    if not path.exists():
        return default

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_selected_wallets():
    data = load_json(SELECTED_FILE, [])

    if isinstance(data, dict):
        if "wallets" in data:
            data = data["wallets"]
        elif "selected_wallets" in data:
            data = data["selected_wallets"]

    wallets = []

    for item in data:
        if isinstance(item, str):
            wallets.append(item.lower())

        elif isinstance(item, dict):
            address = (
                item.get("wallet")
                or item.get("address")
            )

            if address:
                wallets.append(address.lower())

    return wallets


def parse_timestamp(transfer):
    metadata = transfer.get("metadata") or {}

    timestamp = metadata.get("blockTimestamp")

    if not timestamp:
        return None

    try:
        dt = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

        return dt.timestamp()

    except (ValueError, TypeError):
        return None


def parse_block_number(transfer):
    value = transfer.get("blockNum")

    if not value:
        return None

    try:
        if isinstance(value, str):
            return int(value, 16)

        return int(value)

    except (ValueError, TypeError):
        return None


def parse_value(transfer):
    value = transfer.get("value")

    try:
        if value is None:
            return 0.0

        value = float(value)

        if not math.isfinite(value):
            return 0.0

        return max(value, 0.0)

    except (ValueError, TypeError):
        return 0.0


def get_asset_identity(transfer):
    category = (
        transfer.get("category") or ""
    ).lower()

    asset = (
        transfer.get("asset") or "UNKNOWN"
    ).strip().upper()

    raw_contract = (
        transfer.get("rawContract") or {}
    )

    contract_address = (
        raw_contract.get("address") or ""
    ).lower()

    # ETH transfers do not have a token contract.
    if category == "external":
        return "ETH"

    if contract_address:
        return f"{asset}:{contract_address}"

    return f"{asset}:UNKNOWN"


def get_transfer_id(transfer):
    unique_id = transfer.get("uniqueId")

    if unique_id:
        return unique_id

    return "|".join([
        str(transfer.get("hash", "")),
        str(transfer.get("logIndex", "")),
        str(transfer.get("from", "")),
        str(transfer.get("to", "")),
        str(transfer.get("value", "")),
        str(transfer.get("asset", "")),
    ])


def safe_ratio(numerator, denominator):
    if denominator == 0:
        return 0.0

    return numerator / denominator


# ============================================================
# LOAD DATA
# ============================================================

def main():
    wallets = load_selected_wallets()

    raw_data = load_json(RAW_FILE, [])

    if isinstance(raw_data, dict):
        raw_data = raw_data.get("transfers", [])

    report = load_json(REPORT_FILE, {})

    if not isinstance(report, dict):
        report = {}

    wallet_reports = report.get("wallets", {})

    wallets = list(dict.fromkeys(wallets))

    wallet_set = set(wallets)

    print("=" * 60)
    print("BUILD WALLET FEATURES - DATASET V2")
    print("=" * 60)

    print("Selected wallets:", len(wallets))
    print("Raw transfers:", len(raw_data))


    # ========================================================
    # DEDUP RAW TRANSFERS
    # ========================================================

    transfer_map = {}

    for transfer in raw_data:
        transfer_map[
            get_transfer_id(transfer)
        ] = transfer

    raw_data = list(transfer_map.values())

    print(
        "Unique transfer records:",
        len(raw_data),
    )


    # ========================================================
    # INITIALIZE WALLET DATA
    # ========================================================

    stats = {}

    for wallet in wallets:
        stats[wallet] = {
            "timestamps": set(),
            "blocks": set(),
            "hashes": set(),
            "incoming_hashes": set(),
            "outgoing_hashes": set(),
            "incoming_transfers": set(),
            "outgoing_transfers": set(),
            "counterparties": set(),
            "assets": set(),
            "asset_in_volume": defaultdict(float),
            "asset_out_volume": defaultdict(float),
            "asset_in_transfer_count": defaultdict(int),
            "asset_out_transfer_count": defaultdict(int),
            "incoming_value_total": 0.0,
            "outgoing_value_total": 0.0,
            "incoming_records": 0,
            "outgoing_records": 0,
            "categories": set(),
        }


    # ========================================================
    # PROCESS TRANSFERS
    # ========================================================

    for transfer in raw_data:
        sender = (
            transfer.get("from") or ""
        ).lower()

        receiver = (
            transfer.get("to") or ""
        ).lower()

        tx_hash = transfer.get("hash")

        if not tx_hash:
            continue

        tx_hash = tx_hash.lower()

        timestamp = parse_timestamp(transfer)

        block_number = parse_block_number(transfer)

        transfer_key = get_transfer_id(transfer)

        value = parse_value(transfer)

        category = (
            transfer.get("category") or "unknown"
        ).lower()

        asset_identity = get_asset_identity(
            transfer
        )

        asset_symbol = (
            transfer.get("asset") or "UNKNOWN"
        ).strip().upper()

        if category == "external":
            asset_symbol = "ETH"

        # --------------------------------------------
        # Incoming
        # --------------------------------------------

        if receiver in wallet_set:
            wallet_stats = stats[receiver]

            wallet_stats["hashes"].add(tx_hash)

            wallet_stats["incoming_hashes"].add(
                tx_hash
            )

            wallet_stats["incoming_transfers"].add(
                transfer_key
            )

            wallet_stats["incoming_records"] += 1

            wallet_stats["incoming_value_total"] += value

            wallet_stats["assets"].add(
                asset_identity
            )

            wallet_stats["categories"].add(
                category
            )

            wallet_stats[
                "asset_in_volume"
            ][asset_identity] += value

            wallet_stats[
                "asset_in_transfer_count"
            ][asset_identity] += 1

            if sender and sender != receiver:
                wallet_stats[
                    "counterparties"
                ].add(sender)

            if timestamp is not None:
                wallet_stats["timestamps"].add(
                    timestamp
                )

            if block_number is not None:
                wallet_stats["blocks"].add(
                    block_number
                )


        # --------------------------------------------
        # Outgoing
        # --------------------------------------------

        if sender in wallet_set:
            wallet_stats = stats[sender]

            wallet_stats["hashes"].add(tx_hash)

            wallet_stats["outgoing_hashes"].add(
                tx_hash
            )

            wallet_stats["outgoing_transfers"].add(
                transfer_key
            )

            wallet_stats["outgoing_records"] += 1

            wallet_stats["outgoing_value_total"] += value

            wallet_stats["assets"].add(
                asset_identity
            )

            wallet_stats["categories"].add(
                category
            )

            wallet_stats[
                "asset_out_volume"
            ][asset_identity] += value

            wallet_stats[
                "asset_out_transfer_count"
            ][asset_identity] += 1

            if receiver and receiver != sender:
                wallet_stats[
                    "counterparties"
                ].add(receiver)

            if timestamp is not None:
                wallet_stats["timestamps"].add(
                    timestamp
                )

            if block_number is not None:
                wallet_stats["blocks"].add(
                    block_number
                )


    # ========================================================
    # BUILD FEATURES
    # ========================================================

    rows = []

    for wallet in wallets:
        wallet_stats = stats[wallet]

        timestamps = sorted(
            wallet_stats["timestamps"]
        )

        tx_count = len(
            wallet_stats["hashes"]
        )

        incoming_tx_count = len(
            wallet_stats["incoming_hashes"]
        )

        outgoing_tx_count = len(
            wallet_stats["outgoing_hashes"]
        )

        transfer_count = (
            len(wallet_stats["incoming_transfers"])
            + len(wallet_stats["outgoing_transfers"])
        )

        incoming_transfer_count = len(
            wallet_stats["incoming_transfers"]
        )

        outgoing_transfer_count = len(
            wallet_stats["outgoing_transfers"]
        )

        counterparties = len(
            wallet_stats["counterparties"]
        )

        assets = len(
            wallet_stats["assets"]
        )

        active_days_set = set()

        for ts in timestamps:
            dt = datetime.fromtimestamp(
                ts,
                timezone.utc,
            )

            active_days_set.add(
                dt.strftime("%Y-%m-%d")
            )

        active_days = len(
            active_days_set
        )

        if timestamps:
            active_span_hours = (
                timestamps[-1] - timestamps[0]
            ) / 3600

        else:
            active_span_hours = 0.0

        intervals_minutes = []

        if len(timestamps) >= 2:
            intervals_minutes = [
                (timestamps[i] - timestamps[i - 1])
                / 60
                for i in range(1, len(timestamps))
            ]

        if intervals_minutes:
            avg_interval_minutes = (
                statistics.mean(intervals_minutes)
            )

            median_interval_minutes = (
                statistics.median(intervals_minutes)
            )

        else:
            avg_interval_minutes = 0.0
            median_interval_minutes = 0.0

        incoming_ratio = safe_ratio(
            incoming_transfer_count,
            transfer_count,
        )

        outgoing_ratio = safe_ratio(
            outgoing_transfer_count,
            transfer_count,
        )

        tx_per_active_day = safe_ratio(
            tx_count,
            active_days,
        )

        transfer_per_active_day = safe_ratio(
            transfer_count,
            active_days,
        )

        collection_info = (
            wallet_reports.get(wallet, {})
        )

        collection_complete = bool(
            collection_info.get(
                "collection_complete",
                False,
            )
        )

        row = {
            "wallet": wallet,

            "tx_count": tx_count,

            "transfer_count": transfer_count,

            "incoming_tx_count": incoming_tx_count,

            "outgoing_tx_count": outgoing_tx_count,

            "incoming_transfer_count": incoming_transfer_count,

            "outgoing_transfer_count": outgoing_transfer_count,

            "incoming_ratio": incoming_ratio,

            "outgoing_ratio": outgoing_ratio,

            "unique_counterparties": counterparties,

            "unique_assets": assets,

            "active_days": active_days,

            "tx_per_active_day": tx_per_active_day,

            "transfer_per_active_day": transfer_per_active_day,

            "active_span_hours": active_span_hours,

            "avg_interval_minutes": avg_interval_minutes,

            "median_interval_minutes": median_interval_minutes,

            "incoming_value_total": (
                wallet_stats["incoming_value_total"]
            ),

            "outgoing_value_total": (
                wallet_stats["outgoing_value_total"]
            ),

            "collection_complete": (
                collection_complete
            ),

            "raw_incoming_records": (
                wallet_stats["incoming_records"]
            ),

            "raw_outgoing_records": (
                wallet_stats["outgoing_records"]
            ),
        }


        # ----------------------------------------------------
        # Asset-specific features
        # ----------------------------------------------------

        for asset in TRACKED_ASSETS:
            row[
                f"{asset.lower()}_incoming_volume"
            ] = 0.0

            row[
                f"{asset.lower()}_outgoing_volume"
            ] = 0.0

            row[
                f"{asset.lower()}_incoming_count"
            ] = 0

            row[
                f"{asset.lower()}_outgoing_count"
            ] = 0

            for identity, volume in (
                wallet_stats["asset_in_volume"].items()
            ):
                symbol = identity.split(":")[0]

                if symbol == asset:
                    row[
                        f"{asset.lower()}_incoming_volume"
                    ] += volume

            for identity, volume in (
                wallet_stats["asset_out_volume"].items()
            ):
                symbol = identity.split(":")[0]

                if symbol == asset:
                    row[
                        f"{asset.lower()}_outgoing_volume"
                    ] += volume

            for identity, count in (
                wallet_stats[
                    "asset_in_transfer_count"
                ].items()
            ):
                symbol = identity.split(":")[0]

                if symbol == asset:
                    row[
                        f"{asset.lower()}_incoming_count"
                    ] += count

            for identity, count in (
                wallet_stats[
                    "asset_out_transfer_count"
                ].items()
            ):
                symbol = identity.split(":")[0]

                if symbol == asset:
                    row[
                        f"{asset.lower()}_outgoing_count"
                    ] += count


        # ----------------------------------------------------
        # Collection audit features
        # ----------------------------------------------------

        row["collection_error"] = (
            collection_info.get("error")
        )

        row["outgoing_complete"] = (
            collection_info.get(
                "outgoing_complete",
                False,
            )
        )

        row["incoming_complete"] = (
            collection_info.get(
                "incoming_complete",
                False,
            )
        )

        row["outgoing_pages"] = (
            collection_info.get(
                "outgoing_pages",
                0,
            )
        )

        row["incoming_pages"] = (
            collection_info.get(
                "incoming_pages",
                0,
            )
        )

        rows.append(row)


    # ========================================================
    # EXPORT
    # ========================================================

    df = pd.DataFrame(rows)

    df = df.sort_values(
        "tx_count",
        ascending=False,
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 60)
    print("FEATURE BUILD SUMMARY")
    print("=" * 60)

    print("Wallets:", len(df))

    print(
        "Wallets with transactions:",
        int((df["tx_count"] > 0).sum()),
    )

    print(
        "Wallets with >= 5 transactions:",
        int((df["tx_count"] >= 5).sum()),
    )

    print(
        "Wallets with >= 20 transactions:",
        int((df["tx_count"] >= 20).sum()),
    )

    print(
        "Wallets with >= 100 transactions:",
        int((df["tx_count"] >= 100).sum()),
    )

    print(
        "Complete wallets:",
        int(df["collection_complete"].sum()),
    )

    print(
        "Total unique transactions:",
        int(df["tx_count"].sum()),
    )

    print(
        "Total transfer records:",
        int(df["transfer_count"].sum()),
    )

    print(
        "Output:",
        OUTPUT_FILE,
    )

    print("\nTop 10 wallets by transaction count:")

    print(
        df[
            [
                "wallet",
                "tx_count",
                "transfer_count",
                "unique_counterparties",
                "active_days",
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()

