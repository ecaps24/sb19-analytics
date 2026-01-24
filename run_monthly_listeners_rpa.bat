@echo off
REM Monthly Listeners RPA - Scheduled Task
REM Runs daily at 10:00 AM via Task Scheduler

echo ======================================================================
echo Monthly Listeners RPA
echo Started at: %date% %time%
echo ======================================================================

cd /d "D:\dev\sb19"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the Monthly Listeners RPA script
python artist_monthly_listeners_rpa.py

echo.
echo ======================================================================
echo Completed at: %date% %time%
echo ======================================================================
