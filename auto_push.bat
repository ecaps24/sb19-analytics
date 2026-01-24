@echo off
cd /d D:\dev\sb19
git add -A
git diff --cached --quiet
if %ERRORLEVEL% NEQ 0 (
    git commit -m "Auto-push data update"
    git push
)
