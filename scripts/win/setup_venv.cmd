@echo off
setlocal
cd /d "%~dp0..\.." || exit /b 1
if exist "venv\Scripts\python.exe" (
  echo Virtual environment already exists in venv.
  goto ready
)
if exist "venv" (
  echo ERROR: venv exists but is not a Windows virtual environment. Rename it before retrying.
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  python -m venv venv
) else (
  py -3 -m venv venv
)
if errorlevel 1 (
  echo ERROR: Could not create venv. Install Python 3.11+ with venv support and retry.
  exit /b 1
)
:ready
echo To activate from the project root in CMD: call venv\Scripts\activate.bat
exit /b 0
