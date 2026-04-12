@echo off
REM Post SB19 Monthly Listeners to X - Scheduled Task
cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python social_media_agent.py listeners
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Monthly Listeners post at %date% %time%"
)
