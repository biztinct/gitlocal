# Payobook Attendance Connector - per-user setup, no Access drivers required.
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Windows.Forms
$ErrorActionPreference = 'Stop'
$install = Join-Path $env:LOCALAPPDATA 'PayobookAttendance'
$bundle = $PSScriptRoot
if ($bundle -ne $install) {
    New-Item -ItemType Directory -Force -Path $install | Out-Null
    # Protect database snapshots, queue and credentials from other local users.
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $install /inheritance:r /grant:r "*${sid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect the installation folder.' }
    Get-ChildItem $bundle | Where-Object Name -ne 'data' | Copy-Item -Destination $install -Recurse -Force
}
$python = Join-Path $install 'runtime\python.exe'
$worker = Join-Path $install 'connector.py'
$data = Join-Path $install 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
[xml]$layout = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Payobook Attendance Connector - Windows setup" Width="740" Height="760" MinWidth="620" MinHeight="520" Background="#F6F7FB" WindowStartupLocation="CenterScreen">
 <ScrollViewer VerticalScrollBarVisibility="Auto"><StackPanel Margin="24">
  <TextBlock Text="Connect this Windows PC" FontSize="24" FontWeight="Bold" Margin="0,0,0,14"/>
  <TextBlock Text="Staff download punches in Mitaco as usual. This application only reads its MDB and sends records to Payobook. It never contacts or changes a terminal." TextWrapping="Wrap" Margin="0,0,0,16"/>
  <TextBlock Text="Payobook website address (HTTPS)"/><TextBox Name="Server" Margin="0,5,0,12"/>
  <TextBlock Text="Pairing code from Payobook / Time clocks / Data connectors"/><PasswordBox Name="Code" Margin="0,5,0,12"/>
  <TextBlock Text="Local Mitaco database"/><DockPanel Margin="0,5,0,12"><Button Name="Browse" Content="Browse..." DockPanel.Dock="Right" Padding="12,5"/><TextBox Name="Database"/></DockPanel>
  <WrapPanel><Button Name="Check" Content="Test read-only access" Padding="10,7" Margin="0,0,8,8"/><Button Name="Pair" Content="Pair with Payobook" Padding="10,7" Margin="0,0,8,8"/><Button Name="Install" Content="Enable scheduled sync" Padding="10,7" Margin="0,0,8,8"/></WrapPanel>
  <WrapPanel><Button Name="Sync" Content="Sync now" Padding="10,7" Margin="0,0,8,8"/><Button Name="Replay" Content="Rescan history" Padding="10,7" Margin="0,0,8,8"/><Button Name="Status" Content="Show diagnostics" Padding="10,7" Margin="0,0,8,8"/><Button Name="Tasks" Content="Windows task settings" Padding="10,7" Margin="0,0,8,8"/></WrapPanel>
  <TextBlock Text="Default schedule: while this Windows user is signed in (screen may be locked). For unattended overnight operation, IT can set the task to run whether this same user is logged on or not. The PC must remain awake. Windows stores that task credential, not Payobook." TextWrapping="Wrap" Margin="0,6,0,12"/>
  <Border Background="White" CornerRadius="8" Padding="16" Margin="0,0,0,12">
   <StackPanel><TextBlock Name="RunState" Text="Ready" FontWeight="SemiBold" Foreground="#5342A5"/>
    <ProgressBar Name="Progress" Height="6" Margin="0,10,0,8" IsIndeterminate="True" Visibility="Collapsed"/>
    <TextBlock Name="Elapsed" Text="Connector 1.0.1" Foreground="#646B7C" TextWrapping="Wrap"/>
   </StackPanel>
  </Border>
  <TextBox Name="Output" IsReadOnly="True" TextWrapping="Wrap" Height="155" VerticalScrollBarVisibility="Auto"/>
 </StackPanel></ScrollViewer>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $layout))
$server = $window.FindName('Server'); $code = $window.FindName('Code'); $database = $window.FindName('Database'); $output = $window.FindName('Output')
$preferences = Join-Path $data 'setup.json'
if (Test-Path $preferences) { $pref = Get-Content $preferences -Raw | ConvertFrom-Json; $server.Text = $pref.server; $database.Text = $pref.database }
# Keep the WPF dispatcher free: a timer observes the child process without
# WaitForExit or blocking pipe reads on the UI thread. Worker retains its lock.
$script:activeRun = $null
$script:lastDiagnostics = ''
$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(250)
function Set-Working([bool]$working) {
    foreach ($name in @('Browse','Check','Pair','Install','Sync','Replay','Status','Tasks','Server','Code','Database')) {
        $window.FindName($name).IsEnabled = -not $working
    }
    $window.FindName('Progress').Visibility = if ($working) { 'Visible' } else { 'Collapsed' }
    $window.Cursor = if ($working) { [Windows.Input.Cursors]::AppStarting } else { [Windows.Input.Cursors]::Arrow }
}
function Result-Text($result, [string]$command, [int]$exitCode) {
    if ($result.error) {
        return "Needs attention: $($result.error)`nAny records still queued will be retried on a later sync. See Show diagnostics for details."
    }
    if ($exitCode -ne 0) { return 'The operation did not finish. Check Show diagnostics and ask IT for help.' }
    if ($result.paired) { return "Connected to Payobook: $($result.name)`nNext, select Sync now. You do not need to pair this PC again." }
    if ($result.rescan) { return 'History is ready to rescan. Select Sync now to resend it safely. Payobook checks for duplicates.' }
    if ($result.waiting_for_next_scan) { return 'The next scheduled scan is not due yet. Select Sync now to run it now.' }
    if ($command -eq 'check') {
        return ("Database access confirmed (read-only).`nRows read: {0:N0}`nUnique records: {1:N0}`nLatest punch in this file: {2}`nThis check does not upload records." -f $result.source_rows, $result.unique_records, $result.latest_punch)
    }
    return ("Sync complete.`nRecords sent this run: {0:N0}`nRecords still queued: {1:N0}`nRows in the source file: {2:N0}`nLatest punch in this file: {3}`nYou can check receipt on the Payobook setup page." -f $result.sent, $result.pending, $result.source_rows, $result.latest_punch)
}
function Run-Worker([string]$command, [string]$inputJson = '', [string]$extra = '') {
    if ($script:activeRun) { return }
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo.FileName = $python
    $p.StartInfo.Arguments = '"' + $worker + '" ' + $command + ' --home "' + $data + '" ' + $extra
    $p.StartInfo.UseShellExecute = $false; $p.StartInfo.CreateNoWindow = $true
    $p.StartInfo.RedirectStandardInput = $true; $p.StartInfo.RedirectStandardOutput = $true; $p.StartInfo.RedirectStandardError = $true
    $p.StartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $p.StartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p.StartInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    try {
        $p.Start() | Out-Null
        if ($inputJson) {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($inputJson)
            $p.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
            $p.StandardInput.BaseStream.Flush()
        }
        $p.StandardInput.Close()
        $script:activeRun = @{Process=$p; Stdout=$p.StandardOutput.ReadToEndAsync(); Stderr=$p.StandardError.ReadToEndAsync(); Command=$command; Started=(Get-Date)}
        $window.FindName('RunState').Text = switch ($command) { 'check' {'Checking database access'} 'pair' {'Connecting to Payobook'} 'replay' {'Preparing history rescan'} default {'Sync in progress'} }
        $output.Text = if ($command -in @('check','sync')) { 'Please wait. Reading a large MDB and uploading records can take several minutes. You can minimise this window; keep the PC awake.' } else { 'Please wait while this operation finishes.' }
        $window.FindName('Elapsed').Text = 'Starting...'
        Set-Working $true
        $timer.Start()
    } catch { $p.Dispose(); $script:activeRun = $null; Set-Working $false; throw }
}
$timer.Add_Tick({
    $run = $script:activeRun
    if (-not $run) { return }
    $seconds = [int]((Get-Date) - $run.Started).TotalSeconds
    $window.FindName('Elapsed').Text = "Elapsed: $seconds seconds. Please keep this window open."
    if (-not $run.Process.HasExited -or -not $run.Stdout.IsCompleted -or -not $run.Stderr.IsCompleted) { return }
    $timer.Stop()
    try {
        $script:lastDiagnostics = $run.Stdout.Result
        $result = $script:lastDiagnostics | ConvertFrom-Json
        if (-not $result) { throw 'The worker returned no result. Check file permissions and try again.' }
        $output.Text = Result-Text $result $run.Command $run.Process.ExitCode
        $window.FindName('RunState').Text = if ($run.Process.ExitCode -eq 0 -and -not $result.error) { 'Finished' } else { 'Needs attention' }
        if ($run.Command -eq 'pair' -and $run.Process.ExitCode -eq 0 -and $result.paired) {
            @{server=$server.Text.Trim();database=$database.Text.Trim()} | ConvertTo-Json | Set-Content $preferences -Encoding UTF8
            $code.Clear()
        }
    } catch { $window.FindName('RunState').Text = 'Needs attention'; $output.Text = $_.Exception.Message }
    finally {
        $window.FindName('Elapsed').Text = "Finished after $seconds seconds. Connector 1.0.1"
        $run.Process.Dispose(); $script:activeRun = $null; Set-Working $false
    }
})
$window.Add_Closing({
    if ($script:activeRun) {
        $_.Cancel = $true
        [System.Windows.MessageBox]::Show('An operation is still running. You can minimise this window. Please wait for it to finish before closing.', 'Sync in progress') | Out-Null
    }
})
$window.FindName('Browse').Add_Click({ $dialog = New-Object System.Windows.Forms.OpenFileDialog; $dialog.Filter = 'Access database (*.mdb)|*.mdb'; if ($dialog.ShowDialog() -eq 'OK') { $database.Text = $dialog.FileName } })
$window.FindName('Check').Add_Click({ try { Run-Worker 'check' '' ('--database "' + $database.Text.Replace('"','') + '"') | Out-Null } catch { $output.Text = $_.Exception.Message } })
$window.FindName('Pair').Add_Click({ try {
    $details = @{server=$server.Text.Trim();code=$code.Password.Trim();database=$database.Text.Trim()} | ConvertTo-Json -Compress
    Run-Worker 'pair' $details
} catch { $output.Text = $_.Exception.Message } })
$window.FindName('Install').Add_Click({ try {
    if (-not (Test-Path (Join-Path $data 'settings.bin'))) { throw 'Pair this PC before enabling its schedule.' }
    $who = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $action = New-ScheduledTaskAction -Execute $python -Argument ('"' + $worker + '" sync --home "' + $data + '"') -WorkingDirectory $install
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $principal = New-ScheduledTaskPrincipal -UserId $who -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'Payobook Attendance Connector' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Payobook Attendance Connector.lnk'))
    $shortcut.TargetPath = 'powershell.exe'; $shortcut.Arguments = '-NoProfile -File "' + (Join-Path $install 'Setup.ps1') + '"'; $shortcut.Save()
    $output.Text = 'Scheduled sync enabled. Keep this user signed in and the PC awake, or ask IT to configure the task for logged-off operation under this same account. Test again after logging off if IT changes the task.'
} catch { $output.Text = $_.Exception.Message } })
$window.FindName('Sync').Add_Click({ try { Remove-Item (Join-Path $data 'last_attempt') -ErrorAction SilentlyContinue; Run-Worker 'sync' | Out-Null } catch { $output.Text = $_.Exception.Message } })
$window.FindName('Replay').Add_Click({ try { Run-Worker 'replay' | Out-Null } catch { $output.Text = $_.Exception.Message } })
$window.FindName('Status').Add_Click({ if ($script:lastDiagnostics) { $output.Text = $script:lastDiagnostics } elseif (Test-Path (Join-Path $data 'status.json')) { $output.Text = Get-Content (Join-Path $data 'status.json') -Raw -Encoding UTF8 } else { $output.Text = 'No run recorded yet.' } })
$window.FindName('Tasks').Add_Click({ Start-Process 'taskschd.msc' })
$window.ShowDialog() | Out-Null
