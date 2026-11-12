# Project Handoff & Local Demonstration Guide

**Project**: Crop Insurance Chain: Hardware-Free Multi-Source Blockchain Parametric Crop Insurance Protocol  
**Repository Location**: `C:\Users\SAMA\Desktop\crop-insurance-chain`  
**Current Status**: Academic Research Prototype (Phases 0 through 7 complete, audited, and verified)

---

## 1. Run the Demo Locally

This section provides complete, reproducible instructions to launch the interactive frontend DApp and local EVM simulation environment.

### 1.1 Prerequisites
- **Operating System**: Windows 10/11 with Windows PowerShell
- **Node.js**: v18.0.0+ / v20.0.0+ / v22.0.0+ (Tested with Node.js v22.16.0)
- **Python**: 3.11.x (Tested with Python 3.11.9 in virtual environment `.venv`)
- **Browser Extension**: MetaMask (or compatible Web3 browser wallet)

> **Important Deployment Status**:
> The localhost URL is not shareable. A public link requires a Sepolia deployment, which is not done.
> The demo operates strictly over a local JSON-RPC loopback (`http://127.0.0.1:8545`) and works **only on the machine running the Hardhat node**.

---

### 1.2 Exact Windows PowerShell Commands

To start the demo, open **three separate Windows PowerShell terminals** in the project root directory (`crop-insurance-chain`):

#### Terminal 1: Start Local Hardhat EVM Node
Starts an isolated local Ethereum JSON-RPC node on port 8545 with 20 pre-funded test accounts (10,000 ETH each):
```powershell
npx hardhat node
```
*Keep this terminal running in the background.*

#### Terminal 2: Seed Protocol State & Deploy Contracts
Deploys `CropInsurance.sol`, funds the risk pool with 50 ETH, grants access control roles, seeds 5 policies across different lifecycle states (`ACTIVE`, `AWAITING_ORACLES`, `SETTLED`, `UNDER_REVIEW`, `DISPUTED`), and synchronizes the frontend configuration:
```powershell
python scripts\seed_frontend_demo.py
```
*(If using the project virtual environment, run: `.\.venv\Scripts\python scripts\seed_frontend_demo.py`)*

#### Terminal 3: Install Frontend Dependencies & Launch Web Interface
Navigates to the React/Vite web application, installs client dependencies, and launches the development server:
```powershell
cd frontend
npm install
npm run dev
```

---

### 1.3 Accessing the Web Application
Open your browser and navigate to:
```text
http://localhost:5173
```
*Note: A read-only fallback provider is automatically active. Evaluators can view the pool balances, inspect policies, and observe oracle reports immediately even before connecting a wallet.*

---

### 1.4 MetaMask Configuration (Local Hardhat Network)

To interact with the contract as a Farmer, Admin, or Oracle, configure MetaMask to connect to the local node:

1. In MetaMask, open **Settings $\to$ Networks $\to$ Add a network manually**.
2. Enter the following parameters:
   - **Network Name**: `Hardhat Local 31337`
   - **New RPC URL**: `http://127.0.0.1:8545`
   - **Chain ID**: `31337`
   - **Currency Symbol**: `ETH`
3. Click **Save** and switch to the newly created network.

> [!WARNING]
> **Test Accounts Only**: The private keys listed below are well-known, publicly published Hardhat default test keys. Use them **strictly for local development and testing**. Never transfer real fiat, mainnet cryptocurrency, or production assets to these addresses.

---

### 1.5 Account Roles & Test Keys

The contract uses OpenZeppelin `AccessControl` to partition administrative, underwriting, and oracle capabilities. Roles are configured in `frontend/src/config.json`:

| Account Key | Public Address | Public Test Private Key (Import to MetaMask) | Granted Contract Roles | Primary Purpose in Demo |
|---|---|---|---|---|
| **DEPLOYER_ADMIN** | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80` | `DEFAULT_ADMIN_ROLE`<br/>`FRAUD_CHECKER_ROLE`<br/>`DISPUTE_REVIEWER_ROLE` | Deploys contract, funds risk pool, sets regional risk loadings, flags fraud via `flagFraud()`, and adjudicates disputes via `resolveDispute()`. |
| **FARMER** | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` | `0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d` | `FARMER` *(Standard EOA)* | Buys policies with boundary normalization, pulls indemnity payouts via `withdrawPayout()`, and files claims disputes via `openDispute()`. |
| **ORACLE_WEATHER** | `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC` | `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a` | `ORACLE_WEATHER_ROLE` | Submits ERA5-Land rainfall deficit severity reports via `submitReport()`. |
| **ORACLE_SATELLITE** | `0x90F79bf6EB2c4f870365E785982E1f101E93b906` | `0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6` | `ORACLE_SATELLITE_ROLE` | Submits Sentinel-2 NDVI vegetative canopy loss reports via `submitReport()`. |
| **ORACLE_SOIL** | `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65` | `0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a` | `ORACLE_SOIL_ROLE` | Submits NASA SMAP root-zone soil moisture deficit reports via `submitReport()`. |

---

## 2. Seeded Policies Walkthrough

The seeding script generates five distinct policy scenarios to test the entire lifecycle:

1. **Policy #1 (`ACTIVE`)**:
   - *Region*: Anantapur, *Crop*: Groundnut, *Sum Insured*: 1.0 ETH, *Premium*: 0.065 ETH.
   - *Status*: Future maturity date. Cannot be settled until `block.timestamp >= endTime`.
2. **Policy #2 (`AWAITING_ORACLES`)**:
   - *Status*: Season concluded (time fast-forwarded). Awaiting oracle reports. Demonstrates role-gated submission.
3. **Policy #3 (`SETTLED`)**:
   - *Consensus*: All 3 oracles reported Tier 2 (50% payout).
   - *Status*: Farmer has 1.0 ETH claimable balance. Click **"Withdraw Payout"** to test the pull-payment transfer.
4. **Policy #4 (`UNDER_REVIEW`)**:
   - *Status*: Flagged before settlement by `FRAUD_CHECKER_ROLE` due to duplicate cadastral coordinates. Settlement is halted until reviewed.
5. **Policy #5 (`DISPUTED`)**:
   - *Status*: Settled at Tier 1 (25% payout); farmer filed a dispute within the 7-day window. Reviewer can upgrade payout to Tier 2 or Tier 3 in the Admin tab.

---

## 3. Full Verification & Experiment Reproducibility

To re-run the entire automated test and experiment suite, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_all.ps1
```

Or run individual experiment scripts:
- `python -m experiments.run_all` (E1 to E6 master runner)
- `python -m experiments.e1_consensus_vs_single`
- `python -m experiments.e2_ablation`
- `python -m experiments.e3_faulty_robustness`
- `python -m experiments.e4_tiered_vs_binary`
- `python -m experiments.e5_fraud_comparison`
- `python -m experiments.e6_gas_latency`

All resulting tables and publication plots are saved deterministically to [`results/`](results/).
