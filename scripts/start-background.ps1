# Personal Life OS — Detached Background Launcher (Windows PowerShell)
# Uses Win32_Process.Create so the Backend (port 8000), Production Frontend (port 3000),
# and Auto Screen-Time Collector run completely independent of your terminal window.
# Usage from ANY directory:
#   powershell -ExecutionPolicy Bypass -File "D:\MyAPI\scripts\start-background.ps1"

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Stop any existing instances first
& "$PSScriptRoot\stop-background.ps1" | Out-Null

$LocalNodeBin = "C:\Users\minha\AppData\Local\OpenAI\Codex\runtimes\cua_node\cfb32733c877621e\bin"
if (Test-Path $LocalNodeBin) {
    $env:PATH = "$LocalNodeBin;$env:PATH"
}

$LogsDir = "$RepoRoot\data\logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# Apply any pending Alembic migrations
Set-Location "$RepoRoot\backend"
& "$RepoRoot\backend\.venv\Scripts\alembic.exe" upgrade head

# Ensure optimized Next.js production build exists for instant route transitions
$NodeExe = if (Test-Path "$LocalNodeBin\node.exe") { "$LocalNodeBin\node.exe" } else { "node.exe" }
$NextBin = "$RepoRoot\frontend\node_modules\next\dist\bin\next"

if (-not (Test-Path "$RepoRoot\frontend\.next\BUILD_ID")) {
    Write-Host "Building optimized production frontend for instant navigation..." -ForegroundColor Yellow
    Set-Location "$RepoRoot\frontend"
    & $NodeExe $NextBin build
}

# Create hidden window startup info for Win32_Process
$Startup = New-CimInstance -ClassName Win32_ProcessStartup -Property @{ ShowWindow = [uint16]0 } -ClientOnly

# 1. Launch FastAPI Backend on 0.0.0.0:8000 (accessible from localhost AND Android phone over Wi-Fi)
$BackendCmd = "cmd.exe /c `"`"$RepoRoot\backend\.venv\Scripts\python.exe`" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > `"$LogsDir\backend.out.log`" 2> `"$LogsDir\backend.err.log`"`""
$BackendRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine               = $BackendCmd
    CurrentDirectory          = "$RepoRoot\backend"
    ProcessStartupInformation = $Startup
}
$BackendPid = $BackendRes.ProcessId

# 2. Launch Next.js Production Server (`next start -p 3000`)
$FrontendCmd = "cmd.exe /c `"set PATH=$LocalNodeBin;%PATH% && `"$NodeExe`" `"$NextBin`" start -p 3000 > `"$LogsDir\frontend.out.log`" 2> `"$LogsDir\frontend.err.log`"`""
$FrontendRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine               = $FrontendCmd
    CurrentDirectory          = "$RepoRoot\frontend"
    ProcessStartupInformation = $Startup
}
$FrontendPid = $FrontendRes.ProcessId

Start-Sleep -Seconds 2

# 3. Launch Automatic Screen-Time Collector (Windows Laptop + Android ADB)
$CollectorCmd = "cmd.exe /c `"`"$RepoRoot\backend\.venv\Scripts\python.exe`" -u `"$RepoRoot\scripts\screen_time_collector.py`" --interval 10 --flush-seconds 60 > `"$LogsDir\collector.out.log`" 2> `"$LogsDir\collector.err.log`"`""
$CollectorRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine               = $CollectorCmd
    CurrentDirectory          = $RepoRoot
    ProcessStartupInformation = $Startup
}
$CollectorPid = $CollectorRes.ProcessId

$PidState = @{
    backend_pid   = $BackendPid
    frontend_pid  = $FrontendPid
    collector_pid = $CollectorPid
    started_at    = (Get-Date).ToString("o")
} | ConvertTo-Json

Set-Content -Path "$RepoRoot\data\running_pids.json" -Value $PidState

Set-Location $RepoRoot
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Personal Life OS + Auto Screen-Time Collector is LIVE!   " -ForegroundColor Green
Write-Host " You can safely close your PowerShell window at any time. " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " -> Web UI            : http://localhost:3000" -ForegroundColor Green
Write-Host " -> REST API          : http://localhost:8000/api/v1/docs" -ForegroundColor Green
Write-Host " -> Laptop Collector  : Active in background (PID $CollectorPid)" -ForegroundColor Green
Write-Host " -> Logs              : $LogsDir" -ForegroundColor Gray
Write-Host " -> To stop           : powershell -ExecutionPolicy Bypass -File `"D:\MyAPI\scripts\stop-background.ps1`"" -ForegroundColor Yellow
