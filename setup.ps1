# Sentinel — Windows PowerShell Setup Script
# Run from the sentinel/ directory: .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Sentinel AI GRC Auditor — Windows Setup     " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. Install from https://python.org/ and ensure it is on PATH" -ForegroundColor Red
    exit 1
}

# Check Node
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js not found. Install from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Copy .env if not exists
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env from .env.example — edit it to add your credentials" -ForegroundColor Yellow
} else {
    Write-Host "[OK] .env already exists" -ForegroundColor Green
}

# Backend virtual environment
Write-Host ""
Write-Host "Setting up backend..." -ForegroundColor Cyan

Set-Location backend

if (-Not (Test-Path ".venv")) {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv .venv
}

Write-Host "  Activating virtual environment..." -ForegroundColor Gray
& ".\.venv\Scripts\Activate.ps1"

Write-Host "  Installing Python dependencies..." -ForegroundColor Gray
pip install -e . --quiet

Write-Host "[OK] Backend dependencies installed" -ForegroundColor Green
Set-Location ..

# Mock agent virtual environment
Write-Host ""
Write-Host "Setting up mock agent..." -ForegroundColor Cyan

Set-Location mock_agent

if (-Not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"
pip install fastapi uvicorn pydantic --quiet

Write-Host "[OK] Mock agent dependencies installed" -ForegroundColor Green
Set-Location ..

# Frontend dependencies
Write-Host ""
Write-Host "Setting up frontend..." -ForegroundColor Cyan

Set-Location frontend
npm install --silent
Write-Host "[OK] Frontend dependencies installed" -ForegroundColor Green
Set-Location ..

# Done
Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start all services, open 3 PowerShell windows:" -ForegroundColor White
Write-Host ""
Write-Host "  Window 1 — Backend:" -ForegroundColor Yellow
Write-Host "    cd backend; .\.venv\Scripts\Activate.ps1; uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Gray
Write-Host ""
Write-Host "  Window 2 — Mock Agent:" -ForegroundColor Yellow
Write-Host "    cd mock_agent; .\.venv\Scripts\Activate.ps1; uvicorn main:app --host 0.0.0.0 --port 8001" -ForegroundColor Gray
Write-Host ""
Write-Host "  Window 3 — Frontend:" -ForegroundColor Yellow
Write-Host "    cd frontend; npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  Then open http://localhost:3000 in your browser." -ForegroundColor Cyan
Write-Host ""
Write-Host "  See no-docker-setup.md for full instructions." -ForegroundColor White
Write-Host ""
