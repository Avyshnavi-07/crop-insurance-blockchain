"""
Common utilities, cryptographic helpers, and dataset loaders for oracle services.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict
import pandas as pd
from web3 import Web3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "tier_rules.json"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "dataset.csv"

# Hardhat default well-known test keys for local development (Accounts #0 to #6)
DEFAULT_LOCAL_KEYS = {
    "DEPLOYER": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "WEATHER": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "SATELLITE": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
    "SOIL": "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
    "FARMER": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
    "DISPUTE_REVIEWER": "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba",
    "FRAUD_CHECKER": "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e",
}


def setup_oracle_logger(name: str) -> logging.Logger:
    """Configures a standardized console logger for oracle daemons."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def compute_rules_hash(config_file: Path = CONFIG_PATH) -> bytes:
    """
    Computes keccak256 hash of the tier_rules.json file content.
    This exact hash is committed on-chain at policy creation.
    """
    if not config_file.exists():
        raise FileNotFoundError(f"Rules configuration file not found at {config_file}")

    with open(config_file, "rb") as f:
        content = f.read()

    return Web3.keccak(content)


def load_processed_dataset(dataset_file: Path = DATASET_PATH) -> pd.DataFrame:
    """Loads processed seasonal crop insurance dataset."""
    if not dataset_file.exists():
        raise FileNotFoundError(
            f"Dataset not found at {dataset_file}. Run 'python build_dataset.py' first."
        )
    return pd.read_csv(dataset_file)


def get_district_year_metrics(
    district: str, year: int, dataset_file: Path = DATASET_PATH
) -> Dict[str, Any]:
    """Retrieves single seasonal record by district and year."""
    df = load_processed_dataset(dataset_file)
    matches = df[(df["district"] == district) & (df["year"] == year)]
    if matches.empty:
        raise KeyError(f"No record found for district='{district}', year={year}")
    return matches.iloc[0].to_dict()


def get_oracle_private_key(source_name: str) -> str:
    """
    Retrieves private key for specified oracle source from environment,
    falling back to known local test keys.
    """
    key_env_var = f"ORACLE_{source_name.upper()}_KEY"
    env_val = os.getenv(key_env_var)
    if env_val and not env_val.startswith("0x000000000000000000000000000000000000000000000000000000000000000"):
        return env_val
    return DEFAULT_LOCAL_KEYS.get(source_name.upper(), DEFAULT_LOCAL_KEYS["WEATHER"])


def get_deployer_key() -> str:
    """Returns deployer private key."""
    env_val = os.getenv("DEPLOYER_PRIVATE_KEY")
    if env_val and not env_val.startswith("0x000000000000000000000000000000000000000000000000000000000000000"):
        return env_val
    return DEFAULT_LOCAL_KEYS["DEPLOYER"]


def get_rpc_url() -> str:
    """Returns JSON-RPC URL from environment or local default."""
    local_url = os.getenv("LOCAL_RPC_URL")
    if local_url:
        return local_url
    sepolia_url = os.getenv("SEPOLIA_RPC_URL")
    if sepolia_url and "YOUR_ALCHEMY_KEY" not in sepolia_url and "YOUR_INFURA_KEY" not in sepolia_url:
        return sepolia_url
    return "http://127.0.0.1:8545"
