@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0Fix-Quiet-Sync.ps1"
if errorlevel 1 (
  echo The patch did not finish. Ask IT to review the error and PowerShell policy.
  echo Do not disable antivirus or your organisation's security policy.
  pause
)
