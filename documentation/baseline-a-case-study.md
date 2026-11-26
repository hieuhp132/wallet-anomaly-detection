# Baseline A: Wallet Anomaly Detection Case Study

## Problem

The project explores whether wallet-level transaction behavior can be used to prioritize wallets for manual review. There are no labeled fraud outcomes in this dataset, so this is an unsupervised anomaly-ranking experiment—not a fraud classifier.

## Data snapshot

The saved collection report describes an Ethereum Mainnet sample covering a 30-day lookback. It contains 300 selected wallets and 54,624 unique transfer records across the `external`, `internal`, and `erc20` categories. The report marks all 300 wallet collections complete.

Wallet discovery samples blocks at a fixed interval, identifies externally owned accounts, and uses a fixed random seed when selecting the target sample. This is a sampled population, not a census of Ethereum users or activity.

## Preparation

The feature table contains 300 wallet rows. Preparation applies a minimum activity threshold of 20 transactions:

| Outcome | Wallets |
| --- | ---: |
| Eligible for Baseline A | 117 |
| Excluded below the threshold | 183 |

The model uses 11 behavioral features covering transaction volume, counterparties, asset diversity, and activity timing. Nine skewed count/rate/interval features receive `log1p`; `active_days` and `active_span_hours` remain on their original scale. No scaling or clipping is applied.

## Model and outcome

Baseline A uses scikit-learn's Isolation Forest with 300 estimators, `max_samples="auto"`, contamination `0.05`, and random seed `42`. On the saved eligible dataset, it labels 6 of 117 wallets as anomalous (5.13%) and 111 as normal.

The output includes ranked anomaly scores and a feature-deviation table. The deviation table compares each feature value with the dataset median and percentile; it is descriptive context, not a model-native explanation or causal attribution.

## Interpretation

The model identifies observations that differ from this particular sample. A high score should prompt investigation of the underlying wallet history and data coverage; it does not establish malicious intent. The 5% contamination setting controls the expected outlier fraction for this run and is not a measured real-world fraud prevalence.

## Limitations and next steps

- There are no confirmed fraud labels, so precision, recall, and ROC-AUC cannot be measured.
- The eligible set is small (117 wallets) and derives from a block-sampled, activity-filtered population.
- The 20-transaction cutoff excludes most selected wallets; this changes the population the model describes.
- Follow-up work should validate against reviewed cases, expand and diversify the sample, and test feature and threshold stability before using scores operationally.

See [model evaluation](model-evaluation.md) for the saved feature-ablation evidence and [data quality analysis](data-quality-analysis.md) for collection and preparation checks.
