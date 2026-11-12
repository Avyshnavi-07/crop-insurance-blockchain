"""
Heuristic Rule Engine for Parametric Crop Insurance Fraud Detection.

Implements deterministic business rules with explicit, documented thresholds
derived from Andhra Pradesh agricultural research assumptions.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fraud.generate_fraud_data import CONFIG_PATH, load_fraud_config  # noqa: E402


class HeuristicRuleEngine:
    """
    Deterministic rule engine checking:
    1. Spatial bounds: parcel centroid must fall within district bounding box.
    2. Valuation ceiling: sum_insured per hectare ratio must not exceed threshold.
    3. Claim timing: high past claim history combined with last-minute purchase.
    4. Sybil duplicates: duplicate cadastral boundary hashes across distinct farmers.
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config = load_fraud_config(config_path)
        self.dist_boxes = self.config["district_bounding_boxes"]
        rule_thresh = self.config["rule_engine_thresholds"]

        self.inflated_ratio_threshold = float(rule_thresh["inflated_ratio_threshold"])
        self.anomalous_days_threshold = int(rule_thresh["anomalous_days_before_season"])
        self.anomalous_claims_threshold = int(rule_thresh["anomalous_claim_history_count"])
        self.max_policies_threshold = int(rule_thresh["max_farmer_policies_per_season"])
        self.buffer_deg = float(rule_thresh["buffer_deg_outside_district"])

        # Registry of known active boundary hashes: hash -> farmer_id
        self.registered_hashes: Dict[str, str] = {}

    def fit(self, df_train: pd.DataFrame, y_train: Optional[np.ndarray] = None):
        """
        Populates registered cadastral boundary hashes from baseline training policies.
        """
        self.registered_hashes.clear()
        if "boundary_hash" in df_train.columns and "farmer_id" in df_train.columns:
            for _, row in df_train.iterrows():
                self.registered_hashes[str(row["boundary_hash"])] = str(row["farmer_id"])
        return self

    def evaluate_record(self, record: Union[pd.Series, Dict]) -> Tuple[bool, str, str]:
        """
        Evaluates a single policy against deterministic fraud rules.

        Returns:
            (is_fraud, fraud_type_detected, triggering_rule)
        """
        district = str(record["district"])
        lat = float(record["parcel_lat"])
        lon = float(record["parcel_lon"])
        ratio = float(record["sum_insured_per_ha_ratio"])
        days_before = int(record["days_before_season"])
        claims = int(record["claim_history_count"])
        policies = int(record["farmer_policy_count"])
        farmer_id = str(record.get("farmer_id", ""))
        b_hash = str(record.get("boundary_hash", ""))

        # Rule 1: Spatial Bounding Box Check
        if district in self.dist_boxes:
            box = self.dist_boxes[district]
            min_lat = box["min_lat"] - self.buffer_deg
            max_lat = box["max_lat"] + self.buffer_deg
            min_lon = box["min_lon"] - self.buffer_deg
            max_lon = box["max_lon"] + self.buffer_deg

            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                return True, "out_of_district", "RULE_SPATIAL_BOUNDS_EXCEEDED"

        # Rule 2: Inflated Valuation Check
        if ratio > self.inflated_ratio_threshold:
            return True, "inflated_sum_insured", "RULE_INFLATED_VALUATION_CEILING"

        # Rule 3: Anomalous Claim Timing Pattern
        if days_before < self.anomalous_days_threshold and claims >= self.anomalous_claims_threshold:
            return True, "anomalous_claim_pattern", "RULE_ANOMALOUS_CLAIM_TIMING"

        if policies > self.max_policies_threshold and claims >= self.anomalous_claims_threshold:
            return True, "anomalous_claim_pattern", "RULE_EXCESSIVE_POLICIES_HIGH_CLAIMS"

        # Rule 4: Duplicate Boundary Hash (different farmer claiming same boundary)
        if b_hash and b_hash in self.registered_hashes:
            registered_farmer = self.registered_hashes[b_hash]
            if farmer_id and registered_farmer != farmer_id:
                return True, "duplicate_boundary", "RULE_DUPLICATE_CADASTRAL_HASH"

        return False, "legitimate", "NONE"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predicts binary fraud labels (0 = legitimate, 1 = fraud).
        """
        preds = []
        for _, row in df.iterrows():
            is_fraud, _, _ = self.evaluate_record(row)
            preds.append(1 if is_fraud else 0)
        return np.array(preds, dtype=int)

    def predict_detailed(self, df: pd.DataFrame) -> List[Dict]:
        """
        Returns rich prediction details including rule name and detected category.
        """
        results = []
        for _, row in df.iterrows():
            is_fraud, fraud_type, rule_name = self.evaluate_record(row)
            results.append({
                "policy_id": row.get("policy_id", None),
                "is_fraud": int(is_fraud),
                "predicted_type": fraud_type,
                "rule_name": rule_name,
            })
        return results
