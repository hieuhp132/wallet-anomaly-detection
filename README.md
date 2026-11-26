# Hive Network ML Portfolio

An unsupervised machine-learning baseline for surfacing unusual Ethereum wallet activity for further review. The project includes wallet discovery, transfer collection, wallet-level feature engineering, dataset quality checks, an Isolation Forest experiment, and saved analysis outputs.

> **Scope:** An anomaly is not a fraud label. Baseline A ranks wallets by how unusual their behavior is relative to this sampled dataset. The project has no ground-truth fraud labels, so its outputs are exploratory and require human review.

## Project structure

```text
documentation/
  baseline-a-case-study.md
  technical-overview.md
  data-quality-analysis.md
  feature-engineering.md
  model-evaluation.md
source-code/
  discover_wallets.py
  collect_eoa_history.py
  build_features.py
  prepare_dataset.py
  train_isolation_forest.py
  feature_ablation.py
  audit_scripts/
model-artifacts/
  model.joblib
  model_config.json
  anomaly_summary.json
analysis-results/
  anomaly_scores.csv
  top_anomaly_wallets.csv
  feature_deviation_analysis.csv
  feature_ablation_results.csv
  feature_correlation.csv
  preparation_report.json
data/                       # local-only raw inputs; excluded from Git
requirements.txt
```

The local `data/` folder contains raw inputs and supporting reports used to produce the saved outputs; it is intentionally excluded from Git because it is large and is not part of the portfolio deliverable. The local `.env` and virtual environment are also excluded.

## Documentation

- [Baseline A case study](documentation/baseline-a-case-study.md)
- [Technical overview](documentation/technical-overview.md)
- [Data quality analysis](documentation/data-quality-analysis.md)
- [Feature engineering](documentation/feature-engineering.md)
- [Model evaluation](documentation/model-evaluation.md)

## Source and results

- Pipeline scripts: [source-code/](source-code/)
- Dataset audit and inspection scripts: [source-code/audit_scripts/](source-code/audit_scripts/)
- Serialized model and run configuration: [model-artifacts/](model-artifacts/)
- Saved scores and analyses: [analysis-results/](analysis-results/)

## Evidence and reproducibility note

The documentation and portfolio artifacts were assembled from the source files and outputs already present in the workspace; the data collection, feature-building, preparation, training, and ablation pipelines were **not rerun**. The report JSON files may contain absolute paths from the original workspace. Source files were moved without editing their path constants, so their original runtime path assumptions have not been validated against this portfolio layout.

Install the declared Python dependencies with `pip install -r requirements.txt`. Data collection also depends on the appropriate Alchemy environment variables and a working API configuration; do not commit credentials.
