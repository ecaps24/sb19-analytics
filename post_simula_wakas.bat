@echo off
REM Post SB19 Simula at Wakas Album Update to X - Scheduled Task
cd /d D:\dev\sb19

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python social_media_agent.py album
if %ERRORLEVEL% NEQ 0 (
    python notify.py "FAILED: Simula at Wakas post at %date% %time%"
)
