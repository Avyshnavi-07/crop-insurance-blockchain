# Crop Insurance Chain - Frontend DApp

A lightweight, research-grade React + Vite + TypeScript web application built with Ethers.js v6 for the **Crop Insurance Chain** parametric blockchain crop insurance protocol (Andhra Pradesh: Anantapur, Kurnool, Kadapa).

Designed with zero UI framework bloat (custom high-contrast CSS), full custom error decoding, in-browser cryptographic polygon normalization and keccak256 hashing, and complete role-gated admin/oracle/farmer workflows.

---

## 1. Quick Start Guide (PowerShell)

### Step 1: Start the Local Hardhat Ethereum Node
In your first terminal, run:
```powershell
Set-Location C:\Users\SAMA\Desktop\crop-insurance-chain
npx hardhat node
```
This starts an EVM JSON-RPC node on `http://127.0.0.1:8545` with Chain ID `31337`. Keep this terminal open.

### Step 2: Seed the Demo Environment
In a second terminal, seed the smart contract with initial risk pool liquidity, access roles, and 5 demo policies in distinct lifecycle states:
```powershell
Set-Location C:\Users\SAMA\Desktop\crop-insurance-chain
.\.venv\Scripts\python scripts/seed_frontend_demo.py
```
This automatically:
- Deploys `CropInsurance.sol`.
- Grants `ORACLE_WEATHER_ROLE`, `ORACLE_SATELLITE_ROLE`, `ORACLE_SOIL_ROLE`, `FRAUD_CHECKER_ROLE`, and `DISPUTE_REVIEWER_ROLE`.
- Funds the solvency risk pool with 50.0 ETH.
- Configures regional risk loadings (Anantapur: 350 bps, Kurnool: 250 bps, Kadapa: 200 bps).
- Seeds 5 demonstration policies:
  * **Policy #1 (`ACTIVE`)**: Future maturity (active coverage).
  * **Policy #2 (`AWAITING_ORACLES`)**: Matured, ready for multi-oracle reports.
  * **Policy #3 (`SETTLED`)**: 2-of-3 consensus reached at Tier 2 (Severe), **1.0 ETH claimable payout**.
  * **Policy #4 (`UNDER_REVIEW`)**: Flagged for cadastral duplicate spatial anomaly.
  * **Policy #5 (`DISPUTED`)**: Settled at 25%, farmer filed formal dispute, awaiting review.
- Exports the contract ABI to `frontend/src/abi/CropInsurance.json` and active address to `frontend/src/config.json`.

### Step 3: Launch the Frontend Web Application
In a third terminal, run:
```powershell
Set-Location C:\Users\SAMA\Desktop\crop-insurance-chain\frontend
npm run dev
```
Open your browser at:
`http://localhost:5173`

---

## 2. MetaMask Wallet Configuration

1. **Add Custom Network**:
   - **Network Name**: Hardhat Localhost
   - **RPC URL**: `http://127.0.0.1:8545`
   - **Chain ID**: `31337`
   - **Currency Symbol**: `ETH`

2. **Import Test Accounts**:
   Import any of these standard local Hardhat test private keys into MetaMask to switch between roles:

| Role | Public Address | Private Key (Local Dev Only) |
|---|---|---|
| **Deployer / Admin / Reviewer** | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80` |
| **Farmer (Policyholder)** | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` | `0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a` |
| **Weather Oracle** | `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC` | `0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d` |
| **Satellite Oracle** | `0x90F79bf6EB2c4f870365E785982E1f101E93b906` | `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a` |
| **Soil Oracle** | `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65` | `0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6` |

*(Note: The DApp features a read-only fallback provider, so you can explore all seeded policies and metrics even before connecting MetaMask).*

---

## 3. Interactive Demonstration Flows

### Flow A: Register Land & Purchase Policy (Farmer Portal)
1. Navigate to **👨‍🌾 Farmer Portal**.
2. Click **Preset: Anantapur Groundnut** to populate coordinates.
3. Observe live canonical coordinate normalization and the generated Keccak256 `landHash`.
4. Click **🔍 Check Cadastral Registry Availability** to confirm the land is clear.
5. Select Sum Insured (e.g. `1.0 ETH`). Observe dynamic premium calculation (`0.0650 ETH` due to 6.5% rate for Anantapur).
6. Click **📝 Underwrite & Pay Premium** to create the policy on-chain.

### Flow B: Pull Payout Withdrawal
1. In the **Active & Historical Policies** table, find **Policy #3**.
2. Notice its status is `SETTLED` (Consensus Tier 2 - 50%), with **1.0000 ETH Claimable Payout**.
3. Click **💸 Withdraw Payout**.
4. The smart contract validates the `ReentrancyGuard`, zeroes out `payoutAmount`, marks `payoutWithdrawn = true`, and transfers 1.0 ETH directly to your wallet via pull payments.

### Flow C: Multi-Oracle Submission & Consensus Settlement
1. Switch to the **⚖️ Admin & Oracles** tab.
2. Select **Policy #2** in the **Multi-Oracle Submission Portal**.
3. Submit a report from the Weather Oracle (Tier 1).
4. Submit a report from the Satellite Oracle (Tier 1).
5. Switch to **🛠️ Dev & Simulation** and trigger settlement. The contract resolves 2-of-3 matching consensus without needing to wait for the 3rd soil report!

### Flow D: Dispute Adjudication & Payout Upgrade
1. In **Active & Historical Policies**, find **Policy #5** (`DISPUTED`).
2. Switch to **⚖️ Admin & Oracles**, scroll to **Review Queue & Dispute Adjudication**.
3. Select Policy #5, set **Adjudicated New Tier** to **Tier 2: Severe (50%)**, and click **⚖️ Execute Dispute Resolution**.
4. The contract upgrades the farmer's payout from 0.25 ETH to 0.50 ETH!

### Flow E: EVM Time Machine (Dev Panel)
1. Switch to **🛠️ Dev & Simulation**.
2. Click **⏩ Advance +1 Day** or **⏭️ Advance +15 Days** to trigger block timestamp shifts on the local Hardhat EVM (`evm_increaseTime`).

---

## 4. Frontend Testing & Build Verification

Run unit tests:
```powershell
npm run test
```
*(14/14 tests verify polygon normalization, keccak256 hashing, rulesHash agreement with Python, custom Solidity error decoding, and enum mappings).*

Run linter:
```powershell
npm run lint
```

Build production bundle:
```powershell
npm run build
```
*(Generates optimized static bundle in `frontend/dist/`).*
