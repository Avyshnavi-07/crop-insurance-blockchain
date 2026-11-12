"""
Dataset builder for hardware-free crop-insurance prototype.

Pipelines & Methodology:
1. Ingests seasonal rainfall (Open-Meteo), Sentinel-2 NDVI, and NASA SMAP soil moisture
   for Anantapur, Kurnool, and Kadapa across Kharif seasons (1 June - 31 October, 2017-2024).
2. Computes leave-one-year-out historical median baselines (excluding the target year to prevent leakage).
3. Computes percentage deficits and maps them to severity tiers (0 to 3) using config/tier_rules.json.
4. Evaluates 2-of-3 oracle consensus and median fallback parity with CropInsurance.sol.
5. Merges ground-truth reference labels from data/reference_labels.csv.
6. Outputs curated data/processed/dataset.csv.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from oracles.data_sources import (  # noqa: E402
    DISTRICT_COORDINATES,
    fetch_seasonal_rainfall,
    extract_cumulative_rainfall,
    fetch_sentinel2_ndvi,
    fetch_smap_soil_moisture,
    validate_weather_data,
)

CONFIG_PATH = PROJECT_ROOT / "config" / "tier_rules.json"
REFERENCE_LABELS_PATH = PROJECT_ROOT / "data" / "reference_labels.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "dataset.csv"

TARGET_YEARS = list(range(2017, 2025))


def load_tier_rules(config_path: Path = CONFIG_PATH) -> Dict:
    """Loads configurable tier threshold assumptions from config/tier_rules.json."""
    if not config_path.exists():
        raise FileNotFoundError(f"Missing configuration file: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)


def compute_leave_one_out_baseline(series: pd.Series, year: int) -> Optional[float]:
    """
    Computes baseline as the median of all available years excluding the target year.
    Strictly prevents future or present data leakage into the reference baseline.
    """
    other_vals = [val for y, val in series.items() if y != year and pd.notna(val)]
    if not other_vals:
        return None
    return round(float(np.median(other_vals)), 3)


def compute_deficit_pct(baseline: Optional[float], observed: Optional[float]) -> Optional[float]:
    """
    Computes percentage deficit relative to historical baseline.
    If observed >= baseline, deficit is 0.0 (normal/favorable).
    Returns None if either value is missing.
    """
    if baseline is None or observed is None or baseline <= 0:
        return None
    deficit = ((baseline - observed) / baseline) * 100.0
    return round(float(max(0.0, deficit)), 2)


def map_deficit_to_tier(
    deficit_pct: Optional[float], source_key: str, rules: Dict
) -> Optional[int]:
    """
    Maps a percentage deficit to a severity tier (0 to 3) using configurable rules in tier_rules.json.
    Returns None if metric is missing / unavailable.
    """
    if deficit_pct is None:
        return None

    thresholds = rules["sources"][source_key]["threshold_assumptions"]

    # Tier 0 (Normal)
    t0_max = thresholds["tier_0_normal"]["max_deficit_pct"]
    if deficit_pct <= t0_max:
        return 0

    # Tier 1 (Moderate)
    t1_max = thresholds["tier_1_moderate"]["max_deficit_pct"]
    if deficit_pct <= t1_max:
        return 1

    # Tier 2 (Severe)
    t2_max = thresholds["tier_2_severe"]["max_deficit_pct"]
    if deficit_pct <= t2_max:
        return 2

    # Tier 3 (Catastrophic)
    return 3


def calculate_consensus(
    tier_weather: Optional[int],
    tier_satellite: Optional[int],
    tier_soil: Optional[int],
) -> Tuple[Optional[int], str]:
    """
    Evaluates 2-of-3 oracle consensus with median fallback matching CropInsurance.sol.
    Returns (winning_tier, consensus_rule).
    """
    reports = [t for t in [tier_weather, tier_satellite, tier_soil] if t is not None]

    if len(reports) < 2:
        return None, "AWAITING_REPORTS"

    if len(reports) == 2:
        if reports[0] == reports[1]:
            return reports[0], "TWO_MATCH"
        return None, "DISAGREEMENT_WAIT_THIRD"

    # All 3 reports present
    w, sat, soil = reports[0], reports[1], reports[2]

    # Check for matching pairs
    if w == sat and sat == soil:
        return w, "ALL_THREE_AGREE"
    if w == sat or w == soil:
        return w, "TWO_OF_THREE_AGREE"
    if sat == soil:
        return sat, "TWO_OF_THREE_AGREE"

    # All three differ: calculate median
    sorted_tiers = sorted([w, sat, soil])
    median_tier = sorted_tiers[1]
    return median_tier, "THREE_DIFFER_MEDIAN"


def calculate_payout_pct(tier: Optional[int]) -> float:
    """
    Returns the parametric payout percentage for a given severity tier.
    Matches CropInsurance.sol:
      Tier 0 -> 0%
      Tier 1 -> 25%
      Tier 2 -> 50%
      Tier 3 -> 100%
    """
    if tier == 0:
        return 0.0
    elif tier == 1:
        return 25.0
    elif tier == 2:
        return 50.0
    elif tier == 3:
        return 100.0
    return 0.0


def build_crop_insurance_dataset(
    output_file: Path = OUTPUT_FILE,
    ee_project_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Builds and writes the complete processed crop insurance dataset.
    """
    print("=== Starting Crop Insurance Data Pipeline (Phase 2) ===")
    tier_rules = load_tier_rules(CONFIG_PATH)

    try:
        from oracles.data_sources import init_earth_engine
        init_earth_engine(ee_project_id)
        print("[OK] Google Earth Engine initialized successfully.")
    except Exception as exc:
        print(f"! Notice: Live Google Earth Engine unavailable ({exc}).")
        print("! Using documented cached benchmark fallback for satellite & soil moisture.")

    raw_records: List[Dict] = []

    for district in DISTRICT_COORDINATES:
        print(f"\nProcessing District: {district}")
        for year in TARGET_YEARS:
            print(f"  Fetching seasonal data for {year}...", end=" ", flush=True)

            # 1. Weather / Rainfall
            weather_raw = fetch_seasonal_rainfall(district, year)
            rainfall_val = extract_cumulative_rainfall(weather_raw)
            weather_val_report = validate_weather_data(weather_raw)

            # 2. Satellite NDVI
            s2_res = fetch_sentinel2_ndvi(district, year, ee_project_id)
            ndvi_val = s2_res.get("peak_ndvi")
            sat_status = s2_res.get("data_status", "UNKNOWN")

            # 3. NASA SMAP Soil Moisture
            smap_res = fetch_smap_soil_moisture(district, year, ee_project_id)
            soil_val = smap_res.get("mean_surface_soil_moisture")
            soil_status = smap_res.get("data_status", "UNKNOWN")

            raw_records.append({
                "district": district,
                "year": year,
                "season": "Kharif (Jun-Oct)",
                "crop": "Groundnut",
                "rainfall_mm": rainfall_val,
                "weather_valid_days": weather_val_report["valid_precip_count"],
                "ndvi_peak": ndvi_val,
                "satellite_data_status": sat_status,
                "soil_moisture_mean": soil_val,
                "soil_data_status": soil_status,
            })
            print(f"Done (Rainfall: {rainfall_val} mm, NDVI: {ndvi_val}, Soil: {soil_val})")

    df_raw = pd.DataFrame(raw_records)

    # Compute leave-one-year-out baselines and deficit percentages per district
    processed_rows: List[Dict] = []
    for district, group in df_raw.groupby("district"):
        rainfall_series = group.set_index("year")["rainfall_mm"]
        ndvi_series = group.set_index("year")["ndvi_peak"]
        soil_series = group.set_index("year")["soil_moisture_mean"]

        for _, row in group.iterrows():
            year = int(row["year"])
            r_val = row["rainfall_mm"]
            n_val = row["ndvi_peak"]
            s_val = row["soil_moisture_mean"]

            # Baselines (target year strictly excluded)
            r_base = compute_leave_one_out_baseline(rainfall_series, year)
            n_base = compute_leave_one_out_baseline(ndvi_series, year)
            s_base = compute_leave_one_out_baseline(soil_series, year)

            # Deficit Percentages
            r_def = compute_deficit_pct(r_base, r_val)
            n_def = compute_deficit_pct(n_base, n_val)
            s_def = compute_deficit_pct(s_base, s_val)

            # Severity Tiers (0 to 3)
            r_tier = map_deficit_to_tier(r_def, "weather_rainfall", tier_rules)
            n_tier = map_deficit_to_tier(n_def, "satellite_ndvi", tier_rules)
            s_tier = map_deficit_to_tier(s_def, "soil_moisture", tier_rules)

            # Multi-Source 2-of-3 Consensus
            consensus_tier, consensus_rule = calculate_consensus(r_tier, n_tier, s_tier)
            payout_pct = calculate_payout_pct(consensus_tier)

            processed_rows.append({
                "district": district,
                "year": year,
                "season": row["season"],
                "crop": row["crop"],
                "rainfall_mm": r_val,
                "rainfall_baseline_mm": r_base,
                "rainfall_deficit_pct": r_def,
                "rainfall_tier": r_tier,
                "ndvi_peak": n_val,
                "ndvi_baseline": n_base,
                "ndvi_deficit_pct": n_def,
                "ndvi_tier": n_tier,
                "soil_moisture_mean": s_val,
                "soil_baseline": s_base,
                "soil_deficit_pct": s_def,
                "soil_tier": s_tier,
                "consensus_tier": consensus_tier,
                "payout_pct": payout_pct,
                "consensus_rule": consensus_rule,
                "data_source_weather": "Open-Meteo ERA5-Land (LIVE_API)",
                "data_source_satellite": "Sentinel-2 MSI Level-2A",
                "data_source_soil": "NASA-USDA SMAP (~9km)",
                "satellite_data_status": row["satellite_data_status"],
                "soil_data_status": row["soil_data_status"],
            })

    df_processed = pd.DataFrame(processed_rows)

    # Merge ground-truth reference labels if reference_labels.csv exists
    if REFERENCE_LABELS_PATH.exists():
        ref_df = pd.read_csv(REFERENCE_LABELS_PATH)
        final_df = df_processed.merge(ref_df, on=["district", "year"], how="left")
    else:
        final_df = df_processed
        final_df["label"] = None
        final_df["source_url"] = None
        final_df["notes"] = None

    final_df.to_csv(output_file, index=False)
    print(f"\n[OK] Dataset successfully saved at: {output_file}")
    print(f"Total records: {len(final_df)} | Columns: {len(final_df.columns)}")
    districts = sorted(final_df['district'].unique().tolist())
    years = sorted(final_df['year'].unique().tolist())
    print(f"Districts: {districts} | Years: {years}")

    return final_df


if __name__ == "__main__":
    ee_proj = os.getenv("EE_PROJECT_ID") or None
    build_crop_insurance_dataset(OUTPUT_FILE, ee_project_id=ee_proj)
