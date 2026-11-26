
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

RAW_FILE = Path("data/raw_transfers.json")
SELECTED_FILE = Path("data/selected_wallets.json")


def load_json(path, default):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_wallets():
    data = load_json(SELECTED_FILE, [])

    if isinstance(data, dict):
        data = data.get(
            "wallets",
            data.get("selected_wallets", [])
        )

    wallets = set()

    for item in data:
        if isinstance(item, str):
            wallets.add(item.lower())
        elif isinstance(item, dict):
            address = item.get("wallet") or item.get("address")
            if address:
                wallets.add(address.lower())

    return wallets


def parse_timestamp(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        # Chuẩn hóa timestamp không có timezone về UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.timestamp()

    except (ValueError, TypeError, AttributeError):
        return None


def main():
    wallets = load_wallets()
    raw_data = load_json(RAW_FILE, [])

    if isinstance(raw_data, dict):
        raw_data = raw_data.get("transfers", [])

    hash_records = defaultdict(list)
    self_transfers = []

    for transfer in raw_data:
        sender = (transfer.get("from") or "").lower()
        receiver = (transfer.get("to") or "").lower()

        if sender not in wallets and receiver not in wallets:
            continue

        tx_hash = (transfer.get("hash") or "").lower()

        if not tx_hash:
            continue

        metadata = transfer.get("metadata") or {}
        raw_timestamp = metadata.get("blockTimestamp")
        epoch = parse_timestamp(raw_timestamp)

        hash_records[tx_hash].append({
            "timestamp_raw": raw_timestamp,
            "timestamp_epoch": epoch,
            "from": sender,
            "to": receiver,
            "asset": transfer.get("asset"),
            "category": transfer.get("category"),
            "unique_id": transfer.get("uniqueId"),
            "log_index": transfer.get("logIndex"),
        })

        if sender and sender == receiver:
            self_transfers.append({
                "hash": tx_hash,
                "wallet": sender,
                "timestamp": raw_timestamp,
                "asset": transfer.get("asset"),
                "category": transfer.get("category"),
                "unique_id": transfer.get("uniqueId"),
                "log_index": transfer.get("logIndex"),
            })

    print("=" * 80)
    print("TRANSACTION HASH TIMESTAMP INVESTIGATION")
    print("=" * 80)

    raw_string_conflicts = 0
    actual_time_conflicts = 0

    for tx_hash, records in hash_records.items():
        raw_values = {
            r["timestamp_raw"]
            for r in records
            if r["timestamp_raw"] is not None
        }

        epoch_values = {
            r["timestamp_epoch"]
            for r in records
            if r["timestamp_epoch"] is not None
        }

        if len(raw_values) > 1:
            raw_string_conflicts += 1

            print("\nHash:", tx_hash)
            print("Records:", len(records))
            print("Raw timestamp variants:")

            for value in sorted(raw_values):
                print("  ", value)

            print("Normalized UTC timestamps:")

            for value in sorted(epoch_values):
                dt = datetime.fromtimestamp(
                    value,
                    timezone.utc
                )
                print("  ", dt.isoformat())

            if len(epoch_values) > 1:
                actual_time_conflicts += 1
                print("STATUS: ACTUAL TIMESTAMP CONFLICT")
            else:
                print("STATUS: SAME INSTANT, DIFFERENT STRING FORMAT")

            print("Record details:")

            for record in records:
                print(
                    " ",
                    {
                        "asset": record["asset"],
                        "category": record["category"],
                        "log_index": record["log_index"],
                        "unique_id": record["unique_id"],
                    }
                )

    print("\nRaw string conflicts:", raw_string_conflicts)
    print("Actual timestamp conflicts:", actual_time_conflicts)

    print("\n" + "=" * 80)
    print("SELF-TRANSFER INVESTIGATION")
    print("=" * 80)

    print("Self-transfer records:", len(self_transfers))
    print(
        "Unique self-transfer hashes:",
        len({r["hash"] for r in self_transfers})
    )

    for record in self_transfers[:20]:
        print(record)


if __name__ == "__main__":
    main()

