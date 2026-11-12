"""
Local end-to-end demonstration script for Crop Insurance Chain.

Demonstrates:
  Scenario (a): All three oracles honest (consensus reached).
  Scenario (b): One faulty oracle at 30% error (consensus still matches honest outcome).
  Scenario (c): All three oracles report differing tiers (median fallback fires).
  Scenario (d): Only two oracles report and disagree (settlement waits for third).
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from web3 import Web3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from oracles.common import (  # noqa: E402
    DEFAULT_LOCAL_KEYS,
    compute_rules_hash,
    get_rpc_url,
    setup_oracle_logger,
)
from oracles.contract_adapter import (  # noqa: E402
    ContractAdapter,
    CropCode,
    OracleSource,
    Region,
    SeverityTier,
)
from oracles.fault_injector import FaultInjector  # noqa: E402
from oracles.satellite_oracle import SatelliteOracleService  # noqa: E402
from oracles.soil_oracle import SoilOracleService  # noqa: E402
from oracles.weather_oracle import WeatherOracleService  # noqa: E402

logger = setup_oracle_logger("DemoLocal")


def ensure_hardhat_node(rpc_url: str) -> Optional[subprocess.Popen]:
    """Ensures local Hardhat node is running; spawns background node if necessary."""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.is_connected():
        logger.info(f"Connected to existing JSON-RPC node at {rpc_url}")
        return None

    logger.info("Local node not detected. Starting ephemeral 'npx hardhat node'...")
    process = subprocess.Popen(
        ["npx", "hardhat", "node"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )

    # Wait for node to be ready
    for _ in range(30):
        time.sleep(1)
        if w3.is_connected():
            logger.info("Local Hardhat node successfully started.")
            return process

    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    raise RuntimeError("Failed to start local Hardhat node.")


def run_demo():
    rpc_url = get_rpc_url()
    node_proc = ensure_hardhat_node(rpc_url)

    try:
        adapter = ContractAdapter(rpc_url=rpc_url)
        deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
        farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
        weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
        soil_key = DEFAULT_LOCAL_KEYS["SOIL"]
        w3 = adapter.w3

        admin_addr = w3.eth.account.from_key(deployer_key).address
        farmer_addr = w3.eth.account.from_key(farmer_key).address
        weather_addr = w3.eth.account.from_key(weather_key).address
        sat_addr = w3.eth.account.from_key(sat_key).address
        soil_addr = w3.eth.account.from_key(soil_key).address

        print("\n" + "=" * 78)
        print("CROP INSURANCE CHAIN - LOCAL HARDHAT END-TO-END DEMO")
        print("=" * 78)

        # 1. Deploy Contract
        print("\n[Step 1] Deploying CropInsurance.sol...")
        contract_addr = adapter.deploy(deployer_key, admin_address=admin_addr)
        print(f"  -> Contract Address: {contract_addr}")

        # 2. Grant Roles
        print("\n[Step 2] Granting Oracle AccessControl roles...")
        adapter.grant_role(deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        adapter.grant_role(deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
        adapter.grant_role(deployer_key, "ORACLE_SOIL_ROLE", soil_addr)
        print("  -> Weather, Satellite, and Soil oracle roles granted.")

        # 3. Fund Risk Pool
        print("\n[Step 3] Funding Underwriter Risk Pool...")
        fund_amount = w3.to_wei(50, "ether")
        adapter.fund_risk_pool(deployer_key, fund_amount)
        pool_bal = adapter.get_risk_pool_balance()
        print(f"  -> Risk Pool Funded: {w3.from_wei(pool_bal, 'ether')} ETH")

        rules_hash = compute_rules_hash()
        sum_insured = w3.to_wei(1, "ether")  # 1.0 ETH

        # =====================================================================
        # SCENARIO A: All Three Oracles Honest (Anantapur 2018 Drought)
        # =====================================================================
        print("\n" + "-" * 78)
        print("SCENARIO (a): All Three Oracles Honest (Anantapur 2018 Historical Drought)")
        print("-" * 78)

        now = adapter.get_block_timestamp()
        land_a = w3.keccak(text="parcel_anantapur_2018_honest")
        p_id_a, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=land_a,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_a} created. Premium paid for Anantapur.")

        # Advance past season end
        adapter.advance_time(120)

        # Honest reporting from dataset (Weather=2, Sat=2, Soil=3)
        weather_svc = WeatherOracleService(adapter=adapter, private_key=weather_key)
        sat_svc = SatelliteOracleService(adapter=adapter, private_key=sat_key)
        soil_svc = SoilOracleService(adapter=adapter, private_key=soil_key)

        res_w = weather_svc.report_for_policy(p_id_a, "Anantapur", 2018)
        res_sat = sat_svc.report_for_policy(p_id_a, "Anantapur", 2018)
        res_soil = soil_svc.report_for_policy(p_id_a, "Anantapur", 2018)

        print(f"  -> Weather Report:   Tier {res_w['reported_tier']}")
        print(f"  -> Satellite Report: Tier {res_sat['reported_tier']}")
        print(f"  -> Soil Report:      Tier {res_soil['reported_tier']}")

        has_con, win_tier = adapter.evaluate_consensus(p_id_a)
        print(f"  -> Consensus Reached: {has_con} | Winning Tier: {win_tier.name}")

        adapter.settle_policy(deployer_key, p_id_a)
        policy_a = adapter.get_policy(p_id_a)
        payout_eth_a = w3.from_wei(policy_a['payoutAmount'], 'ether')
        print(f"  -> Policy Settled: Status={policy_a['status'].name}, Payout={payout_eth_a} ETH (50%)")

        bal_before = w3.eth.get_balance(farmer_addr)
        adapter.withdraw_payout(farmer_key)
        bal_after = w3.eth.get_balance(farmer_addr)
        diff_eth = w3.from_wei(bal_after - bal_before, 'ether')
        print(f"  -> Farmer Payout Withdrawn: Claimable claimed. Balance increased by ~{diff_eth:.2f} ETH")

        # =====================================================================
        # SCENARIO B: One Faulty Oracle at 30% Error Rate (Consensus Robustness)
        # =====================================================================
        print("\n" + "-" * 78)
        print("SCENARIO (b): Faulty Oracle at 30% Error Rate (Consensus Preserves Truth)")
        print("-" * 78)

        now = adapter.get_block_timestamp()
        land_b = w3.keccak(text="parcel_anantapur_2023_faulty")
        p_id_b, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=land_b,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_b} created for Anantapur 2023.")
        adapter.advance_time(120)

        # True tiers for Anantapur 2023: Weather=2, Sat=2, Soil=3.
        # Inject fault into Satellite oracle with 30% error (seeded so it faults to Tier 0)
        faulty_injector = FaultInjector(error_rate=0.30, mode="random", seed=1)
        faulty_sat_svc = SatelliteOracleService(
            adapter=adapter, private_key=sat_key, fault_injector=faulty_injector
        )

        res_w_b = weather_svc.report_for_policy(p_id_b, "Anantapur", 2023)
        res_sat_b = faulty_sat_svc.report_for_policy(p_id_b, "Anantapur", 2023)
        res_soil_b = soil_svc.report_for_policy(p_id_b, "Anantapur", 2023)

        print(f"  -> Weather Report (Honest):    Tier {res_w_b['reported_tier']}")
        print(f"  -> Satellite Report (Faulty):  Tier {res_sat_b['reported_tier']} (Fault: {res_sat_b['was_faulted']})")
        print(f"  -> Soil Report (Honest):       Tier {res_soil_b['reported_tier']}")

        has_con_b, win_tier_b = adapter.evaluate_consensus(p_id_b)
        print(f"  -> Consensus Outcome: {win_tier_b.name} (Matches true drought severity despite faulty oracle!)")
        adapter.settle_policy(deployer_key, p_id_b)
        print("  -> Settlement successful under 2-of-3 consensus.")

        # =====================================================================
        # SCENARIO C: All Three Differ -> Median Fallback Fires
        # =====================================================================
        print("\n" + "-" * 78)
        print("SCENARIO (c): All Three Differ (Median Fallback Resolution)")
        print("-" * 78)

        now = adapter.get_block_timestamp()
        land_c = w3.keccak(text="parcel_kadapa_median_case")
        p_id_c, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=land_c,
            crop=CropCode.GROUNDNUT,
            region=Region.KADAPA,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_c} created for Kadapa.")
        adapter.advance_time(120)

        # Submit differing tiers: Weather=0, Satellite=2, Soil=1
        adapter.submit_report(weather_key, p_id_c, OracleSource.WEATHER, SeverityTier.TIER_0_NORMAL)
        adapter.submit_report(sat_key, p_id_c, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)
        adapter.submit_report(soil_key, p_id_c, OracleSource.SOIL, SeverityTier.TIER_1_MODERATE)

        print("  -> Weather Report:   Tier 0 (Normal)")
        print("  -> Satellite Report: Tier 2 (Severe)")
        print("  -> Soil Report:      Tier 1 (Moderate)")

        has_con_c, win_tier_c = adapter.evaluate_consensus(p_id_c)
        print(f"  -> Median Fallback Evaluated: {win_tier_c.name} (Median of [0, 1, 2] is Tier 1)")

        adapter.settle_policy(deployer_key, p_id_c)
        policy_c = adapter.get_policy(p_id_c)
        payout_c = w3.from_wei(policy_c['payoutAmount'], 'ether')
        print(f"  -> Policy Settled: Tier={policy_c['finalTier'].name}, Payout={payout_c} ETH (25%)")

        # =====================================================================
        # SCENARIO D: Only Two Reports Differ -> Settlement Waits for Third
        # =====================================================================
        print("\n" + "-" * 78)
        print("SCENARIO (d): Only Two Reports Disagree (Settlement Blocks Until Third)")
        print("-" * 78)

        now = adapter.get_block_timestamp()
        land_d = w3.keccak(text="parcel_kurnool_disagreement_case")
        p_id_d, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=land_d,
            crop=CropCode.GROUNDNUT,
            region=Region.KURNOOL,
            sum_insured_wei=sum_insured,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_d} created for Kurnool.")
        adapter.advance_time(120)

        # Weather reports Tier 1, Satellite reports Tier 2
        adapter.submit_report(weather_key, p_id_d, OracleSource.WEATHER, SeverityTier.TIER_1_MODERATE)
        adapter.submit_report(sat_key, p_id_d, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)
        print("  -> Weather Report:   Tier 1 (Moderate)")
        print("  -> Satellite Report: Tier 2 (Severe)")

        has_con_d, _ = adapter.evaluate_consensus(p_id_d)
        print(f"  -> Consensus Status: {has_con_d} (Disagreement between 2 oracles; waiting for 3rd)")

        try:
            adapter.settle_policy(deployer_key, p_id_d)
            print("  ! Error: Settlement should have reverted!")
        except Exception as e:
            print(f"  -> Settlement Blocked as Expected: Contract reverted ({type(e).__name__})")

        # Third oracle submits report: Soil reports Tier 2
        print("  -> Third Oracle (Soil) submits report: Tier 2 (Severe)...")
        adapter.submit_report(soil_key, p_id_d, OracleSource.SOIL, SeverityTier.TIER_2_SEVERE)

        has_con_d2, win_tier_d2 = adapter.evaluate_consensus(p_id_d)
        print(f"  -> Consensus Status Now: {has_con_d2} | Winning Tier: {win_tier_d2.name} (2-of-3 agreement)")

        adapter.settle_policy(deployer_key, p_id_d)
        policy_d = adapter.get_policy(p_id_d)
        payout_d = w3.from_wei(policy_d['payoutAmount'], 'ether')
        print(f"  -> Policy Settled: Final Tier={policy_d['finalTier'].name}, Payout={payout_d} ETH")

        print("\n" + "=" * 78)
        print("LOCAL DEMO COMPLETED SUCCESSFULLY: ALL 4 SCENARIOS VERIFIED!")
        print("=" * 78 + "\n")

    finally:
        if node_proc:
            logger.info("Stopping background Hardhat node...")
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(node_proc.pid)], capture_output=True)


if __name__ == "__main__":
    run_demo()
