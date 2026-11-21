# Cross-platform worker-control test. WPF rendering still needs a Windows pilot.
param([string]$Python = 'python3')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../Setup.ps1'
$errors = $null; $tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Run-Worker','Result-Text')) {
    $fn = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name}, $true)
    Invoke-Expression $fn.Extent.Text
}
$tick = $ast.Find({param($node) $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] -and $node.Member.Value -eq 'Add_Tick'}, $true)
$tickBody = [scriptblock]::Create($tick.Arguments[0].ScriptBlock.Extent.Text.Trim().Substring(1).TrimEnd().TrimEnd('}'))
$script:controls = @{}
foreach ($name in @('RunState','Elapsed')) { $script:controls[$name] = [pscustomobject]@{Text=''} }
$window = [pscustomobject]@{}
$window | Add-Member ScriptMethod FindName {param($name) $script:controls[$name]}
$timer = [pscustomobject]@{Running=$false}
$timer | Add-Member ScriptMethod Start {$this.Running=$true}
$timer | Add-Member ScriptMethod Stop {$this.Running=$false}
function Set-Working([bool]$working) {$script:working=$working}
$output = [pscustomobject]@{Text=''}
$server = [pscustomobject]@{Text='https://example.invalid'}
$database = [pscustomobject]@{Text='test.mdb'}
$code = [pscustomobject]@{Cleared=$false}
$code | Add-Member ScriptMethod Clear {$this.Cleared=$true}
$script:activeRun=$null
$script:lastDiagnostics=''
$data = Join-Path ([IO.Path]::GetTempPath()) ('pb-connector-ui-test-' + [guid]::NewGuid())
New-Item -ItemType Directory $data | Out-Null
$preferences=Join-Path $data 'setup.json'
$worker=Join-Path $data 'worker.py'
@'
import json, sys, time
time.sleep(1)
command=sys.argv[1]
if command=='pair':
    data=json.load(sys.stdin)
    assert data['name']=='Tiếng Việt'
    print(json.dumps({'paired':True,'name':'Group B · validation'}))
elif command=='replay':
    print(json.dumps({'error':'Simulated connection failure'}));sys.exit(1)
else:
    print(json.dumps({'sent':12,'pending':0,'source_rows':100,'latest_punch':'2026-11-12 07:32:37'}))
'@ | Set-Content $worker -Encoding utf8
function Complete-Run {
    $deadline=(Get-Date).AddSeconds(15)
    while ($script:activeRun -and (Get-Date) -lt $deadline) {Start-Sleep -Milliseconds 40; . $tickBody}
    if ($script:activeRun) {throw 'Worker did not complete'}
    if ($script:working -or $timer.Running) {throw 'Controls stayed busy after completion'}
}
try {
    $sw=[Diagnostics.Stopwatch]::StartNew()
    Run-Worker 'sync'
    if ($sw.ElapsedMilliseconds -gt 700) {throw 'Run-Worker blocked the UI'}
    if (-not $script:working -or -not $timer.Running) {throw 'No working indicator'}
    $first=$script:activeRun.Process.Id
    Run-Worker 'sync'
    if ($script:activeRun.Process.Id -ne $first) {throw 'Overlapping worker started'}
    Complete-Run
    if ($output.Text -notmatch 'Records sent this run: 12') {throw $output.Text}
    Run-Worker 'pair' (@{name='Tiếng Việt'} | ConvertTo-Json -Compress)
    Complete-Run
    if (-not $code.Cleared -or -not (Test-Path $preferences)) {throw 'Pair completion did not save preferences'}
    if ($output.Text -notmatch 'Group B · validation') {throw 'Unicode response not decoded'}
    Run-Worker 'replay'
    Complete-Run
    if ($window.FindName('RunState').Text -ne 'Needs attention') {throw 'Failure incorrectly shown as success'}
    if ($output.Text -notmatch 'Simulated connection failure') {throw 'Failure not explained'}
    'PASS: nonblocking start, overlap protection, completion, UTF-8 pairing, friendly results, error recovery'
} finally {Remove-Item $data -Recurse -Force}
