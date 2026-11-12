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
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Payobook Attendance Connector - Windows setup" Width="680" Height="650" WindowStartupLocation="CenterScreen">
 <StackPanel Margin="24">
  <TextBlock Text="Connect this Windows PC" FontSize="24" FontWeight="Bold" Margin="0,0,0,14"/>
  <TextBlock Text="Staff download punches in Mitaco as usual. This application only reads its MDB and sends records to Payobook. It never contacts or changes a terminal." TextWrapping="Wrap" Margin="0,0,0,16"/>
  <TextBlock Text="Payobook website address (HTTPS)"/><TextBox Name="Server" Margin="0,5,0,12"/>
  <TextBlock Text="Pairing code from Payobook → Time clocks → Data connectors"/><PasswordBox Name="Code" Margin="0,5,0,12"/>
  <TextBlock Text="Local Mitaco database"/><DockPanel Margin="0,5,0,12"><Button Name="Browse" Content="Browse…" DockPanel.Dock="Right" Padding="12,5"/><TextBox Name="Database"/></DockPanel>
  <WrapPanel><Button Name="Check" Content="Test read-only access" Padding="10,7" Margin="0,0,8,8"/><Button Name="Pair" Content="Pair with Payobook" Padding="10,7" Margin="0,0,8,8"/><Button Name="Install" Content="Enable scheduled sync" Padding="10,7" Margin="0,0,8,8"/></WrapPanel>
  <WrapPanel><Button Name="Sync" Content="Sync now" Padding="10,7" Margin="0,0,8,8"/><Button Name="Replay" Content="Rescan history" Padding="10,7" Margin="0,0,8,8"/><Button Name="Status" Content="Show diagnostics" Padding="10,7" Margin="0,0,8,8"/><Button Name="Tasks" Content="Windows task settings" Padding="10,7" Margin="0,0,8,8"/></WrapPanel>
  <TextBlock Text="Default schedule: while this Windows user is signed in (screen may be locked). For unattended overnight operation, IT can set the task to run whether this same user is logged on or not. The PC must remain awake. Windows stores that task credential, not Payobook." TextWrapping="Wrap" Margin="0,6,0,12"/>
  <TextBox Name="Output" IsReadOnly="True" TextWrapping="Wrap" Height="155" VerticalScrollBarVisibility="Auto"/>
 </StackPanel>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $layout))
$server = $window.FindName('Server'); $code = $window.FindName('Code'); $database = $window.FindName('Database'); $output = $window.FindName('Output')
$preferences = Join-Path $data 'setup.json'
if (Test-Path $preferences) { $pref = Get-Content $preferences -Raw | ConvertFrom-Json; $server.Text = $pref.server; $database.Text = $pref.database }
function Run-Worker([string]$command, [string]$inputJson = '', [string]$extra = '') {
    $output.Text = 'Working… A full MDB check can take a few minutes. Please wait.'
    $window.Dispatcher.Invoke([Action]{}, [Windows.Threading.DispatcherPriority]::Render)
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo.FileName = $python
    $p.StartInfo.Arguments = '"' + $worker + '" ' + $command + ' --home "' + $data + '" ' + $extra
    $p.StartInfo.UseShellExecute = $false; $p.StartInfo.CreateNoWindow = $true
    $p.StartInfo.RedirectStandardInput = $true; $p.StartInfo.RedirectStandardOutput = $true; $p.StartInfo.RedirectStandardError = $true
    $p.Start() | Out-Null
    if ($inputJson) { $p.StandardInput.Write($inputJson) }; $p.StandardInput.Close()
    $stdout = $p.StandardOutput.ReadToEndAsync(); $stderr = $p.StandardError.ReadToEndAsync()
    $p.WaitForExit()
    $output.Text = $stdout.Result
    if ($p.ExitCode -ne 0 -and -not $output.Text) { $output.Text = 'The reader failed. Check Windows file permissions and contact IT.' }
    return $p.ExitCode
}
$window.FindName('Browse').Add_Click({ $dialog = New-Object System.Windows.Forms.OpenFileDialog; $dialog.Filter = 'Access database (*.mdb)|*.mdb'; if ($dialog.ShowDialog() -eq 'OK') { $database.Text = $dialog.FileName } })
$window.FindName('Check').Add_Click({ try { Run-Worker 'check' '' ('--database "' + $database.Text.Replace('"','') + '"') | Out-Null } catch { $output.Text = $_.Exception.Message } })
$window.FindName('Pair').Add_Click({ try {
    $details = @{server=$server.Text.Trim();code=$code.Password.Trim();database=$database.Text.Trim()} | ConvertTo-Json -Compress
    $rc = Run-Worker 'pair' $details
    if ($rc -eq 0) { @{server=$server.Text.Trim();database=$database.Text.Trim()} | ConvertTo-Json | Set-Content $preferences -Encoding UTF8; $code.Clear() }
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
$window.FindName('Replay').Add_Click({ try { Run-Worker 'replay' | Out-Null; $output.Text += "`nThe next scan will resend history safely. Payobook deduplicates it." } catch { $output.Text = $_.Exception.Message } })
$window.FindName('Status').Add_Click({ if (Test-Path (Join-Path $data 'status.json')) { $output.Text = Get-Content (Join-Path $data 'status.json') -Raw } else { $output.Text = 'No run recorded yet.' } })
$window.FindName('Tasks').Add_Click({ Start-Process 'taskschd.msc' })
$window.ShowDialog() | Out-Null
