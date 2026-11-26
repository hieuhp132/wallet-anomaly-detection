# Data Quality Analysis

This summary is based on the saved collection report, feature audit outputs, and preparation report. No collection or audit job was rerun.

## Collection coverage

- The saved collection report covers 300 selected wallets over a 30-day Ethereum Mainnet lookback.
- It records 54,624 unique transfer records across external, internal, and ERC-20 categories.
- All 300 wallet entries are marked `collection_complete`; the report contains no recorded wallet errors.
- The collection-complete flag describes API pagination for the requested range. It does not imply that the sampled discovery process captured all chain activity.

## Feature-table checks

The saved wallet feature table has 300 rows and 63 columns. The audit outputs report:

- No infinite values.
- No missing values in the wallet or behavioral feature columns.
- The audit-only `collection_error` field is missing for all 300 rows; it is not used as a model feature.
- Strong redundancy among raw features: 36 pairs in the saved audit table have absolute Spearman correlation of at least 0.90. Examples include incoming transaction count vs. incoming transfer count, and asset-specific volume vs. count fields.

## Activity imbalance and modeling filter

The audit groups show a heavily low-activity sample: 3 wallets have zero transactions, 107 have 1–4, and 73 have 5–19. The preparation step requires `tx_count >= 20`, leaving 117 of 300 wallets and excluding 183.

On the prepared 11-feature dataset, the saved report identifies four feature pairs with absolute Spearman correlation of at least 0.90. These include transaction count vs. transfer count and average interval vs. transaction rate. The report records these pairs; it does not claim that correlated features were removed.

## Implications

1. The activity cutoff materially narrows the population and may bias conclusions toward more active wallets.
2. Feature redundancy can give related behaviors multiple representations in an isolation-based model.
3. Complete collection status should not be confused with representative sampling or complete network coverage.
4. The feature-deviation output is descriptive and should be interpreted alongside collection coverage and raw transactions.

The original audit tables and metadata remain in the local workspace and are excluded from the public repository. The selected preparation report is published in [`analysis-results/`](../analysis-results/).
