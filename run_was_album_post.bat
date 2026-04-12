@echo off
REM Post SB19 Wakas At Simula Album Update to X - Scheduled Task (8:00 AM daily)
cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python social_media_agent.py was-album
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Wakas At Simula album post at %date% %time%"
)
