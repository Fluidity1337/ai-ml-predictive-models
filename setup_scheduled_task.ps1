# Run this script as Administrator to create the scheduled task
# MLB RFI Pipeline - Daily Scheduler Setup

$taskName = "MLB RFI Pipeline Daily"
$scriptPath = "C:\dev\vscode\workspaces\ai-ml-predictive-models\run_daily_pipeline.bat"
$startTime = "06:00"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Task '$taskName' already exists. Removing old task..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create new scheduled task
$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Daily -At $startTime
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Create the task with current user context
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal

Write-Host "Scheduled task '$taskName' created successfully!"
Write-Host "Task will run daily at $startTime"
Write-Host "To view the task: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "To run manually: Start-ScheduledTask -TaskName '$taskName'"
