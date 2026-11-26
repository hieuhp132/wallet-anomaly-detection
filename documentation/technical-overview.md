# Technical Overview

## Goal

Build a reproducible wallet-level behavioral baseline that surfaces unusual activity for investigation. The system reports relative anomalies; it does not decide whether a wallet is fraudulent.

## Pipeline

1. **Discover wallets** — [`discover_wallets.py`](../source-code/discover_wallets.py) samples Ethereum blocks, extracts observed addresses, classifies candidate EOAs, and selects a reproducible target sample.
2. **Collect transfer history** — [`collect_eoa_history.py`](../source-code/collect_eoa_history.py) collects external, internal, and ERC-20 transfers for selected wallets and records collection status.
3. **Build wallet features** — [`build_features.py`](../source-code/build_features.py) deduplicates transfer records and aggregates transaction, counterparty, asset, volume, and timing behavior.
4. **Audit and prepare** — scripts in [`audit_scripts/`](../source-code/audit_scripts/) inspect raw data and engineered features. [`prepare_dataset.py`](../source-code/prepare_dataset.py) filters low-activity wallets, selects 11 features, applies configured transforms, and writes model inputs and preparation reports.
5. **Train and analyze** — [`train_isolation_forest.py`](../source-code/train_isolation_forest.py) fits Baseline A and saves scores, model configuration, and descriptive feature deviations. [`feature_ablation.py`](../source-code/feature_ablation.py) compares saved feature-group variants.

## Current saved snapshot

The collection report records 300 selected wallets and 54,624 unique transfers over a 30-day lookback. Preparation retained 117 wallets with at least 20 transactions and selected 11 features. Baseline A flagged 6 wallets as anomalous.

The serialized estimator and its configuration are in [`model-artifacts/`](../model-artifacts/). Saved rankings, preparation metrics, feature correlations, and ablation outputs are in [`analysis-results/`](../analysis-results/). Raw inputs and supporting audit reports remain local and are excluded from the public repository.

## Dependencies and configuration

Python dependencies are listed in [`requirements.txt`](../requirements.txt). Wallet discovery and collection require Alchemy configuration through environment variables; credentials must remain local and must not be committed.

## Portfolio layout and execution caveat

The scripts are grouped under `source-code/` for presentation. Their existing path constants were intentionally left unchanged. Consequently, this reorganization does not guarantee that the scripts will locate their original inputs and outputs if run from the new layout. Saved artifacts document the completed run; no pipeline was rerun for this portfolio reorganization. Some saved JSON reports also retain absolute paths from the original workspace.
