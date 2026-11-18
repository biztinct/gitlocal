$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../Schedule.ps1')
$script:task=$null; $script:registered=$null; $script:updated=$null; $script:missing=$false
function Test-Path {param($Path) return -not $script:missing}
function Get-ScheduledTask {param($TaskName,$TaskPath,$ErrorAction) return $script:task}
function New-ScheduledTaskAction {param($Execute,$Argument,$WorkingDirectory) return [pscustomobject]@{Execute=$Execute;Arguments=$Argument;WorkingDirectory=$WorkingDirectory}}
function New-ScheduledTaskTrigger {param($Once,$At,$RepetitionInterval) return 'trigger'}
# Switch binding mirrors the real cmdlets.
Remove-Item Function:New-ScheduledTaskTrigger
function New-ScheduledTaskTrigger {param([switch]$Once,$At,$RepetitionInterval) return 'trigger'}
function New-ScheduledTaskPrincipal {param($UserId,$LogonType,$RunLevel) return 'principal'}
function New-ScheduledTaskSettingsSet {param([switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit,[switch]$AllowStartIfOnBatteries,[switch]$DontStopIfGoingOnBatteries) return 'settings'}
function Register-ScheduledTask {param($TaskName,$TaskPath,$Action,$Trigger,$Principal,$Settings) $script:registered=$Action}
function Set-ScheduledTask {param($TaskName,$TaskPath,$Action,$ErrorAction) $script:updated=$Action}
$root=Join-Path ([IO.Path]::GetTempPath()) 'Payobook Attendance'
$result=Enable-PayobookSchedule $root 'DOMAIN\HR' 'S-1-5-21-1'
if ($script:registered.Execute -ne (Join-Path $root 'runtime\pythonw.exe')) {throw 'New task not windowless'}
$script:task=[pscustomobject]@{TaskName='Payobook Attendance Connector';TaskPath='\';Principal=[pscustomobject]@{UserId='S-1-5-21-1'};Actions=@([pscustomobject]@{Execute=(Join-Path $root 'runtime\python.exe');Arguments=$script:registered.Arguments;WorkingDirectory='custom working folder'})}
$result=Enable-PayobookSchedule $root 'DOMAIN\HR' 'S-1-5-21-1'
if ($script:updated.Execute -ne (Join-Path $root 'runtime\pythonw.exe') -or $script:updated.WorkingDirectory -ne 'custom working folder' -or $script:updated.Arguments -ne $script:registered.Arguments) {throw 'Existing action not safely updated'}
$script:updated=$null
$script:task.Principal.UserId='OTHER\USER'
try {Enable-PayobookSchedule $root 'DOMAIN\HR' 'S-1-5-21-1';throw 'WRONG_OWNER_NOT_BLOCKED'} catch {if ($_.Exception.Message -notmatch 'another Windows account') {throw}}
$script:task.Principal.UserId='DOMAIN\HR';$script:task.Actions[0].Arguments='custom args'
try {Enable-PayobookSchedule $root 'DOMAIN\HR' 'S-1-5-21-1';throw 'CUSTOM_ACTION_NOT_BLOCKED'} catch {if ($_.Exception.Message -notmatch 'customised') {throw}}
$script:missing=$true
try {Enable-PayobookSchedule $root 'DOMAIN\HR' 'S-1-5-21-1';throw 'MISSING_RUNTIME_NOT_BLOCKED'} catch {if ($_.Exception.Message -notmatch 'Windowless Python is missing') {throw}}
if ($script:updated) {throw 'Rejected task was modified'}
'PASS: quiet new action, action-only update, preserved arguments/working directory, wrong account/custom action/missing runtime refused'
