# ⚙️ НастSwarmка

После установки бота необходимо выполнить его первоначальную настSwarmку.

## Получение API ключей

### Telegram Bot Token

1. ОткSwarmте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Выберите имя для бота (например: "My DMarket Bot")
4. Выберите username (должен заканчиваться на "bot", например: "my_dmarket_bot")
5. BotFather отправит вам токен в формате: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
6. Скопируйте токен и сохраните в `.env` файл:

```ini
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

!!! warning "Важно"
    Никогда не делитесь токеном бота! Любой, у кого есть токен, может контролировать вашего бота.

### DMarket API Keys

1. Перейдите на [DMarket](https://dmarket.com/)
2. Войдите в аккаунт или зарегистрируйтесь
3. ОткSwarmте [API Settings](https://dmarket.com/account/api-settings)
4. Нажмите "Create new API key"
5. Скопируйте Public Key и Secret Key
6. Добавьте в `.env`:

```ini
DMARKET_PUBLIC_KEY=your_public_key_here
DMARKET_SECRET_KEY=your_secret_key_here
```

!!! tip "Sandbox режим"
    Для тестирования можно использовать DMarket sandbox environment:
    ```ini
    DMARKET_API_URL=https://api.sandbox.dmarket.com
    ```

## НастSwarmка базы данных

### SQLite (по умолчанию)

Самый простой вариант для начала:

```ini
DATABASE_URL=sqlite:///./dmarket_bot.db
```

База данных будет создана автоматически при первом запуске.

### PostgreSQL (рекомендуется для production)

1. Установите PostgreSQL
2. Создайте базу данных:

```sql
CREATE DATABASE dmarket_bot;
CREATE USER dmarket_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dmarket_bot TO dmarket_user;
```

3. НастSwarmте в `.env`:

```ini
DATABASE_URL=postgresql://dmarket_user:your_password@localhost/dmarket_bot
```

## НастSwarmка Redis (опционально)

Redis используется для кэширования и очередей задач.

### Локальная установка

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

### НастSwarmка

```ini
REDIS_URL=redis://localhost:6379/0
```

### Docker

```bash
docker run -d -p 6379:6379 redis:alpine
```

## Генерация ключа шифрования

Для безопасного хранения API ключей пользователей:

```python
import secrets
print(secrets.token_hex(32))
```

Добавьте в `.env`:

```ini
ENCRYPTION_KEY=generated_64_character_hex_string
```

## Применение миграций

После настSwarmки базы данных:

```bash
# Применить все миграции
alembic upgrade head

# Проверить текущую версию
alembic current

# История миграций
alembic history
```

## Проверка конфигурации

Запустите бота в тестовом режиме:

```bash
# Проверить что все зависимости установлены
python -c "import src.mAlgon; print('OK')"

# Запустить бота
python -m src.mAlgon
```

Вы должны увидеть:

```
INFO     Configuration loaded successfully
INFO     Database connection established
INFO     Redis connection established (or skipped if not configured)
INFO     Bot started: @your_bot_username
INFO     Press Ctrl+C to stop
```

## Дополнительные настSwarmки

### Логирование

```ini
# Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Файл логов
LOG_FILE=bot.log
```

### Лимиты

```ini
# Максимальная цена предмета для автопокупки (в центах)
MAX_AUTO_BUY_PRICE=50000  # $500

# Максимальное количество активных таргетов на пользователя
MAX_USER_TARGETS=100

# Интервал сканирования (секунды)
SCAN_INTERVAL=300  # 5 минут
```

### Sentry (мониторинг ошибок)

```ini
SENTRY_DSN=https://your_sentry_dsn
SENTRY_ENVIRONMENT=production
```

## Полный пример .env

```ini
# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# DMarket API
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
# DMARKET_API_URL=https://api.sandbox.dmarket.com  # Для тестирования

# Database
DATABASE_URL=postgresql://dmarket_user:password@localhost/dmarket_bot
# DATABASE_URL=sqlite:///./dmarket_bot.db  # Альтернатива для разработки

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=your_64_character_hex_string

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Limits
MAX_AUTO_BUY_PRICE=50000
MAX_USER_TARGETS=100
SCAN_INTERVAL=300

# Sentry (опционально)
# SENTRY_DSN=https://your_sentry_dsn
# SENTRY_ENVIRONMENT=production
```

## Следующие шаги

- [Первые шаги](first-steps.md) - Начало работы с ботом
- [Арбитраж](arbitrage.md) - Как использовать арбитраж
- [НастSwarmки меню](../telegram-ui/settings-menu.md) - UI настроек

## Troubleshooting

### Ошибка: Invalid bot token

Проверьте что токен скопирован правильно, без лишних пробелов.

### Ошибка: Database connection fAlgoled

- Проверьте что PostgreSQL запущен: `sudo systemctl status postgresql`
- Проверьте логин/пароль в DATABASE_URL
- Проверьте что база данных создана

### Ошибка: DMarket API authentication fAlgoled

- Проверьте что API ключи активны в DMarket настSwarmках
- Проверьте что нет лишних пробелов в ключах
- Попробуйте пересоздать API ключи
