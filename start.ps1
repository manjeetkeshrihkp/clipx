# ClipX Studio PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "              Starting ClipX Studio                " -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[.venv not found. Creating virtual environment...]" -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[Installing requirements...]" -ForegroundColor Yellow
    .\.venv\Scripts\pip install -r requirements.txt
}

Write-Host "[Launching Web Server at http://127.0.0.1:8765]" -ForegroundColor Green
Write-Host "Open http://127.0.0.1:8765 in your browser." -ForegroundColor White
Write-Host "Press Ctrl+C to stop the server.`n" -ForegroundColor DarkGray

Start-Process "http://127.0.0.1:8765"
& ".\.venv\Scripts\python.exe" -m studio.server
