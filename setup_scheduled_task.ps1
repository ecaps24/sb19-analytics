# SB19 Daily Streams Scraper - Task Scheduler Setup
# Run this script as Administrator to create the scheduled task

$taskName = "SB19 Daily Streams Scraper"
$taskPath = "D:\dev\sb19\run_daily_scrape.bat"
$description = "Scrapes Spotify track streams for SB19 daily and calculates daily stream changes"

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create the action
$action = New-ScheduledTaskAction -Execute $taskPath -WorkingDirectory "D:\dev\sb19"

# Create the trigger (daily at 6:00 AM)
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"

# Create the principal (run whether user is logged in or not)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $description

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Scheduled task created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task Name: $taskName"
Write-Host "Schedule: Daily at 6:00 AM"
Write-Host "Script: $taskPath"
Write-Host ""
Write-Host "To modify the schedule, open Task Scheduler and edit the task."
Write-Host "To run manually: schtasks /run /tn `"$taskName`""
