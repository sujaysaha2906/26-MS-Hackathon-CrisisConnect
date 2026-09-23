@echo off
cd /d "%~dp0"
py -3 main.py --demo
if errorlevel 1 pause
