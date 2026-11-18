# Update the action only on an existing installation. Preserve IT's account,
# triggers, conditions, logon mode and stored task credentials.
function Enable-PayobookSchedule([string]$InstallPath, [string]$AccountName, [string]$AccountSid) {
    $quietPython = Join-Path $InstallPath 'runtime\pythonw.exe'
    $consolePython = Join-Path $InstallPath 'runtime\python.exe'
    $workerPath = Join-Path $InstallPath 'connector.py'
    $dataPath = Join-Path $InstallPath 'data'
    if (-not (Test-Path $quietPython)) { throw 'Windowless Python is missing. Extract the complete connector package and try again.' }
    if (-not (Test-Path (Join-Path $dataPath 'settings.bin'))) { throw 'Pair this PC before enabling its schedule.' }
    $arguments = '"' + $workerPath + '" sync --home "' + $dataPath + '"'
    $existing = Get-ScheduledTask -TaskName 'Payobook Attendance Connector' -TaskPath '\' -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.Principal.UserId -notin @($AccountName, $AccountSid)) {
            throw 'This task belongs to another Windows account. Ask IT to update its action under the original account.'
        }
        $actions = @($existing.Actions)
        if ($actions.Count -ne 1 -or $actions[0].Execute -notin @($consolePython, $quietPython) -or $actions[0].Arguments -ne $arguments) {
            throw 'IT has customised this task action. Ask IT to change only python.exe to pythonw.exe in its existing action.'
        }
        # Keep the existing arguments and working directory exactly as configured.
        $action = New-ScheduledTaskAction -Execute $quietPython -Argument $actions[0].Arguments -WorkingDirectory $actions[0].WorkingDirectory
        Set-ScheduledTask -TaskName $existing.TaskName -TaskPath $existing.TaskPath -Action $action -ErrorAction Stop | Out-Null
        return 'Existing schedule updated to run without a command window. Its account, timings, logon mode and enabled/disabled state are unchanged. Check Windows task settings and run the task once to verify.'
    }
    $action = New-ScheduledTaskAction -Execute $quietPython -Argument $arguments -WorkingDirectory $InstallPath
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $principal = New-ScheduledTaskPrincipal -UserId $AccountName -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'Payobook Attendance Connector' -TaskPath '\' -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    return 'Scheduled sync enabled without a command window. Keep this user signed in and the PC awake, or ask IT to configure logged-off operation under this same account. Test again after logging off if IT changes the task.'
}
