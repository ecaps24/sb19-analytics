@echo off
REM Post SB19 Solo Top 10 Streams to X - Scheduled Task
cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python social_media_agent.py solo-top10
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Solo Top 10 Streams post at %date% %time%"
)
