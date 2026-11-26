
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

RAW_FILE = Path("data/raw_transfers.json")
SELECTED_FILE = Path("data/selected_wallets.json")


def load_json(path, default):
    if not path.exists():
        return default

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


def get_transfer_id(transfer):
    unique_id = transfer.get("uniqueId")

    if unique_id:
        return str(unique_id), "uniqueId"

    fallback = "|".join([
        str(transfer.get("hash", "")),
        str(transfer.get("logIndex", "")),
        str(transfer.get("from", "")),
        str(transfer.get("to", "")),
        str(transfer.get("value", "")),
        str(transfer.get("asset", "")),
    ])

    return fallback, "fallback"


def get_signature(transfer):
    metadata = transfer.get("metadata") or {}
    raw_contract = transfer.get("rawContract") or {}

    return (
        str(transfer.get("hash", "")).lower(),
        str(transfer.get("logIndex", "")),
        str(transfer.get("from", "")).lower(),
        str(transfer.get("to", "")).lower(),
        str(transfer.get("value", "")),
        str(transfer.get("asset", "")),
        str(metadata.get("blockTimestamp", "")),
        str(raw_contract.get("address", "")).lower(),
        str(transfer.get("category", "")),
    )


def main():
    wallets = load_wallets()
    raw_data = load_json(RAW_FILE, [])

    if isinstance(raw_data, dict):
        raw_data = raw_data.get("transfers", [])

    print("=" * 75)
    print("RAW DATA AUDIT")
    print("=" * 75)

    print("Selected wallets:", len(wallets))
    print("Raw records:", len(raw_data))

    relevant = 0
    missing_hash = 0
    missing_timestamp = 0
    invalid_timestamp = 0
    self_transfers = 0

    id_counts = Counter()
    id_first_signature = {}
    conflicting_ids = set()

    unique_id_count = 0
    fallback_id_count = 0

    hash_timestamps = {}
    hash_timestamp_conflicts = set()

    for transfer in raw_data:
        sender = (transfer.get("from") or "").lower()
        receiver = (transfer.get("to") or "").lower()

        if sender not in wallets and receiver not in wallets:
            continue

        relevant += 1

        tx_hash = transfer.get("hash")

        if not tx_hash:
            missing_hash += 1
            continue

        tx_hash = tx_hash.lower()

        if sender == receiver and sender in wallets:
            self_transfers += 1

        metadata = transfer.get("metadata") or {}
        timestamp = metadata.get("blockTimestamp")

        if not timestamp:
            missing_timestamp += 1
        else:
            try:
                datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
            except (ValueError, TypeError, AttributeError):
                invalid_timestamp += 1

        if timestamp:
            previous = hash_timestamps.get(tx_hash)

            if previous is None:
                hash_timestamps[tx_hash] = timestamp
            elif previous != timestamp:
                hash_timestamp_conflicts.add(tx_hash)

        transfer_id, id_type = get_transfer_id(transfer)

        if id_type == "uniqueId":
            unique_id_count += 1
        else:
            fallback_id_count += 1

        id_counts[transfer_id] += 1

        signature = get_signature(transfer)

        if transfer_id not in id_first_signature:
            id_first_signature[transfer_id] = signature
        elif id_first_signature[transfer_id] != signature:
            conflicting_ids.add(transfer_id)

    duplicate_ids = {
        key for key, count in id_counts.items()
        if count > 1
    }

    duplicate_records = sum(
        count - 1
        for count in id_counts.values()
        if count > 1
    )

    print("\n" + "=" * 75)
    print("RECORD COUNTS")
    print("=" * 75)
    print("Relevant records:", relevant)
    print("Records missing hash:", missing_hash)
    print("Records missing timestamp:", missing_timestamp)
    print("Records with invalid timestamp:", invalid_timestamp)
    print("Self-transfer records:", self_transfers)

    print("\n" + "=" * 75)
    print("TRANSFER ID AUDIT")
    print("=" * 75)
    print("Records using uniqueId:", unique_id_count)
    print("Records using fallback ID:", fallback_id_count)
    print("Unique transfer IDs:", len(id_counts))
    print("Duplicate transfer IDs:", len(duplicate_ids))
    print("Records removed by dedup (within selected wallets):", duplicate_records)
    print("IDs with conflicting content:", len(conflicting_ids))

    print("\n" + "=" * 75)
    print("TRANSACTION TIMESTAMP AUDIT")
    print("=" * 75)
    print("Unique transaction hashes:", len(hash_timestamps))
    print("Hashes with multiple timestamps:", len(hash_timestamp_conflicts))

    print("\n" + "=" * 75)
    print("TOP DUPLICATE IDS")
    print("=" * 75)

    for transfer_id, count in id_counts.most_common(10):
        if count > 1:
            print("Count:", count, "| ID:", transfer_id[:120])

    print("\n" + "=" * 75)
    print("TOP CONFLICTING IDS")
    print("=" * 75)

    for transfer_id in list(conflicting_ids)[:10]:
        print("ID:", transfer_id[:120])
        print("First signature:", id_first_signature[transfer_id])

    print("\nAudit completed.")


if __name__ == "__main__":
    main()

