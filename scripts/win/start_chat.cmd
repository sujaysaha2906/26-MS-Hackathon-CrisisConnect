@echo off
cd /d "%~dp0..\.."
if not exist "venv\Scripts\python.exe" (
  echo Run scripts\win\setup_venv.cmd and install requirements-live.txt first. See README.md.
  pause
  exit /b 1
)
venv\Scripts\python.exe main.py %*
if errorlevel 1 pause
