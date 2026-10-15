# Start Vantage DD (API + built dashboard) on http://127.0.0.1:8000
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
& $Py scripts\manage.py check-config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Open http://127.0.0.1:8000  (Ctrl+C to stop)"
& $Py -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
