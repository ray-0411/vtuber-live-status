@echo off
setlocal

cd /d "%~dp0"
python src\list_working.py --limit 30 %*
pause
