"""
Experiment E4: Parametric Tiered Payout vs. Binary Trigger Payout Schedules.

Compares:
1. Tiered Payout (0%, 25%, 50%, 100%) as implemented in CropInsurance.sol.
2. Binary Trigger (Tier >= 1 paying 100%).
3. Binary Trigger (Tier >= 2 paying 100%).
4. Binary Trigger (Tier >= 3 paying 100%).

Evaluation Reference:
Continuous Proxy Loss Fraction derived from Step 0 Continuous Mean Deficit Index (CMDI).
Note: Labeled explicitly as an agronomic deficit proxy; not claimed as ground-truth yield loss.

Metrics:
- Basis Risk: Mean Absolute Payout Gap (|Payout - Loss|).
- Signed Payout Gap (Payout - Loss).
- Over-payment rate (Payout > Loss by > 5 pp).
- Under-payment rate (Payout < Loss by > 5 pp).
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from experiments.common import (  # noqa: E402
    CB_PALETTE,
    RESULTS_DIR,
    get_metadata,
    load_experiment_dataset,
    setup_matplotlib_style,
    tier_to_payout_pct,
)


def evaluate_payout_rule(
    payout_series: pd.Series, loss_series: pd.Series
) -> Dict[str, float]:
    """Computes basis risk, signed gap, and over/under-payment rates."""
    gaps = payout_series - loss_series
    abs_gaps = np.abs(gaps)

    mape = float(np.mean(abs_gaps))
    signed_gap = float(np.mean(gaps))

    over_rate = float(np.mean(gaps > 5.0)) * 100.0
    under_rate = float(np.mean(gaps < -5.0)) * 100.0
    mean_payout = float(np.mean(payout_series))

    return {
        "basis_risk_mape_pp": round(mape, 2),
        "signed_payout_gap_pp": round(signed_gap, 2),
        "overpayment_rate_pct": round(over_rate, 2),
        "underpayment_rate_pct": round(under_rate, 2),
        "mean_payout_pct": round(mean_payout, 2),
    }


def run_experiment_e4(seed: int = 42) -> Tuple[pd.DataFrame, Path, Path]:
    """
    Executes Experiment E4, runs sensitivity analysis across 4 CMDI loss mappings,
    and outputs results/e4_tiered_vs_binary.csv, results/e4_sensitivity_mappings.csv, and .png.
    """
    df = load_experiment_dataset()
    meta = get_metadata(seed)

    cmdi = df["cmdi_mean_deficit_pct"]
    rank = df["severity_rank"]
    n_scenarios = len(df)
    consensus_tiers = df["consensus_tier"]

    # 1. Tiered Payout (CropInsurance.sol)
    payout_tiered = consensus_tiers.apply(tier_to_payout_pct)

    # 2. Binary Trigger >= 1 (pays 100%)
    payout_bin_ge1 = (consensus_tiers >= 1).astype(float) * 100.0

    # 3. Binary Trigger >= 2 (pays 100%)
    payout_bin_ge2 = (consensus_tiers >= 2).astype(float) * 100.0

    # 4. Binary Trigger >= 3 (pays 100%)
    payout_bin_ge3 = (consensus_tiers >= 3).astype(float) * 100.0

    rules = [
        ("Tiered (0/25/50/100%) [Ours]", payout_tiered, "Multi-level parametric schedule"),
        ("Binary Trigger (Tier >= 1)", payout_bin_ge1, "Pays 100% on moderate, severe, or catastrophic"),
        ("Binary Trigger (Tier >= 2)", payout_bin_ge2, "Pays 100% on severe or catastrophic only"),
        ("Binary Trigger (Tier >= 3)", payout_bin_ge3, "Pays 100% on catastrophic only"),
    ]

    # Primary continuous proxy loss percentage: [0.0, 100.0] (Linear Cap 60%)
    ref_loss_pct = df["proxy_loss_fraction"] * 100.0

    records: List[Dict] = []
    for name, p_series, desc in rules:
        metrics = evaluate_payout_rule(p_series, ref_loss_pct)
        records.append({
            "payout_rule": name,
            "description": desc,
            **metrics,
            **meta,
        })

    res_df = pd.DataFrame(records)
    csv_path = RESULTS_DIR / "e4_tiered_vs_binary.csv"
    res_df.to_csv(csv_path, index=False)

    # Sensitivity Analysis across 4 CMDI-to-loss mappings
    loss_mappings = {
        "Linear Cap 60%": (
            np.clip(cmdi / 60.0, 0.0, 1.0) * 100.0,
            "Linear scaling with 100% loss at 60% deficit",
        ),
        "Linear Cap 45%": (
            np.clip(cmdi / 45.0, 0.0, 1.0) * 100.0,
            "Aggressive linear ramp with 100% loss at 45% deficit",
        ),
        "Rank-based Quantile": (
            (rank / (n_scenarios - 1)) * 100.0,
            "Uniform empirical quantile loss from 0% to 100%",
        ),
        "Convex Power 1.5": (
            (np.clip(cmdi / 60.0, 0.0, 1.0) ** 1.5) * 100.0,
            "Non-linear damage accelerating in severe drought",
        ),
    }

    sensitivity_records: List[Dict] = []
    for map_name, (loss_series, map_desc) in loss_mappings.items():
        for r_name, p_series, r_desc in rules:
            metrics = evaluate_payout_rule(p_series, loss_series)
            sensitivity_records.append({
                "loss_mapping": map_name,
                "mapping_description": map_desc,
                "payout_rule": r_name,
                "rule_description": r_desc,
                **metrics,
                **meta,
            })

    sens_df = pd.DataFrame(sensitivity_records)
    sens_csv_path = RESULTS_DIR / "e4_sensitivity_mappings.csv"
    sens_df.to_csv(sens_csv_path, index=False)

    # Plotting
    setup_matplotlib_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    short_names = ["Tiered (Ours)", "Binary >= 1", "Binary >= 2", "Binary >= 3"]
    basis_risks = [r["basis_risk_mape_pp"] for r in records]
    over_rates = [r["overpayment_rate_pct"] for r in records]
    under_rates = [r["underpayment_rate_pct"] for r in records]

    x = np.arange(len(short_names))

    # Subplot 1: Basis Risk MAPE
    colors = [CB_PALETTE["green"], CB_PALETTE["red"], CB_PALETTE["orange"], CB_PALETTE["purple"]]
    rects1 = ax1.bar(x, basis_risks, color=colors, alpha=0.9, width=0.55)
    ax1.set_ylabel("Basis Risk MAPE (percentage points)")
    ax1.set_title("Basis Risk Comparison (|Payout - Proxy Loss|)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(short_names, weight="bold", rotation=10)
    ax1.set_ylim(0, max(basis_risks) * 1.3)

    for rect in rects1:
        h = rect.get_height()
        ax1.annotate(f"{h:.1f} pp", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9, weight="bold")

    # Subplot 2: Over-payment vs. Under-payment rates
    width = 0.35
    r_over = ax2.bar(x - width / 2, over_rates, width, label="Over-payment Rate (%)",
                     color=CB_PALETTE["blue"], alpha=0.9)
    r_under = ax2.bar(x + width / 2, under_rates, width, label="Under-payment Rate (%)",
                      color=CB_PALETTE["red"], alpha=0.9)
    ax2.set_ylabel("Occurrence Rate (%)")
    ax2.set_title("Over-payment and Under-payment Exposure")
    ax2.set_xticks(x)
    ax2.set_xticklabels(short_names, weight="bold", rotation=10)
    ax2.set_ylim(0, 115)
    ax2.legend(loc="upper right")

    for rect in r_over:
        h = rect.get_height()
        ax2.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    for rect in r_under:
        h = rect.get_height()
        ax2.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    fig.suptitle("E4: Tiered Payout Schedule vs. Binary All-or-Nothing Triggers", fontsize=13)
    fig.tight_layout()
    png_path = RESULTS_DIR / "e4_tiered_vs_binary.png"
    plt.savefig(png_path)
    plt.close()

    return res_df, csv_path, png_path


if __name__ == "__main__":
    df, cpath, ppath = run_experiment_e4()
    print("=== Experiment E4 Results ===")
    cols = [
        "payout_rule", "basis_risk_mape_pp", "signed_payout_gap_pp",
        "overpayment_rate_pct", "underpayment_rate_pct",
    ]
    print(df[cols].to_string(index=False))
    print(f"\nSaved CSV: {cpath}\nSaved PNG: {ppath}")
