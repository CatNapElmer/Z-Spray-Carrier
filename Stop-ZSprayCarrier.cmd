@echo off
rem The servers run hidden, so this is how you shut them down.
rem Only stops what the launcher started - it will not touch other node or
rem python processes you have running.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command ^
 "$f = Join-Path '%~dp0' 'logs\running.txt'; if (Test-Path $f) { Get-Content $f | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Remove-Item $f -ErrorAction SilentlyContinue }"
exit
