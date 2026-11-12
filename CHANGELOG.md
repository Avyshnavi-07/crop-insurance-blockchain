# Changelog

All notable changes to the **Crop Insurance Chain** research prototype are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-research-prototype] - 2026-11-10

### Added
- **Phase 0: Environment Setup**: Hardhat 2.29, OpenZeppelin 5.1, Python 3.11 virtualenv, configuration schemas, baseline directory structure.
- **Phase 1: Smart Contracts (`CropInsurance.sol`)**:
  - OpenZeppelin `AccessControl` and `ReentrancyGuard` integration.
  - On-chain solvency invariant enforcement (`riskPoolBalance + premium >= reservedExposure + sumInsured`).
  - Regional dynamic pricing incorporating base rate (3.0%) and district loadings (Anantapur 3.5%, Kurnool 2.5%, Kadapa 2.0%).
  - Duplicate parcel protection via `activeLandHashes` mapping.
  - 2-of-3 oracle consensus with median fallback for three-way divergence.
  - Graduated 4-tier payout schedule (0%, 25%, 50%, 100%).
  - Pre-settlement fraud flag hook (`flagFraud`) and 14-day timeout escalation.
  - 7-day post-settlement dispute resolution window (`openDispute`, `resolveDispute`).
  - Pull-payment payouts (`withdrawPayout`) preventing reentrancy attacks.
  - 23/23 Hardhat test suite and Slither static analysis triage.
- **Phase 2: Agricultural Data Pipeline**:
  - Ingestion modules for Open-Meteo ERA5-Land rainfall, Sentinel-2 NDVI peak canopy indices, and NASA SMAP root-zone soil moisture.
  - Leave-one-year-out historical baseline methodology avoiding data leakage across 2017–2024 Kharif seasons.
  - Curated 24 historical district-year dataset in `data/processed/dataset.csv`.
- **Phase 3: Oracle Services & Local Demo**:
  - Independent oracle daemon signers for weather, satellite, and soil moisture.
  - Synthetic fault injector with `random` and `off_by_one` corruption modes.
  - End-to-end integration demo verifying 2-of-3 agreement, single-fault resilience, median fallback, and 2-report waiting logic.
- **Phase 4: Fraud Detection ML Module**:
  - Non-circular synthetic fraud data generator with continuous anomaly spectra and hard negatives ($n=3,200$, 9.0% fraud rate).
  - Tri-model benchmark: Heuristic Rule Engine, Unsupervised Isolation Forest, and Reconstruction MLP Autoencoder.
  - Pre-settlement fraud integration script connecting ML warnings to on-chain `flagFraud()`.
- **Phase 5: Reproducible Scientific Experiments (E1–E6)**:
  - Unified runner `python -m experiments.run_all` generating CSVs, 300 DPI publication charts, and LaTeX tables.
  - Ground truth audit establishing Continuous Mean Deficit Index (CMDI) secondary reference.
  - E1: Multi-source consensus vs. single-source physical oracles.
  - E2: Pairwise oracle ablation study with Variant A (strict) and Variant B (conservative min).
  - E3: 200 Monte Carlo fault trials and 30-policy on-chain EVM parity verification.
  - E4: Basis risk evaluation across 4 continuous damage curves comparing tiered vs. binary triggers.
  - E5: Spatial nearest-neighbor proximity enhancement for near-duplicate boundary jitter attacks.
  - E6: Gas profiling over 30 fresh runs per function and Sepolia testnet execution harness.
- **Phase 6: React + Vite + Ethers Web Application**:
  - High-contrast, framework-free responsive UI in `frontend/`.
  - In-browser polygon normalization and Keccak256 `landHash` calculation.
  - Complete custom error decoding for all Solidity custom errors.
  - Farmer portal for cadastral registration, premium calculation, policy purchase, dispute filing, and pull payout withdrawals.
  - Role-gated Admin/Oracle dashboard for pool solvency, oracle reporting, and dispute adjudication.
  - Dev panel with EVM time travel and 1-click batch consensus verification.
  - 14/14 Vitest unit tests verifying cryptographic helpers and error decoders.
- **Phase 7: Final Documentation, Claims Audit & Reproducibility**:
  - Meticulous claims audit verifying all documentation numbers against `results/*.csv`.
  - Comprehensive `README.md` with system architecture, lifecycle, and sequence Mermaid diagrams.
  - Complete `docs/viva_guide.md` with 30 examiner questions, demo scripts, fallback checklist, and cheat sheet.
  - Reproducibility verification scripts (`scripts/verify_all.ps1` and `scripts/verify_all.sh`).
  - `LICENSE` (MIT for software; data under original provider terms) and `THIRD_PARTY.md`.
  - `results/MANIFEST.md` cataloging all experiment outputs, scripts, and seeds.
