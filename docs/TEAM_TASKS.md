# Team Tasks & Contribution Matrix

**Project**: Crop Insurance Chain: Hardware-Free Multi-Source Blockchain Parametric Crop Insurance Protocol  
**Lead Researcher & Developer**: Lakshmi Prasanna (`donthuprasanna27@gmail.com`)  
**Institution / Scope**: Final Year Engineering Capstone / Master's Research Prototype  
**Date**: November 2026  

---

## 1. Project Roles & Task Attribution

| Role / Responsibility | Assigned Contributor | Key Tasks & Deliverables Completed |
|---|---|---|
| **Principal System Architect & Smart Contract Lead** | **Lakshmi Prasanna** | - Designed mathematical solvency invariant: `riskPoolBalance + premium >= reservedExposure + sumInsured`<br/>- Authored `CropInsurance.sol` with OpenZeppelin `AccessControl`, `ReentrancyGuard`, and Checks-Effects-Interactions pattern<br/>- Implemented on-chain 2-of-3 consensus engine and median fallback algorithm<br/>- Integrated cadastral boundary polygon hashing (`activeLandHashes` duplicate guard)<br/>- Conducted Slither static analysis security audit and triaged findings |
| **Data Pipeline & Oracles Engineer** | **Lakshmi Prasanna** | - Engineered public data extraction pipeline for Open-Meteo ERA5-Land precipitation<br/>- Developed Google Earth Engine interfaces for Sentinel-2 NDVI canopy index and NASA SMAP root-zone soil moisture<br/>- Designed leave-one-year-out (LOO) historical median baseline calculation (2017–2024)<br/>- Built independent Python oracle daemons and contract adapter with Web3.py<br/>- Implemented automated cached benchmark fallbacks for reproducible evaluation |
| **Machine Learning & Fraud Specialist** | **Lakshmi Prasanna** | - Formulated adversarial threat model: duplicate cadastral polygons, bounding box evasion, anomaly claims, valuation inflation<br/>- Synthesized reproducible 3,200-sample policy dataset with continuous anomaly spectra and hard negatives<br/>- Evaluated Heuristic Rule Engine, Isolation Forest, and MLP Autoencoder architectures<br/>- Engineered nearest-neighbor spatial proximity enhancement, doubling duplicate boundary recall ($26.67\% \to 53.33\%$) |
| **Experimental Design & Evaluation Lead** | **Lakshmi Prasanna** | - Conducted Ground Truth Audit and defined Continuous Mean Deficit Index (CMDI)<br/>- Executed Experiment E1 (Consensus vs. Single Source, $r_s = 0.8068$, MAPE $7.72$ pp)<br/>- Executed Experiment E2 (Ablation of pairwise configurations and disagreement variants)<br/>- Executed Experiment E3 (Monte Carlo fault injection, demonstrating 8.9x error suppression and 100% EVM parity)<br/>- Executed Experiment E4 (Tiered vs. Binary triggers basis risk evaluation across 4 continuous loss mappings)<br/>- Executed Experiment E5 (Adversarial ML fraud benchmark across 5 random seeds)<br/>- Executed Experiment E6 (Smart contract empirical gas profiling and transaction latency across $N=30$ runs) |
| **Frontend Engineer & Web3 Integration** | **Lakshmi Prasanna** | - Developed modern React 18 / TypeScript single-page application using Tailwind CSS and Lucide icons<br/>- Implemented client-side coordinate normalization to 5-decimal precision and Keccak-256 boundary hashing<br/>- Built interactive role-based portals (Farmer Portal, Admin Solvency Dashboard, Oracle Dispatcher, Review Queue)<br/>- Implemented custom Solidity error decoding via `ethers.Interface.parseError()`<br/>- Added zero-setup read-only JsonRpcProvider fallback for frictionless evaluation |
| **Documentation & Viva Preparation** | **Lakshmi Prasanna** | - Authored comprehensive research documentation (`README.md`, `experiments.md`, `viva_guide.md`, `HANDOFF.md`, `INDEX.md`)<br/>- Created automated 8-gate protocol verification suite (`scripts/verify_all.ps1`)<br/>- Prepared 30 comprehensive viva voce defense examination questions and 5/10-minute demonstration scripts |

---

## 2. Phase-by-Phase Task Matrix

```mermaid
gantt
    title Research Prototype Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 0 & 1
    Environment Setup & Smart Contracts       :done, p0, 2026-09-15, 2026-09-25
    Access Control, Solvency & Consensus       :done, p1, 2026-09-26, 2026-10-05
    section Phase 2 & 3
    Public Earth Observation Pipeline         :done, p2, 2026-10-06, 2026-10-18
    Oracle Daemons & Contract Adapter          :done, p3, 2026-10-19, 2026-10-28
    section Phase 4 & 5
    Adversarial Fraud Module & Spatial ML      :done, p4, 2026-10-29, 2026-11-04
    Scientific Experiments E1 to E6            :done, p5, 2026-11-05, 2026-11-08
    section Phase 6 & 7
    Interactive React DApp & Demo Seeder       :done, p6, 2026-11-08, 2026-11-10
    Final Documentation, Audit & Packaging     :done, p7, 2026-11-10, 2026-11-11
```

---

## 3. Contact & Authorship Notice
All primary source code, smart contracts, machine learning models, and evaluation documentation were developed by **Lakshmi Prasanna** as an open-source academic research prototype.
For academic inquiries or reproduction guidance, contact:
- **Email**: `donthuprasanna27@gmail.com`
- **GitHub**: [`https://github.com/crop-insurance-chain/crop-insurance-chain`](https://github.com/crop-insurance-chain/crop-insurance-chain)
