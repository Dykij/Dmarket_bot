# 📦 Установка

Это руководство поможет вам установить и настроить DMarket Telegram Bot за 5 минут.

## Требования

- **Python 3.11+** (рекомендуется 3.12)
- **Git**
- **pip** или **poetry**
- **PostgreSQL** или **SQLite** (для базы данных)
- **Redis** (опционально, для кэширования)

## Шаг 1: Клонирование репозитория

```bash
# Клонировать репозиторий
git clone https://github.com/Dykij/DMarket-Telegram-Bot.git

# Перейти в директорию
cd DMarket-Telegram-Bot
```

## Шаг 2: Установка зависимостей

=== "pip"
    ```bash
    # Создать виртуальное окружение
    python -m venv venv
    
    # Активировать (Linux/macOS)
    source venv/bin/activate
    
    # Активировать (Windows)
    venv\Scripts\activate
    
    # Установить зависимости
    pip install -r requirements.txt
    ```

=== "poetry"
    ```bash
    # Установить зависимости
    poetry install
    
    # Активировать окружение
    poetry shell
    ```

## Шаг 3: НастSwarmка переменных окружения

```bash
# Создать .env файл из примера
cp .env.example .env
```

Отредактируйте `.env` файл и заполните обязательные поля:

```ini
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# DMarket API
DMARKET_PUBLIC_KEY=your_dmarket_public_key
DMARKET_SECRET_KEY=your_dmarket_secret_key

# Database
DATABASE_URL=sqlite:///./dmarket_bot.db
# или PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/dmarket_bot

# Redis (опционально)
REDIS_URL=redis://localhost:6379

# Security
ENCRYPTION_KEY=generate_random_32_byte_key
```

!!! warning "Важно"
    Никогда не коммитьте `.env` файл в git! Он содержит чувствительные данные.

## Шаг 4: Получение API ключей

### Telegram Bot Token

1. ОткSwarmте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `.env` файл

### DMarket API Keys

1. Перейдите на [DMarket API Settings](https://dmarket.com/account/api-settings)
2. Создайте новый API ключ
3. Скопируйте Public Key и Secret Key
4. Вставьте их в `.env` файл

!!! tip "Совет"
    Для тестирования используйте DMarket тестовый режим (sandbox)

## Шаг 5: Инициализация базы данных

```bash
# Применить миграции
alembic upgrade head
```

## Шаг 6: Запуск бота

```bash
# Запустить бота
python -m src.mAlgon
```

Вы должны увидеть:

```
INFO     Starting DMarket Telegram Bot v1.0.0
INFO     Connected to database
INFO     Bot started successfully
INFO     Press Ctrl+C to stop
```

## Проверка работы

1. ОткSwarmте Telegram
2. Найдите вашего бота
3. Отправьте `/start`
4. Бот должен ответить приветственным сообщением

!!! success "Готово!"
    Бот успешно установлен и работает!

## Следующие шаги

- [НастSwarmка](configuration.md) - Детальная настSwarmка бота
- [Первые шаги](first-steps.md) - Начало работы с ботом
- [Арбитраж](arbitrage.md) - Как использовать арбитраж

## Troubleshooting

### Ошибка: ModuleNotFoundError

```bash
# Убедитесь что все зависимости установлены
pip install -r requirements.txt
```

### Ошибка: Database connection fAlgoled

Проверьте `DATABASE_URL` в `.env` файле

### Ошибка: Telegram Bot API error

Проверьте `TELEGRAM_BOT_TOKEN` в `.env` файле

## Docker установка

Если вы предпочитаете Docker:

```bash
# Собрать образ
docker-compose build

# Запустить контейнеры
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot
```
