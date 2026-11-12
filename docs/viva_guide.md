# Comprehensive Viva Voce Defense Guide & Examination Preparation

This document prepares the research team for thesis defense, viva voce examination, and live technical demonstration of the **Crop Insurance Chain** research prototype.

---

## 1. Key Metrics Cheat Sheet (One-Page Quick Reference)

All empirical numbers are verifiable from reproducible CSVs in [`results/`](../results/):

| Metric / Evaluation Gate | Value | Baseline / Comparison | Source File |
|---|---|---|---|
| **Consensus Correlation with CMDI ($r_s$)** | **0.8068** ($p < 10^{-5}$) | Weather: 0.8068, Satellite: 0.8096, Soil: 0.8567 | [`e1_consensus_vs_single.csv`](../results/e1_consensus_vs_single.csv) |
| **Consensus Error vs. Continuous CMDI Loss** | **7.72 pp** | Matches Weather (7.72 pp); Soil alone has 6.15 pp; Satellite: 8.76 pp | [`e1_consensus_vs_single.csv`](../results/e1_consensus_vs_single.csv), [`e2_ablation.csv`](../results/e2_ablation.csv) |
| **Clean Data Baseline Agreement** | **20 / 24 scenarios ($83.33\%$)** | 4 / 24 ($16.67\%$) have clean divergence | [`e3_faulty_robustness.csv`](../results/e3_faulty_robustness.csv) |
| **Consensus Error on Agreeing Clean Data** | **0.00%** | Single faulty oracle error: 10.19% to 30.13% | [`e3_faulty_robustness.csv`](../results/e3_faulty_robustness.csv) |
| **Consensus Error Under Multi-Fault Regime** | **4.38% (10%), 12.33% (20%), 22.48% (30%)** | All 3 oracles independently faulty | [`e3_faulty_robustness.csv`](../results/e3_faulty_robustness.csv) |
| **Error Suppression at 30% Single Fault** | **8.9x reduction** | Single: 30.13% $\to$ Consensus: 3.40% | [`e3_faulty_robustness.csv`](../results/e3_faulty_robustness.csv) |
| **On-Chain EVM Parity Verification** | **100% (30/30 trials matched)** | Zero EVM vs Python discrepancies | `experiments/e3_faulty_robustness.py` |
| **Exhaustive Tier Combinations Parity** | **100% (64/64 combinations)** | All $4 \times 4 \times 4$ tier combinations matched on-chain | `test/test_experiments.py` |
| **Basis Risk MAPE (Linear Cap 60%)** | **7.72 pp [Tiered Schedule]** | Binary $\ge 1$: 11.89 pp, Binary $\ge 2$: 11.39 pp | [`e4_tiered_vs_binary.csv`](../results/e4_tiered_vs_binary.csv) |
| **Basis Risk MAPE (Convex Power 1.5)** | **3.36 pp [Tiered Schedule]** | Binary $\ge 1$: 13.06 pp, Binary $\ge 2$: 11.33 pp | [`e4_sensitivity_mappings.csv`](../results/e4_sensitivity_mappings.csv) |
| **Binary $\ge 1$ Over-Payment Exposure** | **25.00%** (+5.82 pp signed bias) | Tiered Schedule: **0.00%** overpayment | [`e4_tiered_vs_binary.csv`](../results/e4_tiered_vs_binary.csv) |
| **Duplicate Boundary Recall (Before $\to$ After)**| **26.67% $\to$ 53.33%** (+26.66 pp) | Baseline Rule Engine $\to$ Spatial Proximity | [`e5_fraud_per_type_comparison.csv`](../results/e5_fraud_per_type_comparison.csv) |
| **Enhanced Fraud Model Precision / Recall / F1** | **Prec: 0.8534, Rec: 0.8345, F1: 0.8431** | ROC-AUC: **0.9100 $\pm$ 0.0150** | [`e5_fraud_comparison.csv`](../results/e5_fraud_comparison.csv) |
| **`createPolicy` Gas Consumption** | **259,838.2 $\pm$ 3,070.1 gas** | Hardhat static profiler: 276,371 gas (-5.98%) | [`e6_gas_latency.csv`](../results/e6_gas_latency.csv) |
| **`settlePolicy (2-of-3)` Gas Consumption** | **153,704.0 $\pm$ 2,207.9 gas** | Hardhat static profiler: 165,555 gas (-7.16%) | [`e6_gas_latency.csv`](../results/e6_gas_latency.csv) |
| **`resolveDispute` Gas Discrepancy** | **121,526.6 $\pm$ 6.5 gas (+16.37%)** | Empirical post-withdrawal SSTORE slot resets vs static profiler | [`e6_gas_latency.csv`](../results/e6_gas_latency.csv) |
| **`withdrawPayout` (Pull Payment) Gas** | **32,394.0 $\pm$ 0.0 gas** | Zero variance across repeated runs | [`e6_gas_latency.csv`](../results/e6_gas_latency.csv) |
| **Smart Contract Test Suite** | **23 / 23 passing (100%)** | Coverage: AccessControl, Solvency, CEI, Reentrancy | `test/CropInsurance.test.ts` |
| **Python Unit & Pipeline Tests** | **40 / 40 passing (100%)** | Data pipeline, oracles, fraud ML, experiments | `test/test_*.py` |
| **Frontend Unit Tests** | **14 / 14 passing (100%)** | Normalization, keccak256, error decoding | `frontend/test/web3.test.ts` |

---

## 2. 30 Comprehensive Examiner Questions & Answers

### Group 1: Problem Definition, Motivation & Academic Context

#### Q1: What specific gap in existing blockchain crop insurance does this project address?
> **Answer**: Existing decentralized insurance systems like *AgriInsureDON* (Frontiers in Blockchain 2025) and *IEEE HSWTech 2025* rely heavily on on-field physical IoT sensors. Physical IoT sensors impose prohibitive capital expenditure, battery maintenance, calibration drift, and physical tampering vulnerabilities for smallholder farmers. Our prototype eliminates physical IoT hardware entirely by synthesizing three freely available public remote-sensing and meteorological streams (Open-Meteo rainfall, Sentinel-2 NDVI, and NASA SMAP soil moisture) into a 2-of-3 consensus protocol.

#### Q2: Why focus on groundnut farming in Anantapur, Kurnool, and Kadapa?
> **Answer**: Rayalaseema in Andhra Pradesh is one of India's most drought-prone semi-arid agricultural belts. Kharif rainfed groundnut (*Arachis hypogaea*) is highly sensitive to mid-season dry spells during flowering and pod development. The region suffers from acute rainfall deficit and poor groundwater recharge, making it an ideal real-world testbed for parametric multi-source index insurance.

#### Q3: Why is this labeled a "research prototype" rather than commercial insurance?
> **Answer**: This is strictly an academic research prototype. Commercial insurance requires statutory actuarial certification, insurance regulatory authority licensing (e.g., IRDAI in India), legal KYC compliance, and commercial reinsurance backing. Our prototype investigates technical feasibility, smart contract solvency mechanisms, multi-source consensus dynamics, and basis risk reduction under research assumptions.

---

### Group 2: Smart Contract Design, Security & Solvency

#### Q4: How does the smart contract mathematically enforce risk pool solvency?
> **Answer**: In `createPolicy()`, the contract checks the strict solvency invariant:
> $$\text{riskPoolBalance} + \text{premium} \ge \text{reservedExposure} + \text{sumInsured}$$
> If the pool does not have sufficient liquid headroom to back 100% of the newly underwritten liability, the transaction reverts with `InsufficientRiskPool(headroom, required)`. This prevents fractional-reserve insolvency common in poorly designed DeFi protocols.

#### Q5: Why did you choose pull-payments over push-payments for claim payouts?
> **Answer**: Push payments (directly sending Ether to farmer wallets inside `settlePolicy`) introduce severe denial-of-service vulnerabilities: a single failing recipient or a malicious contract with a reverting `receive()` function can freeze settlement for the entire batch. In [`CropInsurance.sol`](../contracts/CropInsurance.sol), we use pull payments (`withdrawPayout`): the contract credits `payoutAmount` during settlement, and the farmer pulls their funds individually. This is protected by `nonReentrant` and the Checks-Effects-Interactions pattern.

#### Q6: How does the contract prevent duplicate land parcel underwriting?
> **Answer**: The contract maintains a mapping `mapping(bytes32 => bool) public activeLandHashes`. When a policy is created, the farmer submits a `bytes32 landHash` representing the normalized cadastral boundary polygon. If `activeLandHashes[landHash]` is true, the call reverts with `LandAlreadyInsured(landHash)`. When the policy closes or settles with 0% payout, the hash is released.

#### Q7: What were the findings of the Slither static analysis audit?
> **Answer**: In [`docs/slither_audit.md`](slither_audit.md), Slither v0.11.6 identified 1 medium issue (`uninitialized-local` in `evaluateConsensus`) which was fixed by explicitly initializing tier variables. Six informational/false-positive findings (such as `arbitrary-send-eth` on `withdrawRiskPool`, which is strictly restricted to `DEFAULT_ADMIN_ROLE`) were formally triaged and justified.

---

### Group 3: Multi-Source Oracles & Consensus Logic

#### Q8: How does the 2-of-3 consensus mechanism operate in Solidity?
> **Answer**: After season end, each of the three authorized oracles (Weather, Satellite, Soil) submits an assessed `SeverityTier` (0 to 3).
> 1. If any 2 reports match ($t_w = t_{sat}$, $t_w = t_{soil}$, or $t_{sat} = t_{soil}$), that tier wins immediately.
> 2. If all 3 reports differ (e.g. Tiers 1, 2, and 3), the contract computes the **median tier** (Tier 2).
> 3. If only 2 reports exist and they disagree, settlement reverts with `ConsensusNotReached`, pausing until the 3rd oracle submits.

#### Q9: What happens if all three oracles differ? Why use the median?
> **Answer**: Three-way disagreement (e.g., Tiers 0, 1, 2 or Tiers 1, 2, 3) indicates moderate sensor variance across physical domains. The median is statistically the most robust $L_1$ estimator against extreme single-source outliers. Choosing the median prevents an overly conservative denial of payout (Tier 0) while protecting pool solvency against an isolated catastrophic false alarm (Tier 3).

#### Q10: What is the exact role of `rulesHash` in the smart contract?
> **Answer**: `rulesHash` is an on-chain **cryptographic commitment and audit anchor** (`keccak256` of `config/tier_rules.json`). It is immutably recorded at policy creation. **Crucially, the contract does NOT verify that oracles applied those thresholds**, because tier calculations are executed off-chain and trusted via oracle role signatures (`ORACLE_*_ROLE`). `rulesHash` serves as an immutable reference for post-settlement audits and dispute resolution.

---

### Group 4: Solvency, Pricing & Actuarial Assumptions

#### Q11: How is the dynamic premium calculated?
> **Answer**: The contract uses regional risk-based pricing:
> $$\text{Premium} = \frac{\text{sumInsured} \times (\text{basePremiumBps} + \text{regionalRiskBps}[\text{region}])}{10,000}$$
> With base rate $= 300\text{ bps}$ ($3.0\%$), Anantapur risk $= 350\text{ bps}$ (total $6.5\%$), Kurnool risk $= 250\text{ bps}$ (total $5.5\%$), and Kadapa risk $= 200\text{ bps}$ (total $5.0\%$). Anantapur incurs the highest loading due to historical drought frequency in the Rayalaseema rain shadow.

#### Q12: How are premium rates adjusted over time?
> **Answer**: The protocol administrator (`DEFAULT_ADMIN_ROLE`) can update regional loading using `setRegionalRiskBps(region, newBps)`. This allows underwriters to adjust premiums between seasons based on multi-year climate trends without redeploying the contract.

---

### Group 5: Data Pipeline, Baseline Methodology & Spatial Resolution

#### Q13: How do you prevent data leakage in historical baseline calculations?
> **Answer**: We use a dynamic **leave-one-year-out (LOO)** baseline methodology across the 8-year historical window (2017–2024). When assessing season $Y$, the historical baseline is computed as the median of all other 7 years ($\{y \in 2017\dots2024 \mid y \neq Y\}$). The target year $Y$ is strictly excluded from its own baseline, preventing future-data or current-season data leakage.

#### Q14: How do you reconcile a 2 km farm parcel with NASA SMAP's ~9 km resolution?
> **Answer**: This highlights the distinction between **district-level index triggers** and **parcel-level policy underwriting**. Parametric drought indices and severity tiers in our prototype are evaluated at the **district level** (macro-scale meteorological and satellite aggregation for Anantapur, Kurnool, and Kadapa), because NASA SMAP (~9 km) and ERA5-Land (~10 km) operate at regional resolutions. Policy creation, premium calculation, sum insured allocation, and cadastral duplicate-parcel hash checks occur at the **individual parcel level**. In future production systems, regional satellite streams would be paired with parcel-level downscaled radar (Sentinel-1 SAR) or local micro-weather stations.

#### Q15: Why are satellite NDVI and SMAP labeled as `CACHED_BENCHMARK_FALLBACK` in the results?
> **Answer**: While rainfall data is fetched live from the Open-Meteo API, Sentinel-2 and NASA SMAP pipelines rely on Google Earth Engine (GEE). For environments where GEE cloud credentials are not active, the system automatically falls back to pre-computed, verified historical benchmark caches in `data/processed/dataset.csv`. This ensures 100% deterministic reproducibility without requiring external cloud accounts.

---

### Group 6: Fraud Detection & Adversarial Machine Learning

#### Q16: How did you ensure the fraud evaluation is non-circular?
> **Answer**: We evaluated models on **3,200 synthetic policy records** (288 fraud cases, 9.0% fraud rate, stratified 60/20/20 train/val/test split) generated with realistic continuous anomaly spectra (e.g., valuation multipliers from $1.70\times$ to $3.80\times$, while the heuristic rule threshold is $2.00\times$). To prevent trivial detection, we introduced realistic **hard negatives**: legitimate commercial large farms ($10-22$ ha), progressive multi-parcel owners, parcels near district borders, and genuine late-sowing farmers.

#### Q17: What was the motivation and result of the spatial proximity enhancement in E5?
> **Answer**: A critical attack on exact hash checks is the **jitter attack**: adding $+0.0001^{\circ}$ (~11 meters) to a parcel vertex creates a completely distinct `keccak256` hash, bypassing on-chain duplicate checks. In E5, we augmented the rule engine with a nearest-neighbor spatial distance check. This **doubled duplicate boundary recall from $26.67\%$ to $53.33\%$** (+26.66 pp), raising overall recall from $76.90\%$ to $83.45\%$ and ROC-AUC to $0.9100$.
>
> *Evaluation Scope Caveat*: In the 20% test partition, duplicate-boundary recall is evaluated on roughly 14–15 positive test cases per seed (~72 duplicate records across the full 3,200 dataset). Because the synthetic data generator's coordinate jitter model and the spatial proximity feature are related, this improvement demonstrates an algorithmic feasibility signal rather than defense against arbitrary human adversarial manipulation.

#### Q18: What is the precision/recall trade-off in the spatial proximity module?
> **Answer**: Tuning the spatial proximity threshold on the validation set increased duplicate recall, but caused overall precision to drop from $90.90\%$ to $85.34\%$ (-5.56 pp). This trade-off occurs because genuine smallholder farmers with neighboring parcels can trigger spatial proximity warnings. In our architecture, spatial warnings do not reject policies automatically; they escalate the policy to the 7-day administrative review queue.

---

### Group 7: Empirical Experiments, Statistics & Results

#### Q19: In E1, why are CMDI metrics headline results while agreement rates are labeled "internal consistency"?
> **Answer**: In our dataset, `consensus_tier` is derived directly from the three physical source tiers. Measuring tier agreement or wrong-payout rates against `consensus_tier` measures whether consensus logic functioned as programmed (internal consistency), not independent external truth. To evaluate continuous fidelity without discrete threshold artifacts, we benchmarked all models against the **Continuous Mean Deficit Index (CMDI)**: a threshold-free continuous severity index computed from the same three deficit percentages; independent of the tier cut-offs but not of the data sources.
>
> Crucially, across all 24 clean historical district-years, the 2-of-3 consensus tier equals the weather rainfall tier in 100% of cases ($r_s = 0.8068$, MAPE $7.72$ pp vs. CMDI loss for both). Thus, consensus provides no accuracy gain over weather alone on clean historical records, and Soil Moisture alone actually achieves a lower MAPE ($6.15$ pp, $r_s = 0.8567$). The primary demonstrated benefit of multi-source consensus is **fault robustness (E3)** when an individual oracle fails or is corrupted.

#### Q20: In E3, how does consensus error behave under single-oracle vs. multi-oracle faults?
> **Answer**: 
> 1. **Single-Oracle Fault Regime**: On the 20 historical scenarios where clean physical oracles agree ($w = sat = soil$), corrupting any single oracle leaves the remaining two clean sources in agreement. Under 2-of-3 majority consensus, the two honest sources outvote the single corrupt report with mathematical certainty (**0.00% error**). Across all 24 historical seasons, consensus suppresses single-fault wrong payouts from $30.13\%$ down to $3.40\%$ (an **8.9x error reduction**). Residual error comes strictly from the 4 historical seasons where clean sensors had already diverged.
> 2. **Multi-Oracle Independent Fault Regime**: When all three oracles experience simultaneous independent random corruptions, consensus error scales with the probability of $\ge 2$ concurrent faults: **$4.38\% \pm 4.29\%$** at 10% fault rate, **$12.33\% \pm 6.81\%$** at 20% fault rate, and **$22.48\% \pm 8.79\%$** at 30% fault rate.

#### Q21: In E4, how does the tiered payout schedule compare to binary triggers under the same loss mapping?
> **Answer**: In Experiment E4, we compared tiered and binary triggers strictly under the **same** continuous loss mapping:
> - **Under the baseline Linear Cap 60% mapping**: The 4-tier schedule achieves a basis risk MAPE of **7.72 pp**, outperforming Binary $\ge 1$ (**11.89 pp**), Binary $\ge 2$ (**11.39 pp**), and Binary $\ge 3$ (**19.18 pp**). Furthermore, Binary $\ge 1$ incurs a **25.00% over-payment rate** (+5.82 pp signed gap) in mild-to-moderate years, threatening insurer solvency, whereas the tiered schedule maintains **0.00% over-payment**.
> - **Under the Convex Power 1.5 mapping** (accelerating crop damage under severe drought): The tiered schedule achieves **3.36 pp** MAPE, compared to **13.06 pp** for Binary $\ge 1$ and **11.33 pp** for Binary $\ge 2$.
> - **Sensitivity Caveat (Linear Cap 45%)**: If crop loss is aggressively compressed (100% loss at 45% deficit), Binary $\ge 1$ achieves lower MAPE (**7.89 pp vs. 13.74 pp**) because moderate droughts already count as total failure. However, this comes at the cost of a severe **25.00% over-payment rate** (+5.82 pp signed bias) in lighter drought years.

---

### Group 8: Frontend Architecture & User Experience

#### Q22: How does the frontend handle Solidity custom errors?
> **Answer**: The frontend uses `ethers.Interface.parseError()` in [`decodeContractError`](../frontend/src/utils/web3.ts). When a transaction reverts, the UI extracts the error selector and parameters and maps them to clear user messages (e.g., explaining exact available vs required liquidity for `InsufficientRiskPool`, or cadastral occupancy for `LandAlreadyInsured`).

#### Q23: Why does the frontend feature a read-only fallback provider?
> **Answer**: To enable zero-setup evaluation. If MetaMask is not installed or the user is not connected, the DApp automatically instantiates an `ethers.JsonRpcProvider("http://127.0.0.1:8545")`. Evaluators can inspect the risk pool, view all 5 seeded policies, and examine oracle reports without wallet friction.

---

### Group 9: Hardest Attack & Defense Questions

#### Q24: Why trust the oracles at all? Isn't this just centralized multi-sig?
> **Answer**: In this research prototype, each oracle is an independent cryptographic keyholder (`ORACLE_*_ROLE`) ingesting a distinct physical domain. While this demonstrates multi-source consensus, it remains trusted federated infrastructure. In a production mainnet deployment, each oracle role would be assigned to a Decentralized Oracle Network (DON) node group (e.g., Chainlink Functions or UMA optimistic oracles) or backed by TLSNotary / zkWasm cryptographic proofs.

#### Q25: Why not simply use Chainlink?
> **Answer**: Chainlink Functions executes off-chain JavaScript and aggregates responses via a decentralized oracle network (DON) before relaying a single aggregated value on-chain, requiring payment in LINK tokens. Our prototype explores an alternative direct multi-source architecture where raw independent reports (Copernicus Sentinel-2, Open-Meteo ERA5, NASA SMAP) are submitted directly to the smart contract, enabling the EVM itself to execute the 2-of-3 majority consensus and median fallback on-chain with verifiable per-source transaction attribution.

#### Q26: What if all three oracles are wrong simultaneously?
> **Answer**: If a regional sensor blackout or correlated data pipeline corruption causes all three oracles to misreport, consensus cannot recover truth. To mitigate this:
> 1. The contract enforces a **7-day post-settlement dispute window** (`openDispute`) allowing farmers to file formal challenges.
> 2. The fraud checker can halt settlement via `flagFraud()`.
> 3. The 14-day timeout escalation (`escalateTimeout`) protects funds if oracles fail to report altogether.

#### Q27: How would gas costs behave on Ethereum mainnet or Layer 2?
> **Answer**: On Ethereum mainnet ($30\text{ gwei}$, $\$3,000/\text{ETH}$), `createPolicy` (259,838.2 gas) would cost $\approx \$23.39$, which is prohibitive for smallholder farmers. However, Layer 2 rollups (Arbitrum, Optimism, or Polygon PoS at $< 0.1\text{ gwei}$) reduce execution gas fees by 10x to 50x compared to Ethereum L1, making automated micro-payouts viable without prohibitive transaction overhead.

#### Q28: Why 2-of-3 majority consensus instead of 3-of-5 or 5-of-7?
> **Answer**: In remote agricultural monitoring, only three distinct, freely available public physical observation domains exist at macro scale: surface meteorological (rainfall/temperature), optical canopy reflectance (NDVI), and microwave soil moisture (SMAP). Introducing additional oracles would require subdividing these physical domains or deploying physical IoT hardware, re-introducing the exact maintenance overhead we set out to eliminate.

#### Q29: What happens if an oracle key is compromised?
> **Answer**: `CropInsurance.sol` uses OpenZeppelin `AccessControl`. The admin (`DEFAULT_ADMIN_ROLE`) can revoke the compromised key via `revokeRole()` and grant the oracle role to a freshly generated key without contract redeployment. Because settlement requires 2-of-3 agreement, a single compromised oracle key cannot unilaterally trigger or steal payouts.

#### Q30: How are tier thresholds justified, and how does this interface with PMFBY?
> **Answer**: 
> 1. **Threshold Assumptions**: Thresholds in `config/tier_rules.json` (rainfall 20/40/60%, NDVI and soil moisture 15/30/45% deficit) are **research assumptions**; deficits are measured against leave-one-year-out medians over 2017–2024, and the cut-offs are assumptions rather than APSDMA government drought declarations or actuarially certified tables.
> 2. **PMFBY Relationship**: According to the Comptroller and Auditor General (CAG) Performance Audit Report on PMFBY (Report No. 7 of 2022), traditional Crop Cutting Experiment (CCE) indemnity assessments have frequently faced multi-month yield compilation and subsidy reconciliation delays. Our prototype is an academic exploration of an automated parametric buffer that settles within days of seasonal conclusion based on objective biophysical indicators.

---

## 3. Five-Minute Live Demonstration Script

| Time | Action & Screen View | Spoken Narrative | Expected On-Screen Result |
|---|---|---|---|
| **0:00 - 1:00** | Terminal 1 & 2: Show running node and seeding output. | "We begin with a fresh Hardhat EVM node. Our seeding script deploys CropInsurance.sol, funds the risk pool with 50 ETH, and seeds policies across all lifecycle states." | Clean terminal logs showing 5 policies seeded. |
| **1:00 - 2:00** | Browser: Open `http://localhost:5173`. Show Header & Solvency metrics. | "The frontend connects to our contract on chain 31337. Here we see our risk pool balance of 50 ETH, total reserved exposure, and available solvency headroom." | Responsive dashboard displaying balances and connected roles. |
| **2:00 - 3:00** | Farmer Portal: Click "Preset: Anantapur Groundnut", show `landHash` calculation, check registry. | "When a farmer enters parcel coordinates, the browser normalizes them to fixed 5-decimal precision and hashes them with Keccak256. Notice the instant check confirming the parcel is free." | Canonical string, green 'Available' badge, dynamic premium 0.065 ETH. |
| **3:00 - 4:00** | Policy Table: Locate Policy #3 (`SETTLED`), click "Withdraw Payout". | "Policy #3 has settled via 2-of-3 consensus at Tier 2 (50% payout). The farmer has 1.0 ETH claimable. Clicking 'Withdraw Payout' executes our pull payment." | MetaMask confirmation, green toast with tx hash, balance updates. |
| **4:00 - 5:00** | Admin & Dev Tab: Show EVM Time Machine and Median Fallback Simulator. | "Finally, our Dev Panel demonstrates smart contract time-travel and 1-click median fallback consensus, where differing tiers [1, 3, 2] resolve safely to median Tier 2." | Toast showing median resolution at Tier 2 (50% payout). |

---

## 4. Ten-Minute Comprehensive Technical Demonstration Script

- **0:00 - 2:00 (Architecture & Problem)**: Walk through the three public data sources in [`docs/data_pipeline.md`](data_pipeline.md). Explain why on-field IoT hardware is replaced with remote sensing.
- **2:00 - 4:00 (Smart Contract & Solvency)**: Open [`contracts/CropInsurance.sol`](../contracts/CropInsurance.sol). Walk through the solvency invariant check in `createPolicy()` and pull payments in `withdrawPayout()`.
- **4:00 - 6:00 (Farmer DApp Flow)**: Connect MetaMask as Farmer. Demonstrate boundary registration, dynamic premium calculation, and policy creation. Show how re-registering the same parcel reverts with `LandAlreadyInsured`.
- **6:00 - 7:30 (Oracle Consensus & Settlement)**: Connect as Oracle. Submit reports for Policy #2 from Weather and Satellite at Tier 1. Show that the contract reaches consensus without waiting for the 3rd soil report.
- **7:30 - 9:00 (Dispute Adjudication & Fraud Hook)**: Show Policy #5 (`DISPUTED`). Switch to Admin role, enter Review Queue, and execute dispute resolution upgrading the payout from Tier 1 (25%) to Tier 2 (50%).
- **9:00 - 10:00 (Scientific Experiments & Q&A Transition)**: Display [`results/e3_faulty_robustness.png`](../results/e3_faulty_robustness.png) and [`results/e4_tiered_vs_binary.png`](../results/e4_tiered_vs_binary.png). Highlight the 8.9x error suppression and basis risk reduction.

---

## 5. "If Something Fails Live" Fallback Checklist

1. **MetaMask fails to connect or shows wrong network**:
   - *Action*: Use the read-only fallback provider already active in the DApp. All seeded policies, risk pool metrics, and reports are fully viewable without wallet connection.
   - *Fix*: Click the red "Switch to Chain 31337" button in the header, or reset MetaMask account activity (Settings $\to$ Advanced $\to$ Clear activity tab data).
2. **Hardhat node crashes or port 8545 occupied**:
   - *Action*: In PowerShell, run `Get-Process node | Stop-Process -Force`, then restart `npx hardhat node` and run `python scripts/seed_frontend_demo.py`.
3. **Transaction reverts unexpectedly**:
   - *Action*: Look at the toast alert! Our custom error decoder ([`decodeContractError`](../frontend/src/utils/web3.ts)) translates raw revert data into human-readable text (e.g. season not ended, land already insured).
4. **Live experiment execution is too slow during presentation**:
   - *Action*: Open pre-generated publication charts directly from [`results/`](../results/) (`e1_consensus_vs_single.png`, `e3_faulty_robustness.png`, `e4_tiered_vs_binary.png`, `e5_fraud_benchmark.png`, `e6_gas_comparison.png`). Every figure is pre-rendered at 300 DPI.

---

## 6. Manual Screenshot Guide for Presentation

If Playwright is not installed, capture these four clean screenshots for your presentation slides:

1. **Farmer Registration View**: `http://localhost:5173` on *Farmer Portal* showing the Anantapur Groundnut preset, canonical coordinate string, Keccak256 hash, and green availability badge.
2. **Active & Historical Policies Table**: Table showing policies across distinct lifecycle states (`ACTIVE`, `AWAITING_ORACLES`, `SETTLED`, `UNDER_REVIEW`, `DISPUTED`) with per-oracle report pills.
3. **Admin Solvency & Review Dashboard**: *Admin & Oracles* tab showing the Risk Pool metrics (Total Balance, Reserved Exposure, Solvency Headroom) and Review Queue.
4. **Dev Simulation & EVM Time Machine**: *Dev & Simulation* tab showing Hardhat time travel buttons and the Hardhat test accounts credentials table.
