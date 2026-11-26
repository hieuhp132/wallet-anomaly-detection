
import json
from pathlib import Path
from collections import defaultdict, Counter

RAW_FILE = Path("data/raw_transfers.json")
SELECTED_FILE = Path("data/selected_wallets.json")

TARGET_HASHES = {
    "0x9d61b33447240b42b9313323819059d452950abdbe628fdb6d3c694a6e247bc8",
    "0xe17bf0030cb4c29003a6cc10f0da278aa1556f2f4e3118c3f3915a801189c8d7",
    "0xce29046fc59af7a1acca5cad4a7a14c620e5e09fca563fd0cd5cb4a570582230",
    "0xaa1eea00812423b5eba1f09bc49642cbccd8fb80f56b80f911d11ce724a9792c",
    "0x629bc3a93e87baa4b7f8172d1c81a37b5f4c155a2432ff1fc5cea8a19a2bc116",
    "0x4fce0788a4223d9dfc018df5d2ac59868cafcf99c16d8de1d03c5a004bf15c3f",
    "0xce81a256b9f315b72bb66e1ff8d9ac9ea4d2d94d20c51e8e3b8040114cadfe36",
}


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    wallets_data = load_json(SELECTED_FILE)

    if isinstance(wallets_data, dict):
        wallets_data = wallets_data.get(
            "wallets",
            wallets_data.get("selected_wallets", [])
        )

    wallets = set()

    for item in wallets_data:
        if isinstance(item, str):
            wallets.add(item.lower())
        elif isinstance(item, dict):
            address = item.get("wallet") or item.get("address")
            if address:
                wallets.add(address.lower())

    raw_data = load_json(RAW_FILE)

    if isinstance(raw_data, dict):
        raw_data = raw_data.get("transfers", [])

    conflicts = defaultdict(list)
    self_by_wallet = defaultdict(list)

    for transfer in raw_data:
        sender = (transfer.get("from") or "").lower()
        receiver = (transfer.get("to") or "").lower()
        tx_hash = (transfer.get("hash") or "").lower()

        if sender not in wallets and receiver not in wallets:
            continue

        metadata = transfer.get("metadata") or {}

        if tx_hash in TARGET_HASHES:
            conflicts[tx_hash].append({
                "timestamp": metadata.get("blockTimestamp"),
                "block_num": transfer.get("blockNum"),
                "from": sender,
                "to": receiver,
                "asset": transfer.get("asset"),
                "category": transfer.get("category"),
                "unique_id": transfer.get("uniqueId"),
            })

        if sender and sender == receiver:
            self_by_wallet[sender].append({
                "hash": tx_hash,
                "asset": transfer.get("asset"),
                "category": transfer.get("category"),
                "timestamp": metadata.get("blockTimestamp"),
                "block_num": transfer.get("blockNum"),
                "unique_id": transfer.get("uniqueId"),
            })

    print("=" * 80)
    print("TIMESTAMP AND BLOCK NUMBER CONFLICTS")
    print("=" * 80)

    for tx_hash, records in conflicts.items():
        print("\nHASH:", tx_hash)

        for record in records:
            print(record)

        block_numbers = {
            str(record["block_num"])
            for record in records
        }

        print("Distinct block numbers:", block_numbers)

    print("\n" + "=" * 80)
    print("SELF-TRANSFER SUMMARY BY WALLET")
    print("=" * 80)

    total = 0

    for wallet, records in sorted(
        self_by_wallet.items(),
        key=lambda item: len(item[1]),
        reverse=True
    ):
        total += len(records)

        assets = Counter(
            str(record["asset"])
            for record in records
        )

        categories = Counter(
            str(record["category"])
            for record in records
        )

        print("\nWallet:", wallet)
        print("Records:", len(records))
        print("Unique hashes:", len({
            record["hash"] for record in records
        }))
        print("Assets:", dict(assets))
        print("Categories:", dict(categories))

    print("\nTotal self-transfer records:", total)
    print("Wallets with self-transfers:", len(self_by_wallet))


if __name__ == "__main__":
    main()

