
from pathlib import Path

import json
import pandas as pd

from sklearn.ensemble import IsolationForest


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "data" / "model"
RESULTS_DIR = MODEL_DIR / "results"

INPUT_FILE = MODEL_DIR / "model_features.csv"
CONFIG_FILE = RESULTS_DIR / "model_config.json"

WALLETS = [
    "0x329ca263df30c3e506c39081403ec95d5942ece8",
    "0x5caa2b55aa4ac56d4798ed70eaf35b9b58c32cf2",
    "0x1907c554b170d355e39c9ee9ae1dbc4a7333035d",
    "0x7833341fff5bbbac5a0bd0ca28d6d9fa7d094601",
    "0x1c7566fe8fae38a93bdcb1fbf7d746fd08c11545",
    "0x5e863003264b21ad200eed95519437cc2afe76f4",
]

GROUPS = {
    "volume": [
        "tx_count",
        "incoming_tx_count",
        "outgoing_tx_count",
        "transfer_count",
        "tx_per_active_day",
    ],
    "network": [
        "unique_counterparties",
    ],
    "asset": [
        "unique_assets",
    ],
    "temporal": [
        "active_days",
        "active_span_hours",
        "avg_interval_minutes",
        "median_interval_minutes",
    ],
}


def main():
    df = pd.read_csv(INPUT_FILE)
    df["wallet"] = df["wallet"].str.lower().str.strip()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    features = config["features"]

    model_config = {
        "n_estimators": config["n_estimators"],
        "max_samples": config["max_samples"],
        "contamination": config["contamination"],
        "max_features": config["max_features"],
        "bootstrap": config["bootstrap"],
        "random_state": config["random_state"],
        "n_jobs": config["n_jobs"],
    }

    X = df[features].copy()

    variants = {
        "baseline": features,
    }

    for group_name, group_features in GROUPS.items():
        variants[f"without_{group_name}"] = [
            f for f in features if f not in group_features
        ]

    results = []
    top15_sets = {}

    for variant_name, selected_features in variants.items():
        print("\n" + "=" * 80)
        print("EXPERIMENT:", variant_name)
        print("Feature count:", len(selected_features))
        print("Features:", selected_features)

        model = IsolationForest(**model_config)
        model.fit(X[selected_features])

        # sklearn score_samples: lower = more anomalous
        raw_scores = model.score_samples(X[selected_features])
        decision_scores = model.decision_function(X[selected_features])
        predictions = model.predict(X[selected_features])

        result = pd.DataFrame({
            "wallet": df["wallet"],
            "variant": variant_name,
            "decision_score": decision_scores,
            "raw_score_samples": raw_scores,
            "anomaly_score": -raw_scores,
            "prediction": predictions,
            "is_anomaly": predictions == -1,
        })

        result["anomaly_rank"] = (
            result["anomaly_score"]
            .rank(method="first", ascending=False)
            .astype(int)
        )

        top15_sets[variant_name] = set(
            result.nsmallest(15, "anomaly_rank")["wallet"]
        )

        results.append(result)

        selected = result[result["wallet"].isin(WALLETS)].copy()
        selected = selected.sort_values("anomaly_rank")

        print("\nSix target wallets:")
        print(
            selected[
                [
                    "wallet",
                    "anomaly_rank",
                    "anomaly_score",
                    "decision_score",
                    "is_anomaly",
                ]
            ].to_string(index=False)
        )

    output = pd.concat(results, ignore_index=True)

    output_path = RESULTS_DIR / "feature_ablation_results.csv"
    output.to_csv(output_path, index=False)

    print("\n" + "=" * 80)
    print("TOP 15 OVERLAP WITH BASELINE")
    print("=" * 80)

    baseline_top15 = top15_sets["baseline"]

    for variant_name, wallet_set in top15_sets.items():
        overlap = len(baseline_top15 & wallet_set)

        print(
            f"{variant_name:22s}"
            f" overlap={overlap:2d}/15"
        )

    print("\nSaved:", output_path)


if __name__ == "__main__":
    main()

