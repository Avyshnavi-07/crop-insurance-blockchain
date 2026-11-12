"""
Contract Adapter for CropInsurance.sol smart contract.

Isolates all Ethereum Web3.py RPC calls, transaction signing, event parsing,
and Hardhat time advancement behind a clean Python interface.
"""

from enum import IntEnum
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from eth_account import Account
from web3 import Web3
from web3.contract import Contract

ARTIFACT_PATH = (
    Path(__file__).resolve().parent.parent
    / "artifacts"
    / "contracts"
    / "CropInsurance.sol"
    / "CropInsurance.json"
)


class SeverityTier(IntEnum):
    TIER_0_NORMAL = 0
    TIER_1_MODERATE = 1
    TIER_2_SEVERE = 2
    TIER_3_CATASTROPHIC = 3


class PolicyStatus(IntEnum):
    ACTIVE = 0
    SETTLED = 1
    UNDER_REVIEW = 2
    EXPIRED = 3


class OracleSource(IntEnum):
    WEATHER = 0
    SATELLITE = 1
    SOIL = 2


class CropCode(IntEnum):
    GROUNDNUT = 0
    CHICKPEA = 1
    COTTON = 2
    RICE = 3


class Region(IntEnum):
    ANANTAPUR = 0
    KURNOOL = 1
    KADAPA = 2


class ContractAdapter:
    """Encapsulates Web3 interactions with CropInsurance.sol."""

    def __init__(
        self,
        rpc_url: str = "http://127.0.0.1:8545",
        contract_address: Optional[str] = None,
        artifact_path: Path = ARTIFACT_PATH,
    ):
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.artifact_path = artifact_path

        if not self.artifact_path.exists():
            raise FileNotFoundError(
                f"Contract artifact not found at {self.artifact_path}. "
                "Please run 'npx hardhat compile' first."
            )

        with open(self.artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)

        self.abi = artifact["abi"]
        self.bytecode = artifact.get("bytecode", "")

        self.contract: Optional[Contract] = None
        if contract_address:
            self.contract_address = self.w3.to_checksum_address(contract_address)
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        else:
            self.contract_address = None

    def is_connected(self) -> bool:
        """Returns True if JSON-RPC node is reachable."""
        return self.w3.is_connected()

    # =========================================================================
    # Deployment & Node Helpers
    # =========================================================================
    def deploy(self, deployer_private_key: str, admin_address: Optional[str] = None) -> str:
        """Deploys a new CropInsurance contract instance to the network."""
        account = Account.from_key(deployer_private_key)
        admin = self.w3.to_checksum_address(admin_address or account.address)

        contract_factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        nonce = self.w3.eth.get_transaction_count(account.address, "pending")
        chain_id = self.w3.eth.chain_id

        tx = contract_factory.constructor(admin).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 4000000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": chain_id,
        })

        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            raise RuntimeError("Contract deployment transaction failed.")

        self.contract_address = self.w3.to_checksum_address(receipt.contractAddress)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        return self.contract_address

    def set_contract_address(self, address: str):
        """Sets the active contract address."""
        self.contract_address = self.w3.to_checksum_address(address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)

    def advance_time(self, seconds: int):
        """Advances Hardhat node EVM time and mines a new block."""
        self.w3.provider.make_request("evm_increaseTime", [seconds])
        self.w3.provider.make_request("evm_mine", [])

    def get_block_timestamp(self) -> int:
        """Returns current block timestamp on the connected EVM."""
        latest_block = self.w3.eth.get_block("latest")
        return int(latest_block["timestamp"])

    # =========================================================================
    # Transaction Helper
    # =========================================================================
    def _send_tx(self, private_key: str, func_call: Any, value: int = 0) -> Dict:
        """Signs and sends a transaction with automatic gas calculation."""
        if not self.contract:
            raise RuntimeError("Contract address not set. Deploy or call set_contract_address().")

        account = Account.from_key(private_key)
        nonce = self.w3.eth.get_transaction_count(account.address, "pending")
        chain_id = self.w3.eth.chain_id

        tx_params = {
            "from": account.address,
            "nonce": nonce,
            "value": value,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": chain_id,
        }

        try:
            estimated_gas = func_call.estimate_gas(tx_params)
            tx_params["gas"] = int(estimated_gas * 1.25)
        except Exception:
            tx_params["gas"] = 600000

        tx = func_call.build_transaction(tx_params)
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            raise RuntimeError(f"Transaction failed (status=0). Hash: {tx_hash.hex()}")

        return receipt

    # =========================================================================
    # Role Management
    # =========================================================================
    def get_role_bytes(self, role_name: str) -> bytes:
        """Returns keccak256 hash of role name string."""
        if role_name == "DEFAULT_ADMIN_ROLE":
            return b"\x00" * 32
        return self.w3.keccak(text=role_name)

    def grant_role(self, admin_private_key: str, role_name_or_bytes: Union[str, bytes], account_address: str):
        """Grants access control role to an account."""
        if isinstance(role_name_or_bytes, str):
            role_bytes = self.get_role_bytes(role_name_or_bytes)
        else:
            role_bytes = role_name_or_bytes

        target_addr = self.w3.to_checksum_address(account_address)
        func = self.contract.functions.grantRole(role_bytes, target_addr)
        return self._send_tx(admin_private_key, func)

    def has_role(self, role_name_or_bytes: Union[str, bytes], account_address: str) -> bool:
        """Checks if account holds given role."""
        if isinstance(role_name_or_bytes, str):
            role_bytes = self.get_role_bytes(role_name_or_bytes)
        else:
            role_bytes = role_name_or_bytes
        target_addr = self.w3.to_checksum_address(account_address)
        return self.contract.functions.hasRole(role_bytes, target_addr).call()

    # =========================================================================
    # Pool & Policy Management
    # =========================================================================
    def fund_risk_pool(self, funder_private_key: str, amount_wei: int):
        """Injects funds into the risk pool."""
        func = self.contract.functions.fundRiskPool()
        return self._send_tx(funder_private_key, func, value=amount_wei)

    def calculate_premium(self, sum_insured_wei: int, region: Union[Region, int]) -> int:
        """Queries on-chain premium required for a given sum insured and region."""
        return self.contract.functions.calculatePremium(sum_insured_wei, int(region)).call()

    def create_policy(
        self,
        farmer_private_key: str,
        land_hash: Union[bytes, str],
        crop: Union[CropCode, int],
        region: Union[Region, int],
        sum_insured_wei: int,
        start_time: int,
        end_time: int,
        rules_hash: Union[bytes, str],
    ) -> Tuple[int, Dict]:
        """
        Purchases crop insurance policy, paying required premium.
        Extracts and returns (policy_id, receipt).
        """
        if isinstance(land_hash, str):
            if land_hash.startswith("0x"):
                b_land = bytes.fromhex(land_hash[2:])
            else:
                b_land = self.w3.keccak(text=land_hash)
        else:
            b_land = land_hash

        if isinstance(rules_hash, str):
            if rules_hash.startswith("0x"):
                b_rules = bytes.fromhex(rules_hash[2:])
            else:
                b_rules = self.w3.keccak(text=rules_hash)
        else:
            b_rules = rules_hash

        premium = self.calculate_premium(sum_insured_wei, region)
        func = self.contract.functions.createPolicy(
            b_land,
            int(crop),
            int(region),
            sum_insured_wei,
            start_time,
            end_time,
            b_rules,
        )

        receipt = self._send_tx(farmer_private_key, func, value=premium)

        # Extract policyId from PolicyCreated event
        logs = self.contract.events.PolicyCreated().process_receipt(receipt)
        if not logs:
            raise RuntimeError("PolicyCreated event not found in transaction receipt.")

        policy_id = logs[0]["args"]["policyId"]
        return policy_id, receipt

    # =========================================================================
    # Oracle Submissions & Consensus
    # =========================================================================
    def submit_report(
        self,
        oracle_private_key: str,
        policy_id: int,
        source: Union[OracleSource, int],
        tier: Union[SeverityTier, int],
    ) -> Dict:
        """Submits severity tier report from authorized oracle account."""
        func = self.contract.functions.submitReport(policy_id, int(source), int(tier))
        return self._send_tx(oracle_private_key, func)

    def settle_policy(self, caller_private_key: str, policy_id: int) -> Dict:
        """Executes 2-of-3 consensus evaluation and settles the policy."""
        func = self.contract.functions.settlePolicy(policy_id)
        return self._send_tx(caller_private_key, func)

    def withdraw_payout(self, farmer_private_key: str) -> Dict:
        """Pulls claimable payout balance for the caller farmer."""
        func = self.contract.functions.withdrawPayout()
        return self._send_tx(farmer_private_key, func)

    # =========================================================================
    # Fraud Hook & Dispute Path
    # =========================================================================
    def flag_fraud(
        self,
        checker_private_key: str,
        policy_id: int,
        reason_hash: Union[bytes, str],
    ) -> Dict:
        """Flags suspicious policy, halting settlement and setting UNDER_REVIEW."""
        if isinstance(reason_hash, str):
            if reason_hash.startswith("0x"):
                b_reason = bytes.fromhex(reason_hash[2:])
            else:
                b_reason = self.w3.keccak(text=reason_hash)
        else:
            b_reason = reason_hash

        func = self.contract.functions.flagFraud(policy_id, b_reason)
        return self._send_tx(checker_private_key, func)

    def open_dispute(self, farmer_private_key: str, policy_id: int) -> Dict:
        """Opens dispute within 7 days of settlement."""
        func = self.contract.functions.openDispute(policy_id)
        return self._send_tx(farmer_private_key, func)

    def resolve_dispute(
        self,
        reviewer_private_key: str,
        policy_id: int,
        override_tier: Union[SeverityTier, int],
        reason_hash: Union[bytes, str],
    ) -> Dict:
        """Resolves dispute with adjusted tier and payout delta."""
        if isinstance(reason_hash, str):
            if reason_hash.startswith("0x"):
                b_reason = bytes.fromhex(reason_hash[2:])
            else:
                b_reason = self.w3.keccak(text=reason_hash)
        else:
            b_reason = reason_hash

        func = self.contract.functions.resolveDispute(policy_id, int(override_tier), b_reason)
        return self._send_tx(reviewer_private_key, func)

    def escalate_timeout(self, admin_private_key: str, policy_id: int) -> Dict:
        """Escalates stalled policy to UNDER_REVIEW after 14-day grace period."""
        func = self.contract.functions.escalateTimeout(policy_id)
        return self._send_tx(admin_private_key, func)

    # =========================================================================
    # View State Queries
    # =========================================================================
    def get_policy(self, policy_id: int) -> Dict[str, Any]:
        """Returns full Policy struct fields."""
        data = self.contract.functions.policies(policy_id).call()
        return {
            "id": data[0],
            "farmer": data[1],
            "landHash": data[2].hex() if isinstance(data[2], bytes) else data[2],
            "crop": CropCode(data[3]),
            "region": Region(data[4]),
            "sumInsured": data[5],
            "premium": data[6],
            "startTime": data[7],
            "endTime": data[8],
            "status": PolicyStatus(data[9]),
            "rulesHash": data[10].hex() if isinstance(data[10], bytes) else data[10],
            "finalTier": SeverityTier(data[11]),
            "payoutAmount": data[12],
            "settledAt": data[13],
        }

    def evaluate_consensus(self, policy_id: int) -> Tuple[bool, SeverityTier]:
        """Evaluates on-chain consensus state for a policy."""
        has_consensus, winning_tier = self.contract.functions.evaluateConsensus(policy_id).call()
        return has_consensus, SeverityTier(winning_tier)

    def get_oracle_reports_summary(self, policy_id: int) -> Dict[str, Any]:
        """Queries count and submitted reports across the three sources."""
        count, reports, sources = self.contract.functions.getOracleReportsSummary(policy_id).call()
        summary = {
            "count": count,
            "reports": {},
        }
        for report, source_code in zip(reports, sources):
            src_name = OracleSource(source_code).name
            summary["reports"][src_name] = {
                "submitted": report[0],
                "tier": SeverityTier(report[1]),
                "timestamp": report[2],
            }
        return summary

    def get_claimable_balance(self, address: str) -> int:
        """Returns claimable payout balance in wei for an address."""
        c_addr = self.w3.to_checksum_address(address)
        return self.contract.functions.claimableBalance(c_addr).call()

    def get_risk_pool_balance(self) -> int:
        """Returns current liquid risk pool balance in wei."""
        return self.contract.functions.riskPoolBalance().call()

    def get_reserved_exposure(self) -> int:
        """Returns total reserved worst-case exposure in wei."""
        return self.contract.functions.reservedExposure().call()
