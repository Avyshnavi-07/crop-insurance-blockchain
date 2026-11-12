"""
Shared Utilities, Plotting Configurations, and Secondary Reference Metrics for Experiments.

Provides:
- Dataset loader with data status metadata.
- Step 0 Ground Truth secondary references:
  * Continuous Mean Deficit Index (CMDI): mean of rainfall, NDVI, and soil deficits.
  * Standardized Composite Deficit Score (SCDS): mean of z-scores.
  * Continuous Proxy Loss Fraction: continuous linear mapping in [0, 1].
- Consensus evaluation matching CropInsurance.sol.
- Colorblind-safe plotting configuration (300 DPI, labeled units).
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "dataset.csv"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Colorblind-friendly palette (Okabe-Ito / Wong)
CB_PALETTE = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "cyan": "#56B4E9",
    "yellow": "#F0E442",
    "dark": "#333333",
    "gray": "#7F7F7F",
}


def setup_matplotlib_style():
    """Configures scientific publication style for figures."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.35,
        "grid.linestyle": "--",
    })


def load_experiment_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """
    Loads dataset.csv and computes Step 0 secondary severity references.
    """
    if not path.exists():
        raise FileNotFoundError(f"Processed dataset not found at {path}. Run build_dataset.py first.")

    df = pd.read_csv(path)

    # Step 0 Secondary References (Independent of tier_rules.json cutoffs):
    # 1. Continuous Mean Deficit Index (CMDI)
    df["cmdi_mean_deficit_pct"] = (
        df["rainfall_deficit_pct"] + df["ndvi_deficit_pct"] + df["soil_deficit_pct"]
    ) / 3.0

    # 2. Standardized Composite Deficit Score (Z-scores per metric across the 24 scenarios)
    for col in ["rainfall_deficit_pct", "ndvi_deficit_pct", "soil_deficit_pct"]:
        mean = df[col].mean()
        std = df[col].std()
        df[f"{col}_zscore"] = (df[col] - mean) / (std if std > 0 else 1.0)

    df["scds_zscore"] = (
        df["rainfall_deficit_pct_zscore"]
        + df["ndvi_deficit_pct_zscore"]
        + df["soil_deficit_pct_zscore"]
    ) / 3.0

    # 3. Continuous Proxy Loss Fraction in [0.0, 1.0]
    # Continuous linear ramp: 0% deficit -> 0.0 loss; 60% deficit -> 1.0 full loss
    # (60% matches the catastrophic tier cutoff, but mapped as a smooth linear continuum)
    df["proxy_loss_fraction"] = np.clip(df["cmdi_mean_deficit_pct"] / 60.0, 0.0, 1.0)

    # 4. Rank-based severity order (0 = least severe, 23 = most severe)
    df["severity_rank"] = df["cmdi_mean_deficit_pct"].rank(method="min", ascending=True).astype(int) - 1

    return df


def get_metadata(seed: int) -> Dict[str, str]:
    """Generates provenance metadata for output CSVs."""
    return {
        "random_seed": str(seed),
        "data_scope": "24 district-years (Anantapur, Kurnool, Kadapa; 2017-2024)",
        "weather_data_status": "Open-Meteo ERA5-Land (LIVE_API)",
        "satellite_data_status": "Sentinel-2 MSI Level-2A (CACHED_BENCHMARK_FALLBACK)",
        "soil_data_status": "NASA-USDA SMAP ~9km (CACHED_BENCHMARK_FALLBACK)",
        "ground_truth_audit": "label column is NaN; primary reference is consensus_tier; secondary is CMDI",
    }


def evaluate_python_consensus(
    tier_w: Optional[int], tier_sat: Optional[int], tier_soil: Optional[int]
) -> Tuple[Optional[int], str]:
    """
    Evaluates 2-of-3 consensus matching CropInsurance.sol logic exactly.
    """
    reports = [t for t in [tier_w, tier_sat, tier_soil] if t is not None]
    if len(reports) < 2:
        return None, "AWAITING_REPORTS"
    if len(reports) == 2:
        if reports[0] == reports[1]:
            return reports[0], "TWO_MATCH"
        return None, "DISAGREEMENT_WAIT_THIRD"

    w, sat, soil = reports[0], reports[1], reports[2]
    if w == sat and sat == soil:
        return w, "ALL_THREE_AGREE"
    if w == sat or w == soil:
        return w, "TWO_OF_THREE_AGREE"
    if sat == soil:
        return sat, "TWO_OF_THREE_AGREE"

    sorted_tiers = sorted([w, sat, soil])
    return sorted_tiers[1], "THREE_DIFFER_MEDIAN"


def tier_to_payout_pct(tier: Optional[int]) -> float:
    """Returns parametric payout percentage for severity tier (0, 25, 50, 100)."""
    mapping = {0: 0.0, 1: 25.0, 2: 50.0, 3: 100.0}
    return mapping.get(tier, 0.0)
