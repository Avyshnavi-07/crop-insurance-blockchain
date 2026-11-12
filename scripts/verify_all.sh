#!/usr/bin/env bash
# ==============================================================================
# Crop Insurance Chain - Full Protocol Verification Script (Bash)
# ==============================================================================
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "================================================================================"
echo " CROP INSURANCE CHAIN - FULL REPRODUCIBILITY & VERIFICATION SUITE (BASH)"
echo "================================================================================"

PY_BIN="python3"
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PY_BIN="$REPO_ROOT/.venv/bin/python"
elif [ -f "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
    PY_BIN="$REPO_ROOT/.venv/Scripts/python.exe"
fi

echo -e "\n>>> [1/8] Running Hardhat Smart Contract Tests..."
npx hardhat test

echo -e "\n>>> [2/8] Running Solhint Solidity Linter..."
npx solhint "contracts/**/*.sol"

echo -e "\n>>> [3/8] Running Pytest Unit & Integration Tests..."
$PY_BIN -m pytest test/

echo -e "\n>>> [4/8] Running Flake8 Python Linter..."
$PY_BIN -m flake8 experiments/ oracles/ fraud/ test/ scripts/

echo -e "\n>>> [5/8] Running Frontend Vitest Suite..."
(cd frontend && npm run test)

echo -e "\n>>> [6/8] Running Frontend TypeCheck..."
(cd frontend && npm run lint)

echo -e "\n>>> [7/8] Running Frontend Build..."
(cd frontend && npm run build)

echo -e "\n>>> [8/8] Running Master Scientific Experiments Runner (E1-E6)..."
$PY_BIN -m experiments.run_all

echo -e "\n================================================================================"
echo "[SUCCESS] ALL 8 VERIFICATION GATES PASSED CLEANLY!"
echo "================================================================================"
