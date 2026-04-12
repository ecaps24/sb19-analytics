@echo off
REM OPM Top Artists by Total Streams - X Post Automation
REM Posts OPM Top Artists by Total Streams to X
REM NOTE: No --headless flag because X blocks headless browsers

cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

set LOG_FILE=opm_top_streams_post.log

echo ============================================ >> %LOG_FILE%
echo [%date% %time%] Starting OPM Top Streams post... >> %LOG_FILE%

REM Skip Edge kill if an RPA scraper is running (uses Edge headless)
tasklist /fi "imagename eq python.exe" /fo csv 2>nul | findstr /i "rpa" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [WARN] RPA scraper running - skipping Edge kill >> %LOG_FILE%
) else (
    taskkill /F /IM msedge.exe >nul 2>&1
    ping -n 6 127.0.0.1 >nul
)

python social_media_agent.py opm-top-streams >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: OPM Top Streams post at %date% %time%"
)
echo [%date% %time%] Exit code: %ERRORLEVEL% >> %LOG_FILE%
echo ============================================ >> %LOG_FILE%
