@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  RCM Originator Portal — Windows Task Scheduler setup
REM  Runs rcm_scraper.py every day at 4:00 PM (local time) to
REM  refresh live cash bids from RCM Co-op's feed.
REM ============================================================

set TASK_NAME=RCMOriginatorPortalBidRefresh
set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%rcm_scraper.py
set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe

echo.
echo ============================================================
echo  RCM Originator Portal — Task Scheduler Setup
echo ============================================================
echo  Task name : %TASK_NAME%
echo  Script    : %SCRIPT%
echo  Runs      : Daily at 4:00 PM (local time)
echo  Python    : %PYTHON%
echo ============================================================
echo.

schtasks /create /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /sc DAILY ^
  /st 16:00 ^
  /ru "%USERNAME%" ^
  /f

if %errorlevel%==0 (
    echo.
    echo [OK] Task "%TASK_NAME%" created successfully.
    echo.
    echo Useful commands:
    echo   Run now:     schtasks /run /tn "%TASK_NAME%"
    echo   View status: schtasks /query /tn "%TASK_NAME%" /fo LIST /v
    echo   Delete:      schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo [ERROR] Task creation failed.
    echo Try right-clicking this .bat file and selecting "Run as administrator".
)

echo.
pause
