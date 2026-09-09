@echo off
rem Fallback launcher for machines where Windows Script Host (.vbs) is blocked.
rem Prefer "Z-Spray Carrier.vbs" - it starts with no window at all.
rem This one flashes a console for a moment and then closes.
start "" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Start-ZSprayCarrier.ps1"
exit
