"""
Experiment E1: Single-Source vs. 2-of-3 Multi-Source Consensus.

Evaluates performance of individual oracle sources (Weather Rainfall, Sentinel-2 NDVI,
NASA SMAP Soil Moisture) versus 2-of-3 multi-source consensus across 24 historical district-years.

Metrics:
- Tier agreement rate with consensus reference.
- Wrong-payout rate (% of seasons with mismatched payout).
- Mean Absolute Payout Error (MAPE) in percentage points.
- Spearman rank correlation with continuous secondary reference (CMDI).
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
from scipy.stats import spearmanr  # noqa: E402

from experiments.common import (  # noqa: E402
    CB_PALETTE,
    RESULTS_DIR,
    get_metadata,
    load_experiment_dataset,
    setup_matplotlib_style,
    tier_to_payout_pct,
)


def run_experiment_e1(seed: int = 42) -> Tuple[pd.DataFrame, Path, Path]:
    """
    Executes Experiment E1 and produces results/e1_consensus_vs_single.csv and .png.
    """
    df = load_experiment_dataset()
    n_total = len(df)

    sources = [
        ("Weather Rainfall", "rainfall_tier"),
        ("Satellite NDVI", "ndvi_tier"),
        ("Soil Moisture", "soil_tier"),
        ("2-of-3 Consensus", "consensus_tier"),
    ]

    records: List[Dict] = []
    meta = get_metadata(seed)

    ref_tier = df["consensus_tier"]
    ref_payout = df["payout_pct"]
    cmdi_loss_pct = df["proxy_loss_fraction"] * 100.0

    for name, col in sources:
        tier_s = df[col]
        payout_s = tier_s.apply(tier_to_payout_pct)

        # Headline Independent Metrics (against CMDI secondary reference)
        corr, pval = spearmanr(tier_s, df["cmdi_mean_deficit_pct"])
        mape_vs_cmdi = float(np.mean(np.abs(payout_s - cmdi_loss_pct)))

        # Internal Consistency Metrics (against derived consensus_tier)
        matches = (tier_s == ref_tier).sum()
        agreement_rate = (matches / n_total) * 100.0
        payout_mismatches = (payout_s != ref_payout).sum()
        wrong_payout_rate = (payout_mismatches / n_total) * 100.0
        mape_vs_consensus = float(np.mean(np.abs(payout_s - ref_payout)))

        records.append({
            "source": name,
            "spearman_corr_cmdi_headline": round(float(corr), 4),
            "spearman_pval": round(float(pval), 5),
            "mape_vs_cmdi_loss_pp_headline": round(mape_vs_cmdi, 2),
            "internal_tier_agreement_pct": round(agreement_rate, 2),
            "internal_wrong_payout_rate_pct": round(wrong_payout_rate, 2),
            "internal_mape_vs_consensus_pp": round(mape_vs_consensus, 2),
            "audit_note": (
                "consensus_tier is derived from source tiers; agreement measures "
                "internal consistency. CMDI metrics are independent."
            ),
            **meta,
        })

    res_df = pd.DataFrame(records)
    csv_path = RESULTS_DIR / "e1_consensus_vs_single.csv"
    res_df.to_csv(csv_path, index=False)

    # Plotting: Headline Independent CMDI Correlation & Payout Error
    setup_matplotlib_style()
    fig, ax1 = plt.subplots(figsize=(8.5, 5))

    names = [r["source"] for r in records]
    corrs = [r["spearman_corr_cmdi_headline"] for r in records]
    cmdi_mapes = [r["mape_vs_cmdi_loss_pp_headline"] for r in records]

    x = np.arange(len(names))
    width = 0.35

    rects1 = ax1.bar(
        x - width / 2,
        corrs,
        width,
        label="Spearman Corr with CMDI (rs)",
        color=CB_PALETTE["blue"],
        alpha=0.9,
    )
    ax1.set_ylabel("Spearman Rank Correlation (rs)", color=CB_PALETTE["blue"])
    ax1.tick_params(axis="y", labelcolor=CB_PALETTE["blue"])
    ax1.set_ylim(0.70, 1.05)

    ax2 = ax1.twinx()
    rects2 = ax2.bar(
        x + width / 2,
        cmdi_mapes,
        width,
        label="MAPE vs. CMDI Loss (pp)",
        color=CB_PALETTE["orange"],
        alpha=0.9,
    )
    ax2.set_ylabel("Mean Abs. Payout Error vs. CMDI Loss (pp)", color=CB_PALETTE["orange"])
    ax2.tick_params(axis="y", labelcolor=CB_PALETTE["orange"])
    ax2.set_ylim(0, max(cmdi_mapes) * 1.5 if max(cmdi_mapes) > 0 else 15)
    ax2.grid(False)

    ax1.set_xticks(x)
    ax1.set_xticklabels(names, weight="bold")
    ax1.set_title("E1: Headline Metrics Against Independent CMDI Deficit Reference")

    for rect in rects1:
        h = rect.get_height()
        ax1.annotate(f"{h:.3f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)
    for rect in rects2:
        h = rect.get_height()
        ax2.annotate(f"{h:.1f} pp", xy=(rect.get_x() + rect.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    png_path = RESULTS_DIR / "e1_consensus_vs_single.png"
    plt.savefig(png_path)
    plt.close()

    return res_df, csv_path, png_path


if __name__ == "__main__":
    df, cpath, ppath = run_experiment_e1()
    print("=== Experiment E1 Results ===")
    cols = [
        "source", "spearman_corr_cmdi_headline", "mape_vs_cmdi_loss_pp_headline",
        "internal_tier_agreement_pct", "internal_wrong_payout_rate_pct"
    ]
    print(df[cols].to_string(index=False))
    print(f"\nSaved CSV: {cpath}\nSaved PNG: {ppath}")
