# Crop Insurance Chain - Documentation Index

This directory contains technical documentation, security audits, empirical experiment reports, and viva examination materials for the **Crop Insurance Chain** research prototype.

---

## Documentation Roadmap

| Document | Description | Primary Audience |
|---|---|---|
| [`README.md`](../README.md) | Protocol overview, architecture diagrams, threat model, reproduction guide | All / Evaluators |
| [`HANDOFF.md`](../HANDOFF.md) | Local demo instructions, prerequisites, and MetaMask test account roles table | Evaluators / Examiners |
| [`docs/TEAM_TASKS.md`](TEAM_TASKS.md) | Contribution matrix, project responsibilities, and implementation roadmap | Academic Reviewers |
| [`docs/viva_guide.md`](viva_guide.md) | 30+ examiner defense Q&As, 5/10-min demo scripts, fallback checklist, numbers cheat sheet | Viva Examiner / Students |
| [`docs/experiments.md`](experiments.md) | Complete empirical results for Experiments E1–E6, methodology, and threats to validity | Researchers / Reviewers |
| [`docs/fraud_module.md`](fraud_module.md) | Dual-layer fraud architecture, synthetic data design, ML benchmarks, and spatial proximity | ML Engineers / Auditors |
| [`docs/data_pipeline.md`](data_pipeline.md) | Ingestion from Open-Meteo, Sentinel-2, NASA SMAP, and leave-one-year-out baseline math | Data Engineers / Agronomists |
| [`docs/slither_audit.md`](slither_audit.md) | Slither v0.11.6 static analysis findings triage and security justifications | Smart Contract Auditors |
| [`frontend/README.md`](../frontend/README.md) | React + Vite + Ethers frontend setup, MetaMask accounts guide, and demo walkthrough | DApp Users / Evaluators |
| [`results/MANIFEST.md`](../results/MANIFEST.md) | Provenance catalog of every CSV, figure, and LaTeX table with generating scripts and seeds | Reproducibility Auditors |
| [`THIRD_PARTY.md`](../THIRD_PARTY.md) | Third-party software dependencies licenses and public data source attribution terms | Legal / Compliance |
| [`CHANGELOG.md`](../CHANGELOG.md) | Version history and phase-by-phase implementation record | Developers |

---

## Architecture at a Glance

1. **Smart Contracts**: [`contracts/CropInsurance.sol`](../contracts/CropInsurance.sol)
2. **Oracle Daemons**: [`oracles/`](../oracles/)
3. **Data Pipeline**: [`build_dataset.py`](../build_dataset.py)
4. **Fraud Detection**: [`fraud/`](../fraud/)
5. **Experiment Suite**: [`experiments/`](../experiments/)
6. **Frontend Web App**: [`frontend/`](../frontend/)
7. **Verification Harness**: [`scripts/verify_all.ps1`](../scripts/verify_all.ps1)
