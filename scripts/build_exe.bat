@echo off
setlocal
cd /d "%~dp0.."
call npm --prefix frontend run typecheck || exit /b 1
call npm --prefix frontend run build || exit /b 1
backend\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean StudyMindAI.spec || exit /b 1
echo Built: %CD%\dist\StudyMindAI.exe