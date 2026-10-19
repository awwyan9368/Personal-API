# Personal Life OS — Windows PowerShell Local Setup Script
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " Personal Life OS — Local-First Setup (100% Free)    " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Ensure data, exports, and backups directories exist
New-Item -ItemType Directory -Force -Path "$RepoRoot\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$RepoRoot\exports" | Out-Null
New-Item -ItemType Directory -Force -Path "$RepoRoot\backups" | Out-Null

# Create .env from .env.example if missing
if (-not (Test-Path "$RepoRoot\.env")) {
    Copy-Item "$RepoRoot\.env.example" "$RepoRoot\.env"
    Write-Host "[OK] Created .env from .env.example" -ForegroundColor Green
}

# 1. Setup Backend Python Virtual Environment & Migrations
Write-Host "`n[1/2] Configuring Python Backend & SQLite Database..." -ForegroundColor Yellow
Set-Location "$RepoRoot\backend"

if (-not (Test-Path "$RepoRoot\backend\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

& "$RepoRoot\backend\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$RepoRoot\backend\.venv\Scripts\alembic.exe" upgrade head
Write-Host "[OK] Backend dependencies installed and Alembic migrations applied." -ForegroundColor Green

# 2. Setup Frontend Dependencies
Write-Host "`n[2/2] Installing Next.js Frontend Dependencies..." -ForegroundColor Yellow
Set-Location "$RepoRoot\frontend"

if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm install
} else {
    npm install
}

Set-Location $RepoRoot
Write-Host "`n[COMPLETE] Personal Life OS is ready! Run .\scripts\start.ps1 to launch locally." -ForegroundColor Green

