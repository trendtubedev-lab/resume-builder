@echo off
REM Kill any running TailorCV server, then start it fresh.
cd /d "%~dp0"

echo Stopping any running TailorCV process...
taskkill /F /FI "WINDOWTITLE eq TailorCV*" /T >nul 2>&1
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)

echo Starting TailorCV at http://localhost:8000  (press Ctrl+C to stop)
.venv\Scripts\python -m app.main >> "C:\Users\May Nerd\Claude Workspace\resume-builder\resume-builder\run.log" 2>&1
pause
