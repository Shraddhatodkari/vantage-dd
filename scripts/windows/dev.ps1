# Developer mode: API with auto-reload on :8000 and the Vite dev server on :5173 (opens two windows).
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Py = Join-Path $Root ".venv\Scripts\python.exe"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root'; & '$Py' -m uvicorn app.main:app --app-dir backend --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\frontend'; npm run dev"
Write-Host "API: http://127.0.0.1:8000   Dashboard (dev): http://127.0.0.1:5173"
