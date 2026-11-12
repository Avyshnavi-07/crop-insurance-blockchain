"""
Experiment E6: Smart Contract Gas Consumption and Transaction Confirmation Latency.

Evaluates empirical on-chain gas costs and confirmation latencies across >=30 repetitions
for all core smart contract state-transition functions:
1. createPolicy (fresh unique parcel polygon)
2. submitReport (oracle submission)
3. settlePolicy (2-of-3 consensus path)
4. settlePolicy (median fallback path)
5. withdrawPayout (pull-based payout withdrawal)
6. flagFraud (underwriting security freeze)
7. openDispute (post-settlement farmer dispute)
8. resolveDispute (reviewer adjudication)

Compares empirical measurements against hardhat-gas-reporter baseline (results/gas-report.txt).
Note: Local transaction latency represents simulated EVM RPC processing time.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from web3 import Web3  # noqa: E402

from experiments.common import (  # noqa: E402
    CB_PALETTE,
    RESULTS_DIR,
    get_metadata,
    setup_matplotlib_style,
)
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

logger = setup_oracle_logger("ExpE6")

GAS_REPORT_BASELINES = {
    "createPolicy": 276371,
    "submitReport": 75749,
    "settlePolicy (2-of-3)": 165555,
    "settlePolicy (Median)": 165555,
    "withdrawPayout": 32394,
    "flagFraud": 48593,
    "openDispute": 81584,
    "resolveDispute": 104429,
}


def ensure_hardhat_node(rpc_url: str) -> Optional[subprocess.Popen]:
    """Ensures local Hardhat node is running; spawns ephemeral node if needed."""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.is_connected():
        return None

    proc = subprocess.Popen(
        ["npx", "hardhat", "node"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )
    for _ in range(30):
        time.sleep(1)
        if w3.is_connected():
            return proc

    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    raise RuntimeError("Failed to start local Hardhat node for E6.")


def run_experiment_e6(n_runs: int = 30, seed: int = 42) -> Tuple[pd.DataFrame, Path, Path]:
    """
    Executes Experiment E6 with n_runs >= 30 per function on fresh policies.
    """
    rpc_url = get_rpc_url()
    node_proc = ensure_hardhat_node(rpc_url)

    try:
        adapter = ContractAdapter(rpc_url=rpc_url)
        w3 = adapter.w3

        deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
        farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
        checker_key = DEFAULT_LOCAL_KEYS["FRAUD_CHECKER"]
        reviewer_key = DEFAULT_LOCAL_KEYS["DISPUTE_REVIEWER"]
        weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
        soil_key = DEFAULT_LOCAL_KEYS["SOIL"]

        admin_addr = w3.eth.account.from_key(deployer_key).address
        checker_addr = w3.eth.account.from_key(checker_key).address
        reviewer_addr = w3.eth.account.from_key(reviewer_key).address
        weather_addr = w3.eth.account.from_key(weather_key).address
        sat_addr = w3.eth.account.from_key(sat_key).address
        soil_addr = w3.eth.account.from_key(soil_key).address

        adapter.deploy(deployer_key, admin_address=admin_addr)
        adapter.grant_role(deployer_key, "FRAUD_CHECKER_ROLE", checker_addr)
        adapter.grant_role(deployer_key, "DISPUTE_REVIEWER_ROLE", reviewer_addr)
        adapter.grant_role(deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        adapter.grant_role(deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
        adapter.grant_role(deployer_key, "ORACLE_SOIL_ROLE", soil_addr)
        adapter.fund_risk_pool(deployer_key, w3.to_wei(100, "ether"))
        rules_hash = compute_rules_hash()

        measurements: Dict[str, Dict[str, List[float]]] = {
            "createPolicy": {"gas": [], "latency_ms": []},
            "submitReport": {"gas": [], "latency_ms": []},
            "settlePolicy (2-of-3)": {"gas": [], "latency_ms": []},
            "settlePolicy (Median)": {"gas": [], "latency_ms": []},
            "withdrawPayout": {"gas": [], "latency_ms": []},
            "flagFraud": {"gas": [], "latency_ms": []},
            "openDispute": {"gas": [], "latency_ms": []},
            "resolveDispute": {"gas": [], "latency_ms": []},
        }

        print(f"Executing Gas & Latency benchmark ({n_runs} runs per function)...")

        for run_i in range(n_runs):
            if (run_i + 1) % 10 == 0:
                print(f"  -> Completed {run_i + 1}/{n_runs} repetitions...")

            # 1. createPolicy
            now = adapter.get_block_timestamp()
            land_hash = w3.keccak(text=f"gas_test_{run_i}_{time.time_ns()}")
            sum_insured = w3.to_wei(0.1, "ether")

            t0 = time.perf_counter()
            p_id, rcpt_create = adapter.create_policy(
                farmer_private_key=farmer_key,
                land_hash=land_hash,
                crop=CropCode.GROUNDNUT,
                region=Region.ANANTAPUR,
                sum_insured_wei=sum_insured,
                start_time=now,
                end_time=now + 50,
                rules_hash=rules_hash,
            )
            lat_create = (time.perf_counter() - t0) * 1000.0
            measurements["createPolicy"]["gas"].append(rcpt_create["gasUsed"])
            measurements["createPolicy"]["latency_ms"].append(lat_create)

            # Advance past season end
            adapter.advance_time(60)

            # 2. submitReport
            t0 = time.perf_counter()
            rcpt_submit = adapter.submit_report(
                weather_key, p_id, OracleSource.WEATHER, SeverityTier.TIER_2_SEVERE
            )
            lat_submit = (time.perf_counter() - t0) * 1000.0
            measurements["submitReport"]["gas"].append(rcpt_submit["gasUsed"])
            measurements["submitReport"]["latency_ms"].append(lat_submit)

            # 3. settlePolicy (2-of-3 path)
            adapter.submit_report(sat_key, p_id, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)
            t0 = time.perf_counter()
            rcpt_settle_2of3 = adapter.settle_policy(deployer_key, p_id)
            lat_settle_2of3 = (time.perf_counter() - t0) * 1000.0
            measurements["settlePolicy (2-of-3)"]["gas"].append(rcpt_settle_2of3["gasUsed"])
            measurements["settlePolicy (2-of-3)"]["latency_ms"].append(lat_settle_2of3)

            # 4. withdrawPayout
            t0 = time.perf_counter()
            rcpt_withdraw = adapter.withdraw_payout(farmer_key)
            lat_withdraw = (time.perf_counter() - t0) * 1000.0
            measurements["withdrawPayout"]["gas"].append(rcpt_withdraw["gasUsed"])
            measurements["withdrawPayout"]["latency_ms"].append(lat_withdraw)

            # 5. openDispute & resolveDispute (on p_id)
            t0 = time.perf_counter()
            rcpt_dispute = adapter.open_dispute(farmer_key, p_id)
            lat_dispute = (time.perf_counter() - t0) * 1000.0
            measurements["openDispute"]["gas"].append(rcpt_dispute["gasUsed"])
            measurements["openDispute"]["latency_ms"].append(lat_dispute)

            reason_d = w3.keccak(text=f"dispute_reason_{run_i}")
            t0 = time.perf_counter()
            rcpt_resolve = adapter.resolve_dispute(
                reviewer_key, p_id, SeverityTier.TIER_3_CATASTROPHIC, reason_d
            )
            lat_resolve = (time.perf_counter() - t0) * 1000.0
            measurements["resolveDispute"]["gas"].append(rcpt_resolve["gasUsed"])
            measurements["resolveDispute"]["latency_ms"].append(lat_resolve)

            # 6. settlePolicy (Median path on fresh policy)
            now2 = adapter.get_block_timestamp()
            land_hash_med = w3.keccak(text=f"gas_median_{run_i}_{time.time_ns()}")
            p_id_med, _ = adapter.create_policy(
                farmer_private_key=farmer_key,
                land_hash=land_hash_med,
                crop=CropCode.GROUNDNUT,
                region=Region.KURNOOL,
                sum_insured_wei=sum_insured,
                start_time=now2,
                end_time=now2 + 50,
                rules_hash=rules_hash,
            )
            adapter.advance_time(60)
            adapter.submit_report(weather_key, p_id_med, OracleSource.WEATHER, SeverityTier.TIER_0_NORMAL)
            adapter.submit_report(sat_key, p_id_med, OracleSource.SATELLITE, SeverityTier.TIER_2_SEVERE)
            adapter.submit_report(soil_key, p_id_med, OracleSource.SOIL, SeverityTier.TIER_1_MODERATE)

            t0 = time.perf_counter()
            rcpt_settle_med = adapter.settle_policy(deployer_key, p_id_med)
            lat_settle_med = (time.perf_counter() - t0) * 1000.0
            measurements["settlePolicy (Median)"]["gas"].append(rcpt_settle_med["gasUsed"])
            measurements["settlePolicy (Median)"]["latency_ms"].append(lat_settle_med)

            # 7. flagFraud on fresh policy
            now3 = adapter.get_block_timestamp()
            land_hash_fraud = w3.keccak(text=f"gas_fraud_{run_i}_{time.time_ns()}")
            p_id_fraud, _ = adapter.create_policy(
                farmer_private_key=farmer_key,
                land_hash=land_hash_fraud,
                crop=CropCode.GROUNDNUT,
                region=Region.KADAPA,
                sum_insured_wei=sum_insured,
                start_time=now3,
                end_time=now3 + 50,
                rules_hash=rules_hash,
            )
            t0 = time.perf_counter()
            rcpt_flag = adapter.flag_fraud(checker_key, p_id_fraud, w3.keccak(text="flag_audit"))
            lat_flag = (time.perf_counter() - t0) * 1000.0
            measurements["flagFraud"]["gas"].append(rcpt_flag["gasUsed"])
            measurements["flagFraud"]["latency_ms"].append(lat_flag)

        # Aggregate summary table
        records = []
        meta = get_metadata(seed)

        for fn_name, data in measurements.items():
            g_mean = float(np.mean(data["gas"]))
            g_std = float(np.std(data["gas"]))
            l_mean = float(np.mean(data["latency_ms"]))
            l_std = float(np.std(data["latency_ms"]))
            profiler_ref = GAS_REPORT_BASELINES.get(fn_name, np.nan)
            diff_pct = ((g_mean - profiler_ref) / profiler_ref) * 100.0 if not np.isnan(profiler_ref) else 0.0

            records.append({
                "contract_function": fn_name,
                "n_runs": n_runs,
                "gas_used_mean": round(g_mean, 1),
                "gas_used_std": round(g_std, 1),
                "hardhat_gas_reporter_ref": profiler_ref,
                "variance_vs_profiler_pct": round(diff_pct, 2),
                "latency_simulated_ms_mean": round(l_mean, 2),
                "latency_simulated_ms_std": round(l_std, 2),
                "network_environment": "Hardhat Local (Simulated, Non-Representative of Public Mempool)",
                **meta,
            })

        res_df = pd.DataFrame(records)
        csv_path = RESULTS_DIR / "e6_gas_latency.csv"
        res_df.to_csv(csv_path, index=False)

        # Plotting
        setup_matplotlib_style()
        fig, ax = plt.subplots(figsize=(10, 6))

        fn_names = [r["contract_function"] for r in records]
        means = [r["gas_used_mean"] for r in records]
        stds = [r["gas_used_std"] for r in records]
        refs = [r["hardhat_gas_reporter_ref"] for r in records]

        y = np.arange(len(fn_names))
        height = 0.38

        rects1 = ax.barh(y - height / 2, means, height, xerr=stds, label="Empirical Gas (E6 Mean +/- Std)",
                         color=CB_PALETTE["blue"], alpha=0.9, capsize=3)
        ax.barh(y + height / 2, refs, height, label="Hardhat Profiler Baseline",
                color=CB_PALETTE["orange"], alpha=0.9)

        ax.set_xlabel("Gas Units Used")
        ax.set_title("E6: Smart Contract Gas Profiling vs. Hardhat Reporter Baseline (N=30 Fresh Runs)")
        ax.set_yticks(y)
        ax.set_yticklabels(fn_names, weight="bold")
        ax.set_xlim(0, max(means) * 1.25)
        ax.legend(loc="lower right")

        for rect in rects1:
            w = rect.get_width()
            ax.annotate(f"{int(w):,}", xy=(w, rect.get_y() + rect.get_height() / 2),
                        xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5)

        fig.tight_layout()
        png_path = RESULTS_DIR / "e6_gas_comparison.png"
        plt.savefig(png_path)
        plt.close()

        return res_df, csv_path, png_path

    finally:
        if node_proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(node_proc.pid)], capture_output=True)


if __name__ == "__main__":
    df, cpath, ppath = run_experiment_e6(n_runs=30, seed=42)
    print("\n=== Experiment E6 Gas Consumption Summary ===")
    cols = [
        "contract_function", "gas_used_mean", "gas_used_std",
        "hardhat_gas_reporter_ref", "variance_vs_profiler_pct",
    ]
    print(df[cols].to_string(index=False))
    print(f"\nSaved CSV: {cpath}\nSaved PNG: {ppath}")
