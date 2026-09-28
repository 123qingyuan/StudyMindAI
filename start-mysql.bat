@echo off
setlocal
cd /d E:\StudyMindAI
if not exist runtime\mysql-data\ibdata1 (
  echo MySQL data directory is not initialized.
  exit /b 1
)
start "StudyMind MySQL" /min runtime\mysql\bin\mysqld.exe --defaults-file=E:\StudyMindAI\runtime\mysql\my.ini --console
