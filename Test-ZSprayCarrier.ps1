Write-Host "Running Backend Tests..."
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
cd backend
.\.venv\Scripts\Activate.ps1
pytest test_app.py

