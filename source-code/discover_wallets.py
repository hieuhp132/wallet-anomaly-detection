import random
import time
import requests

from pathlib import Path
from dotenv import load_dotenv
import os


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

RPC_URL = os.getenv("ALCHEMY_API_URL")

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DISCOVERED_FILE = OUTPUT_DIR / "discovered_addresses.json"
EOA_FILE = OUTPUT_DIR / "eoa_candidates.json"
SELECTED_FILE = OUTPUT_DIR / "selected_wallets.json"

LOOKBACK_DAYS = 30
BLOCK_TIME_SECONDS = 12

# Sample one block every N blocks
BLOCK_STEP = 100

# JSON-RPC batch size
BATCH_SIZE = 5

TARGET_EOA_COUNT = 300

# Keep reproducible selection
RANDOM_SEED = 42

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Rate limiting
REQUEST_DELAY = 1.0
MAX_RETRIES = 8

session = requests.Session()


# ============================================================
# RPC HELPERS
# ============================================================


def rpc_batch(payloads):
    """
    Send JSON-RPC batch with retry and rate-limit handling.
    """

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = session.post(
                RPC_URL,
                json=payloads,
                timeout=120
            )

            # Handle rate limiting
            if response.status_code == 429:

                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    try:
                        wait_seconds = float(retry_after)
                    except ValueError:
                        wait_seconds = min(2 ** attempt, 60)
                else:
                    wait_seconds = min(2 ** attempt, 60)

                if attempt == MAX_RETRIES:
                    raise RuntimeError(
                        "Alchemy rate limit persisted after "
                        f"{MAX_RETRIES} attempts."
                    )

                print(
                    f"HTTP 429 - Rate limited. "
                    f"Retrying in {wait_seconds:.1f}s "
                    f"({attempt}/{MAX_RETRIES})"
                )

                time.sleep(wait_seconds)
                continue

            # Retry temporary server errors
            if response.status_code in (500, 502, 503, 504):

                if attempt == MAX_RETRIES:
                    response.raise_for_status()

                wait_seconds = min(2 ** attempt, 60)

                print(
                    f"HTTP {response.status_code}. "
                    f"Retrying in {wait_seconds}s"
                )

                time.sleep(wait_seconds)
                continue

            response.raise_for_status()

            data = response.json()

            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                raise RuntimeError(
                    "Unexpected JSON-RPC batch response"
                )

            return {
                item.get("id"): item
                for item in data
                if isinstance(item, dict)
            }

        except requests.exceptions.RequestException as error:

            if attempt == MAX_RETRIES:
                raise

            wait_seconds = min(2 ** attempt, 60)

            print(
                f"Network error: {error}. "
                f"Retrying in {wait_seconds}s"
            )

            time.sleep(wait_seconds)

    raise RuntimeError("RPC batch failed.")


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def get_latest_block():
    response = session.post(
        RPC_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_blockNumber",
            "params": []
        },
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return int(data["result"], 16)


# ============================================================
# DISCOVER TRANSACTION ADDRESSES
# ============================================================

def discover_addresses():

    latest_block = get_latest_block()

    blocks_per_day = int(
        24 * 60 * 60 / BLOCK_TIME_SECONDS
    )

    lookback_blocks = LOOKBACK_DAYS * blocks_per_day

    from_block = max(0, latest_block - lookback_blocks)

    block_numbers = list(
        range(from_block, latest_block + 1, BLOCK_STEP)
    )

    if not block_numbers or block_numbers[-1] != latest_block:
        block_numbers.append(latest_block)

    print("=" * 60)
    print("ETHEREUM ADDRESS DISCOVERY")
    print("=" * 60)

    print(f"Latest block: {latest_block}")
    print(f"From block:   {from_block}")
    print(f"To block:     {latest_block}")
    print(f"Blocks sampled: {len(block_numbers)}")

    address_stats = {}

    for batch_index, block_batch in enumerate(
        batched(block_numbers, BATCH_SIZE),
        start=1
    ):

        payloads = []

        for request_id, block_number in enumerate(block_batch, start=1):
            payloads.append({
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "eth_getBlockByNumber",
                "params": [
                    hex(block_number),
                    True
                ]
            })

        results = rpc_batch(payloads)

        for request_id in range(1, len(block_batch) + 1):

            result = results.get(request_id)

            if not result:
                continue

            if "error" in result:
                continue

            block = result.get("result")

            if not block:
                continue

            for tx in block.get("transactions", []):

                if not isinstance(tx, dict):
                    continue

                sender = tx.get("from")
                receiver = tx.get("to")

                for address in [sender, receiver]:

                    if not address:
                        continue

                    address = address.lower()

                    if address == ZERO_ADDRESS:
                        continue

                    if address not in address_stats:
                        address_stats[address] = {
                            "sampled_tx_count": 0,
                            "first_seen_block": block["number"],
                            "last_seen_block": block["number"]
                        }

                    address_stats[address]["sampled_tx_count"] += 1
                    address_stats[address]["last_seen_block"] = block["number"]

        print(
            f"Processed batch {batch_index} "
            f"({min(batch_index * BATCH_SIZE, len(block_numbers))}"
            f"/{len(block_numbers)} sampled blocks)"
        )

        # Save progress after each batch
        discovered = [
            {
                "wallet": address,
                **stats
            }
            for address, stats in address_stats.items()
        ]

        discovered.sort(
            key=lambda item: item["sampled_tx_count"],
            reverse=True
        )

        with open(
            DISCOVERED_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(discovered, f, indent=2)

        time.sleep(0.1)

    discovered = [
        {
            "wallet": address,
            **stats
        }
        for address, stats in address_stats.items()
    ]

    discovered.sort(
        key=lambda item: item["sampled_tx_count"],
        reverse=True
    )

    with open(DISCOVERED_FILE, "w", encoding="utf-8") as f:
        json.dump(discovered, f, indent=2)

    print(f"\nUnique discovered addresses: {len(discovered)}")
    print(f"Saved: {DISCOVERED_FILE}")

    return discovered


# ============================================================
# CLASSIFY EOA / SMART CONTRACT
# ============================================================

def classify_addresses(discovered):

    print("\nClassifying addresses using eth_getCode...")

    eoa_candidates = []
    classified_count = 0

    addresses = [
        item["wallet"]
        for item in discovered
    ]

    for batch_index, address_batch in enumerate(
        batched(addresses, BATCH_SIZE),
        start=1
    ):

        payloads = []

        for request_id, address in enumerate(address_batch, start=1):
            payloads.append({
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "eth_getCode",
                "params": [
                    address,
                    "latest"
                ]
            })

        results = rpc_batch(payloads)

        for request_id, address in enumerate(address_batch, start=1):

            result = results.get(request_id)

            if not result or "error" in result:
                continue

            code = result.get("result")

            if not isinstance(code, str):
                continue

            code_size = max(0, (len(code) - 2) // 2)

            original = discovered[
                next(
                    i for i, item in enumerate(discovered)
                    if item["wallet"] == address
                )
            ]

            classified_count += 1

            if code.lower() == "0x":
                eoa_candidates.append({
                    **original,
                    "address_type": "eoa",
                    "code_size_bytes": 0
                })

        print(
            f"Classified batch {batch_index}: "
            f"{classified_count}/{len(addresses)}"
        )

        time.sleep(0.1)

    eoa_candidates.sort(
        key=lambda item: item["sampled_tx_count"],
        reverse=True
    )

    with open(EOA_FILE, "w", encoding="utf-8") as f:
        json.dump(eoa_candidates, f, indent=2)

    print(f"\nEOA candidates: {len(eoa_candidates)}")
    print(f"Saved: {EOA_FILE}")

    return eoa_candidates


# ============================================================
# SELECT TARGET WALLETS
# ============================================================

def select_wallets(eoa_candidates):

    if len(eoa_candidates) < TARGET_EOA_COUNT:
        raise RuntimeError(
            f"Only found {len(eoa_candidates)} EOA candidates. "
            f"Need {TARGET_EOA_COUNT}. "
            "Increase the block discovery range or reduce BLOCK_STEP."
        )

    # Random selection among discovered EOA candidates.
    # This avoids selecting only the most active wallets.
    rng = random.Random(RANDOM_SEED)

    selected = rng.sample(
        eoa_candidates,
        TARGET_EOA_COUNT
    )

    selected.sort(
        key=lambda item: item["sampled_tx_count"],
        reverse=True
    )

    for index, item in enumerate(selected, start=1):
        item["selection_id"] = index

    with open(SELECTED_FILE, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2)

    print("\n" + "=" * 60)
    print("WALLET SELECTION")
    print("=" * 60)

    print(f"Target wallets: {TARGET_EOA_COUNT}")
    print(f"Selected wallets: {len(selected)}")
    print(f"Saved: {SELECTED_FILE}")

    print("\nTop 10 selected wallets:")

    for item in selected[:10]:
        print(
            item["wallet"],
            "sampled_tx_count=",
            item["sampled_tx_count"]
        )


# ============================================================
# MAIN
# ============================================================

def main():

    if not RPC_URL:
        raise RuntimeError(
            "ALCHEMY_API_URL is missing from .env"
        )

    discovered = discover_addresses()

    eoa_candidates = classify_addresses(discovered)

    select_wallets(eoa_candidates)


if __name__ == "__main__":
    main()

