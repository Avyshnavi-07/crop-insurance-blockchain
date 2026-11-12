"""
Master Orchestration Script for Experiments E1 through E6.

Executes:
- E1: Single-source vs. 2-of-3 consensus (results/e1_consensus_vs_single.csv + png)
- E2: Source ablation & pairwise disagreement variants (results/e2_ablation.csv + png)
- E3: Fault robustness Monte Carlo simulation & on-chain parity (results/e3_faulty_robustness.csv + png)
- E4: Tiered vs. binary payout basis risk evaluation (results/e4_tiered_vs_binary.csv + png)
- E5: Fraud detection benchmark, spatial enhancement, and LaTeX table (results/e5_fraud_comparison.csv + png + tex)
- E6: Smart contract gas consumption & confirmation latency (results/e6_gas_latency.csv + png)
- E6-Sepolia: Live Sepolia testnet check (clean exit if unfunded/unconfigured)
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.e1_consensus_vs_single import run_experiment_e1  # noqa: E402
from experiments.e2_ablation import run_experiment_e2  # noqa: E402
from experiments.e3_faulty_robustness import run_experiment_e3  # noqa: E402
from experiments.e4_tiered_vs_binary import run_experiment_e4  # noqa: E402
from experiments.e5_fraud_benchmark import run_experiment_e5  # noqa: E402
from experiments.e6_gas_latency import run_experiment_e6  # noqa: E402
from experiments.e6_sepolia import run_sepolia_experiments  # noqa: E402


def run_all():
    print("=" * 80)
    print("CROP INSURANCE CHAIN - MASTER EXPERIMENT RUNNER (E1 - E6)")
    print("=" * 80)
    t_start = time.perf_counter()

    # 1. Experiment E1
    print("\n>>> [1/6] Running Experiment E1: Single-Source vs. 2-of-3 Consensus...")
    df_e1, c1, p1 = run_experiment_e1(seed=42)
    print(f"    Done. Saved {c1.name} and {p1.name}")

    # 2. Experiment E2
    print("\n>>> [2/6] Running Experiment E2: Ablation & Pairwise Disagreement Variants...")
    df_e2, c2, p2 = run_experiment_e2(seed=42)
    print(f"    Done. Saved {c2.name} and {p2.name}")

    # 3. Experiment E3
    print("\n>>> [3/6] Running Experiment E3: Fault Robustness (Monte Carlo & On-Chain Parity)...")
    df_e3, c3, p3 = run_experiment_e3(seed=42, run_onchain=True)
    print(f"    Done. Saved {c3.name} and {p3.name}")

    # 4. Experiment E4
    print("\n>>> [4/6] Running Experiment E4: Tiered vs. Binary Payout Schedules (Basis Risk)...")
    df_e4, c4, p4 = run_experiment_e4(seed=42)
    print(f"    Done. Saved {c4.name} and {p4.name}")

    # 5. Experiment E5
    print("\n>>> [5/6] Running Experiment E5: Fraud Benchmark & Spatial Proximity Enhancement...")
    df_e5, c5, p5, l5 = run_experiment_e5(seed=42)
    print(f"    Done. Saved {c5.name}, {p5.name}, and {l5.name}")

    # 6. Experiment E6
    print("\n>>> [6/6] Running Experiment E6: Smart Contract Gas Profiling (N=30 Fresh Runs)...")
    df_e6, c6, p6 = run_experiment_e6(n_runs=30, seed=42)
    print(f"    Done. Saved {c6.name} and {p6.name}")

    # 7. Sepolia check
    print("\n>>> [Extension] Checking Sepolia Testnet Environment...")
    run_sepolia_experiments()

    elapsed = time.perf_counter() - t_start
    print("\n" + "=" * 80)
    print(f"[SUCCESS] ALL EXPERIMENTS E1-E6 COMPLETED IN {elapsed:.2f}s!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all()
