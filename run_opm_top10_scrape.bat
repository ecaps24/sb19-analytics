@echo off
REM OPM Top 10 Daily Streams Scraper
REM Covers: Arthur Nery, fitterkarma, December Avenue, IV of Spades,
REM         Rob Deniel, Ben&Ben, Up Dharma Down, Soapdish, Earl Agustin
REM Schedule: Daily at 9:00 AM (after the 6 AM SB19/BINI run)
REM Uses --force because the 6 AM run already creates entries for today's date

echo ======================================================================
echo OPM Top 10 Daily Streams Scraper
echo Started at: %date% %time%
echo ======================================================================

cd /d "D:\dev\sb19"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the Selenium RPA script with OPM top 10 tracks
REM --force: bypass "data already exists" check (6 AM run already populated today)
REM Output goes to same selenium_results.csv so the dashboard picks it up
python sb19_selenium_rpa.py opm_top10_tracks.csv --force

echo.
echo ======================================================================
echo Completed at: %date% %time%
echo ======================================================================

REM Keep window open for 10 seconds to see results (optional)
timeout /t 10
