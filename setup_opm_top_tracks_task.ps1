# OPM Top 10 Tracks Daily - Task Scheduler Setup
# Run this script as Administrator to create the scheduled tasks
# Places tasks under "OPM Insights" folder in Task Scheduler
# Creates two tasks:
#   1. OPM Top Tracks RPA (daily at 10:00 AM) - scrapes Spotify streams
#   2. OPM Top Tracks Daily Post (daily at 1:30 PM) - posts to X

$taskFolder = "OPM Insights"

# --- Task 1: OPM Top Tracks RPA ---
$rpaTaskName = "OPM Top Tracks RPA"
$rpaTaskPath = "D:\dev\sb19\run_opm_tracks_rpa.bat"
$rpaDescription = "Scrapes Spotify streams for all OPM artist tracks daily at 10:00 AM"

try {
    Unregister-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $rpaTaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$rpaAction = New-ScheduledTaskAction -Execute $rpaTaskPath -WorkingDirectory "D:\dev\sb19"
$rpaTrigger = New-ScheduledTaskTrigger -Daily -At "10:00AM"
$rpaPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$rpaSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $rpaTaskName -Action $rpaAction -Trigger $rpaTrigger -Principal $rpaPrincipal -Settings $rpaSettings -Description $rpaDescription

# --- Task 2: OPM Top Tracks Daily Post ---
$postTaskName = "OPM Top Tracks Daily Post"
$postTaskPath = "D:\dev\sb19\run_opm_top_tracks_post.bat"
$postDescription = "Posts OPM Top 10 Tracks by Daily Streams to X every day at 1:30 PM"

try {
    Unregister-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $postTaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$postAction = New-ScheduledTaskAction -Execute $postTaskPath -WorkingDirectory "D:\dev\sb19"
$postTrigger = New-ScheduledTaskTrigger -Daily -At "1:30PM"
$postPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$postSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $postTaskName -Action $postAction -Trigger $postTrigger -Principal $postPrincipal -Settings $postSettings -Description $postDescription

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Scheduled tasks created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task 1:"
Write-Host "  Folder: $taskFolder"
Write-Host "  Task Name: $rpaTaskName"
Write-Host "  Schedule: Daily at 10:00 AM"
Write-Host "  Script: $rpaTaskPath"
Write-Host ""
Write-Host "Task 2:"
Write-Host "  Folder: $taskFolder"
Write-Host "  Task Name: $postTaskName"
Write-Host "  Schedule: Daily at 1:30 PM"
Write-Host "  Script: $postTaskPath"
Write-Host ""
Write-Host "To run manually:"
Write-Host "  schtasks /run /tn `"\$taskFolder\$rpaTaskName`""
Write-Host "  schtasks /run /tn `"\$taskFolder\$postTaskName`""
Write-Host ""
Write-Host "To remove:"
Write-Host "  schtasks /delete /tn `"\$taskFolder\$rpaTaskName`" /f"
Write-Host "  schtasks /delete /tn `"\$taskFolder\$postTaskName`" /f"
