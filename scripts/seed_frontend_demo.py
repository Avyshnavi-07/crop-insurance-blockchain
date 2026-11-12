"""
Frontend Demo Seeding Script.

Deploys CropInsurance.sol to a running local Hardhat node (http://127.0.0.1:8545),
grants all roles, funds the risk pool, and creates policies across 5 distinct lifecycle states:
  1. Policy 1: ACTIVE (future maturity date)
  2. Policy 2: AWAITING_ORACLES (matured, time advanced past end time, no reports yet)
  3. Policy 3: SETTLED (all 3 reports submitted, 50% payout claimable by farmer)
  4. Policy 4: UNDER_REVIEW (flagged via flagFraud with reason hash)
  5. Policy 5: DISPUTED (settled at 25%, farmer opened dispute, awaiting review)

Also exports:
  - Contract ABI to frontend/src/abi/CropInsurance.json
  - Contract address & configuration to frontend/src/config.json
"""

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web3 import Web3  # noqa: E402
from oracles.common import (  # noqa: E402
    DEFAULT_LOCAL_KEYS,
    compute_rules_hash,
    get_rpc_url,
)
from oracles.contract_adapter import (  # noqa: E402
    ContractAdapter,
    CropCode,
    OracleSource,
    Region,
    SeverityTier,
)


def seed_demo_environment() -> None:
    print("================================================================================")
    print("CROP INSURANCE CHAIN - FRONTEND DEMO SEEDING")
    print("================================================================================")

    rpc_url = get_rpc_url()
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print(f"\n[ERROR] Cannot connect to Ethereum node at {rpc_url}.")
        print("Please start the local Hardhat node in a separate terminal:")
        print("    npx hardhat node")
        sys.exit(1)

    print(f"[OK] Connected to Hardhat node at {rpc_url} (Chain ID: {w3.eth.chain_id})")

    deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
    farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
    weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
    sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
    soil_key = DEFAULT_LOCAL_KEYS["SOIL"]

    admin_addr = w3.eth.account.from_key(deployer_key).address
    farmer_addr = w3.eth.account.from_key(farmer_key).address
    weather_addr = w3.eth.account.from_key(weather_key).address
    sat_addr = w3.eth.account.from_key(sat_key).address
    soil_addr = w3.eth.account.from_key(soil_key).address

    adapter = ContractAdapter(rpc_url=rpc_url)

    # 1. Deploy Contract
    print("\n[1/5] Deploying CropInsurance.sol...")
    contract_addr = adapter.deploy(deployer_key, admin_address=admin_addr)
    print(f"      Deployed at: {contract_addr}")

    # 2. Grant Roles
    print("\n[2/5] Granting AccessControl Roles...")
    adapter.grant_role(deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
    adapter.grant_role(deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
    adapter.grant_role(deployer_key, "ORACLE_SOIL_ROLE", soil_addr)
    adapter.grant_role(deployer_key, "FRAUD_CHECKER_ROLE", admin_addr)
    adapter.grant_role(deployer_key, "DISPUTE_REVIEWER_ROLE", admin_addr)
    print(f"      Admin/Fraud/Reviewer: {admin_addr}")
    print(f"      Weather Oracle:       {weather_addr}")
    print(f"      Satellite Oracle:     {sat_addr}")
    print(f"      Soil Oracle:          {soil_addr}")
    print(f"      Farmer Account:       {farmer_addr}")

    # 3. Fund Risk Pool & Set Regional Risk Rates
    print("\n[3/5] Funding Risk Pool with 50.0 ETH & Configuring Regional Rates...")
    adapter.fund_risk_pool(deployer_key, w3.to_wei(50, "ether"))
    # Base = 300 bps (3.0%), Anantapur = 350 bps (6.5%), Kurnool = 250 bps (5.5%), Kadapa = 200 bps (5.0%)
    adapter.set_regional_risk_bps(deployer_key, Region.ANANTAPUR, 350)
    adapter.set_regional_risk_bps(deployer_key, Region.KURNOOL, 250)
    adapter.set_regional_risk_bps(deployer_key, Region.KADAPA, 200)

    rules_hash = compute_rules_hash()
    print(f"      Rules Hash (config/tier_rules.json): {rules_hash.hex()}")

    # 4. Create Demo Policies
    print("\n[4/5] Seeding 5 Policies in Distinct Lifecycle States...")
    now = adapter.get_block_timestamp()

    # Policy 1: ACTIVE (Matures in 30 days)
    land1 = w3.keccak(text="demo_parcel_anantapur_active_01")
    p1_id, _ = adapter.create_policy(
        farmer_private_key=farmer_key,
        land_hash=land1,
        crop=CropCode.GROUNDNUT,
        region=Region.ANANTAPUR,
        sum_insured_wei=w3.to_wei(1.0, "ether"),
        start_time=now,
        end_time=now + 86400 * 30,
        rules_hash=rules_hash,
    )
    print(f"  -> Policy 1 created (ID: {p1_id}): ACTIVE (Matures in 30 days)")

    # Policy 2: AWAITING_ORACLES (Matured 100 seconds ago, awaiting reports)
    land2 = w3.keccak(text="demo_parcel_kurnool_awaiting_02")
    p2_id, _ = adapter.create_policy(
        farmer_private_key=farmer_key,
        land_hash=land2,
        crop=CropCode.GROUNDNUT,
        region=Region.KURNOOL,
        sum_insured_wei=w3.to_wei(1.0, "ether"),
        start_time=now,
        end_time=now + 30,
        rules_hash=rules_hash,
    )
    print(f"  -> Policy 2 created (ID: {p2_id}): Pending maturity...")

    # Policy 3: SETTLED (All 3 reports submitted -> 50% payout claimable)
    land3 = w3.keccak(text="demo_parcel_kadapa_settled_03")
    p3_id, _ = adapter.create_policy(
        farmer_private_key=farmer_key,
        land_hash=land3,
        crop=CropCode.GROUNDNUT,
        region=Region.KADAPA,
        sum_insured_wei=w3.to_wei(2.0, "ether"),
        start_time=now,
        end_time=now + 30,
        rules_hash=rules_hash,
    )
    print(f"  -> Policy 3 created (ID: {p3_id}): Pending settlement...")

    # Policy 4: UNDER_REVIEW (Flagged for cadastral duplicate anomaly)
    land4 = w3.keccak(text="demo_parcel_anantapur_review_04")
    p4_id, _ = adapter.create_policy(
        farmer_private_key=farmer_key,
        land_hash=land4,
        crop=CropCode.COTTON,
        region=Region.ANANTAPUR,
        sum_insured_wei=w3.to_wei(1.5, "ether"),
        start_time=now,
        end_time=now + 30,
        rules_hash=rules_hash,
    )
    print(f"  -> Policy 4 created (ID: {p4_id}): Pending fraud flag...")

    # Policy 5: DISPUTED (Settled at 25%, farmer opened dispute)
    land5 = w3.keccak(text="demo_parcel_anantapur_disputed_05")
    p5_id, _ = adapter.create_policy(
        farmer_private_key=farmer_key,
        land_hash=land5,
        crop=CropCode.GROUNDNUT,
        region=Region.ANANTAPUR,
        sum_insured_wei=w3.to_wei(1.0, "ether"),
        start_time=now,
        end_time=now + 30,
        rules_hash=rules_hash,
    )
    print(f"  -> Policy 5 created (ID: {p5_id}): Pending dispute...")

    # Advance block time past maturity of policies 2, 3, 4, 5
    adapter.advance_time(60)
    print("      [Time Travel] Advanced EVM time by 60 seconds past season end for policies 2-5.")

    # Settle Policy 3: Weather=Tier 2, Satellite=Tier 2, Soil=Tier 1 -> Consensus Tier 2 (50% payout = 1.0 ETH)
    adapter.submit_report(weather_key, p3_id, OracleSource.WEATHER, SeverityTier.SEVERE)
    adapter.submit_report(sat_key, p3_id, OracleSource.SATELLITE, SeverityTier.SEVERE)
    adapter.submit_report(soil_key, p3_id, OracleSource.SOIL, SeverityTier.MODERATE)
    adapter.settle_policy(deployer_key, p3_id)
    print("  -> Policy 3 updated: SETTLED (Tier 2 SEVERE, Claimable Payout = 1.0 ETH)")

    # Flag Policy 4 as UNDER_REVIEW via fraud checker
    fraud_reason_hash = w3.keccak(text="Cadastral duplicate anomaly detected via spatial proximity")
    adapter.flag_fraud(deployer_key, p4_id, fraud_reason_hash)
    print(f"  -> Policy 4 updated: UNDER_REVIEW (Flagged with reason hash {fraud_reason_hash.hex()[:10]}...)")

    # Settle and Dispute Policy 5:
    adapter.submit_report(weather_key, p5_id, OracleSource.WEATHER, SeverityTier.MODERATE)
    adapter.submit_report(sat_key, p5_id, OracleSource.SATELLITE, SeverityTier.MODERATE)
    adapter.submit_report(soil_key, p5_id, OracleSource.SOIL, SeverityTier.MODERATE)
    adapter.settle_policy(deployer_key, p5_id)
    adapter.open_dispute(farmer_key, p5_id, "Localized satellite cloud cover artifact distorted vegetation index")
    print("  -> Policy 5 updated: DISPUTED (Dispute opened by farmer, awaiting admin review)")

    # 5. Export Artifacts for Frontend
    print("\n[5/5] Exporting Frontend ABI & Configuration...")
    artifact_path = PROJECT_ROOT / "artifacts" / "contracts" / "CropInsurance.sol" / "CropInsurance.json"
    abi_dir = PROJECT_ROOT / "frontend" / "src" / "abi"
    abi_dir.mkdir(parents=True, exist_ok=True)
    dest_abi = abi_dir / "CropInsurance.json"
    shutil.copyfile(artifact_path, dest_abi)
    print(f"      Copied ABI to {dest_abi}")

    config_data = {
        "contractAddress": contract_addr,
        "chainId": 31337,
        "rpcUrl": "http://127.0.0.1:8545",
        "rulesHash": rules_hash.hex(),
        "accounts": {
            "DEPLOYER_ADMIN": {
                "address": admin_addr,
                "privateKey": deployer_key,
                "roles": ["DEFAULT_ADMIN_ROLE", "FRAUD_CHECKER_ROLE", "DISPUTE_REVIEWER_ROLE"],
            },
            "FARMER": {
                "address": farmer_addr,
                "privateKey": farmer_key,
                "roles": ["FARMER"],
            },
            "ORACLE_WEATHER": {
                "address": weather_addr,
                "privateKey": weather_key,
                "roles": ["ORACLE_WEATHER_ROLE"],
            },
            "ORACLE_SATELLITE": {
                "address": sat_addr,
                "privateKey": sat_key,
                "roles": ["ORACLE_SATELLITE_ROLE"],
            },
            "ORACLE_SOIL": {
                "address": soil_addr,
                "privateKey": soil_key,
                "roles": ["ORACLE_SOIL_ROLE"],
            },
        },
        "seedPolicies": [
            {"id": p1_id, "status": "ACTIVE", "sumInsuredEth": "1.0", "district": "Anantapur"},
            {"id": p2_id, "status": "AWAITING_ORACLES", "sumInsuredEth": "1.0", "district": "Kurnool"},
            {"id": p3_id, "status": "SETTLED", "sumInsuredEth": "2.0", "district": "Kadapa", "claimableEth": "1.0"},
            {"id": p4_id, "status": "UNDER_REVIEW", "sumInsuredEth": "1.5", "district": "Anantapur"},
            {"id": p5_id, "status": "DISPUTED", "sumInsuredEth": "1.0", "district": "Anantapur"},
        ],
    }

    config_path = PROJECT_ROOT / "frontend" / "src" / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"      Wrote config to {config_path}")

    print("\n================================================================================")
    print("[SUCCESS] FRONTEND DEMO ENVIRONMENT SEEDED SUCCESSFULLY!")
    print("================================================================================")


if __name__ == "__main__":
    seed_demo_environment()
