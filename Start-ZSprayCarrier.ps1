# Starts the Z Spray Carrier app the way a desktop app should start:
# both servers run hidden, nothing is left on screen, and the browser opens
# once the page is actually ready to serve.
#
# You normally do not run this directly - double-click "Z-Spray Carrier.vbs".

[CmdletBinding()]
param(
    [switch]$NoBrowser,          # start the servers but do not open a browser
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$logDir = Join-Path $root 'logs'
$pidFile = Join-Path $logDir 'running.txt'

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

# Shortcuts can start us with any working directory, and a shortcut's PATH can
# be stale, so rebuild it from the machine and user environment.
Set-Location $root
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

function Show-Problem([string]$Message) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        $Message, 'Z-Spray Carrier',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
}

function Test-PortOpen([int]$Port) {
    # Vite listens on ::1 while uvicorn listens on 127.0.0.1, so probe every
    # address localhost resolves to instead of assuming IPv4. Getting this
    # wrong makes a server that is up look like one that never started.
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses('localhost')
    } catch {
        $addresses = @([System.Net.IPAddress]::Loopback)
    }
    foreach ($addr in $addresses) {
        $client = New-Object System.Net.Sockets.TcpClient($addr.AddressFamily)
        try {
            $async = $client.BeginConnect($addr, $Port, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne(300)) {
                $client.EndConnect($async)
                return $true
            }
        } catch {
            # try the next address
        } finally {
            $client.Close()
        }
    }
    return $false
}

function Wait-ForPort([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $Port) { return $true }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

# --- Check the pieces are there before starting anything ------------------
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$viteJs = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'

if (-not (Test-Path $python)) {
    Show-Problem "The backend virtual environment is missing.`n`nExpected:`n$python`n`nRun this once in the backend folder:`n  python -m venv .venv`n  .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path $viteJs)) {
    Show-Problem "The frontend packages are not installed.`n`nRun this once in the frontend folder:`n  npm install"
    exit 1
}

$startedPids = @()

# --- Backend --------------------------------------------------------------
if (Test-PortOpen $BackendPort) {
    # Already up - leave it alone rather than starting a second copy.
} else {
    $proc = Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', "$BackendPort" `
        -WorkingDirectory (Join-Path $root 'backend') `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'backend.log') `
        -RedirectStandardError  (Join-Path $logDir 'backend.err.log')
    $startedPids += $proc.Id
}

# --- Frontend -------------------------------------------------------------
if (Test-PortOpen $FrontendPort) {
    # Already up.
} else {
    $node = (Get-Command node.exe -ErrorAction SilentlyContinue)
    if (-not $node) {
        Show-Problem "Node.js was not found on PATH.`n`nInstall Node 18 or newer, then try again."
        exit 1
    }
    $proc = Start-Process -FilePath $node.Source `
        -ArgumentList "`"$viteJs`"", '--port', "$FrontendPort", '--strictPort' `
        -WorkingDirectory (Join-Path $root 'frontend') `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'frontend.log') `
        -RedirectStandardError  (Join-Path $logDir 'frontend.err.log')
    $startedPids += $proc.Id
}

# Remember what we started so Stop-ZSprayCarrier can shut exactly those down.
if ($startedPids.Count -gt 0) {
    $startedPids | Set-Content -Path $pidFile -Encoding ASCII
}

# --- Wait until the page will actually load, then open it -----------------
if (-not (Wait-ForPort $FrontendPort $TimeoutSeconds)) {
    Show-Problem "The app did not finish starting within $TimeoutSeconds seconds.`n`nCheck the log files in:`n$logDir"
    exit 1
}

# The backend usually beats the frontend up, but give it its moment so the
# first page load is not greeted by a failed fetch.
Wait-ForPort $BackendPort 15 | Out-Null

if (-not $NoBrowser) {
    Start-Process "http://localhost:$FrontendPort"
}
