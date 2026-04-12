@echo off
REM SB19 Daily Streams Scraper
REM This script is designed to be run by Windows Task Scheduler daily

echo ======================================================================
echo SB19 Daily Streams Scraper
echo Started at: %date% %time%
echo ======================================================================

cd /d "D:\dev\sb19"

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Run the Selenium RPA script for track streams
REM Monthly listeners RPA runs separately at 3:00 AM
python sb19_selenium_rpa.py
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Daily Streams Scraper at %date% %time%"
)

echo.
echo ======================================================================
echo Completed at: %date% %time%
echo ======================================================================

REM Keep window open for 10 seconds to see results (optional)
timeout /t 10
