# Spotify VISA Daily - X Post Task Scheduler Setup
# Run this script as Administrator to create the scheduled task
# Places the task under "OPM Insights" folder in Task Scheduler

$taskFolder = "OPM Insights"
$taskName = "SB19 Spotify VISA Daily Post"
$taskPath = "D:\dev\sb19\run_spotify_visa_post.bat"
$description = "Posts SB19 VISA Spotify daily streams to X every day at 12:00 PM"

# Remove existing task from folder if it exists
try {
    Unregister-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Create the action
$action = New-ScheduledTaskAction -Execute $taskPath -WorkingDirectory "D:\dev\sb19"

# Create the trigger (daily at 12:00 PM)
$trigger = New-ScheduledTaskTrigger -Daily -At "12:00PM"

# Create the principal (run only when user is logged on - needed for browser)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task under OPM Insights folder
Register-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $description

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Scheduled task created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Folder: $taskFolder"
Write-Host "Task Name: $taskName"
Write-Host "Schedule: Daily at 12:00 PM"
Write-Host "Script: $taskPath"
Write-Host ""
Write-Host "To run manually: schtasks /run /tn `"\$taskFolder\$taskName`""
Write-Host "To remove: schtasks /delete /tn `"\$taskFolder\$taskName`" /f"
