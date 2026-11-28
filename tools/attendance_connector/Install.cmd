@echo off
powershell.exe -NoProfile -File "%~dp0Setup.ps1"
if errorlevel 1 (
  echo Setup could not run. Ask IT to review the package and approve its PowerShell execution policy.
  echo Do not disable antivirus or organisation security policy.
  pause
)
