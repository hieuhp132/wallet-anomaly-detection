
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

SELECTED_FILE = DATA_DIR / "selected_wallets.json"
RAW_FILE = DATA_DIR / "raw_transfers.json"
REPORT_FILE = DATA_DIR / "collection_report.json"

LOOKBACK_DAYS = 30
BLOCK_TIME_SECONDS = 12

CATEGORIES = ["external", "internal", "erc20"]

MAX_COUNT = "0x3e8"  # 1000 records per page
MAX_PAGES_PER_DIRECTION = 1000

REQUEST_DELAY = 0.25
MAX_RETRIES = 8

DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()

API_KEY = os.getenv("ALCHEMY_API_KEY")

if not API_KEY:
    raise RuntimeError("ALCHEMY_API_KEY is missing in .env")

RPC_URL = f"https://eth-mainnet.g.alchemy.com/v2/{API_KEY}"

session = requests.Session()


# ============================================================
# RPC
# ============================================================

def rpc(method, params):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = session.post(
                RPC_URL,
                json=payload,
                timeout=60,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")

                try:
                    wait_time = float(retry_after)
                except (TypeError, ValueError):
                    wait_time = min(2 ** attempt, 60)

                print(
                    f"Rate limited. "
                    f"Retry in {wait_time:.1f}s..."
                )

                time.sleep(wait_time)
                continue

            if response.status_code in [500, 502, 503, 504]:
                wait_time = min(2 ** attempt, 60)

                print(
                    f"HTTP {response.status_code}. "
                    f"Retry in {wait_time}s..."
                )

                time.sleep(wait_time)
                continue

            response.raise_for_status()

            data = response.json()

            if "error" in data:
                raise RuntimeError(
                    f"RPC error: {data['error']}"
                )

            return data["result"]

        except requests.RequestException as exc:
            wait_time = min(2 ** attempt, 60)

            print(
                f"Network error: {exc}. "
                f"Retry in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"RPC failed after {MAX_RETRIES} retries: {method}"
    )


# ============================================================
# BLOCK RANGE
# ============================================================

def get_block_range():
    latest_block = int(
        rpc("eth_blockNumber", []),
        16,
    )

    blocks_per_day = (
        24 * 60 * 60 // BLOCK_TIME_SECONDS
    )

    lookback_blocks = (
        LOOKBACK_DAYS * blocks_per_day
    )

    from_block = max(
        0,
        latest_block - lookback_blocks,
    )

    return from_block, latest_block


# ============================================================
# TRANSFER COLLECTION
# ============================================================

def fetch_direction(
    wallet,
    direction,
    from_block,
    to_block,
):
    address_filter = {
        "fromAddress": wallet
    } if direction == "outgoing" else {
        "toAddress": wallet
    }

    params = [{
        **address_filter,
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "category": CATEGORIES,
        "withMetadata": True,
        "excludeZeroValue": False,
        "maxCount": MAX_COUNT,
    }]

    transfers = []
    page_key = None
    page_count = 0

    while True:
        if page_key:
            params[0]["pageKey"] = page_key
        else:
            params[0].pop("pageKey", None)

        result = rpc(
            "alchemy_getAssetTransfers",
            params,
        )

        current = result.get("transfers", [])

        transfers.extend(current)
        page_count += 1

        page_key = result.get("pageKey")

        print(
            f"    {direction}: "
            f"page {page_count}, "
            f"{len(current)} records"
        )

        if not page_key:
            return transfers, True, page_count

        if page_count >= MAX_PAGES_PER_DIRECTION:
            print(
                "    WARNING: page limit reached"
            )

            return transfers, False, page_count

        time.sleep(REQUEST_DELAY)


# ============================================================
# DATA HELPERS
# ============================================================

def transfer_id(transfer):
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


def save_json(path, data):
    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(
        temp_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temp_path.replace(path)


def load_json(path, default):
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

    if not wallets:
        raise RuntimeError(
            "No wallets found in selected_wallets.json"
        )

    return wallets


# ============================================================
# MAIN
# ============================================================

def main():
    wallets = load_selected_wallets()

    from_block, to_block = get_block_range()

    print("=" * 60)
    print("EOA HISTORY COLLECTION - DATASET V2")
    print("=" * 60)

    print("Wallets:", len(wallets))
    print("From block:", from_block)
    print("To block:", to_block)
    print("Categories:", CATEGORIES)

    raw_data = load_json(RAW_FILE, [])

    # Support either old list or new dictionary format
    if isinstance(raw_data, dict):
        raw_data = raw_data.get("transfers", [])

    report = load_json(REPORT_FILE, {})

    if not isinstance(report, dict):
        report = {}

    report.setdefault("wallets", {})

    # Index raw data by transfer ID
    transfer_map = {}

    for item in raw_data:
        transfer_map[transfer_id(item)] = item

    total_wallets = len(wallets)

    for index, wallet in enumerate(wallets, start=1):
        wallet = wallet.lower()

        existing = report["wallets"].get(wallet, {})

        if (
            existing.get("collection_complete")
            and existing.get("from_block") == from_block
            and existing.get("to_block") == to_block
        ):
            print(
                f"[{index}/{total_wallets}] "
                f"SKIP {wallet} - already complete"
            )

            continue

        print(
            f"\n[{index}/{total_wallets}] "
            f"Collecting {wallet}"
        )

        outgoing = []
        incoming = []

        outgoing_complete = False
        incoming_complete = False

        outgoing_pages = 0
        incoming_pages = 0

        try:
            outgoing, outgoing_complete, outgoing_pages = (
                fetch_direction(
                    wallet,
                    "outgoing",
                    from_block,
                    to_block,
                )
            )

            incoming, incoming_complete, incoming_pages = (
                fetch_direction(
                    wallet,
                    "incoming",
                    from_block,
                    to_block,
                )
            )

            wallet_transfers = {}

            for item in outgoing + incoming:
                wallet_transfers[
                    transfer_id(item)
                ] = item

            # Merge into global transfer map
            for key, item in wallet_transfers.items():
                transfer_map[key] = item

            collection_complete = (
                outgoing_complete
                and incoming_complete
            )

            report["wallets"][wallet] = {
                "wallet": wallet,
                "from_block": from_block,
                "to_block": to_block,
                "outgoing_records": len(outgoing),
                "incoming_records": len(incoming),
                "unique_transfer_records": len(
                    wallet_transfers
                ),
                "outgoing_pages": outgoing_pages,
                "incoming_pages": incoming_pages,
                "outgoing_complete": outgoing_complete,
                "incoming_complete": incoming_complete,
                "collection_complete": collection_complete,
                "error": None,
                "updated_at": time.time(),
            }

            print(
                "    Unique transfers:",
                len(wallet_transfers),
            )

            print(
                "    Complete:",
                collection_complete,
            )

        except Exception as exc:
            print(
                "    ERROR:",
                str(exc),
            )

            report["wallets"][wallet] = {
                "wallet": wallet,
                "from_block": from_block,
                "to_block": to_block,
                "collection_complete": False,
                "error": str(exc),
                "updated_at": time.time(),
            }

        # Save after every wallet
        save_json(
            RAW_FILE,
            list(transfer_map.values()),
        )

        report["metadata"] = {
            "source": "Alchemy",
            "network": "Ethereum Mainnet",
            "lookback_days": LOOKBACK_DAYS,
            "from_block": from_block,
            "to_block": to_block,
            "categories": CATEGORIES,
            "target_wallets": total_wallets,
            "unique_transfer_records": len(
                transfer_map
            ),
        }

        save_json(
            REPORT_FILE,
            report,
        )

        time.sleep(REQUEST_DELAY)

    # Final summary
    wallet_reports = report["wallets"]

    complete_count = sum(
        1
        for wallet in wallets
        if wallet_reports.get(wallet, {}).get(
            "collection_complete", False
        )
    )

    incomplete_count = total_wallets - complete_count

    print("\n" + "=" * 60)
    print("COLLECTION SUMMARY")
    print("=" * 60)

    print("Target wallets:", total_wallets)
    print("Complete:", complete_count)
    print("Incomplete:", incomplete_count)
    print(
        "Unique transfer records:",
        len(transfer_map),
    )

    print("Raw file:", RAW_FILE)
    print("Report file:", REPORT_FILE)


if __name__ == "__main__":
    main()

