# Vantage DD — one-time setup on Windows (PowerShell). No Docker or WSL required.
# Prerequisites: Python 3.12 or 3.13 (python.org installer, "Add to PATH"), Node.js 20.19+ or 22 LTS (nodejs.org).
# Run from the repository root:   powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"          # UTF-8 text I/O on Windows (the code also passes encoding="utf-8" explicitly)
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

# PowerShell does not stop when an external program fails: check every exit code explicitly.
function Step([string]$What, [scriptblock]$Run) {
    Write-Host "==> $What"
    & $Run
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $What (exit code $LASTEXITCODE). Setup stopped; nothing else was changed." -ForegroundColor Red; exit 1 }
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is not installed or not on PATH (need 20.19+ or 22 LTS)." -ForegroundColor Red; exit 1
}
$nodeVer = (& node -v).Trim()
$nv = [version]($nodeVer.TrimStart("v"))
if ($nv -lt [version]"20.19.0") { Write-Host "Node.js $nodeVer is too old: install 20.19+ or 22 LTS from nodejs.org." -ForegroundColor Red; exit 1 }

if (-not (Test-Path ".venv")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        Step "create virtual environment" { py -3 -m venv .venv }
    } else {
        Step "create virtual environment" { python -m venv .venv }
    }
}
$Py = Join-Path $Root ".venv\Scripts\python.exe"
Step "upgrade pip" { & $Py -m pip install --upgrade pip }
Step "install Python packages" { & $Py -m pip install -r backend\requirements-dev.txt }

# .env with random JWT secret and a random demo password (printed once). Existing .env is never overwritten.
Step "create .env (only if missing)" { & $Py scripts\manage.py setup }

Push-Location frontend
Step "install front-end packages" { npm ci }
Step "build front end" { npm run build }
Pop-Location

Step "check installation" { & $Py scripts\manage.py doctor }
# Creates a NEW database only. An existing database is never upgraded by setup: it is inspected read-only and
# you decide (see docs\OPERATIONS.md, "Upgrading an existing database").
Step "create new database (never upgrades an existing one)" { & $Py scripts\manage.py migrate --new-only }
Step "check configuration" { & $Py scripts\manage.py check-config }
Write-Host ""
Write-Host "Setup complete. Start the app with:  powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1"
