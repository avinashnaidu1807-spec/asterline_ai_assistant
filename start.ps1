# ==============================================================================
# Asterline Research Assistant - Single-Command Launch Script (Windows PowerShell)
# ==============================================================================
$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Asterline AI Research Assistant - Multi-Agent & Persistent Memory" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$BackendDir = "$ScriptDir\backend"
$FrontendDir = "$ScriptDir\frontend"

Write-Host "`n[1/4] Verifying dependencies..." -ForegroundColor Yellow

# Verify Python
try {
    $pythonVersion = python --version
    Write-Host "  Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "Python 3 is required but was not found in PATH."
}

# Verify Node
try {
    $nodeVersion = node --version
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Error "Node.js is required but was not found in PATH."
}

# Check/create .env if missing
if (-not (Test-Path "$BackendDir\.env") -and (Test-Path "$BackendDir\.env.example")) {
    Copy-Item "$BackendDir\.env.example" "$BackendDir\.env"
    Write-Host "  Created backend\.env from template" -ForegroundColor DarkGray
}

# Free stale processes on ports 8000 & 5173 if any
foreach ($port in @(8000, 5173)) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess -gt 0) {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

Write-Host "`n[2/4] Initializing Database & Vector Store..." -ForegroundColor Yellow

# Ingest corpus and initialize DB
try {
    python scripts/ingest_corpus.py
} catch {
    Write-Host "  Notice during ingestion: $_" -ForegroundColor DarkYellow
}

Write-Host "`n[3/4] Starting Backend API (FastAPI) on port 8000..." -ForegroundColor Yellow
$backendOut = "$BackendDir\backend_out.log"
$backendErr = "$BackendDir\backend_err.log"
$backendJob = Start-Process python -ArgumentList "-u -m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

Write-Host "`n[4/4] Starting Frontend Dev Server (Vite) on port 5173..." -ForegroundColor Yellow
$frontendOut = "$FrontendDir\frontend_out.log"
$frontendErr = "$FrontendDir\frontend_err.log"
$frontendJob = Start-Process "cmd.exe" -ArgumentList "/c npm run dev -- --port 5173" `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru

# Give processes 2 seconds to initialize
Start-Sleep -Seconds 2

# Check if backend died immediately
if ($backendJob.HasExited) {
    Write-Host "`n[ERROR] Backend process failed to start. Error log output:" -ForegroundColor Red
    if (Test-Path $backendErr) { Get-Content $backendErr | ForEach-Object { Write-Host "  $_" -ForegroundColor Red } }
    if ($frontendJob -and -not $frontendJob.HasExited) { Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}

Write-Host "`n==================================================================" -ForegroundColor Green
Write-Host " Asterline Assistant is running!" -ForegroundColor Green
Write-Host " - Web Interface: http://localhost:5173" -ForegroundColor White
Write-Host " - API Docs:      http://localhost:8000/docs" -ForegroundColor White
Write-Host " - Health Check:  http://localhost:8000/health" -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop both servers.`n" -ForegroundColor DarkGray

try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($backendJob.HasExited) {
            Write-Host "`nBackend process exited unexpectedly. Error output:" -ForegroundColor Red
            if (Test-Path $backendErr) { Get-Content $backendErr -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red } }
            break
        }
        if ($frontendJob.HasExited) {
            Write-Host "`nFrontend process exited unexpectedly. Error output:" -ForegroundColor Red
            if (Test-Path $frontendErr) { Get-Content $frontendErr -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red } }
            break
        }
    }
} finally {
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    if ($backendJob -and -not $backendJob.HasExited) {
        Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendJob -and -not $frontendJob.HasExited) {
        Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue
    }
    # Clean up any child processes on ports
    foreach ($port in @(8000, 5173)) {
        try {
            $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
            foreach ($c in $conns) {
                if ($c.OwningProcess -gt 0) {
                    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {}
    }
    Write-Host "Servers stopped cleanly." -ForegroundColor Green
}
