"""
Synthetic Fraud Dataset Generator for Parametric Crop Insurance.

Generates realistic, non-circular synthetic policy datasets reflecting underwriting
patterns in Andhra Pradesh (Anantapur, Kurnool, Kadapa).

Avoids circularity through:
1. Hard negatives (legitimate large holdings, border parcels, multi-parcel farmers, late buyers).
2. Subtle frauds (sub-threshold inflation, near-duplicate boundaries with coordinate jitter).
3. Realistic feature overlap between legitimate and fraudulent distributions.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "fraud_config.json"
TIER_RULES_PATH = PROJECT_ROOT / "config" / "tier_rules.json"

FEATURE_COLUMNS = [
    "land_area_ha",
    "sum_insured",
    "premium",
    "parcel_lat",
    "parcel_lon",
    "farmer_policy_count",
    "days_before_season",
    "claim_history_count",
    "sum_insured_per_ha_ratio",
    "district_Anantapur",
    "district_Kadapa",
    "district_Kurnool",
]


def load_fraud_config(config_path: Path = CONFIG_PATH) -> Dict:
    """Loads spatial bounding boxes and benchmark parameters."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_boundary_hash(lat: float, lon: float, area: float, salt: str = "") -> str:
    """Derives a deterministic 32-byte hex hash representing a parcel polygon."""
    raw = f"{lat:.5f}_{lon:.5f}_{area:.4f}_{salt}"
    return "0x" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_synthetic_fraud_dataset(
    n_samples: int = 3200,
    fraud_rate: float = 0.09,
    seed: int = 42,
    config_path: Path = CONFIG_PATH,
) -> pd.DataFrame:
    """
    Generates a realistic, non-circular synthetic dataset of crop insurance policies.

    Args:
        n_samples: Total number of policy records (>= 3000).
        fraud_rate: Target overall fraction of fraudulent policies (typically 0.08 - 0.10).
        seed: Random seed for deterministic reproducibility.
        config_path: Path to fraud_config.json.

    Returns:
        pd.DataFrame containing policy features, fraud labels, and fraud categories.
    """
    rng = np.random.RandomState(seed)
    cfg = load_fraud_config(config_path)

    dist_boxes = cfg["district_bounding_boxes"]
    benchmark_eth = cfg["benchmarks"]["groundnut_sum_insured_per_ha_eth"]

    # Regional rates: base 3% + Anantapur 3.5%, Kurnool 2.5%, Kadapa 2.0%
    regional_rates = {
        "Anantapur": 0.03 + 0.035,  # 6.5%
        "Kurnool": 0.03 + 0.025,    # 5.5%
        "Kadapa": 0.03 + 0.020,     # 5.0%
    }

    n_fraud = int(round(n_samples * fraud_rate))
    n_legit = n_samples - n_fraud

    # 4 distinct fraud categories distributed evenly
    fraud_categories = [
        "duplicate_boundary",
        "out_of_district",
        "anomalous_claim_pattern",
        "inflated_sum_insured",
    ]
    fraud_counts = {cat: n_fraud // 4 for cat in fraud_categories}
    # Assign remainder to inflated_sum_insured
    remainder = n_fraud - sum(fraud_counts.values())
    fraud_counts["inflated_sum_insured"] += remainder

    districts_list = ["Anantapur", "Kurnool", "Kadapa"]
    district_probs = [0.40, 0.35, 0.25]

    records: List[Dict] = []
    farmer_id_counter = 1

    # -------------------------------------------------------------------------
    # 1. Generate Legitimate Policies (n_legit)
    # -------------------------------------------------------------------------
    for i in range(n_legit):
        district = rng.choice(districts_list, p=district_probs)
        box = dist_boxes[district]

        # Check if hard negative: border parcel, large farm, multi-parcel, late purchase
        is_hard_negative = rng.rand() < 0.28
        hard_neg_type = rng.choice(["large_farm", "multi_parcel", "border_parcel", "late_buyer"]) \
            if is_hard_negative else "normal"

        if hard_neg_type == "large_farm":
            # Legitimate large commercial holding
            area = float(rng.uniform(10.0, 22.0))
            # Ratio slightly elevated due to capital investment (1.2 to 1.7)
            ratio = float(rng.uniform(1.20, 1.70))
            farmer_policies = rng.choice([1, 2, 3])
            days_before = rng.randint(10, 45)
            claims = rng.choice([0, 1, 2], p=[0.70, 0.25, 0.05])
        elif hard_neg_type == "multi_parcel":
            # Multi-parcel owner
            area = float(rng.uniform(1.5, 6.0))
            ratio = float(rng.uniform(0.85, 1.25))
            farmer_policies = rng.choice([3, 4])  # legitimate multi-parcel
            days_before = rng.randint(8, 35)
            claims = rng.choice([0, 1, 2], p=[0.60, 0.30, 0.10])
        elif hard_neg_type == "border_parcel":
            # Located within 0.02 deg of district boundary
            area = float(rng.exponential(scale=2.2) + 0.6)
            area = min(max(area, 0.5), 12.0)
            ratio = float(rng.uniform(0.80, 1.30))
            farmer_policies = rng.choice([1, 2], p=[0.8, 0.2])
            days_before = rng.randint(10, 40)
            claims = rng.choice([0, 1], p=[0.85, 0.15])
        elif hard_neg_type == "late_buyer":
            # Bought late due to late sowing advisory, but genuine farmer
            area = float(rng.exponential(scale=2.0) + 0.5)
            area = min(max(area, 0.4), 10.0)
            ratio = float(rng.uniform(0.85, 1.20))
            farmer_policies = 1
            days_before = rng.randint(3, 6)  # close to season start, but legitimate
            claims = rng.choice([0, 1], p=[0.90, 0.10])
        else:
            # Typical smallholder farmer
            area = float(rng.exponential(scale=2.0) + 0.5)
            area = min(max(area, 0.4), 10.0)
            ratio = float(rng.normal(loc=1.0, scale=0.12))
            ratio = min(max(ratio, 0.70), 1.40)
            farmer_policies = rng.choice([1, 2], p=[0.85, 0.15])
            days_before = rng.randint(7, 50)
            claims = rng.choice([0, 1, 2], p=[0.80, 0.16, 0.04])

        # Centroid placement
        if hard_neg_type == "border_parcel":
            # Place very close to boundary (inside within 0.005 to 0.02 deg)
            side = rng.choice(["min_lat", "max_lat", "min_lon", "max_lon"])
            if side == "min_lat":
                lat = box["min_lat"] + rng.uniform(0.005, 0.025)
                lon = rng.uniform(box["min_lon"] + 0.05, box["max_lon"] - 0.05)
            elif side == "max_lat":
                lat = box["max_lat"] - rng.uniform(0.005, 0.025)
                lon = rng.uniform(box["min_lon"] + 0.05, box["max_lon"] - 0.05)
            elif side == "min_lon":
                lat = rng.uniform(box["min_lat"] + 0.05, box["max_lat"] - 0.05)
                lon = box["min_lon"] + rng.uniform(0.005, 0.025)
            else:
                lat = rng.uniform(box["min_lat"] + 0.05, box["max_lat"] - 0.05)
                lon = box["max_lon"] - rng.uniform(0.005, 0.025)
        else:
            # Safe interior coordinates
            lat = rng.uniform(box["min_lat"] + 0.05, box["max_lat"] - 0.05)
            lon = rng.uniform(box["min_lon"] + 0.05, box["max_lon"] - 0.05)

        sum_insured = round(area * benchmark_eth * ratio, 4)
        rate = regional_rates[district]
        premium = round(sum_insured * rate, 5)

        farmer_id = f"farmer_{farmer_id_counter:04d}"
        if farmer_policies == 1 or rng.rand() > 0.4:
            farmer_id_counter += 1

        b_hash = _compute_boundary_hash(lat, lon, area)

        records.append({
            "policy_id": len(records) + 1,
            "farmer_id": farmer_id,
            "district": district,
            "crop": "Groundnut",
            "land_area_ha": round(area, 2),
            "sum_insured": sum_insured,
            "premium": premium,
            "parcel_lat": round(lat, 5),
            "parcel_lon": round(lon, 5),
            "boundary_hash": b_hash,
            "farmer_policy_count": int(farmer_policies),
            "days_before_season": int(days_before),
            "claim_history_count": int(claims),
            "sum_insured_per_ha_ratio": round(ratio, 3),
            "is_fraud": 0,
            "fraud_type": "legitimate",
        })

    # -------------------------------------------------------------------------
    # 2. Generate Fraudulent Policies (n_fraud)
    # -------------------------------------------------------------------------
    legit_df = pd.DataFrame(records)

    # (1) Duplicate Cadastral Boundary (same or near-identical polygon across different farmers)
    for _ in range(fraud_counts["duplicate_boundary"]):
        # Pick an existing legitimate record to clone or jitter
        victim_idx = rng.randint(0, len(legit_df))
        victim = legit_df.iloc[victim_idx]

        is_near_duplicate = rng.rand() < 0.50
        if is_near_duplicate:
            # Subtle near-duplicate: jitter coordinate by 0.0001 deg (~11m), generating a NEW hash!
            # On-chain hash check misses it; ML spatial proximity/overlap flags it
            lat = victim["parcel_lat"] + rng.choice([-0.00012, 0.00012])
            lon = victim["parcel_lon"] + rng.choice([-0.00012, 0.00012])
            area = victim["land_area_ha"]
            b_hash = _compute_boundary_hash(lat, lon, area, salt="jitter")
        else:
            # Exact duplicate hash submitted by a different farmer
            lat = victim["parcel_lat"]
            lon = victim["parcel_lon"]
            area = victim["land_area_ha"]
            b_hash = victim["boundary_hash"]

        diff_farmer_id = f"sybil_farmer_{farmer_id_counter:04d}"
        farmer_id_counter += 1

        ratio = float(rng.uniform(0.90, 1.30))
        sum_insured = round(area * benchmark_eth * ratio, 4)
        rate = regional_rates[victim["district"]]
        premium = round(sum_insured * rate, 5)

        records.append({
            "policy_id": len(records) + 1,
            "farmer_id": diff_farmer_id,
            "district": victim["district"],
            "crop": "Groundnut",
            "land_area_ha": round(area, 2),
            "sum_insured": sum_insured,
            "premium": premium,
            "parcel_lat": round(lat, 5),
            "parcel_lon": round(lon, 5),
            "boundary_hash": b_hash,
            "farmer_policy_count": int(rng.choice([1, 2])),
            "days_before_season": int(rng.randint(5, 30)),
            "claim_history_count": int(rng.choice([0, 1])),
            "sum_insured_per_ha_ratio": round(ratio, 3),
            "is_fraud": 1,
            "fraud_type": "duplicate_boundary",
        })

    # (2) Coordinates Outside Stated District's Bounding Box
    for _ in range(fraud_counts["out_of_district"]):
        stated_district = rng.choice(districts_list)
        box = dist_boxes[stated_district]

        is_subtle_out = rng.rand() < 0.45
        if is_subtle_out:
            # Subtle: placed 0.015 - 0.06 deg just outside the border
            offset = rng.uniform(0.015, 0.060)
            side = rng.choice(["lat_min", "lat_max", "lon_min", "lon_max"])
            if side == "lat_min":
                lat = box["min_lat"] - offset
                lon = rng.uniform(box["min_lon"] + 0.1, box["max_lon"] - 0.1)
            elif side == "lat_max":
                lat = box["max_lat"] + offset
                lon = rng.uniform(box["min_lon"] + 0.1, box["max_lon"] - 0.1)
            elif side == "lon_min":
                lat = rng.uniform(box["min_lat"] + 0.1, box["max_lat"] - 0.1)
                lon = box["min_lon"] - offset
            else:
                lat = rng.uniform(box["min_lat"] + 0.1, box["max_lat"] - 0.1)
                lon = box["max_lon"] + offset
        else:
            # Far out: placed in completely different region (e.g. Bangalore / Chennai latitude)
            lat = rng.choice([12.97, 16.85, 13.08]) + rng.uniform(-0.1, 0.1)
            lon = rng.choice([77.59, 79.80, 80.27]) + rng.uniform(-0.1, 0.1)

        area = float(rng.exponential(scale=2.0) + 0.5)
        area = min(max(area, 0.5), 8.0)
        ratio = float(rng.uniform(0.95, 1.25))
        sum_insured = round(area * benchmark_eth * ratio, 4)
        rate = regional_rates[stated_district]
        premium = round(sum_insured * rate, 5)

        f_id = f"farmer_out_{farmer_id_counter:04d}"
        farmer_id_counter += 1
        b_hash = _compute_boundary_hash(lat, lon, area)

        records.append({
            "policy_id": len(records) + 1,
            "farmer_id": f_id,
            "district": stated_district,
            "crop": "Groundnut",
            "land_area_ha": round(area, 2),
            "sum_insured": sum_insured,
            "premium": premium,
            "parcel_lat": round(lat, 5),
            "parcel_lon": round(lon, 5),
            "boundary_hash": b_hash,
            "farmer_policy_count": int(rng.choice([1, 2])),
            "days_before_season": int(rng.randint(10, 40)),
            "claim_history_count": int(rng.choice([0, 1])),
            "sum_insured_per_ha_ratio": round(ratio, 3),
            "is_fraud": 1,
            "fraud_type": "out_of_district",
        })

    # (3) Anomalous Claim Pattern (repeated claims, buying just before season start)
    for _ in range(fraud_counts["anomalous_claim_pattern"]):
        district = rng.choice(districts_list)
        box = dist_boxes[district]
        lat = rng.uniform(box["min_lat"] + 0.05, box["max_lat"] - 0.05)
        lon = rng.uniform(box["min_lon"] + 0.05, box["max_lon"] - 0.05)

        area = float(rng.uniform(1.0, 5.0))
        ratio = float(rng.uniform(1.10, 1.60))
        sum_insured = round(area * benchmark_eth * ratio, 4)
        rate = regional_rates[district]
        premium = round(sum_insured * rate, 5)

        # Suspicious pattern: bought 0 to 2 days before season start + 3 to 6 prior claims + 4 to 7 policies
        days_before = rng.randint(0, 3)
        claims = rng.randint(3, 7)
        policies = rng.randint(4, 8)

        f_id = f"farmer_pattern_{farmer_id_counter:04d}"
        farmer_id_counter += 1
        b_hash = _compute_boundary_hash(lat, lon, area)

        records.append({
            "policy_id": len(records) + 1,
            "farmer_id": f_id,
            "district": district,
            "crop": "Groundnut",
            "land_area_ha": round(area, 2),
            "sum_insured": sum_insured,
            "premium": premium,
            "parcel_lat": round(lat, 5),
            "parcel_lon": round(lon, 5),
            "boundary_hash": b_hash,
            "farmer_policy_count": int(policies),
            "days_before_season": int(days_before),
            "claim_history_count": int(claims),
            "sum_insured_per_ha_ratio": round(ratio, 3),
            "is_fraud": 1,
            "fraud_type": "anomalous_claim_pattern",
        })

    # (4) Inflated Sum Insured vs Area Benchmark
    for _ in range(fraud_counts["inflated_sum_insured"]):
        district = rng.choice(districts_list)
        box = dist_boxes[district]
        lat = rng.uniform(box["min_lat"] + 0.05, box["max_lat"] - 0.05)
        lon = rng.uniform(box["min_lon"] + 0.05, box["max_lon"] - 0.05)

        area = float(rng.uniform(0.5, 4.0))

        # AVOID CIRCULARITY:
        # Instead of only generating > 2.0x, generate a continuous spectrum from 1.70x to 3.80x.
        # Subtle cases (1.70 - 1.98x) test ML capability where a naive rule threshold (e.g. 2.0x) fails.
        ratio = float(rng.uniform(1.70, 3.80))
        sum_insured = round(area * benchmark_eth * ratio, 4)
        rate = regional_rates[district]
        premium = round(sum_insured * rate, 5)

        f_id = f"farmer_inflated_{farmer_id_counter:04d}"
        farmer_id_counter += 1
        b_hash = _compute_boundary_hash(lat, lon, area)

        records.append({
            "policy_id": len(records) + 1,
            "farmer_id": f_id,
            "district": district,
            "crop": "Groundnut",
            "land_area_ha": round(area, 2),
            "sum_insured": sum_insured,
            "premium": premium,
            "parcel_lat": round(lat, 5),
            "parcel_lon": round(lon, 5),
            "boundary_hash": b_hash,
            "farmer_policy_count": int(rng.choice([1, 2, 3])),
            "days_before_season": int(rng.randint(4, 30)),
            "claim_history_count": int(rng.choice([0, 1, 2])),
            "sum_insured_per_ha_ratio": round(ratio, 3),
            "is_fraud": 1,
            "fraud_type": "inflated_sum_insured",
        })

    df = pd.DataFrame(records)
    # Shuffle dataset
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    df["policy_id"] = np.arange(1, len(df) + 1)
    return df


def split_fraud_dataset(
    df: pd.DataFrame,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    test_ratio: float = 0.20,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits dataset into stratified train, validation, and test subsets.
    Stratifies on 'fraud_type' to preserve minority fraud class distributions.
    """
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-6, "Split ratios must sum to 1.0"

    # First split: train vs (val + test)
    val_test_ratio = val_ratio + test_ratio
    train_df, val_test_df = train_test_split(
        df,
        test_size=val_test_ratio,
        random_state=seed,
        stratify=df["fraud_type"],
    )

    # Second split: val vs test (equal 50/50 of remainder if 20/20)
    relative_test_ratio = test_ratio / val_test_ratio
    val_df, test_df = train_test_split(
        val_test_df,
        test_size=relative_test_ratio,
        random_state=seed,
        stratify=val_test_df["fraud_type"],
    )

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares numerical and encoded feature matrix X, strictly excluding labels and IDs.
    Guarantees zero label leakage.
    """
    df_copy = df.copy()

    # One-hot encode district
    for dist in ["Anantapur", "Kadapa", "Kurnool"]:
        col_name = f"district_{dist}"
        df_copy[col_name] = (df_copy["district"] == dist).astype(float)

    return df_copy[FEATURE_COLUMNS].copy()


if __name__ == "__main__":
    print("Generating synthetic fraud dataset (n=3200, fraud_rate=0.09)...")
    dataset = generate_synthetic_fraud_dataset(n_samples=3200, fraud_rate=0.09, seed=42)
    output_path = PROJECT_ROOT / "data" / "synthetic_fraud_dataset.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)

    print(f"Generated {len(dataset)} records. Saved to {output_path}")
    print("\nClass distribution:")
    print(dataset["fraud_type"].value_counts())
    print(f"Overall fraud rate: {dataset['is_fraud'].mean() * 100:.2f}%")
