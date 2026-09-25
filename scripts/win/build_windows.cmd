@echo off
cd /d "%~dp0..\.."
if not exist "venv\Scripts\python.exe" (
  echo Run scripts\win\setup_venv.cmd first. See docs\DEPLOY_AND_TEST.md.
  exit /b 1
)
venv\Scripts\python.exe -m pip install -r requirements-live.txt -r requirements-build.txt
if errorlevel 1 exit /b 1
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name CrisisConnectDesktop --add-data "data;data" main.py
if errorlevel 1 exit /b 1
echo Built dist\CrisisConnectDesktop\CrisisConnectDesktop.exe. Copy the WHOLE folder when deploying.
if not exist "dist\CrisisConnectDesktop\config.json" (
  copy /y "config.json" "dist\CrisisConnectDesktop\config.json" >nul
  if errorlevel 1 exit /b 1
)
echo Azure credentials are NOT bundled. Test on Windows before distribution.
