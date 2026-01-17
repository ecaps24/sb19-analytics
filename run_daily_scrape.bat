@echo off
REM SB19 Daily Streams Scraper
REM This script is designed to be run by Windows Task Scheduler daily

echo ======================================================================
echo SB19 Daily Streams Scraper
echo Started at: %date% %time%
echo ======================================================================

cd /d "D:\dev\sb19"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the RPA script
python sb19_tracks_streams_rpa.py

echo.
echo ======================================================================
echo Completed at: %date% %time%
echo ======================================================================

REM Keep window open for 10 seconds to see results (optional)
timeout /t 10
