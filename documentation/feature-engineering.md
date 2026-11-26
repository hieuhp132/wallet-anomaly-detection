# Feature Engineering

## From transfers to wallet behavior

[`build_features.py`](../source-code/build_features.py) reads selected wallets and collected transfer records, deduplicates transfers using the provider's unique identifier (with a fallback composite key), and aggregates activity per wallet. It parses timestamps and block numbers defensively, counts transaction hashes and transfer records separately, and tracks counterparties and assets.

The generated feature table contains 63 columns, including:

- Transaction and transfer counts, split into incoming and outgoing activity.
- Incoming/outgoing ratios and rates per active day.
- Unique counterparties and unique assets.
- Active days, activity span, and average/median inter-transaction intervals.
- Total and asset-specific incoming/outgoing values and counts.
- Collection/audit fields used to assess coverage rather than as model inputs.

The asset-specific aggregation tracks ETH, WETH, USDC, USDT, DAI, WBTC, USDE, UNI, and AAVE; token identity also incorporates the contract address when available.

## Baseline feature set

Preparation selects 11 inputs for Baseline A:

`tx_count`, `incoming_tx_count`, `outgoing_tx_count`, `transfer_count`, `unique_counterparties`, `unique_assets`, `active_days`, `active_span_hours`, `avg_interval_minutes`, `median_interval_minutes`, and `tx_per_active_day`.

The eligible population requires at least 20 transactions. Nine count, rate, or interval fields are transformed with `log1p`. `active_days` and `active_span_hours` remain unchanged. The baseline uses neither scaling nor clipping.

Asset-specific fields, collection metadata, directional transfer-record counts, `outgoing_ratio`, and `transfer_per_active_day` are excluded from model input. The wallet identifier is retained only as a row key.

## Design considerations

- Transaction hashes and transfer records are distinct concepts: one transaction may produce multiple transfer records.
- `log1p` reduces skew while preserving zero-valued observations.
- Several raw features are strongly correlated, so the current feature set is a baseline rather than a claim that each input contributes independent information.
- The exact feature order and transforms must match between training and any future inference path; the saved preparation metadata records this configuration in the local workspace.
