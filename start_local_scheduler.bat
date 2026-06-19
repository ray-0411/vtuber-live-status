@echo off
setlocal

cd /d "%~dp0"

if not defined TWITCH_CLIENT_ID (
  echo TWITCH_CLIENT_ID is not set.
  echo Please set it before running this file.
  pause
  exit /b 1
)

if not defined TWITCH_CLIENT_SECRET (
  echo TWITCH_CLIENT_SECRET is not set.
  echo Please set it before running this file.
  pause
  exit /b 1
)

echo Starting local live-status scheduler...
echo Project: %CD%
echo Interval: 300 seconds
echo.

python src\run_local_scheduler.py --interval-seconds 300

echo.
echo Scheduler stopped.
pause
