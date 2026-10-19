# Personal Life OS — Enable Automatic Startup on Windows Boot / Login
# Places a silent VBScript launcher in your Windows Startup folder (`shell:startup`)
# so Personal Life OS (Backend + Frontend + Screen-Time Collector) starts automatically
# every time you turn on your laptop and sign into Windows.
# Usage:
#   powershell -ExecutionPolicy Bypass -File "D:\MyAPI\scripts\enable-autostart.ps1"

$StartupFolder = [Environment]::GetFolderPath("Startup")
$VbsPath = Join-Path $StartupFolder "PersonalLifeOS-Autostart.vbs"
$ScriptPath = "D:\MyAPI\scripts\start-background.ps1"

$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$ScriptPath""", 0, False
"@

Set-Content -Path $VbsPath -Value $VbsContent -Encoding ASCII

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Windows Auto-Start Enabled for Personal Life OS!         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " -> Startup Launcher : $VbsPath" -ForegroundColor Green
Write-Host " -> Behavior         : Automatically launches in the background whenever you turn on your laptop." -ForegroundColor Gray
Write-Host " -> To disable       : powershell -ExecutionPolicy Bypass -File `"D:\MyAPI\scripts\disable-autostart.ps1`"" -ForegroundColor Yellow

