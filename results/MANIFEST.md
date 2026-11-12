# Results Manifest & Provenance Catalog

This manifest documents every empirical data file, visualization figure, and LaTeX artifact in the `results/` directory, including the generating script, execution command, random seed, and primary output metrics.

All artifacts are generated deterministically and can be reproduced using `python -m experiments.run_all`.

---

## 1. Catalog of Results Artifacts

| Output File | Generating Script | Execution Command | Random Seed | Description & Headline Metrics |
|---|---|---|---|---|
| [`e1_consensus_vs_single.csv`](e1_consensus_vs_single.csv) | `experiments/e1_consensus_vs_single.py` | `python -m experiments.e1_consensus_vs_single` | `42` | Consensus vs single oracles across 24 district-years. Consensus $r_s = 0.8068$, MAPE vs CMDI = $7.72$ pp. |
| [`e1_consensus_vs_single.png`](e1_consensus_vs_single.png) | `experiments/e1_consensus_vs_single.py` | `python -m experiments.e1_consensus_vs_single` | `42` | Publication plot (300 DPI) comparing Spearman correlation and continuous loss error. |
| [`e2_ablation.csv`](e2_ablation.csv) | `experiments/e2_ablation.py` | `python -m experiments.e2_ablation` | `42` | Ablation of single, pairwise (Variants A and B), and 3-source consensus. Full consensus achieves $7.72$ pp error. |
| [`e2_ablation.png`](e2_ablation.png) | `experiments/e2_ablation.py` | `python -m experiments.e2_ablation` | `42` | Publication plot (300 DPI) showing pairwise disagreement variants vs 3-source consensus. |
| [`e3_faulty_robustness.csv`](e3_faulty_robustness.csv) | `experiments/e3_faulty_robustness.py` | `python -m experiments.e3_faulty_robustness` | `42` | 200 Monte Carlo trials per setting. Proves 0.00% consensus error on agreeing scenarios; 8.9x error suppression at 30% fault. |
| [`e3_faulty_robustness.png`](e3_faulty_robustness.png) | `experiments/e3_faulty_robustness.py` | `python -m experiments.e3_faulty_robustness` | `42` | Publication plot (300 DPI) of single faulty oracle alone vs 2-of-3 consensus error suppression. |
| [`e4_tiered_vs_binary.csv`](e4_tiered_vs_binary.csv) | `experiments/e4_tiered_vs_binary.py` | `python -m experiments.e4_tiered_vs_binary` | `42` | Basis risk MAPE of Tiered (7.72 pp) vs Binary $\ge 1$ (11.89 pp), Binary $\ge 2$ (11.39 pp), and Binary $\ge 3$ (19.18 pp). |
| [`e4_sensitivity_mappings.csv`](e4_sensitivity_mappings.csv) | `experiments/e4_tiered_vs_binary.py` | `python -m experiments.e4_tiered_vs_binary` | `42` | Sensitivity breakdown across 4 loss curves: Linear Cap 60%, Linear Cap 45%, Rank-based, Convex Power 1.5. |
| [`e4_tiered_vs_binary.png`](e4_tiered_vs_binary.png) | `experiments/e4_tiered_vs_binary.py` | `python -m experiments.e4_tiered_vs_binary` | `42` | Publication plot (300 DPI) comparing basis risk and over/under-payment rates. |
| [`fraud_metrics.csv`](fraud_metrics.csv) | `fraud/evaluate.py` | `python -m fraud.evaluate` | `[42, 43, 44, 45, 46]` | 5-seed baseline fraud benchmark (Rule Engine, Isolation Forest, MLP Autoencoder). |
| [`fraud_per_type.csv`](fraud_per_type.csv) | `fraud/evaluate.py` | `python -m fraud.evaluate` | `[42, 43, 44, 45, 46]` | 5-seed per-fraud-type breakdown across the 4 synthetic fraud categories. |
| [`e5_fraud_comparison.csv`](e5_fraud_comparison.csv) | `experiments/e5_fraud_benchmark.py` | `python -m experiments.e5_fraud_benchmark` | `[42, 43, 44, 45, 46]` | Benchmark augmented with Spatial Nearest-Neighbor Rule Engine ($F_1 = 0.8431$, ROC-AUC = $0.9100$). |
| [`e5_fraud_per_type_comparison.csv`](e5_fraud_per_type_comparison.csv) | `experiments/e5_fraud_benchmark.py` | `python -m experiments.e5_fraud_benchmark` | `[42, 43, 44, 45, 46]` | Per-type breakdown showing duplicate boundary recall doubled from $26.67\%$ to $53.33\%$. |
| [`e5_fraud_benchmark.png`](e5_fraud_benchmark.png) | `experiments/e5_fraud_benchmark.py` | `python -m experiments.e5_fraud_benchmark` | `[42, 43, 44, 45, 46]` | Publication grouped bar chart (300 DPI) comparing Precision, Recall, F1, and AUC. |
| [`e5_fraud_latex_table.tex`](e5_fraud_latex_table.tex) | `experiments/e5_fraud_benchmark.py` | `python -m experiments.e5_fraud_benchmark` | `[42, 43, 44, 45, 46]` | Publication-ready LaTeX table for academic manuscript inclusion. |
| [`e6_gas_latency.csv`](e6_gas_latency.csv) | `experiments/e6_gas_latency.py` | `python -m experiments.e6_gas_latency` | `42` | Gas and local latency over N=30 fresh runs per function (`createPolicy`: 259,839 gas, `settlePolicy`: 153,704 gas). |
| [`e6_gas_comparison.png`](e6_gas_comparison.png) | `experiments/e6_gas_latency.py` | `python -m experiments.e6_gas_latency` | `42` | Publication bar chart (300 DPI) comparing empirical gas measurements vs Hardhat profiler. |

---

## 2. Master Reproduction Command
To execute all experiments in automated sequence:
```powershell
.\.venv\Scripts\python -m experiments.run_all
```
Total expected runtime: ~85 seconds on modern multi-core workstation.
