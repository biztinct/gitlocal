$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
try {
    . (Join-Path $PSScriptRoot 'Schedule.ps1')
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $install = Join-Path $env:LOCALAPPDATA 'PayobookAttendance'
    $backup = Join-Path $install ('data\task-before-quiet-fix-' + [guid]::NewGuid().ToString('N') + '.xml')
    $result = Enable-PayobookSchedule -InstallPath $install -AccountName $identity.Name -AccountSid $identity.User.Value -ExistingOnly -BackupPath $backup
    $details = "$result`n`nKeep this PC awake and this user signed in for 20 minutes. Ask Payobook to check the next automatic upload. An upload already running may finish in its existing window."
    if (Test-Path -LiteralPath $backup) { $details += "`n`nTask backup: $backup" }
    [System.Windows.MessageBox]::Show($details, 'Payobook - quiet sync patch', 'OK', 'Information') | Out-Null
} catch {
    [System.Windows.MessageBox]::Show("The patch could not finish.`n`n$($_.Exception.Message)`n`nSend this message to IT. Do not reinstall or pair again.", 'Payobook - needs IT help', 'OK', 'Error') | Out-Null
    exit 1
}
