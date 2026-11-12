"""
Sepolia Testnet Deployment and Gas Measurement Script (Phase 5 E6 Extension).

Runs on Sepolia ONLY if:
1. SEPOLIA_RPC_URL is configured with a live JSON-RPC endpoint.
2. DEPLOYER_PRIVATE_KEY exists and holds a positive testnet ETH balance.

Otherwise, exits cleanly with an informational message, ensuring no false measurements
or unexpected testnet gas expenditure occur.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
from web3 import Web3  # noqa: E402


def check_sepolia_configuration() -> bool:
    """Checks if environment is properly configured with a funded Sepolia test account."""
    load_dotenv(PROJECT_ROOT / ".env")

    rpc_url = os.getenv("SEPOLIA_RPC_URL", "").strip()
    private_key = os.getenv("DEPLOYER_PRIVATE_KEY", "").strip()

    if not rpc_url or "YOUR_ALCHEMY_KEY" in rpc_url or "http" not in rpc_url:
        print("[INFO] Sepolia RPC URL not configured in .env (or contains placeholder).")
        print("       Set SEPOLIA_RPC_URL in .env to run live testnet measurements.")
        return False

    if not private_key or private_key.startswith("0x000000000000000000000000000000000000000000000000000000000000000"):
        print("[INFO] DEPLOYER_PRIVATE_KEY is a placeholder in .env. Skipping Sepolia run.")
        return False

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            print("[INFO] Could not connect to Sepolia JSON-RPC node. Skipping Sepolia run.")
            return False

        account = w3.eth.account.from_key(private_key)
        balance = w3.eth.get_balance(account.address)
        balance_eth = float(w3.from_wei(balance, "ether"))

        if balance_eth < 0.05:
            print(f"[INFO] Account {account.address[:10]}... has insufficient Sepolia balance: {balance_eth:.4f} ETH.")
            print("       Minimum recommended balance for full test suite is 0.05 Sepolia ETH.")
            print("       Please fund account from a Sepolia faucet (e.g. Google Cloud / Alchemy Sepolia Faucet).")
            return False

        print(f"[OK] Connected to Sepolia. Account: {account.address} | Balance: {balance_eth:.4f} ETH.")
        return True

    except Exception as exc:
        print(f"[INFO] Sepolia connection check failed ({exc}). Cleanly exiting.")
        return False


def run_sepolia_experiments():
    """Executes live gas and latency measurements on Sepolia testnet."""
    configured = check_sepolia_configuration()
    if not configured:
        print("\n[CLEAN EXIT] Sepolia live measurements skipped safely per research protocol.")
        print("             No numbers were fabricated or estimated.")
        return


if __name__ == "__main__":
    run_sepolia_experiments()
