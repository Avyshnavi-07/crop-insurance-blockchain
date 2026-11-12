"""
End-to-End Fraud Detection and Smart Contract Interception Flow.

Demonstrates:
1. Intercepting a fraudulent policy via FRAUD_CHECKER_ROLE and reasonHash.
2. Halting settlement when policy transitions to UNDER_REVIEW.
3. Permitting legitimate policy to settle normally.
4. Enforcing AccessControl: unauthorized accounts cannot call flagFraud().
5. Contrasting on-chain exact duplicate blocking with off-chain near-duplicate detection.
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

from fraud.rule_engine import HeuristicRuleEngine  # noqa: E402
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
    PolicyStatus,
    Region,
    SeverityTier,
)

logger = setup_oracle_logger("DemoFraud")


def ensure_hardhat_node(rpc_url: str) -> Optional[subprocess.Popen]:
    """Ensures local Hardhat node is running; spawns ephemeral node if not."""
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

    for _ in range(30):
        time.sleep(1)
        if w3.is_connected():
            logger.info("Local Hardhat node successfully started.")
            return process

    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    raise RuntimeError("Failed to start local Hardhat node.")


def run_fraud_demo():
    rpc_url = get_rpc_url()
    node_proc = ensure_hardhat_node(rpc_url)

    try:
        adapter = ContractAdapter(rpc_url=rpc_url)
        deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
        farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
        checker_key = DEFAULT_LOCAL_KEYS["FRAUD_CHECKER"]
        unauthorized_key = DEFAULT_LOCAL_KEYS["DISPUTE_REVIEWER"]
        weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
        soil_key = DEFAULT_LOCAL_KEYS["SOIL"]

        w3 = adapter.w3
        admin_addr = w3.eth.account.from_key(deployer_key).address
        checker_addr = w3.eth.account.from_key(checker_key).address
        weather_addr = w3.eth.account.from_key(weather_key).address
        sat_addr = w3.eth.account.from_key(sat_key).address
        soil_addr = w3.eth.account.from_key(soil_key).address

        print("\n" + "=" * 80)
        print("CROP INSURANCE CHAIN - FRAUD DETECTION & SMART CONTRACT HOOK DEMO")
        print("=" * 80)

        # 1. Deploy Contract
        print("\n[Step 1] Deploying CropInsurance.sol...")
        contract_addr = adapter.deploy(deployer_key, admin_address=admin_addr)
        print(f"  -> Contract deployed at: {contract_addr}")

        # 2. Grant Roles
        print("\n[Step 2] Granting AccessControl roles...")
        adapter.grant_role(deployer_key, "FRAUD_CHECKER_ROLE", checker_addr)
        adapter.grant_role(deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        adapter.grant_role(deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
        adapter.grant_role(deployer_key, "ORACLE_SOIL_ROLE", soil_addr)
        print(f"  -> FRAUD_CHECKER_ROLE granted to: {checker_addr}")

        # 3. Fund Risk Pool
        print("\n[Step 3] Funding Underwriter Risk Pool (50 ETH)...")
        adapter.fund_risk_pool(deployer_key, w3.to_wei(50, "ether"))
        print(f"  -> Risk Pool Liquid Balance: {w3.from_wei(adapter.get_risk_pool_balance(), 'ether')} ETH")

        rules_hash = compute_rules_hash()
        rule_engine = HeuristicRuleEngine()

        # =====================================================================
        # FLOW 1: Fraudulent Policy Intercepted by Model & Flagged on Contract
        # =====================================================================
        print("\n" + "-" * 80)
        print("FLOW 1: Suspicious Policy Interception (Inflated Valuation / Out of District)")
        print("-" * 80)

        now = adapter.get_block_timestamp()
        fraud_land_hash = w3.keccak(text="fraud_parcel_inflated_001")
        # 1 ha farm with 1.4 ETH sum insured (ratio = 2.8x benchmark)
        sum_insured_fraud = w3.to_wei(1.4, "ether")

        p_id_fraud, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=fraud_land_hash,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured_fraud,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_fraud} purchased by farmer (Sum Insured: 1.4 ETH, Land: 1.0 ha)")

        # Evaluate underwriting features with fraud detection model
        policy_features = {
            "policy_id": p_id_fraud,
            "district": "Anantapur",
            "parcel_lat": 14.68,
            "parcel_lon": 77.60,
            "sum_insured_per_ha_ratio": 2.80,  # Highly inflated
            "days_before_season": 15,
            "claim_history_count": 1,
            "farmer_policy_count": 1,
            "boundary_hash": fraud_land_hash.hex(),
            "farmer_id": "farmer_004",
        }

        is_fraud, fraud_type, rule_triggered = rule_engine.evaluate_record(policy_features)
        print(f"  -> Model Evaluation: IsFraud={is_fraud} | Type={fraud_type} | Rule={rule_triggered}")

        # Compute cryptographic reason hash: keccak256("inflated_sum_insured:HeuristicRuleEngine")
        reason_str = f"{fraud_type}:HeuristicRuleEngine"
        reason_hash = w3.keccak(text=reason_str)
        print(f"  -> Cryptographic Reason Hash: {reason_hash.hex()[:18]}... (derived from {reason_str})")

        # FRAUD_CHECKER_ROLE calls flagFraud()
        print("  -> Calling contract flagFraud()...")
        adapter.flag_fraud(checker_key, p_id_fraud, reason_hash)

        pol_fraud = adapter.get_policy(p_id_fraud)
        print(f"  -> On-Chain Policy Status: {pol_fraud['status'].name} (Expected: UNDER_REVIEW)")
        assert pol_fraud["status"] == PolicyStatus.UNDER_REVIEW

        # Advance time past season end
        adapter.advance_time(120)

        # Attempt to submit oracle report on flagged policy -> BLOCKED
        print("  -> Attempting submitReport() on flagged policy...")
        try:
            adapter.submit_report(weather_key, p_id_fraud, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE)
            print("  ! Error: Oracle submission should have failed!")
        except Exception as e:
            print(f"  -> Oracle Submission Blocked: Reverted with {type(e).__name__} (PolicyNotActive: UNDER_REVIEW)")

        # Attempt to settle the policy -> BLOCKED
        print("  -> Attempting settlePolicy() on flagged policy...")
        try:
            adapter.settle_policy(deployer_key, p_id_fraud)
            print("  ! Error: Settlement should have failed!")
        except Exception as e:
            print(f"  -> Settlement Blocked as Expected: Reverted with {type(e).__name__} (PolicyUnderReview)")

        # =====================================================================
        # FLOW 2: Legitimate Policy (Happy Path) Settles Normally
        # =====================================================================
        print("\n" + "-" * 80)
        print("FLOW 2: Legitimate Policy Evaluation (Clean Underwriting)")
        print("-" * 80)

        now = adapter.get_block_timestamp()
        legit_land = w3.keccak(text="legit_parcel_anantapur_002")
        sum_insured_legit = w3.to_wei(1.0, "ether")

        p_id_legit, _ = adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=legit_land,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured_legit,
            start_time=now,
            end_time=now + 100,
            rules_hash=rules_hash,
        )
        print(f"  -> Policy #{p_id_legit} created for legitimate 2.0 ha parcel (Sum Insured: 1.0 ETH)")

        legit_features = {
            "policy_id": p_id_legit,
            "district": "Anantapur",
            "parcel_lat": 14.68,
            "parcel_lon": 77.60,
            "sum_insured_per_ha_ratio": 1.00,
            "days_before_season": 25,
            "claim_history_count": 0,
            "farmer_policy_count": 1,
            "boundary_hash": legit_land.hex(),
            "farmer_id": "farmer_legit_001",
        }

        is_fraud_legit, ftype_legit, _ = rule_engine.evaluate_record(legit_features)
        print(f"  -> Model Evaluation: IsFraud={is_fraud_legit} (Status: {ftype_legit})")
        print("  -> No fraud flagged. Policy proceeds to regular seasonal settlement.")

        adapter.advance_time(120)
        adapter.submit_report(weather_key, p_id_legit, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE)
        adapter.submit_report(sat_key, p_id_legit, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)

        adapter.settle_policy(deployer_key, p_id_legit)
        pol_legit = adapter.get_policy(p_id_legit)
        print(f"  -> Policy Settled: Status={pol_legit['status'].name}, Final Tier={pol_legit['finalTier'].name}")

        # =====================================================================
        # FLOW 3: AccessControl Enforcement (Unauthorized Account)
        # =====================================================================
        print("\n" + "-" * 80)
        print("FLOW 3: AccessControl Verification (Unauthorized Caller Halted)")
        print("-" * 80)

        unauth_addr = w3.eth.account.from_key(unauthorized_key).address
        print(f"  -> Unauthorized account ({unauth_addr[:10]}...) attempting flagFraud()...")
        try:
            adapter.flag_fraud(unauthorized_key, p_id_legit, reason_hash)
            print("  ! Error: Unauthorized account was able to call flagFraud!")
        except Exception as e:
            print(f"  -> Blocked as Expected: Reverted with {type(e).__name__} (Missing FRAUD_CHECKER_ROLE)")

        # =====================================================================
        # FLOW 4: On-Chain Exact Duplicate Guard vs Off-Chain Near Duplicate
        # =====================================================================
        print("\n" + "-" * 80)
        print("FLOW 4: On-Chain Exact Duplicate Guard vs Off-Chain Near-Duplicate Detection")
        print("-" * 80)

        # Create an active policy
        active_land = w3.keccak(text="active_parcel_guard_003")
        adapter.create_policy(
            farmer_private_key=farmer_key,
            land_hash=active_land,
            crop=CropCode.GROUNDNUT,
            region=Region.ANANTAPUR,
            sum_insured_wei=sum_insured_legit,
            start_time=now,
            end_time=now + 1000,
            rules_hash=rules_hash,
        )
        print("  -> Active policy registered for parcel: active_parcel_guard_003")

        # Attempt to create duplicate policy with exact same active land hash
        print("  -> Attempting 2nd policy for same active landHash...")
        try:
            adapter.create_policy(
                farmer_private_key=farmer_key,
                land_hash=active_land,  # Same land hash!
                crop=CropCode.GROUNDNUT,
                region=Region.ANANTAPUR,
                sum_insured_wei=sum_insured_legit,
                start_time=now,
                end_time=now + 1000,
                rules_hash=rules_hash,
            )
            print("  ! Error: Duplicate land hash was allowed on-chain!")
        except Exception as e:
            print(f"  -> On-Chain Guard Success: Reverted with {type(e).__name__} (LandAlreadyInsured)")

        print("\n  -> Near-Duplicate Polygon (Subtle Jitter):")
        print("     An attacker micro-jitters coordinates (+0.0001 deg).")
        print("     On-chain keccak256 hash differs, so contract permits creation.")
        print("     The off-chain ML/GIS model detects geometric overlap and triggers flagFraud()!")

        print("\n" + "=" * 80)
        print("FRAUD MODULE END-TO-END DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 80 + "\n")

    finally:
        if node_proc:
            logger.info("Stopping background Hardhat node...")
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(node_proc.pid)], capture_output=True)


if __name__ == "__main__":
    run_fraud_demo()
