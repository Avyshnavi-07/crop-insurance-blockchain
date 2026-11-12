"""
Experiment E3: Faulty-Source Robustness & Monte Carlo Consensus Verification.

Evaluates:
- Synthetic fault injection at 10%, 20%, 30% error rates into:
  * Weather alone
  * Satellite alone
  * Soil alone
  * All sources independently
- Both error modes: 'random' and 'off_by_one'.
- 200 Monte Carlo seeded trials per setting over all 24 historical district-years.
- Compares single faulty source degradation vs. 2-of-3 consensus resilience.
- Includes theoretical analytic expectation.
- Verifies 30 on-chain policies against real CropInsurance.sol to prove EVM parity.
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
    evaluate_python_consensus,
    get_metadata,
    load_experiment_dataset,
    setup_matplotlib_style,
    tier_to_payout_pct,
)
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
from oracles.fault_injector import FaultInjector  # noqa: E402


def run_monte_carlo_trials(
    df: pd.DataFrame,
    target: str,
    error_rate: float,
    mode: str,
    n_trials: int = 200,
    base_seed: int = 42,
) -> Dict[str, float]:
    """
    Executes n_trials Monte Carlo trials for a specific fault injection configuration.
    """
    single_wrong_rates = []
    con_wrong_rates = []
    single_agreements = []
    con_agreements = []
    con_wrong_agree_rates = []
    con_wrong_disagree_rates = []

    true_tiers = df["consensus_tier"].values
    true_payouts = df["payout_pct"].values

    base_w = df["rainfall_tier"].values
    base_sat = df["ndvi_tier"].values
    base_soil = df["soil_tier"].values
    n_scenarios = len(df)

    clean_agree_mask = (base_w == base_sat) & (base_sat == base_soil)
    n_clean_agree = int(clean_agree_mask.sum())
    n_clean_disagree = n_scenarios - n_clean_agree

    for trial in range(n_trials):
        trial_seed = base_seed * 1000 + trial
        fi_w = FaultInjector(error_rate if target in ["weather_only", "all_independent"] else 0.0,
                             mode=mode, seed=trial_seed + 1)
        fi_sat = FaultInjector(error_rate if target in ["satellite_only", "all_independent"] else 0.0,
                               mode=mode, seed=trial_seed + 2)
        fi_soil = FaultInjector(error_rate if target in ["soil_only", "all_independent"] else 0.0,
                                mode=mode, seed=trial_seed + 3)

        single_wrong_count = 0
        con_wrong_count = 0
        con_wrong_agree_count = 0
        con_wrong_disagree_count = 0
        single_agree_count = 0
        con_agree_count = 0

        for i in range(n_scenarios):
            rep_w, _ = fi_w.inject(int(base_w[i]))
            rep_sat, _ = fi_sat.inject(int(base_sat[i]))
            rep_soil, _ = fi_soil.inject(int(base_soil[i]))

            # The faulty source under test
            if target == "weather_only":
                single_rep = rep_w
            elif target == "satellite_only":
                single_rep = rep_sat
            elif target == "soil_only":
                single_rep = rep_soil
            else:
                single_rep = rep_w  # representative single source

            single_payout = tier_to_payout_pct(single_rep)
            con_tier, _ = evaluate_python_consensus(rep_w, rep_sat, rep_soil)
            con_payout = tier_to_payout_pct(con_tier)

            if single_payout != true_payouts[i]:
                single_wrong_count += 1
            if con_payout != true_payouts[i]:
                con_wrong_count += 1
                if clean_agree_mask[i]:
                    con_wrong_agree_count += 1
                else:
                    con_wrong_disagree_count += 1

            if single_rep == true_tiers[i]:
                single_agree_count += 1
            if con_tier == true_tiers[i]:
                con_agree_count += 1

        single_wrong_rates.append((single_wrong_count / n_scenarios) * 100.0)
        con_wrong_rates.append((con_wrong_count / n_scenarios) * 100.0)
        single_agreements.append((single_agree_count / n_scenarios) * 100.0)
        con_agreements.append((con_agree_count / n_scenarios) * 100.0)
        con_wrong_agree_rates.append((con_wrong_agree_count / n_clean_agree) * 100.0 if n_clean_agree > 0 else 0.0)
        con_wrong_disagree_rates.append(
            (con_wrong_disagree_count / n_clean_disagree) * 100.0 if n_clean_disagree > 0 else 0.0
        )

    # Analytic expectation for single source: wrong payout rate is approximately equal to error rate
    # Analytic expectation for consensus: only a fraction of single-source faults break 2-of-3 consensus
    analytic_single = error_rate * 100.0
    analytic_consensus = (error_rate ** 2) * 100.0 if target == "all_independent" else (error_rate * 0.15) * 100.0

    return {
        "fault_regime": "single_source" if target != "all_independent" else "all_sources_independent",
        "clean_disagreement_count": n_clean_disagree,
        "clean_disagreement_pct": round((n_clean_disagree / n_scenarios) * 100.0, 2),
        "clean_agreement_count": n_clean_agree,
        "clean_agreement_pct": round((n_clean_agree / n_scenarios) * 100.0, 2),
        "single_wrong_mean": float(np.mean(single_wrong_rates)),
        "single_wrong_std": float(np.std(single_wrong_rates)),
        "consensus_wrong_mean": float(np.mean(con_wrong_rates)),
        "consensus_wrong_std": float(np.std(con_wrong_rates)),
        "con_wrong_on_clean_agree_mean": float(np.mean(con_wrong_agree_rates)),
        "con_wrong_on_clean_agree_std": float(np.std(con_wrong_agree_rates)),
        "con_wrong_on_clean_disagree_mean": float(np.mean(con_wrong_disagree_rates)),
        "con_wrong_on_clean_disagree_std": float(np.std(con_wrong_disagree_rates)),
        "single_agree_mean": float(np.mean(single_agreements)),
        "single_agree_std": float(np.std(single_agreements)),
        "consensus_agree_mean": float(np.mean(con_agreements)),
        "consensus_agree_std": float(np.std(con_agreements)),
        "analytic_single_wrong": round(analytic_single, 2),
        "analytic_consensus_wrong": round(analytic_consensus, 2),
    }


def verify_on_chain_parity(n_policies: int = 30, seed: int = 42) -> bool:
    """
    Executes n_policies on-chain runs against Hardhat to prove Python simulation
    matches CropInsurance.sol consensus with 100% parity under fault injection.
    """
    print(f"\n[On-Chain Parity] Verifying {n_policies} randomized fault trials against real contract...")
    rpc_url = get_rpc_url()
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    proc: Optional[subprocess.Popen] = None

    if not w3.is_connected():
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
                break

    try:
        adapter = ContractAdapter(rpc_url=rpc_url)
        deployer_key = DEFAULT_LOCAL_KEYS["DEPLOYER"]
        farmer_key = DEFAULT_LOCAL_KEYS["FARMER"]
        weather_key = DEFAULT_LOCAL_KEYS["WEATHER"]
        sat_key = DEFAULT_LOCAL_KEYS["SATELLITE"]
        soil_key = DEFAULT_LOCAL_KEYS["SOIL"]

        admin_addr = w3.eth.account.from_key(deployer_key).address
        weather_addr = w3.eth.account.from_key(weather_key).address
        sat_addr = w3.eth.account.from_key(sat_key).address
        soil_addr = w3.eth.account.from_key(soil_key).address

        adapter.deploy(deployer_key, admin_address=admin_addr)
        adapter.grant_role(deployer_key, "ORACLE_WEATHER_ROLE", weather_addr)
        adapter.grant_role(deployer_key, "ORACLE_SATELLITE_ROLE", sat_addr)
        adapter.grant_role(deployer_key, "ORACLE_SOIL_ROLE", soil_addr)
        adapter.fund_risk_pool(deployer_key, w3.to_wei(50, "ether"))
        rules_hash = compute_rules_hash()

        rng = np.random.RandomState(seed)

        for i in range(n_policies):
            # Sample random tiers in [0, 3]
            w_t = int(rng.choice([0, 1, 2, 3]))
            sat_t = int(rng.choice([0, 1, 2, 3]))
            soil_t = int(rng.choice([0, 1, 2, 3]))

            # Python expected consensus
            py_tier, _ = evaluate_python_consensus(w_t, sat_t, soil_t)

            # Create on-chain policy
            now = adapter.get_block_timestamp()
            land_hash = w3.keccak(text=f"parity_land_{i}_{time.time_ns()}")
            sum_insured = w3.to_wei(0.5, "ether")

            p_id, _ = adapter.create_policy(
                farmer_private_key=farmer_key,
                land_hash=land_hash,
                crop=CropCode.GROUNDNUT,
                region=Region.ANANTAPUR,
                sum_insured_wei=sum_insured,
                start_time=now,
                end_time=now + 50,
                rules_hash=rules_hash,
            )

            adapter.advance_time(60)

            # Submit on-chain reports
            adapter.submit_report(weather_key, p_id, OracleSource.WEATHER, SeverityTier(w_t))
            adapter.submit_report(sat_key, p_id, OracleSource.SATELLITE, SeverityTier(sat_t))
            adapter.submit_report(soil_key, p_id, OracleSource.SOIL, SeverityTier(soil_t))

            # Settle on-chain
            adapter.settle_policy(deployer_key, p_id)
            pol = adapter.get_policy(p_id)
            onchain_tier = int(pol["finalTier"])

            assert onchain_tier == py_tier, (
                f"Mismatch on trial {i}: inputs ({w_t}, {sat_t}, {soil_t}) -> "
                f"Python={py_tier}, OnChain={onchain_tier}"
            )

        print(f"  -> [OK] All {n_policies} on-chain trials matched Python consensus simulation exactly (100% parity).")
        return True

    finally:
        if proc:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)


def run_experiment_e3(seed: int = 42, run_onchain: bool = True) -> Tuple[pd.DataFrame, Path, Path]:
    """
    Executes full E3 experiment: 200 Monte Carlo trials per setting + optional on-chain validation.
    """
    df = load_experiment_dataset()
    meta = get_metadata(seed)

    targets = ["weather_only", "satellite_only", "soil_only", "all_independent"]
    error_rates = [0.10, 0.20, 0.30]
    modes = ["random", "off_by_one"]

    records: List[Dict] = []
    print("Running Experiment E3 Monte Carlo simulations (200 trials per setting)...")

    for target in targets:
        for mode in modes:
            for rate in error_rates:
                res = run_monte_carlo_trials(df, target=target, error_rate=rate, mode=mode,
                                             n_trials=200, base_seed=seed)
                records.append({
                    "target_source": target,
                    "error_mode": mode,
                    "injected_error_rate_pct": rate * 100.0,
                    **res,
                    **meta,
                })

    res_df = pd.DataFrame(records)
    csv_path = RESULTS_DIR / "e3_faulty_robustness.csv"
    res_df.to_csv(csv_path, index=False)

    # Plotting: Error Rate vs. Wrong Payout Rate (Single vs Consensus) for Random Mode
    setup_matplotlib_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    subset_random = res_df[(res_df["target_source"] == "weather_only") & (res_df["error_mode"] == "random")]
    subset_all = res_df[(res_df["target_source"] == "all_independent") & (res_df["error_mode"] == "random")]

    rates = [10, 20, 30]

    # Subplot 1: Weather Oracle Faulty Alone
    ax1 = axes[0]
    ax1.errorbar(rates, subset_random["single_wrong_mean"], yerr=subset_random["single_wrong_std"],
                 fmt="o-", color=CB_PALETTE["red"], label="Single Faulty Oracle Alone", capsize=4, linewidth=2)
    ax1.errorbar(rates, subset_random["consensus_wrong_mean"], yerr=subset_random["consensus_wrong_std"],
                 fmt="s-", color=CB_PALETTE["blue"], label="2-of-3 Consensus Resilience", capsize=4, linewidth=2)
    ax1.plot(rates, subset_random["analytic_single_wrong"], "--", color=CB_PALETTE["dark"],
             alpha=0.6, label="Analytic Single Expectation (y=p)")
    ax1.set_xlabel("Injected Error Rate (%)")
    ax1.set_ylabel("Wrong-Payout Rate (%)")
    ax1.set_title("Single Oracle Faulty (Weather)")
    ax1.legend(loc="upper left")

    # Subplot 2: All Oracles Independently Faulty
    ax2 = axes[1]
    ax2.errorbar(rates, subset_all["single_wrong_mean"], yerr=subset_all["single_wrong_std"],
                 fmt="o-", color=CB_PALETTE["red"], label="Single Oracle Baseline", capsize=4, linewidth=2)
    ax2.errorbar(rates, subset_all["consensus_wrong_mean"], yerr=subset_all["consensus_wrong_std"],
                 fmt="s-", color=CB_PALETTE["blue"], label="2-of-3 Consensus", capsize=4, linewidth=2)
    ax2.set_xlabel("Injected Error Rate (%)")
    ax2.set_title("All 3 Oracles Independently Faulty")
    ax2.legend(loc="upper left")

    fig.suptitle("E3: Fault Robustness — Single Oracle vs. 2-of-3 Consensus (200 Monte Carlo Trials)", fontsize=13)
    fig.tight_layout()
    png_path = RESULTS_DIR / "e3_faulty_robustness.png"
    plt.savefig(png_path)
    plt.close()

    if run_onchain:
        verify_on_chain_parity(n_policies=30, seed=seed)

    return res_df, csv_path, png_path


if __name__ == "__main__":
    df, cpath, ppath = run_experiment_e3(seed=42, run_onchain=True)
    print("=== Experiment E3 Summary (Weather Only, Random Mode) ===")
    sub = df[(df["target_source"] == "weather_only") & (df["error_mode"] == "random")]
    cols = ["injected_error_rate_pct", "single_wrong_mean", "consensus_wrong_mean"]
    print(sub[cols].to_string(index=False))
    print(f"\nSaved CSV: {cpath}\nSaved PNG: {ppath}")
