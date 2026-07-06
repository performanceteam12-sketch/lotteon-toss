# Register the Toss re-collection worker to auto-start at logon (Task Scheduler).
# NOTE: needs Administrator. If you get "Access denied", use install_autostart.py
#       instead (no admin needed) -- recommended.
# Run (as admin):
#   powershell -ExecutionPolicy Bypass -File register_worker_local.ps1

$ErrorActionPreference = "Stop"

$TaskName = "TossWorker"
$PythonW  = "$env:LOCALAPPDATA\Programs\Python\Python314\pythonw.exe"
$WorkDir  = $PSScriptRoot
$Script   = Join-Path $WorkDir "_worker_service.py"

if (-not (Test-Path $PythonW)) {
    Write-Host "[!] pythonw not found: $PythonW"
    Write-Host "    Install Python 3.14 (user scope) or fix this path."
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task"
}

$action   = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$Script`"" -WorkingDirectory $WorkDir
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Toss re-collection queue worker" -Force | Out-Null

Write-Host "[OK] Task '$TaskName' registered (auto-start at logon)"
schtasks /Run /TN $TaskName | Out-Null
Write-Host "[OK] Worker started now"
