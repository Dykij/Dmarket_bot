# Arkady Watcher 2.0 (Self-Healing Script)
# Logic: Monitor docker container, log errors, and notify architect.

$ContainerName = "dmarket-bot"
$LogDir = "D:\DMarket-Telegram-Bot-main\.arkady\logs"

Write-Host "[*] Arkady Watcher 2.0 started. Monitoring: $ContainerName" -ForegroundColor Cyan

while($true) {
    # 1. Проверка статуса контейнера
    $Status = docker inspect --format='{{.State.Status}}' $ContainerName 2>$null

    if ($Status -ne "running") {
        Write-Host "[!] Container $ContainerName is $Status. Emergency handling initiated." -ForegroundColor Red
        
        $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $LogPath = Join-Path $LogDir "CRASH_REPORT_$Timestamp.json"
        
        # a) Копирование последних 50 строк
        $Logs = docker logs --tail 50 $ContainerName 2>&1
        
        # b) Создание тикета
        $Report = @{
            timestamp = $Timestamp
            container = $ContainerName
            status = $Status
            logs = $Logs
            action = "Restart attempted"
        } | ConvertTo-Json
        
        $Report | Out-File -FilePath $LogPath
        
        # c) Эмуляция вызова Архитектора
        Write-Host "[ARCHITECT CALL] Вызываю Архитектора для анализа лога: CRASH_REPORT_$Timestamp.json" -ForegroundColor Yellow
        
        # d) Перезапуск
        docker start $ContainerName
    }

    # 2. Поиск ERROR в последних логах (даже если контейнер запущен)
    $RecentLogs = docker logs --since 1m $ContainerName 2>&1 | Select-String "ERROR", "CRITICAL"
    if ($RecentLogs) {
        Write-Host "[!] Detected runtime errors in logs. Reporting..." -ForegroundColor Red
        # Логика аналогична крашу, но без рестарта
    }

    Start-Sleep -Seconds 30
}
