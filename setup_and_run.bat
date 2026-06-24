@echo off
cd /d "%~dp0"

echo === TailorCV Setup ===
echo.

REM .venv already exists, skip creation
if exist ".venv" goto run_app

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=py -3
) else (
    set PYTHON=python
)

echo Creating virtual environment...
%PYTHON% -m venv .venv
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt

:run_app
echo Starting TailorCV at http://localhost:8000
echo.
.venv\Scripts\python -m app.main > tailorcv.log 2>&1
echo.
echo App stopped. Check tailorcv.log for errors.
pause
