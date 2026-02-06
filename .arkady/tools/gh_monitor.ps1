# GitHub Monitor Script v1.0
$LogDir = "D:\DMarket-Telegram-Bot-main\.arkady\logs"

Write-Host "[WATCHER] Starting GitHub Actions Monitor..." -ForegroundColor Cyan

while($true) {
    # Проверка статуса последнего запуска через gh CLI
    $RunStatus = gh run list --limit 1 --json status,conclusion,displayTitle
    $Parsed = $RunStatus | ConvertFrom-Json

    if ($Parsed.conclusion -eq "failure") {
        Write-Host "[!] ALERT: GitHub Action Failed: $($Parsed.displayTitle)" -ForegroundColor Red
        
        # Создание тикета о падении
        $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $TicketPath = Join-Path $LogDir "GH_FAILURE_$Timestamp.json"
        
        $Parsed | ConvertTo-Json | Out-File $TicketPath
        Write-Host "[WATCHER] Failure logged to $TicketPath"
    }

    Start-Sleep -Seconds 300
}
