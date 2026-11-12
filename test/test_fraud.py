"""
Unit and Integration Tests for Fraud Detection Module (Phase 4).

Covers:
1. Synthetic Data Generator:
   - Seed reproducibility
   - Fraud rate target adherence (8 - 10%)
   - No label leakage in extract_features
   - Stratified train/val/test splitting
2. Model APIs:
   - HeuristicRuleEngine
   - IsolationForestDetector (unsupervised fit + validation threshold tuning)
   - AutoencoderDetector (reconstruction on legit profiles + validation threshold tuning)
3. Smart Contract Integration:
   - FRAUD_CHECKER_ROLE calls flagFraud() with cryptographic reasonHash
   - Flagged policy enters UNDER_REVIEW and blocks settlement
   - Unauthorized caller cannot flag fraud
   - Legitimate policy settles normally
"""

import subprocess
import time
import unittest
from pathlib import Path
from typing import Optional

import numpy as np
from web3 import Web3

from fraud.autoencoder_model import AutoencoderDetector
from fraud.generate_fraud_data import (
    FEATURE_COLUMNS,
    extract_features,
    generate_synthetic_fraud_dataset,
    split_fraud_dataset,
)
from fraud.isolation_forest_model import IsolationForestDetector
from fraud.rule_engine import HeuristicRuleEngine
from oracles.common import (
    DEFAULT_LOCAL_KEYS,
    compute_rules_hash,
    get_rpc_url,
)
from oracles.contract_adapter import (
    ContractAdapter,
    CropCode,
    OracleSource,
    PolicyStatus,
    Region,
    SeverityTier,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFraudGeneratorAndModels(unittest.TestCase):
    """Unit tests for data generation and model interfaces."""

    @classmethod
    def setUpClass(cls):
        cls.df = generate_synthetic_fraud_dataset(n_samples=500, fraud_rate=0.09, seed=42)
        cls.train_df, cls.val_df, cls.test_df = split_fraud_dataset(cls.df, seed=42)

    def test_seed_reproducibility(self):
        """Verifies generator produces identical records for the same seed."""
        df1 = generate_synthetic_fraud_dataset(n_samples=200, seed=123)
        df2 = generate_synthetic_fraud_dataset(n_samples=200, seed=123)
        pd_testing = unittest.TestCase()
        pd_testing.assertTrue(df1.equals(df2))

    def test_fraud_rate_within_expected_window(self):
        """Verifies fraud rate matches the target ~8-10% window."""
        fraud_rate = self.df["is_fraud"].mean()
        self.assertGreaterEqual(fraud_rate, 0.08)
        self.assertLessEqual(fraud_rate, 0.10)

    def test_no_label_leakage_in_features(self):
        """Verifies label, ID, and ground truth columns are excluded from features."""
        X = extract_features(self.df)
        self.assertNotIn("is_fraud", X.columns)
        self.assertNotIn("fraud_type", X.columns)
        self.assertNotIn("policy_id", X.columns)
        self.assertNotIn("farmer_id", X.columns)
        self.assertNotIn("boundary_hash", X.columns)
        self.assertEqual(list(X.columns), FEATURE_COLUMNS)

    def test_stratified_split_preserves_proportions(self):
        """Verifies stratified split preserves class ratios across train, val, test."""
        total_rate = self.df["is_fraud"].mean()
        train_rate = self.train_df["is_fraud"].mean()
        val_rate = self.val_df["is_fraud"].mean()
        test_rate = self.test_df["is_fraud"].mean()

        self.assertAlmostEqual(train_rate, total_rate, delta=0.02)
        self.assertAlmostEqual(val_rate, total_rate, delta=0.02)
        self.assertAlmostEqual(test_rate, total_rate, delta=0.02)

    def test_rule_engine_api(self):
        """Verifies HeuristicRuleEngine fit, predict, and evaluate_record."""
        engine = HeuristicRuleEngine().fit(self.train_df)
        preds = engine.predict(self.test_df)
        self.assertEqual(len(preds), len(self.test_df))
        self.assertTrue(set(preds).issubset({0, 1}))

        details = engine.predict_detailed(self.test_df.iloc[:5])
        self.assertEqual(len(details), 5)
        for d in details:
            self.assertIn("is_fraud", d)
            self.assertIn("predicted_type", d)

    def test_isolation_forest_api(self):
        """Verifies IsolationForestDetector training, score generation, and predictions."""
        X_train = extract_features(self.train_df)
        X_val = extract_features(self.val_df)
        y_val = self.val_df["is_fraud"].values
        X_test = extract_features(self.test_df)

        iso = IsolationForestDetector(n_estimators=30, random_state=42)
        iso.fit(X_train=X_train, y_train=None, X_val=X_val, y_val=y_val)

        preds = iso.predict(X_test)
        self.assertEqual(len(preds), len(X_test))
        self.assertTrue(set(preds).issubset({0, 1}))

        scores = iso.predict_anomaly_score(X_test)
        self.assertTrue(np.all((scores >= 0.0) & (scores <= 1.0)))

    def test_autoencoder_api(self):
        """Verifies AutoencoderDetector training on non-fraud rows and threshold tuning."""
        X_train = extract_features(self.train_df)
        y_train = self.train_df["is_fraud"].values
        X_val = extract_features(self.val_df)
        y_val = self.val_df["is_fraud"].values
        X_test = extract_features(self.test_df)

        ae = AutoencoderDetector(hidden_layer_sizes=(6, 3, 6), max_iter=80, random_state=42)
        ae.fit(X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val)

        preds = ae.predict(X_test)
        self.assertEqual(len(preds), len(X_test))
        self.assertTrue(set(preds).issubset({0, 1}))

        errors = ae.compute_reconstruction_error(X_test)
        self.assertTrue(np.all(errors >= 0.0))


class TestFraudContractIntegration(unittest.TestCase):
    """Integration tests running against real CropInsurance.sol on Hardhat node."""

    node_process: Optional[subprocess.Popen] = None
    adapter: ContractAdapter
    deployer_key: str
    farmer_key: str
    checker_key: str
    unauthorized_key: str
    weather_key: str
    sat_key: str
    rules_hash: bytes

    @classmethod
    def setUpClass(cls):
        rpc_url = get_rpc_url()
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not w3.is_connected():
            cls.node_process = subprocess.Popen(
                ["npx", "hardhat", "node"],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            for _ in range(30):
                time.sleep(1)
                if w3.is_connected():
                    break
            if not w3.is_connected():
                if cls.node_process:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(cls.node_process.pid)], capture_output=True)
                raise RuntimeError("Could not connect to or start local Hardhat node.")

        cls.adapter = ContractAdapter(rpc_url=rpc_url)
        cls.deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
        cls.farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
        cls.checker_key = DEFAULT_LOCAL_KEYS["FRAUD_CHECKER"]
        cls.unauthorized_key = DEFAULT_LOCAL_KEYS["DISPUTE_REVIEWER"]
        cls.weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        cls.sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]

        admin_addr = cls.adapter.w3.eth.account.from_key(cls.deployer_key).address
        checker_addr = cls.adapter.w3.eth.account.from_key(cls.checker_key).address
        weather_addr = cls.adapter.w3.eth.account.from_key(cls.weather_key).address
        sat_addr = cls.adapter.w3.eth.account.from_key(cls.sat_key).address

        cls.adapter.deploy(cls.deployer_key, admin_address=admin_addr)
        cls.adapter.grant_role(cls.deployer_key, "FRAUD_CHECKER_ROLE", checker_addr)
        cls.adapter.grant_role(cls.deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        cls.adapter.grant_role(cls.deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)

        cls.adapter.fund_risk_pool(cls.deployer_key, cls.adapter.w3.to_wei(50, "ether"))
        cls.rules_hash = compute_rules_hash()

    @classmethod
    def tearDownClass(cls):
        if cls.node_process:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(cls.node_process.pid)], capture_output=True)

    def test_fraud_flag_blocks_settlement(self):
        """Verifies flagFraud() moves policy to UNDER_REVIEW and halts settlement."""
        w3 = self.adapter.w3
        now = self.adapter.get_block_timestamp()
        land_hash = w3.keccak(text=f"fraud_test_{time.time_ns()}")
        sum_insured = w3.to_wei(1, "ether")

        p_id, _ = self.adapter.create_policy(
            farmer_private_key=self.farmer_key,
            land_hash=land_hash,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=self.rules_hash,
        )

        reason_hash = w3.keccak(text="inflated_sum_insured:MLPAutoencoder")
        self.adapter.flag_fraud(self.checker_key, p_id, reason_hash)

        pol = self.adapter.get_policy(p_id)
        self.assertEqual(pol["status"], PolicyStatus.UNDER_REVIEW)

        self.adapter.advance_time(120)

        # Settlement must revert because status is UNDER_REVIEW
        with self.assertRaises(Exception):
            self.adapter.settle_policy(self.deployer_key, p_id)

    def test_unauthorized_flag_fraud_reverts(self):
        """Verifies account without FRAUD_CHECKER_ROLE cannot call flagFraud()."""
        w3 = self.adapter.w3
        now = self.adapter.get_block_timestamp()
        land_hash = w3.keccak(text=f"unauth_test_{time.time_ns()}")
        sum_insured = w3.to_wei(1, "ether")

        p_id, _ = self.adapter.create_policy(
            farmer_private_key=self.farmer_key,
            land_hash=land_hash,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=self.rules_hash,
        )

        reason_hash = w3.keccak(text="anomalous_claim:HeuristicRuleEngine")
        with self.assertRaises(Exception):
            self.adapter.flag_fraud(self.unauthorized_key, p_id, reason_hash)

        # Policy should remain ACTIVE
        pol = self.adapter.get_policy(p_id)
        self.assertEqual(pol["status"], PolicyStatus.ACTIVE)

    def test_legitimate_policy_settles_normally(self):
        """Verifies legitimate policy with no flag settles smoothly."""
        w3 = self.adapter.w3
        now = self.adapter.get_block_timestamp()
        land_hash = w3.keccak(text=f"legit_test_{time.time_ns()}")
        sum_insured = w3.to_wei(1, "ether")

        p_id, _ = self.adapter.create_policy(
            farmer_private_key=self.farmer_key,
            land_hash=land_hash,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=self.rules_hash,
        )

        self.adapter.advance_time(120)
        self.adapter.submit_report(self.weather_key, p_id, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE)
        self.adapter.submit_report(self.sat_key, p_id, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)

        self.adapter.settle_policy(self.deployer_key, p_id)
        pol = self.adapter.get_policy(p_id)
        self.assertEqual(pol["status"], PolicyStatus.SETTLED)
        self.assertEqual(pol["finalTier"], SeverityTier.TIER_2_SEVERE)


if __name__ == "__main__":
    unittest.main()
