@echo off
REM Track Discovery RPA - Weekly Scheduled Task
REM Runs every Saturday at 6:00 AM via Task Scheduler
REM Scans Spotify for new releases and updates track CSVs

echo ======================================================================
echo Track Discovery RPA - Weekly Scan
echo Started at: %date% %time%
echo ======================================================================

cd /d "D:\dev\sb19"

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Run the Track Discovery RPA script in headless mode
python track_discovery_rpa.py --headless
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Track Discovery RPA at %date% %time%"
)

echo.
echo ======================================================================
echo Completed at: %date% %time%
echo ======================================================================

timeout /t 10
