# 🔐 Руководство по безопасности

**Дата**: 28 декабря 2025 г.
**Версия**: 1.0.0
**Последнее обновление**: Полная актуализация документации

---

## 📋 Оглавление

- [Общие принципы безопасности](#общие-принципы-безопасности)
- [🚨 Безопасная торговля на реальных деньгах](#безопасная-торговля-на-реальных-деньгах)
- [Защита API ключей](#защита-api-ключей)
- [Безопасность базы данных](#безопасность-базы-данных)
- [Безопасность Telegram бота](#безопасность-telegram-бота)
- [Обработка ошибок и логирование](#обработка-ошибок-и-логирование)
- [Лучшие практики](#лучшие-практики)

---

## 🚨 Безопасная торговля на реальных деньгах

### ⚠️ КРИТИЧЕСКИ ВАЖНО: Режим DRY_RUN

По умолчанию бот работает в **безопасном режиме** (`DRY_RUN=true`), при котором:
- ✅ **НЕ** совершаются реальные сделки
- ✅ Все операции покупки/продажи **симулируются**
- ✅ Ваш баланс на DMarket **остается неизменным**
- ✅ Логи помечаются `[DRY-RUN]`

**НИКОГДА** не переключайтесь на реальную торговлю (`DRY_RUN=false`) без тщательного тестирования!

### 📋 Чеклист перед запуском на реальных деньгах

#### Шаг 1: Тестирование в DRY_RUN режиме (48-72 часа минимум)

- [ ] ✅ Бот протестирован минимум **48-72 часа** в `DRY_RUN=true`
- [ ] ✅ Все логи проверены на отсутствие критических ошибок
- [ ] ✅ Арбитражный сканер работает стабильно
- [ ] ✅ Система таргетов создает корректные заявки (в DRY_RUN)
- [ ] ✅ Уведомления приходят своевременно
- [ ] ✅ База данных работает без ошибок
- [ ] ✅ Нет утечек памяти (проверить через `htop`/`Task Manager`)
- [ ] ✅ Метрики Sentry показывают стабильность (если настроено)

#### Шаг 2: Настroка безопасных лимитов

Перед включением реальной торговли **обязательно** установите защитные лимиты:

```env
# .env файл - ОБЯЗАТЕЛЬНЫЕ лимиты для реальной торговли
DRY_RUN=false  # ОПАСНО! Реальная торговля!

# Защитные лимиты
MAX_TRADE_VALUE=50.00          # Макс $50 на одну сделку
daily_TRADE_LIMIT=500.00       # Макс $500 в день
MIN_PROFIT_PERCENT=5.0         # Мин 5% прибыли
MAX_CONCURRENT_TRADES=3        # Макс 3 одновременных сделки

# Стоп-лосс защита
STOP_LOSS_PERCENT=10.0         # Остановить если цена упала на 10%
MAX_CONSECUTIVE_LOSSES=5       # Остановить после 5 убыточных сделок подряд

# Мониторинг баланса
MIN_BALANCE_THRESHOLD=10.00    # Остановить если баланс < $10
BALANCE_CHECK_INTERVAL=300     # Проверять баланс каждые 5 минут
```

- [ ] ✅ `MAX_TRADE_VALUE` установлен на безопасное значение
- [ ] ✅ `daily_TRADE_LIMIT` установлен
- [ ] ✅ `MIN_PROFIT_PERCENT` не менее 3-5%
- [ ] ✅ `STOP_LOSS_PERCENT` настроен
- [ ] ✅ `MIN_BALANCE_THRESHOLD` установлен

#### Шаг 3: Настroка системы мониторинга

- [ ] ✅ **Sentry** настроен для отслеживания ошибок
- [ ] ✅ **email/Telegram алерты** на критические события:
  - Баланс ниже порога
  - Серия убыточных сделок
  - Ошибки API DMarket
  - Превышение дневного лимита
- [ ] ✅ **Логи** сохраняются с ротацией (не переполняют диск)
- [ ] ✅ **Dashboard** для мониторинга (опционально)

#### Шаг 4: Резервное копирование

- [ ] ✅ Автоматический бэкап базы данных (ежедневно)
- [ ] ✅ Бэкап конфигурации `.env` (в безопасном месте)
- [ ] ✅ Бэкап логов торговли
- [ ] ✅ План восстановления при сбое

#### Шаг 5: Финальная проверка

- [ ] ✅ **Начальный баланс записан** для отслеживания результатов
- [ ] ✅ **Уведомления работают** (проверить тестовое сообщение)
- [ ] ✅ **Доступ к серверу** есть для экстренной остановки
- [ ] ✅ **Время начала** записано
- [ ] ✅ Прочитана документация [DEBUG_WORKFLOW.md](DEBUG_WORKFLOW.md)

### 🛑 Процедура экстренной остановки

Если что-то пошло не так, **немедленно** выполните:

#### Метод 1: Через Telegram (самый быстрый)

```
/stop_trading        # Остановить все активные сделки
/cancel_all_targets  # Отменить все таргеты
/withdraw_balance    # Вывести баланс (опционально)
```

#### Метод 2: Через сервер (если бот не отвечает)

```bash
# SSH на сервер
ssh user@your-server.com

# Найти процесс бота
ps aux | grep python

# Остановить процесс
kill -TERM <PID>  # Graceful shutdown
# или
kill -KILL <PID>  # Force kill (крайний случай)

# Для Docker
docker stop dmarket-bot
```

#### Метод 3: Переключить DRY_RUN обратно

```bash
# Отредактировать .env
nano .env

# Изменить
DRY_RUN=true  # Вернуть безопасный режим

# Перезапустить бота
docker-compose restart bot
# или
systemctl restart dmarket-bot
```

### 🔍 Что проверять ежедневно при реальной торговле

#### Утренний чек-лист (5 минут)

- [ ] Баланс на DMarket соответствует ожидаемому
- [ ] Нет критических ошибок в Sentry
- [ ] Бот активен и отвечает на команды
- [ ] Последние сделки были прибыльными
- [ ] Логи не показывают проблем с API

#### Вечерний чек-лист (10 минут)

- [ ] Просмотреть все сделки за день
- [ ] Проверить общую прибыль/убыток
- [ ] Проанализировать убыточные сделки
- [ ] Проверить использование лимитов
- [ ] Обновить стратегию если нужно

#### Еженедельный чек-лист (30 минут)

- [ ] Полный аудит всех сделок
- [ ] Проверка здоровья базы данных
- [ ] Обновление зависимостей (если есть патчи безопасности)
- [ ] Ротация логов
- [ ] Бэкап всех данных
- [ ] Анализ эффективности стратегий

### ⚡ Красные флаги - немедленно остановить торговлю!

Остановите бота **НЕМЕДЛЕННО** если:

1. 🚨 **Баланс резко упал** (более 10% за час)
2. 🚨 **5+ убыточных сделок подряд**
3. 🚨 **API DMarket возвращает ошибки** (429, 500, 503)
4. 🚨 **Необычно высокие цены** (возможный баг скрейпинга)
5. 🚨 **Бот покупает одни и те же предметы** (зацикливание)
6. 🚨 **Нет прибыльных сделок 24+ часа**
7. 🚨 **Sentry показывает критические ошибки**
8. 🚨 **Дневной лимит исчерпан раньше времени**

### 💡 Рекомендации по безопасности торговли

#### Начинайте с малого

```
День 1-3:   MAX_TRADE_VALUE=$10,  daily_LIMIT=$50
День 4-7:   MAX_TRADE_VALUE=$25,  daily_LIMIT=$150
День 8-14:  MAX_TRADE_VALUE=$50,  daily_LIMIT=$300
День 15+:   Постепенно увеличивайте на основе результатов
```

#### Диверсификация

- ✅ Торгуйте **разными играми** (CS:GO, CS2, Rust)
- ✅ Используйте **разные уровни** (boost, standard, medium)
- ✅ Комбинируйте **таргеты + прямые покупки**
- ✅ Не держите все яйца в одной корзине

#### Стратегия на первый месяц

```
Неделя 1: Только наблюдение (DRY_RUN=true)
Неделя 2: Минимальные лимиты, активное тестирование
Неделя 3: Умеренные лимиты, если результаты положительные
Неделя 4: Постепенное увеличение на основе ROI
```

#### Регулярное обновление

- 🔄 Проверяйте обновления бота **еженедельно**
- 🔄 Обновляйте безопасность зависимостей **немедленно**
- 🔄 Читайте [CHANGELOG.md](../CHANGELOG.md) перед обновлением
- 🔄 Тестируйте обновления в DRY_RUN **24 часа** перед production

### 📞 Поддержка и помощь

Если возникли проблемы:

1. **Проверьте логи**: `logs/dmarket_bot.log`
2. **Проверьте Sentry**: Ошибки и трейсы
3. **Создайте Issue**: [GitHub Issues](https://github.com/your-repo/issues)
4. **Экстренная помощь**: `support@your-domain.com`

**ПОМНИТЕ**: Лучше остановить торговлю и разобраться, чем потерять деньги!

---

## 🛡️ Общие принципы безопасности

### Принцип минимальных привилегий

- Предоставляйте минимально необходимые права доступа
- Используйте разные учетные записи для разработки и production
- Регулярно проверяйте и обновляйте права доступа

### Защита в глубину

- Используйте многоуровневую защиту
- Не полагайтесь на единственный механизм безопасности
- Применяйте шифрование на всех уровнях

---

## 🔑 Защита API ключей

### Хранение секретов

**✅ Правильно:**

```python
# Используйте переменные окружения
import os
from dotenv import load_dotenv

load_dotenv()

DMARKET_PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY")
DMARKET_SECRET_KEY = os.getenv("DMARKET_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

**❌ Неправильно:**

```python
# НЕ храните секреты в коде!
DMARKET_PUBLIC_KEY = "abc123def456"
DMARKET_SECRET_KEY = "secret_key_here"
```

### Файл .env

Создайте `.env` файл в корне проекта:

```env
# DMarket API
DMARKET_PUBLIC_KEY=your_public_key_here
DMARKET_SECRET_KEY=your_secret_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# База данных
DATABASE_URL=postgresql://user:password@localhost/dmarket_bot

# Redis
REDIS_URL=redis://localhost:6379/0
```

**Важно:** Добавьте `.env` в `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.*.local
```

### Шифрование API ключей в БД

Для хранения пользовательских API ключей используйте шифрование:

```python
from cryptography.fernet import Fernet
import base64
import os

class EncryptionManager:
    """Менеджер шифрования для API ключей."""

    def __init__(self):
        # Получить ключ шифрования из переменной окружения
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY не установлен")

        self.cipher = Fernet(encryption_key.encode())

    def encrypt_api_key(self, api_key: str) -> str:
        """Зашифровать API ключ."""
        encrypted = self.cipher.encrypt(api_key.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Расшифровать API ключ."""
        encrypted = base64.b64decode(encrypted_key.encode())
        return self.cipher.decrypt(encrypted).decode()
```

### Генерация ключа шифрования

```python
from cryptography.fernet import Fernet

# Сгенерировать новый ключ (только один раз!)
key = Fernet.generate_key()
print(f"ENCRYPTION_KEY={key.decode()}")
```

---

## 🗄️ Безопасность базы данных

### Параметризованные запросы

**✅ Правильно (SQLAlchemy):**

```python
from sqlalchemy import select

async def get_user(user_id: int):
    stmt = select(User).where(User.telegram_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

**❌ Неправильно (SQL инъекция):**

```python
# НЕ используйте форматирование строк для SQL!
query = f"SELECT * FROM users WHERE telegram_id = {user_id}"
```

### Безопасное подключение к БД

```python
# Используйте SSL для production
DATABASE_URL = "postgresql://user:password@localhost/db?sslmode=require"
```

### Регулярные бэкапы

```bash
#!/bin/bash
# Скрипт автоматического бэкапа БД

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# PostgreSQL бэкап
pg_dump dmarket_bot_prod > "$BACKUP_DIR/dmarket_bot_$DATE.sql"

# Шифрование бэкапа
gpg --encrypt --recipient admin@example.com "$BACKUP_DIR/dmarket_bot_$DATE.sql"

# Удаление незашифрованного бэкапа
rm "$BACKUP_DIR/dmarket_bot_$DATE.sql"

# Хранить только последние 30 дней
find $BACKUP_DIR -name "*.sql.gpg" -mtime +30 -delete
```

---

## 🤖 Безопасность Telegram бота

### Ограничение доступа

```python
from telegram import Update
from telegram.ext import ContextTypes

# Список разрешенных пользователей
ALLOWED_USERS = [123456789, 987654321]

async def restricted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Декоратор для ограничения доступа."""
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту")
        return False

    return True

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда только для администраторов."""
    if not await restricted(update, context):
        return

    # Выполнить команду
    await update.message.reply_text("✅ Команда выполнена")
```

### Валидация входных данных

```python
import re

async def create_target_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик создания таргета с валидацией."""

    # Получить цену от пользователя
    price_input = context.args[0] if context.args else None

    if not price_input:
        await update.message.reply_text("❌ Укажите цену")
        return

    # Валидация цены
    if not re.match(r'^\d+\.?\d{0,2}$', price_input):
        await update.message.reply_text("❌ Неверный формат цены. Используйте: 10.50")
        return

    price = float(price_input)

    # Проверка диапазона
    if not 0.01 <= price <= 10000:
        await update.message.reply_text("❌ Цена должна быть от $0.01 до $10,000")
        return

    # Продолжить создание таргета
    # ...
```

### Rate Limiting для команд

```python
from datetime import datetime, timedelta
from collections import defaultdict

class CommandRateLimiter:
    """Rate limiter для команд бота."""

    def __init__(self, max_calls: int = 10, time_window: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window  # секунд
        self.calls = defaultdict(list)

    async def is_allowed(self, user_id: int) -> bool:
        """Проверить, разрешен ли запрос."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.time_window)

        # Удалить старые записи
        self.calls[user_id] = [
            t for t in self.calls[user_id] if t > cutoff
        ]

        # Проверить лимит
        if len(self.calls[user_id]) >= self.max_calls:
            return False

        # Добавить новый вызов
        self.calls[user_id].append(now)
        return True

# Использование
rate_limiter = CommandRateLimiter(max_calls=5, time_window=60)

async def scanner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏱️ Слишком много запросов. Подождите минуту."
        )
        return

    # Выполнить команду
    # ...
```

---

## 📝 Обработка ошибок и логирование

### Безопасное логирование

**✅ Правильно:**

```python
import structlog

logger = structlog.get_logger(__name__)

async def process_payment(user_id: int, amount: float):
    logger.info(
        "processing_payment",
        user_id=user_id,
        amount=amount
    )
    # Не логировать чувствительные данные!
```

**❌ Неправильно:**

```python
# НЕ логировать API ключи, пароли, токены!
logger.info(f"API key: {api_key}")  # НЕПРАВИЛЬНО!
logger.info(f"Password: {password}")  # НЕПРАВИЛЬНО!
```

### Маскирование чувствительных данных

```python
def mask_api_key(api_key: str) -> str:
    """Маскировать API ключ для логирования."""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}***{api_key[-4:]}"

# Использование
logger.info(f"Using API key: {mask_api_key(api_key)}")
# Output: "Using API key: abcd***xyz9"
```

---

## 🎯 Лучшие практики

### 1. Обновление зависимостей

```bash
# Регулярно проверяйте уязвимости
pip-audit

# Обновляйте зависимости
pip install --upgrade -r requirements.txt

# Проверка безопасности с Safety
safety check
```

### 2. HTTPS для всех соединений

```python
# Всегда используйте HTTPS для API запросов
DMARKET_API_URL = "https://api.dmarket.com"  # ✅
# НЕ используйте HTTP:
# DMARKET_API_URL = "http://api.dmarket.com"  # ❌
```

### 3. Двухфакторная аутентификация (2FA)

Включите 2FA для всех важных сервисов:
- GitHub
- DMarket аккаунт
- Хостинг провайдер
- email

### 4. Мониторинг безопасности

```python
# Интеграция с Sentry для отслеживания ошибок
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=1.0,
    send_default_pii=False  # Не отправлять личные данные
)
```

### 5. Безопасность Docker

```dockerfile
# Используйте non-root пользователя
FROM python:3.11-slim

# Создать непривилегированного пользователя
RUN useradd -m -u 1000 botuser

# Установить зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Переключиться на непривилегированного пользователя
USER botuser

# Скопировать код
COPY --chown=botuser:botuser . .

CMD ["python", "-m", "src.main"]
```

### 6. Секреты в Docker

Используйте Docker secrets вместо переменных окружения:

```bash
# Создать secret
echo "my_secret_key" | docker secret create dmarket_secret_key -

# Использовать в docker-compose.yml
version: '3.8'
services:
  bot:
    image: dmarket-bot
    secrets:
      - dmarket_secret_key

secrets:
  dmarket_secret_key:
    external: true
```

---

## 🚨 Что делать при утечке секретов

### 1. Немедленные действия

1. **Отзовите скомпрометированные ключи** в панели DMarket
2. **Смените токен Telegram бота** через @BotFather
3. **Обновите пароли** ко всем связанным сервисам
4. **Проверьте логи** на подозрительную активность

### 2. Очистка Git истории

```bash
# Удалить файл из всей истории Git
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Принудительный push
git push origin --force --all
git push origin --force --tags
```

### 3. Уведомление

- Уведомите всех пользователей о возможной утечке
- Запросите смену паролей
- Проанализируйте причину утечки

---

## 📚 Дополнительные ресурсы

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Telegram Bot Security Guide](https://core.telegram.org/bots/security)
- [DMarket API Security](https://docs.dmarket.com/docs/security)

---

**Помните:** Безопасность - это не одноразовая задача, а непрерывный процесс!


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*