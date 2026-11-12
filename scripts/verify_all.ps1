# ==============================================================================
# Crop Insurance Chain - Full Protocol Verification Script (PowerShell)
# Runs all linters, test suites, build harnesses, and scientific experiments.
# ==============================================================================

$ErrorActionPreference = "Continue"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " CROP INSURANCE CHAIN - FULL REPRODUCIBILITY & VERIFICATION SUITE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$results = [ordered]@{}
$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $repoRoot

function Run-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host ">>> [RUNNING] $Name..." -ForegroundColor Yellow
    $startTime = Get-Date
    try {
        & $Action
        if ($LASTEXITCODE -eq 0 -or $? -eq $true) {
            $elapsed = ((Get-Date) - $startTime).TotalSeconds
            $rounded = [math]::Round($elapsed, 2)
            Write-Host "    [PASS] $Name completed in ${rounded}s" -ForegroundColor Green
            $results[$Name] = "PASS (${rounded}s)"
        } else {
            Write-Host "    [FAIL] $Name failed with exit code $LASTEXITCODE" -ForegroundColor Red
            $results[$Name] = "FAIL"
        }
    } catch {
        Write-Host "    [ERROR] $Name encountered exception: $_" -ForegroundColor Red
        $results[$Name] = "ERROR"
    }
}

$pyPath = "python"
if (Test-Path "$repoRoot\.venv\Scripts\python.exe") {
    $pyPath = "$repoRoot\.venv\Scripts\python.exe"
}
$flakePath = "flake8"
if (Test-Path "$repoRoot\.venv\Scripts\flake8.exe") {
    $flakePath = "$repoRoot\.venv\Scripts\flake8.exe"
}

# 1. Smart Contract Tests
Run-Check "1. Smart Contract Tests (Hardhat)" {
    npx hardhat test
}

# 2. Solidity Linter (Solhint)
Run-Check "2. Solidity Static Linter (Solhint)" {
    npx solhint "contracts/**/*.sol"
}

# 3. Python Unit Tests (pytest)
Run-Check "3. Python Unit & Integration Tests (pytest)" {
    & $pyPath -m pytest test/
}

# 4. Python Linter (flake8)
Run-Check "4. Python Static Linter (flake8)" {
    & $flakePath experiments/ oracles/ fraud/ test/ scripts/
}

# 5. Frontend Unit Tests (vitest)
Run-Check "5. Frontend Unit Tests (Vitest)" {
    Set-Location "$repoRoot\frontend"
    npm run test
    Set-Location $repoRoot
}

# 6. Frontend TypeScript Linter
Run-Check "6. Frontend TypeCheck (tsc --noEmit)" {
    Set-Location "$repoRoot\frontend"
    npm run lint
    Set-Location $repoRoot
}

# 7. Frontend Production Build
Run-Check "7. Frontend Bundle Build (Vite)" {
    Set-Location "$repoRoot\frontend"
    npm run build
    Set-Location $repoRoot
}

# 8. Reproducible Scientific Experiments E1-E6
Run-Check "8. Scientific Experiments Suite E1-E6" {
    & $pyPath -m experiments.run_all
}

# Summary Report
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " VERIFICATION SUMMARY REPORT" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$allPass = $true
foreach ($key in $results.Keys) {
    $status = $results[$key]
    if ($status -like "*PASS*") {
        Write-Host "  [OK] $key : $status" -ForegroundColor Green
    } else {
        Write-Host "  [XX] $key : $status" -ForegroundColor Red
        $allPass = $false
    }
}

Write-Host "================================================================================" -ForegroundColor Cyan
if ($allPass) {
    Write-Host "[SUCCESS] ALL 8 VERIFICATION GATES PASSED CLEANLY!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[WARNING] ONE OR MORE VERIFICATION GATES FAILED." -ForegroundColor Red
    exit 1
}
