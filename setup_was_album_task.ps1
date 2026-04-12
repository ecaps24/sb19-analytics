# Wakas At Simula Album Daily - X Post Task Scheduler Setup
# Run this script as Administrator to create the scheduled task
# Places the task under "OPM Insights" folder in Task Scheduler

$taskFolder = "OPM Insights"
$taskName = "SB19 Wakas At Simula Album Post"
$taskPath = "D:\dev\sb19\run_was_album_post.bat"
$description = "Posts SB19 Wakas At Simula album streams and track ranking to X every day at 8:00 AM"

# Remove existing task from folder if it exists
try {
    Unregister-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Create the action
$action = New-ScheduledTaskAction -Execute $taskPath -WorkingDirectory "D:\dev\sb19"

# Create the trigger (daily at 8:00 AM — after 6AM stream scrape completes)
$trigger = New-ScheduledTaskTrigger -Daily -At "8:00AM"

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
Write-Host "Schedule: Daily at 8:00 AM"
Write-Host "Script: $taskPath"
Write-Host ""
Write-Host "To run manually: schtasks /run /tn `"\$taskFolder\$taskName`""
Write-Host "To remove: schtasks /delete /tn `"\$taskFolder\$taskName`" /f"
