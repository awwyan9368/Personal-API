# Personal Life OS — Windows PowerShell Startup Script
# Launches both the FastAPI Backend (http://localhost:8000) and Next.js Production Frontend (http://localhost:3000)
# Usage from ANY directory:
#   powershell -ExecutionPolicy Bypass -File "D:\MyAPI\scripts\start.ps1"

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LocalNodeBin = "C:\Users\minha\AppData\Local\OpenAI\Codex\runtimes\cua_node\cfb32733c877621e\bin"
if (Test-Path $LocalNodeBin) {
    $env:PATH = "$LocalNodeBin;$env:PATH"
}

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " Starting Personal Life OS (Local-First Architecture)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " -> Backend REST API & Docs : http://localhost:8000/docs" -ForegroundColor Green
Write-Host " -> Frontend Web Interface  : http://localhost:3000" -ForegroundColor Green
Write-Host " -> SQLite Database         : $RepoRoot\data\personal_life_os.db" -ForegroundColor Gray

# Apply any pending Alembic migrations before starting
Set-Location "$RepoRoot\backend"
& "$RepoRoot\backend\.venv\Scripts\alembic.exe" upgrade head

$BackendProc = Start-Process -FilePath "$RepoRoot\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory "$RepoRoot\backend" `
    -PassThru

try {
    Set-Location "$RepoRoot\frontend"
    $NodeExe = if (Test-Path "$LocalNodeBin\node.exe") { "$LocalNodeBin\node.exe" } else { "node.exe" }
    $NextBin = "$RepoRoot\frontend\node_modules\next\dist\bin\next"
    if (-not (Test-Path "$RepoRoot\frontend\.next\BUILD_ID")) {
        Write-Host "Building optimized production frontend for instant navigation..." -ForegroundColor Yellow
        & $NodeExe $NextBin build
    }
    & $NodeExe $NextBin start -p 3000
} finally {
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Write-Host "`nStopping FastAPI backend server..." -ForegroundColor Yellow
        Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
