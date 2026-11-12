"""
Unit and Integration Tests for Experiment Suite (Phase 5).

Covers:
1. Core Experiment Unit Functions:
   - E1 agreement and MAPE metric calculation.
   - E2 ablation disagreement variants (Variant A: strict 0%, Variant B: conservative min).
   - E3 Monte Carlo fault trial reproducibility.
   - E4 basis risk, signed bias, and over/under-payment formulas.
2. Full Exhaustive Consensus Parity (Python vs. Real CropInsurance.sol):
   - All 64 combinations of three severity tiers (4 x 4 x 4 = 64).
   - 2-report agreeing pairs (2-of-3 consensus without 3rd report).
   - 2-report disagreeing pairs (reversion with ConsensusNotReached).
"""

import subprocess
import time
import unittest
from pathlib import Path
from typing import Optional

import pandas as pd
from web3 import Web3

from experiments.common import (
    evaluate_python_consensus,
    load_experiment_dataset,
    tier_to_payout_pct,
)
from experiments.e2_ablation import evaluate_pair
from experiments.e3_faulty_robustness import run_monte_carlo_trials
from experiments.e4_tiered_vs_binary import evaluate_payout_rule
from oracles.common import (
    DEFAULT_LOCAL_KEYS,
    compute_rules_hash,
    get_rpc_url,
)
from oracles.contract_adapter import (
    ContractAdapter,
    CropCode,
    OracleSource,
    Region,
    SeverityTier,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestExperimentCoreFunctions(unittest.TestCase):
    """Unit tests for experiment metric calculations and ablation variants."""

    def test_e1_payout_mapping(self):
        """Verifies parametric tier to payout percentage mapping."""
        self.assertEqual(tier_to_payout_pct(0), 0.0)
        self.assertEqual(tier_to_payout_pct(1), 25.0)
        self.assertEqual(tier_to_payout_pct(2), 50.0)
        self.assertEqual(tier_to_payout_pct(3), 100.0)
        self.assertEqual(tier_to_payout_pct(None), 0.0)

    def test_e2_ablation_variants(self):
        """Verifies Variant A (no payout) and Variant B (conservative min) logic."""
        s1 = pd.Series([2, 1, 0, 3])
        s2 = pd.Series([2, 2, 1, 3])

        # Variant A
        tiers_a, payouts_a = evaluate_pair(s1, s2, variant="A")
        self.assertEqual(tiers_a.iloc[0], 2)
        self.assertEqual(payouts_a.iloc[0], 50.0)
        self.assertTrue(pd.isna(tiers_a.iloc[1]))  # Disagreement 1 vs 2 (represented as NaN in float series)
        self.assertEqual(payouts_a.iloc[1], 0.0)

        # Variant B
        tiers_b, payouts_b = evaluate_pair(s1, s2, variant="B")
        self.assertEqual(tiers_b.iloc[0], 2)
        self.assertEqual(payouts_b.iloc[0], 50.0)
        self.assertEqual(tiers_b.iloc[1], 1)  # min(1, 2) = 1
        self.assertEqual(payouts_b.iloc[1], 25.0)

    def test_e3_monte_carlo_determinism(self):
        """Verifies identical seed produces identical Monte Carlo simulation outputs."""
        df = load_experiment_dataset()
        res1 = run_monte_carlo_trials(df, target="weather_only", error_rate=0.20,
                                      mode="random", n_trials=10, base_seed=777)
        res2 = run_monte_carlo_trials(df, target="weather_only", error_rate=0.20,
                                      mode="random", n_trials=10, base_seed=777)
        self.assertAlmostEqual(res1["single_wrong_mean"], res2["single_wrong_mean"], places=6)
        self.assertAlmostEqual(res1["consensus_wrong_mean"], res2["consensus_wrong_mean"], places=6)

    def test_e4_basis_risk_calculation(self):
        """Verifies MAPE, signed gap, and over/under payment formulas."""
        payouts = pd.Series([50.0, 0.0, 100.0, 25.0])
        losses = pd.Series([40.0, 10.0, 95.0, 40.0])
        res = evaluate_payout_rule(payouts, losses)

        # Gaps: [+10.0, -10.0, +5.0, -15.0]
        # Absolute gaps: [10.0, 10.0, 5.0, 15.0] -> Mean = 10.0
        self.assertEqual(res["basis_risk_mape_pp"], 10.0)
        # Signed gap: (10 - 10 + 5 - 15) / 4 = -2.5
        self.assertEqual(res["signed_payout_gap_pp"], -2.5)
        # Over-payment (> 5 pp): only index 0 (+10) -> 1/4 = 25%
        self.assertEqual(res["overpayment_rate_pct"], 25.0)
        # Under-payment (< -5 pp): index 1 (-10) and index 3 (-15) -> 2/4 = 50%
        self.assertEqual(res["underpayment_rate_pct"], 50.0)


class TestConsensusContractParity(unittest.TestCase):
    """Exhaustive integration verification against real CropInsurance.sol contract."""

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
        cls.adapter.fund_risk_pool(cls.deployer_key, cls.adapter.w3.to_wei(200, "ether"))
        cls.rules_hash = compute_rules_hash()

    @classmethod
    def tearDownClass(cls):
        if cls.node_process:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(cls.node_process.pid)], capture_output=True)

    def _create_matured_policy(self, tag: str) -> int:
        w3 = self.adapter.w3
        now = self.adapter.get_block_timestamp()
        land_hash = w3.keccak(text=f"parity_{tag}_{time.time_ns()}")
        sum_insured = w3.to_wei(0.05, "ether")

        p_id, _ = self.adapter.create_policy(
            farmer_private_key=self.farmer_key,
            land_hash=land_hash,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 50,
            rules_hash=self.rules_hash,
        )
        self.adapter.advance_time(60)
        return p_id

    def test_python_vs_contract_all_64_combinations(self):
        """
        Exhaustively verifies all 64 combinations (4 x 4 x 4) of three severity tiers.
        Proves Python evaluate_python_consensus() matches CropInsurance.sol on-chain consensus.
        """
        print("\n[Exhaustive Parity Test] Testing all 64 combinations of (w, sat, soil)...")
        comb_count = 0

        for w in (0, 1, 2, 3):
            for sat in (0, 1, 2, 3):
                for soil in (0, 1, 2, 3):
                    py_tier, py_rule = evaluate_python_consensus(w, sat, soil)

                    p_id = self._create_matured_policy(f"comb_{w}_{sat}_{soil}")

                    self.adapter.submit_report(self.weather_key, p_id, OracleSource.WEATHER, SeverityTier(w))
                    self.adapter.submit_report(self.sat_key, p_id, OracleSource.SATELLITE, SeverityTier(sat))
                    self.adapter.submit_report(self.soil_key, p_id, OracleSource.SOIL, SeverityTier(soil))

                    has_con, onchain_tier = self.adapter.evaluate_consensus(p_id)

                    self.assertTrue(has_con)
                    self.assertEqual(
                        int(onchain_tier),
                        py_tier,
                        f"Mismatch for ({w}, {sat}, {soil}): Python={py_tier} ({py_rule}), OnChain={int(onchain_tier)}"
                    )
                    comb_count += 1

        self.assertEqual(comb_count, 64)
        print(f"  -> Successfully verified all {comb_count}/64 tier combinations on real EVM contract.")

    def test_python_vs_contract_two_report_cases(self):
        """
        Verifies 2-report cases against the contract:
        - 2 matching reports reach consensus immediately without 3rd report.
        - 2 disagreeing reports block settlement with ConsensusNotReached.
        """
        # Case 1: 2 agreeing reports [2, 2]
        p_id_agree = self._create_matured_policy("two_agree")
        self.adapter.submit_report(self.weather_key, p_id_agree, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE)
        self.adapter.submit_report(self.sat_key, p_id_agree, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)

        has_con_agree, winning_tier = self.adapter.evaluate_consensus(p_id_agree)
        self.assertTrue(has_con_agree)
        self.assertEqual(winning_tier, SeverityTier.TIER_2_SEVERE)

        # Can settle immediately without waiting for soil
        self.adapter.settle_policy(self.deployer_key, p_id_agree)
        pol_agree = self.adapter.get_policy(p_id_agree)
        self.assertEqual(pol_agree["finalTier"], SeverityTier.TIER_2_SEVERE)

        # Case 2: 2 disagreeing reports [1, 2]
        p_id_disagree = self._create_matured_policy("two_disagree")
        self.adapter.submit_report(self.weather_key, p_id_disagree, OracleSource.WEATHER, SeverityTier.TIER_1_MODERATE)
        self.adapter.submit_report(self.sat_key, p_id_disagree, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)

        has_con_disagree, _ = self.adapter.evaluate_consensus(p_id_disagree)
        self.assertFalse(has_con_disagree)

        # Must revert with ConsensusNotReached
        with self.assertRaises(Exception):
            self.adapter.settle_policy(self.deployer_key, p_id_disagree)


if __name__ == "__main__":
    unittest.main()
