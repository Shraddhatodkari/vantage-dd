# Run every automated check. Add -Live to also hit SEC/GLEIF/FRED (needs internet and VANTAGE_SEC_USER_AGENT).
# Uses temporary databases only: your vantage.db is never touched.
param([switch]$Live)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if ($Live) { $env:VANTAGE_LIVE_TESTS = "1" }
$results = [ordered]@{}

Push-Location backend
& $Py -m pytest -q; $results["backend tests"] = $LASTEXITCODE
Pop-Location
& $Py ml\eval\run_eval.py | Select-String "QUALITY GATE|blind_expectations_met"; $results["AI evaluation"] = $LASTEXITCODE
& $Py scripts\verify_source_to_screen.py; $results["source-to-screen (5 companies)"] = $LASTEXITCODE
Push-Location frontend
npx tsc -b --noEmit; $results["front-end type check"] = $LASTEXITCODE
npm test; $results["front-end tests"] = $LASTEXITCODE
Pop-Location

Write-Host ""
$failed = $false
foreach ($k in $results.Keys) {
    if ($results[$k] -eq 0) { Write-Host ("PASS  " + $k) -ForegroundColor Green }
    else { Write-Host ("FAIL  " + $k + " (exit code " + $results[$k] + ")") -ForegroundColor Red; $failed = $true }
}
if ($failed) { Write-Host "SOME CHECKS FAILED"; exit 1 } else { Write-Host "ALL CHECKS PASSED" }
