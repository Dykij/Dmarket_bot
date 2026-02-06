if (Test-Path "D:\DMarket-Telegram-Bot-main\.venv\Scripts\Activate.ps1") {
    . "D:\DMarket-Telegram-Bot-main\.venv\Scripts\Activate.ps1"
}

# Просто запускаем. Теперь он обязан прочитать конфиг из %USERPROFILE%\.openclaw\
openclaw gateway
