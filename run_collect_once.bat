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

echo Running one live-status collection...
echo Project: %CD%
echo Timezone: Asia/Taipei
echo.

python src\run_local_scheduler.py --once --timezone Asia/Taipei

echo.
echo One-time collection finished.
pause
