"""
Unit and Integration tests for Oracle Services & Robustness (Phase 3).

Covers:
1. FaultInjector unit tests:
   - Deterministic seeding reproducibility
   - 0% error rate (honest baseline)
   - 100% error rate (complete corruption) in 'random' and 'off_by_one' modes
   - Boundary condition handling (tiers 0 and 3 in off_by_one)
   - Input validation and exception handling
2. Integration tests against real CropInsurance.sol contract:
   - Scenario (b): 1 faulty oracle at 30% error rate preserves consensus truth
   - Scenario (c): 3 differing reports trigger median fallback
   - Scenario (d): 2 disagreeing reports block settlement until 3rd report arrives
"""

import subprocess
import time
import unittest
from pathlib import Path
from typing import Optional

from web3 import Web3

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
from oracles.fault_injector import FaultInjector

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFaultInjector(unittest.TestCase):
    """Unit tests for FaultInjector probabilistic behavior and modes."""

    def test_deterministic_seed(self):
        """Verifies that identical seeds produce identical corrupted tier sequences."""
        fi1 = FaultInjector(error_rate=0.40, mode="random", seed=999)
        fi2 = FaultInjector(error_rate=0.40, mode="random", seed=999)

        seq1 = [fi1.inject(2) for _ in range(50)]
        seq2 = [fi2.inject(2) for _ in range(50)]
        self.assertEqual(seq1, seq2)

    def test_zero_error_rate(self):
        """Verifies 0% error rate never corrupts any severity tier."""
        fi = FaultInjector(error_rate=0.0, mode="random")
        for tier in (0, 1, 2, 3):
            for _ in range(25):
                rep_tier, faulted = fi.inject(tier)
                self.assertFalse(faulted)
                self.assertEqual(rep_tier, tier)

    def test_hundred_percent_error_rate_random(self):
        """Verifies 100% error rate in random mode always corrupts tier within valid set."""
        fi = FaultInjector(error_rate=1.0, mode="random", seed=42)
        for true_tier in (0, 1, 2, 3):
            for _ in range(25):
                rep_tier, faulted = fi.inject(true_tier)
                self.assertTrue(faulted)
                self.assertNotEqual(rep_tier, true_tier)
                self.assertIn(rep_tier, (0, 1, 2, 3))

    def test_hundred_percent_error_rate_off_by_one(self):
        """Verifies off_by_one mode always shifts tier by exactly +/- 1 within [0, 3]."""
        fi = FaultInjector(error_rate=1.0, mode="off_by_one", seed=101)
        for true_tier in (0, 1, 2, 3):
            for _ in range(25):
                rep_tier, faulted = fi.inject(true_tier)
                self.assertTrue(faulted)
                self.assertEqual(abs(rep_tier - true_tier), 1)
                self.assertIn(rep_tier, (0, 1, 2, 3))

    def test_off_by_one_boundaries(self):
        """Verifies off_by_one boundary behavior: tier 0 -> 1, tier 3 -> 2."""
        fi = FaultInjector(error_rate=1.0, mode="off_by_one", seed=7)
        for _ in range(10):
            rep0, f0 = fi.inject(0)
            self.assertTrue(f0)
            self.assertEqual(rep0, 1)

            rep3, f3 = fi.inject(3)
            self.assertTrue(f3)
            self.assertEqual(rep3, 2)

    def test_validation_errors(self):
        """Verifies constructor and method argument validation."""
        with self.assertRaises(ValueError):
            FaultInjector(error_rate=-0.1)
        with self.assertRaises(ValueError):
            FaultInjector(error_rate=1.1)
        with self.assertRaises(ValueError):
            FaultInjector(mode="unsupported_mode")

        fi = FaultInjector()
        with self.assertRaises(ValueError):
            fi.set_error_rate(1.5)
        with self.assertRaises(ValueError):
            fi.set_mode("bad_mode")
        with self.assertRaises(ValueError):
            fi.inject(4)  # 4 is not in [0, 1, 2, 3]


class TestOracleContractIntegration(unittest.TestCase):
    """Integration tests running against real CropInsurance.sol contract."""

    node_process: Optional[subprocess.Popen] = None
    adapter: ContractAdapter
    deployer_key: str
    farmer_key: str
    weather_key: str
    sat_key: str
    soil_key: str
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
        cls.weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        cls.sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
        cls.soil_key = DEFAULT_LOCAL_KEYS["SOIL"]

        admin_addr = cls.adapter.w3.eth.account.from_key(cls.deployer_key).address
        weather_addr = cls.adapter.w3.eth.account.from_key(cls.weather_key).address
        sat_addr = cls.adapter.w3.eth.account.from_key(cls.sat_key).address
        soil_addr = cls.adapter.w3.eth.account.from_key(cls.soil_key).address

        cls.adapter.deploy(cls.deployer_key, admin_address=admin_addr)
        cls.adapter.grant_role(cls.deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        cls.adapter.grant_role(cls.deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
        cls.adapter.grant_role(cls.deployer_key, "ORACLE_SOIL_ROLE", soil_addr)

        cls.adapter.fund_risk_pool(cls.deployer_key, cls.adapter.w3.to_wei(50, "ether"))
        cls.rules_hash = compute_rules_hash()

    @classmethod
    def tearDownClass(cls):
        if cls.node_process:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(cls.node_process.pid)], capture_output=True)

    def _create_and_mature_policy(self, tag: str, region: Region = Region.ANANTAPUR) -> int:
        """Helper to create a fresh policy and advance EVM time past its endTime."""
        w3 = self.adapter.w3
        now = self.adapter.get_block_timestamp()
        land_hash = w3.keccak(text=f"test_land_{tag}_{time.time_ns()}")
        sum_insured = w3.to_wei(1, "ether")

        p_id, _ = self.adapter.create_policy(
            farmer_private_key=self.farmer_key,
            land_hash=land_hash,
            crop=CropCode.GROUNDNUT,
            region=region,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=self.rules_hash,
        )
        self.adapter.advance_time(120)
        return p_id

    def test_integration_scenario_b_faulty_oracle_30pct(self):
        """
        Scenario (b): One faulty oracle at 30% error rate.
        Honest weather and soil report severe drought (Tier 2 and Tier 3).
        Faulty satellite is corrupted to Tier 0.
        Reports: Weather=2, Sat=0, Soil=3.
        Median fallback evaluates [0, 2, 3] -> Tier 2.
        Consensus successfully protects farmer despite faulty oracle report.
        """
        p_id = self._create_and_mature_policy("scenario_b", Region.ANANTAPUR)

        # Weather reports honest Tier 2
        self.adapter.submit_report(self.weather_key, p_id, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE)

        # Satellite injects fault with 30% rate, seeded to guarantee corruption
        fi = FaultInjector(error_rate=0.30, mode="random", seed=1)
        corrupted_tier, was_faulted = fi.inject(2)
        self.assertTrue(was_faulted)
        self.adapter.submit_report(self.sat_key, p_id, OracleSource.SATELLITE, corrupted_tier)

        # Soil reports honest Tier 3
        self.adapter.submit_report(self.soil_key, p_id, OracleSource.SOIL, SeverityTier.TIER_3_CATASTROPHIC)

        has_con, win_tier = self.adapter.evaluate_consensus(p_id)
        self.assertTrue(has_con)
        self.assertEqual(win_tier, SeverityTier.TIER_2_SEVERE)

        self.adapter.settle_policy(self.deployer_key, p_id)
        policy = self.adapter.get_policy(p_id)
        self.assertEqual(policy["status"], PolicyStatus.SETTLED)
        self.assertEqual(policy["finalTier"], SeverityTier.TIER_2_SEVERE)
        expected_payout = self.adapter.w3.to_wei(0.5, "ether")  # 50% payout
        self.assertEqual(policy["payoutAmount"], expected_payout)

    def test_integration_scenario_c_median_fallback(self):
        """
        Scenario (c): All three oracles report differing tiers.
        Weather=0, Satellite=2, Soil=1.
        Evaluates median of [0, 1, 2] = Tier 1 (Moderate).
        """
        p_id = self._create_and_mature_policy("scenario_c", Region.KADAPA)

        self.adapter.submit_report(self.weather_key, p_id, OracleSource.WEATHER, SeverityTier.TIER_0_NORMAL)
        self.adapter.submit_report(self.sat_key, p_id, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)
        self.adapter.submit_report(self.soil_key, p_id, OracleSource.SOIL, SeverityTier.TIER_1_MODERATE)

        has_con, win_tier = self.adapter.evaluate_consensus(p_id)
        self.assertTrue(has_con)
        self.assertEqual(win_tier, SeverityTier.TIER_1_MODERATE)

        self.adapter.settle_policy(self.deployer_key, p_id)
        policy = self.adapter.get_policy(p_id)
        self.assertEqual(policy["status"], PolicyStatus.SETTLED)
        self.assertEqual(policy["finalTier"], SeverityTier.TIER_1_MODERATE)
        expected_payout = self.adapter.w3.to_wei(0.25, "ether")  # 25% payout
        self.assertEqual(policy["payoutAmount"], expected_payout)

    def test_integration_scenario_d_waiting_for_third_oracle(self):
        """
        Scenario (d): Only two oracles report and they disagree.
        Settlement must revert with ConsensusNotReached until the 3rd oracle submits.
        """
        p_id = self._create_and_mature_policy("scenario_d", Region.KURNOOL)

        # Weather=1, Satellite=2
        self.adapter.submit_report(self.weather_key, p_id, OracleSource.WEATHER, SeverityTier.TIER_1_MODERATE)
        self.adapter.submit_report(self.sat_key, p_id, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)

        has_con, _ = self.adapter.evaluate_consensus(p_id)
        self.assertFalse(has_con)

        # Settlement should fail / revert
        with self.assertRaises(Exception):
            self.adapter.settle_policy(self.deployer_key, p_id)

        # Third oracle submits: Soil=2 -> Satellite & Soil match on Tier 2
        self.adapter.submit_report(self.soil_key, p_id, OracleSource.SOIL, SeverityTier.TIER_2_SEVERE)

        has_con_after, win_tier_after = self.adapter.evaluate_consensus(p_id)
        self.assertTrue(has_con_after)
        self.assertEqual(win_tier_after, SeverityTier.TIER_2_SEVERE)

        self.adapter.settle_policy(self.deployer_key, p_id)
        policy = self.adapter.get_policy(p_id)
        self.assertEqual(policy["status"], PolicyStatus.SETTLED)
        self.assertEqual(policy["finalTier"], SeverityTier.TIER_2_SEVERE)
        expected_payout = self.adapter.w3.to_wei(0.50, "ether")  # 50% payout
        self.assertEqual(policy["payoutAmount"], expected_payout)


if __name__ == "__main__":
    unittest.main()
