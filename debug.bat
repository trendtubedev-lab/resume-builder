@echo off
cd /d "%~dp0"
set LOG=C:\Users\May Nerd\Claude Workspace\resume-builder\resume-builder\run.log
echo Starting app... > "%LOG%"
echo Dir: %CD% >> "%LOG%"
.venv\Scripts\python -m app.main >> "%LOG%" 2>&1
echo Exit code: %errorlevel% >> "%LOG%"
pause
