$logPath = "D:\DMarket-Telegram-Bot-main\debug.log"
$dbPath = "D:\DMarket-Telegram-Bot-main\bot_database.db"

Write-Host "--- Health Check ---"
if (Test-Path $dbPath) { Write-Host "[OK] Database file found." } else { Write-Host "[ERROR] Database file MISSING!" }
$cpu = (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue
Write-Host "[INFO] CPU Usage: $([Math]::Round($cpu, 2))%"
Write-Host "--------------------"