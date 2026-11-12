"""
Experiment E2: Oracle Source Ablation Study.

Evaluates:
- Single sources: Weather alone, Satellite alone, Soil alone.
- Pairwise combinations: Weather+Satellite, Weather+Soil, Satellite+Soil.
- Full ensemble: Weather+Satellite+Soil (2-of-3 consensus with median fallback).

Pairwise Disagreement Resolution:
- Variant A (No Consensus -> No Payout): If two sources disagree, payout is 0.0% (strict agreement).
- Variant B (Conservative Minimum Tier): If two sources disagree, winning tier is min(t1, t2).
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


def evaluate_pair(
    t1_series: pd.Series, t2_series: pd.Series, variant: str = "A"
) -> Tuple[pd.Series, pd.Series]:
    """
    Evaluates a pairwise oracle system across the dataset under Variant A or B.
    Returns (tier_series, payout_pct_series).
    """
    tiers = []
    payouts = []

    for t1, t2 in zip(t1_series, t2_series):
        if t1 == t2:
            resolved_tier = t1
            payout = tier_to_payout_pct(resolved_tier)
        else:
            if variant == "A":
                # Strict: disagreement yields no payout / no tier
                resolved_tier = None
                payout = 0.0
            else:
                # Conservative minimum tier
                resolved_tier = min(t1, t2)
                payout = tier_to_payout_pct(resolved_tier)

        tiers.append(resolved_tier)
        payouts.append(payout)

    return pd.Series(tiers), pd.Series(payouts)


def run_experiment_e2(seed: int = 42) -> Tuple[pd.DataFrame, Path, Path]:
    """
    Executes Experiment E2 and saves results/e2_ablation.csv and .png.
    """
    df = load_experiment_dataset()
    n_total = len(df)
    ref_tier = df["consensus_tier"]
    ref_payout = df["payout_pct"]
    cmdi_loss_pct = df["proxy_loss_fraction"] * 100.0
    meta = get_metadata(seed)

    records: List[Dict] = []

    # 1. Single Sources
    singles = [
        ("Weather Alone", "rainfall_tier"),
        ("Satellite Alone", "ndvi_tier"),
        ("Soil Alone", "soil_tier"),
    ]
    for name, col in singles:
        t_s = df[col]
        p_s = t_s.apply(tier_to_payout_pct)
        agree = (t_s == ref_tier).sum() / n_total * 100.0
        wrong = (p_s != ref_payout).sum() / n_total * 100.0
        mape_consensus = float(np.mean(np.abs(p_s - ref_payout)))
        mape_cmdi = float(np.mean(np.abs(p_s - cmdi_loss_pct)))
        signed_gap = float(np.mean(p_s - ref_payout))
        mean_payout = float(np.mean(p_s))

        records.append({
            "configuration": name,
            "system_type": "Single Source",
            "disagreement_variant": "N/A",
            "mape_vs_cmdi_loss_pp_headline": round(mape_cmdi, 2),
            "internal_tier_agreement_pct": round(agree, 2),
            "internal_wrong_payout_rate_pct": round(wrong, 2),
            "internal_mape_vs_consensus_pp": round(mape_consensus, 2),
            "mean_signed_payout_gap_pp": round(signed_gap, 2),
            "mean_payout_pct": round(mean_payout, 2),
            "audit_note": "Consensus is derived; CMDI error is independent.",
            **meta,
        })

    # 2. Pairwise Combinations (Weather+Satellite, Weather+Soil, Satellite+Soil)
    pairs = [
        ("Weather + Satellite", "rainfall_tier", "ndvi_tier"),
        ("Weather + Soil", "rainfall_tier", "soil_tier"),
        ("Satellite + Soil", "ndvi_tier", "soil_tier"),
    ]

    for name, c1, c2 in pairs:
        for variant in ["A", "B"]:
            var_label = "Variant A (No Payout)" if variant == "A" else "Variant B (Conservative Min)"
            t_s, p_s = evaluate_pair(df[c1], df[c2], variant=variant)

            # Agreement: check match with reference
            agree_mask = (t_s == ref_tier)
            agree = float(agree_mask.sum()) / n_total * 100.0
            wrong = float((p_s != ref_payout).sum()) / n_total * 100.0
            mape_consensus = float(np.mean(np.abs(p_s - ref_payout)))
            mape_cmdi = float(np.mean(np.abs(p_s - cmdi_loss_pct)))
            signed_gap = float(np.mean(p_s - ref_payout))
            mean_payout = float(np.mean(p_s))

            records.append({
                "configuration": name,
                "system_type": "Pairwise Ensemble",
                "disagreement_variant": var_label,
                "mape_vs_cmdi_loss_pp_headline": round(mape_cmdi, 2),
                "internal_tier_agreement_pct": round(agree, 2),
                "internal_wrong_payout_rate_pct": round(wrong, 2),
                "internal_mape_vs_consensus_pp": round(mape_consensus, 2),
                "mean_signed_payout_gap_pp": round(signed_gap, 2),
                "mean_payout_pct": round(mean_payout, 2),
                "audit_note": "Consensus is derived; CMDI error is independent.",
                **meta,
            })

    # 3. Full Ensemble (3 Oracles)
    full_payout = df["payout_pct"]
    mape_full_cmdi = float(np.mean(np.abs(full_payout - cmdi_loss_pct)))
    records.append({
        "configuration": "Weather + Satellite + Soil (Full)",
        "system_type": "3-Source Consensus",
        "disagreement_variant": "2-of-3 + Median Fallback",
        "mape_vs_cmdi_loss_pp_headline": round(mape_full_cmdi, 2),
        "internal_tier_agreement_pct": 100.0,
        "internal_wrong_payout_rate_pct": 0.0,
        "internal_mape_vs_consensus_pp": 0.0,
        "mean_signed_payout_gap_pp": 0.0,
        "mean_payout_pct": round(float(np.mean(full_payout)), 2),
        "audit_note": "Consensus is derived; CMDI error is independent.",
        **meta,
    })

    res_df = pd.DataFrame(records)
    csv_path = RESULTS_DIR / "e2_ablation.csv"
    res_df.to_csv(csv_path, index=False)

    # Plotting
    setup_matplotlib_style()
    fig, ax = plt.subplots(figsize=(10, 5.5))

    # Compare Pairwise and Full across MAPE
    pair_rows_a = res_df[res_df["disagreement_variant"] == "Variant A (No Payout)"]
    pair_rows_b = res_df[res_df["disagreement_variant"] == "Variant B (Conservative Min)"]

    configs = ["Weather + Satellite", "Weather + Soil", "Satellite + Soil"]
    mape_a = [
        pair_rows_a[pair_rows_a["configuration"] == c]["mape_vs_cmdi_loss_pp_headline"].values[0]
        for c in configs
    ]
    mape_b = [
        pair_rows_b[pair_rows_b["configuration"] == c]["mape_vs_cmdi_loss_pp_headline"].values[0]
        for c in configs
    ]

    x = np.arange(len(configs))
    width = 0.35

    rects1 = ax.bar(x - width / 2, mape_a, width, label="Variant A: Disagreement -> 0% Payout",
                    color=CB_PALETTE["red"], alpha=0.9)
    rects2 = ax.bar(x + width / 2, mape_b, width, label="Variant B: Disagreement -> Conservative Min Tier",
                    color=CB_PALETTE["blue"], alpha=0.9)

    # Add full 3-source headline reference line
    full_row = res_df[res_df["system_type"] == "3-Source Consensus"]
    full_mape = full_row["mape_vs_cmdi_loss_pp_headline"].values[0] if len(full_row) else 7.72
    ax.axhline(
        full_mape,
        color=CB_PALETTE["green"],
        linestyle="--",
        linewidth=2,
        label=f"3-Source Consensus Reference ({full_mape:.2f} pp)",
    )

    ax.set_ylabel("MAPE vs. CMDI Continuous Loss (pp)")
    ax.set_title("E2: Pairwise Ablation & Disagreement Variants vs. 3-Source Consensus")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, weight="bold")
    ax.set_ylim(0, max(max(mape_a), max(mape_b)) * 1.35 + 1.0)
    ax.legend(loc="upper right")

    for rect in rects1:
        h = rect.get_height()
        ax.annotate(f"{h:.2f} pp", xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(f"{h:.2f} pp", xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    png_path = RESULTS_DIR / "e2_ablation.png"
    plt.savefig(png_path)
    plt.close()

    return res_df, csv_path, png_path


if __name__ == "__main__":
    df, cpath, ppath = run_experiment_e2()
    print("=== Experiment E2 Results ===")
    cols = [
        "configuration", "disagreement_variant", "tier_agreement_pct",
        "mean_abs_payout_error_pp", "mean_payout_pct",
    ]
    print(df[cols].to_string(index=False))
    print(f"\nSaved CSV: {cpath}\nSaved PNG: {ppath}")
