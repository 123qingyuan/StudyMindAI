@echo off
setlocal
cd /d "%~dp0.."
call npm --prefix frontend run typecheck || exit /b 1
call npm --prefix frontend run build || exit /b 1
backend\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist/v2.0.0 --workpath build/v2.0.0 StudyMindAI.spec || exit /b 1
echo Built: %CD%\dist\v2.0.0\StudyMindAI.exe