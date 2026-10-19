# Personal Life OS — Disable Automatic Startup on Windows Boot / Login
# Removes the silent launcher from your Windows Startup folder (`shell:startup`).
# Usage:
#   powershell -ExecutionPolicy Bypass -File "D:\MyAPI\scripts\disable-autostart.ps1"

$StartupFolder = [Environment]::GetFolderPath("Startup")
$VbsPath = Join-Path $StartupFolder "PersonalLifeOS-Autostart.vbs"

if (Test-Path $VbsPath) {
    Remove-Item -Path $VbsPath -Force
    Write-Host "[OK] Removed Personal Life OS from Windows Startup ($VbsPath)" -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Personal Life OS auto-start was not registered in Windows Startup." -ForegroundColor Gray
}

