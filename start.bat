@echo off
REM Double-click on Windows to launch TailorCV.
cd /d "%~dp0"

if not exist ".venv" (
  echo First-time setup: creating virtual environment...
  python -m venv .venv
  .venv\Scripts\pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)

if not exist ".env" (
  echo.
  echo No .env file found. Copy .env.example to .env and add your Anthropic API key.
  echo.
)

echo Starting TailorCV at http://localhost:8000  (press Ctrl+C to stop)
.venv\Scripts\python -m app.main
pause
