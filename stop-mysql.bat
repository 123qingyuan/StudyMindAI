@echo off
setlocal
cd /d E:\StudyMindAI
runtime\mysql\bin\mysqladmin.exe --protocol=tcp -h127.0.0.1 -P3306 -ustudymind -p shutdown
