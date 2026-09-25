@echo off
cd /d "%~dp0..\.." || exit /b 1
call scripts\win\setup_venv.cmd
if errorlevel 1 exit /b 1
venv\Scripts\python.exe -m pip install -r requirements-demo.txt
if errorlevel 1 exit /b 1
venv\Scripts\python.exe -m crisisconnect.setup_demo_model
if errorlevel 1 exit /b 1
echo Demo ready. Run scripts\win\start_demo.cmd.
echo Install eSpeak NG for English, Spanish, and Bengali voices, or matching Windows desktop voices.
