@echo off
REM OPM Tracks RPA - Daily Spotify scrape for all OPM artist tracks
REM Scheduled daily at 10:00 AM (takes ~3-4 hours for 1900+ tracks)
REM Output: opm_tracks_results.csv (semicolon-delimited with timestamps)
REM WARNING: Posting scripts check for this process before killing Edge

cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

set LOG_FILE=opm_tracks_rpa.log

echo ============================================ >> %LOG_FILE%
echo [%date% %time%] Starting OPM tracks RPA... >> %LOG_FILE%

python sb19_selenium_rpa.py opm_all_tracks.csv --output opm_tracks_results.csv --headless >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: OPM Tracks RPA at %date% %time%"
)
echo [%date% %time%] Exit code: %ERRORLEVEL% >> %LOG_FILE%
echo ============================================ >> %LOG_FILE%
