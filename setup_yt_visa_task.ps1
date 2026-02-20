# YouTube VISA MV - X Post Task Scheduler Setup
# Run this script as Administrator to create the scheduled task
# Places the task under "OPM Insights" folder in Task Scheduler

$taskFolder = "OPM Insights"
$taskName = "SB19 YouTube VISA Post"
$oldTaskName = "SB19 YouTube VISA Hourly Post"
$taskPath = "D:\dev\sb19\run_yt_visa_post.bat"
$description = "Posts SB19 VISA MV YouTube stats (views, likes, comments) to X every 30 minutes"

# Remove old task from root if it exists
Unregister-ScheduledTask -TaskName $oldTaskName -Confirm:$false -ErrorAction SilentlyContinue

# Remove existing task from folder if it exists
try {
    Unregister-ScheduledTask -TaskPath "\$taskFolder\" -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Create the action
$action = New-ScheduledTaskAction -Execute $taskPath -WorkingDirectory "D:\dev\sb19"

# Create the trigger (repeats every 30 minutes, starting now, indefinitely)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)

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
Write-Host "Schedule: Every 30 minutes"
Write-Host "Script: $taskPath"
Write-Host ""
Write-Host "To run manually: schtasks /run /tn `"\$taskFolder\$taskName`""
Write-Host "To remove: schtasks /delete /tn `"\$taskFolder\$taskName`" /f"
