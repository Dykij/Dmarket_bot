# Arkady Environment Setup Script v1.0

# 1. Aliases & Functions
function Get-ArkLogs {
    Get-Content "D:\DMarket-Telegram-Bot-main\.arkady\logs\activity.jsonl" -Tail 20
}

function Get-ArkStatus {
    $state = Get-Content "D:\DMarket-Telegram-Bot-main\.arkady\EVOLUTION_STATE.json" | ConvertFrom-Json
    Write-Host "`n--- ARKADY SYSTEM STATUS ---" -ForegroundColor Cyan
    Write-Host "Phase: $($state.phase)"
    Write-Host "Status: $($state.status)"
    Write-Host "Last Action: $($state.last_action)"
    Write-Host "---------------------------`n"
}

function Start-ArkWatch {
    Write-Host "[*] Launching GitHub Monitor..." -ForegroundColor Yellow
    powershell.exe -File "D:\DMarket-Telegram-Bot-main\.arkady\tools\gh_monitor.ps1"
}

function Open-ArkReport {
    $reportPath = "D:\DMarket-Telegram-Bot-main\.arkady\reports\INSIGHTS_WEEKLY.html"
    if (Test-Path $reportPath) {
        Write-Host "[*] Opening Arkady Insights..." -ForegroundColor Green
        Start-Process $reportPath
    } else {
        Write-Error "Report not found. Run insight_generator.py first."
    }
}

# Set Aliases
New-Alias ark-logs Get-ArkLogs -Force
New-Alias ark-status Get-ArkStatus -Force
New-Alias ark-watch Start-ArkWatch -Force
New-Alias ark-report Open-ArkReport -Force

# 2. GitHub CLI Completion
if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh completion -s powershell | Out-String | Invoke-Expression
    Write-Host "[+] GitHub CLI Autocomplete loaded." -ForegroundColor Gray
}

Write-Host "`n🚀 Arkady Environment Activated!" -ForegroundColor Magenta
Write-Host "Commands: ark-logs, ark-status, ark-watch, ark-report`n" -ForegroundColor Gray
