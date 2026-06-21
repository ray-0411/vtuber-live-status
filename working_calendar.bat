@echo off
setlocal

cd /d "%~dp0"
python src\working_calendar.py %*
