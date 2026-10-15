@echo off
REM Start Vantage DD from cmd.exe (same as start.ps1)
cd /d "%~dp0..\.."
".venv\Scripts\python.exe" scripts\manage.py check-config || exit /b 1
echo Open http://127.0.0.1:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
