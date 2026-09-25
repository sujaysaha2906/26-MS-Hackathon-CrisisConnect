@echo off
cd /d "%~dp0..\.." || exit /b 1
if not exist "venv\Scripts\python.exe" (
  echo Run scripts\win\setup_demo.cmd first.
  exit /b 1
)
venv\Scripts\python.exe main.py --demo %*
exit /b %errorlevel%
