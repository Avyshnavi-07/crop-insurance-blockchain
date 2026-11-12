"""
Comprehensive Evaluation Suite for Crop Insurance Fraud Detection Models.

Evaluates:
- Heuristic Rule Engine
- Isolation Forest (Unsupervised)
- MLP Autoencoder (Reconstruction)

Metrics:
- Precision, Recall, F1, ROC-AUC
- Confusion Matrix (TP, FP, TN, FN)
- Per-fraud-type Recall (duplicate boundary, out of district, anomalous claim, inflated valuation)
- Inference latency in ms/record (mean +/- std)
- 5-seed statistical aggregation saved to results/fraud_metrics.csv and results/fraud_per_type.csv
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from fraud.autoencoder_model import AutoencoderDetector  # noqa: E402
from fraud.generate_fraud_data import (  # noqa: E402
    extract_features,
    generate_synthetic_fraud_dataset,
    split_fraud_dataset,
)
from fraud.isolation_forest_model import IsolationForestDetector  # noqa: E402
from fraud.rule_engine import HeuristicRuleEngine  # noqa: E402
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FRAUD_TYPES = [
    "duplicate_boundary",
    "out_of_district",
    "anomalous_claim_pattern",
    "inflated_sum_insured",
]


def measure_inference_latency(model, X_test, raw_df_test=None, n_repeats: int = 25) -> Tuple[float, float]:
    """
    Measures inference latency in milliseconds per record over repeated runs.
    Returns (mean_latency_ms, std_latency_ms).
    """
    latencies = []
    n_samples = len(X_test)

    for _ in range(n_repeats):
        t0 = time.perf_counter()
        if isinstance(model, HeuristicRuleEngine):
            _ = model.predict(raw_df_test)
        else:
            _ = model.predict(X_test)
        elapsed = time.perf_counter() - t0
        latency_per_record = (elapsed * 1000.0) / n_samples
        latencies.append(latency_per_record)

    return float(np.mean(latencies)), float(np.std(latencies))


def evaluate_single_seed(seed: int) -> Tuple[List[Dict], List[Dict]]:
    """
    Executes end-to-end data generation, model fitting, and test evaluation for one seed.
    Returns (overall_metrics_records, per_type_records).
    """
    # 1. Generate dataset
    df = generate_synthetic_fraud_dataset(n_samples=3200, fraud_rate=0.09, seed=seed)
    train_df, val_df, test_df = split_fraud_dataset(df, seed=seed)

    X_train = extract_features(train_df)
    y_train = train_df["is_fraud"].values

    X_val = extract_features(val_df)
    y_val = val_df["is_fraud"].values

    X_test = extract_features(test_df)
    y_test = test_df["is_fraud"].values
    test_fraud_types = test_df["fraud_type"].values

    # 2. Instantiate and train models
    rule_engine = HeuristicRuleEngine().fit(train_df)

    iso_forest = IsolationForestDetector(random_state=seed)
    iso_forest.fit(X_train=X_train, y_train=None, X_val=X_val, y_val=y_val)

    autoencoder = AutoencoderDetector(random_state=seed)
    autoencoder.fit(X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val)

    models = [
        ("Heuristic Rule Engine", rule_engine),
        ("Isolation Forest", iso_forest),
        ("MLP Autoencoder", autoencoder),
    ]

    seed_overall_results = []
    seed_per_type_results = []

    for name, model in models:
        # Predictions
        if isinstance(model, HeuristicRuleEngine):
            y_pred = model.predict(test_df)
            y_score = y_pred.astype(float)  # Binary score for rules
        elif isinstance(model, IsolationForestDetector):
            y_pred = model.predict(X_test)
            y_score = -model.decision_function(X_test)
        else:  # AutoencoderDetector
            y_pred = model.predict(X_test)
            y_score = model.decision_function(X_test)

        # Standard metrics
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_score)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

        lat_mean, lat_std = measure_inference_latency(model, X_test, raw_df_test=test_df)

        seed_overall_results.append({
            "seed": seed,
            "model": name,
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1),
            "roc_auc": float(auc),
            "true_positive": int(tp),
            "false_positive": int(fp),
            "true_negative": int(tn),
            "false_negative": int(fn),
            "latency_ms_record": float(lat_mean),
            "latency_std_record": float(lat_std),
        })

        # Per-fraud-type recall
        for ftype in FRAUD_TYPES:
            mask = (test_fraud_types == ftype)
            if np.sum(mask) > 0:
                type_rec = np.sum((y_pred == 1) & mask) / np.sum(mask)
            else:
                type_rec = 0.0

            seed_per_type_results.append({
                "seed": seed,
                "model": name,
                "fraud_type": ftype,
                "recall": float(type_rec),
            })

    return seed_overall_results, seed_per_type_results


def run_multi_seed_evaluation(seeds: List[int] = [42, 43, 44, 45, 46]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes evaluation across multiple random seeds and aggregates statistical mean +/- std.
    """
    all_overall = []
    all_per_type = []

    print(f"Evaluating models across {len(seeds)} random seeds: {seeds}...")
    for s in seeds:
        print(f"  -> Running seed {s}...")
        ov, pt = evaluate_single_seed(s)
        all_overall.extend(ov)
        all_per_type.extend(pt)

    df_overall = pd.DataFrame(all_overall)
    df_per_type = pd.DataFrame(all_per_type)

    # Aggregate overall metrics
    agg_metrics = df_overall.groupby("model").agg(
        precision_mean=("precision", "mean"),
        precision_std=("precision", "std"),
        recall_mean=("recall", "mean"),
        recall_std=("recall", "std"),
        f1_mean=("f1_score", "mean"),
        f1_std=("f1_score", "std"),
        roc_auc_mean=("roc_auc", "mean"),
        roc_auc_std=("roc_auc", "std"),
        tp_mean=("true_positive", "mean"),
        fp_mean=("false_positive", "mean"),
        tn_mean=("true_negative", "mean"),
        fn_mean=("false_negative", "mean"),
        latency_ms_mean=("latency_ms_record", "mean"),
        latency_ms_std=("latency_ms_record", "std"),
    ).reset_index()

    # Aggregate per-type recall
    agg_per_type = df_per_type.groupby(["model", "fraud_type"]).agg(
        recall_mean=("recall", "mean"),
        recall_std=("recall", "std"),
    ).reset_index()

    # Save to results/
    metrics_file = RESULTS_DIR / "fraud_metrics.csv"
    per_type_file = RESULTS_DIR / "fraud_per_type.csv"

    agg_metrics.to_csv(metrics_file, index=False)
    agg_per_type.to_csv(per_type_file, index=False)

    print(f"\n[OK] Results saved to:\n  - {metrics_file}\n  - {per_type_file}")
    return agg_metrics, agg_per_type


if __name__ == "__main__":
    metrics_summary, per_type_summary = run_multi_seed_evaluation()

    print("\n" + "=" * 80)
    print("OVERALL FRAUD DETECTION EVALUATION METRICS (5-SEED MEAN +/- STD)")
    print("=" * 80)
    for _, row in metrics_summary.iterrows():
        print(f"\nModel: {row['model']}")
        print(f"  Precision: {row['precision_mean']:.4f} +/- {row['precision_std']:.4f}")
        print(f"  Recall:    {row['recall_mean']:.4f} +/- {row['recall_std']:.4f}")
        print(f"  F1-Score:  {row['f1_mean']:.4f} +/- {row['f1_std']:.4f}")
        print(f"  ROC-AUC:   {row['roc_auc_mean']:.4f} +/- {row['roc_auc_std']:.4f}")
        print(f"  Latency:   {row['latency_ms_mean']:.3f} +/- {row['latency_ms_std']:.3f} ms/record")

    print("\n" + "=" * 80)
    print("PER-FRAUD-TYPE RECALL BREAKDOWN")
    print("=" * 80)
    print(per_type_summary.to_string(index=False))
