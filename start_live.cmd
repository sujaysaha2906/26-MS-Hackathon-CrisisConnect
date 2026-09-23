@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv and install requirements-live.txt first. See README.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py --live
if errorlevel 1 pause
