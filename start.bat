@echo off
setlocal
cd /d "%~dp0"
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0scripts\launch.py" %*
if errorlevel 1 pause
