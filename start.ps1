# Smart Study Generator — PowerShell launcher
# Run from any location: .\start.ps1

$root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy    = Join-Path $root "venv\Scripts\python.exe"
$backend   = Join-Path $root "backend"
$envSrc    = Join-Path $root ".env"
$envDst    = Join-Path $backend ".env"
$reqs      = Join-Path $root "requirements.txt"
$sysPy     = "C:\Users\avira\AppData\Local\Programs\Python\Python312\python.exe"

Write-Host ""
Write-Host "  Smart Study Generator" -ForegroundColor Cyan
Write-Host "  =====================" -ForegroundColor Cyan

# Sync .env
if (Test-Path $envSrc) {
    Copy-Item $envSrc $envDst -Force
    Write-Host "  [OK] .env synced" -ForegroundColor Green
} else {
    Write-Host "  [!!] .env not found. Copy .env.example to .env and add your GROQ_API_KEY" -ForegroundColor Red
    exit 1
}

# Create venv if missing
if (-not (Test-Path $venvPy)) {
    Write-Host "  [..] Creating virtual environment..." -ForegroundColor Yellow
    & $sysPy -m venv "$root\venv"
    Write-Host "  [OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  [OK] Virtual environment found" -ForegroundColor Green
}

# Install deps
Write-Host "  [..] Installing dependencies..." -ForegroundColor Yellow
& "$root\venv\Scripts\pip.exe" install -q -r $reqs
Write-Host "  [OK] Dependencies ready" -ForegroundColor Green

# Open browser after 3s
Start-Job { Start-Sleep 3; Start-Process "http://127.0.0.1:5000" } | Out-Null

# Start server
Write-Host ""
Write-Host "  Starting server at http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

Set-Location $backend
& $venvPy app.py
