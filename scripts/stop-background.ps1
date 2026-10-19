# Personal Life OS — Stop Background Processes (Windows PowerShell)
# Cleanly stops the detached FastAPI backend, Next.js frontend, and Screen-Time Collector processes.
# Usage from ANY directory:
#   powershell -ExecutionPolicy Bypass -File "D:\MyAPI\scripts\stop-background.ps1"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PidFile = "$RepoRoot\data\running_pids.json"

if (Test-Path $PidFile) {
    try {
        $Pids = Get-Content $PidFile | ConvertFrom-Json
        foreach ($p in @($Pids.backend_pid, $Pids.frontend_pid, $Pids.collector_pid)) {
            if ($p) {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# Stop any remaining screen_time_collector.py python processes
$CollectorProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' AND CommandLine LIKE '%screen_time_collector.py%'" -ErrorAction SilentlyContinue
foreach ($cp in $CollectorProcs) {
    Stop-Process -Id $cp.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Stopped Screen-Time Collector (PID $($cp.ProcessId))" -ForegroundColor Green
}

foreach ($port in @(8000, 3000)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Stopped process on port $port (PID $($c.OwningProcess))" -ForegroundColor Green
    }
}
