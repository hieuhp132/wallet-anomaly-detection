# Model Evaluation

## Available evidence

The saved run uses an Isolation Forest with 300 estimators, `max_samples="auto"`, `contamination=0.05`, `max_features=1.0`, no bootstrap, and `random_state=42`. The prepared dataset has 117 wallets and 11 input features.

| Saved-run measure | Result |
| --- | ---: |
| Predicted anomalies | 6 |
| Predicted normal wallets | 111 |
| Observed anomaly fraction | 5.13% |
| Configured contamination | 5% |

The score file ranks larger `anomaly_score` values as more unusual. In scikit-learn terms, the raw `score_samples` values are negated for this presentation; `predict == -1` denotes an anomaly and `predict == 1` denotes normal.

## Feature ablation

The saved ablation CSV compares the baseline against four retrained variants, each omitting one feature group: volume, network, asset, or temporal. Each variant contains 117 wallet predictions and flags 6 anomalies. The top-15 ranking overlap with the baseline is:

| Variant | Shared wallets in top 15 |
| --- | ---: |
| Without volume | 13 / 15 |
| Without network | 12 / 15 |
| Without asset | 13 / 15 |
| Without temporal | 11 / 15 |

This suggests some ranking stability under these specific feature removals, but does not demonstrate predictive accuracy. The experiment is small, unsupervised, and does not provide external validation.

## Interpretation and limitations

- There are no ground-truth labels; precision, recall, ROC-AUC, and calibration cannot be assessed.
- Contamination is a model setting, not an empirically established fraud rate.
- Scores and ranks are relative to the 117 eligible wallets and may change with a different sample or feature set.
- `feature_deviation_analysis.csv` gives percentile and median comparisons. It is not a model-native feature-attribution method and does not establish why a wallet is anomalous.
- An anomaly must not be presented as evidence of fraud.

## Suggested validation

Before operational use, review cases with domain experts, gather reliable labels, evaluate temporal and sampling stability, and compare the baseline against simple rule-based and alternative unsupervised approaches. Tune thresholds using the intended review capacity and validated outcomes rather than assuming the configured contamination is a risk prevalence.
