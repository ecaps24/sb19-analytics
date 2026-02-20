@echo off
REM YouTube VISA MV - X Post Automation (runs every 30 min)
REM Posts VISA YouTube stats (views, likes, comments) to X
REM NOTE: No --headless flag because X blocks headless browsers

cd /d D:\dev\sb19

echo ============================================ >> yt_visa_post.log
echo [%date% %time%] Starting YouTube VISA post... >> yt_visa_post.log

REM Kill any lingering Edge processes and wait for cleanup
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 5 /nobreak >nul

python social_media_agent.py youtube-visa >> yt_visa_post.log 2>&1
echo [%date% %time%] Exit code: %ERRORLEVEL% >> yt_visa_post.log
echo ============================================ >> yt_visa_post.log
