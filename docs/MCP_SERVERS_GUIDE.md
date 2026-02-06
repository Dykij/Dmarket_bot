# MCP Servers Guide

Руководство по Model Context Protocol (MCP) серверам в DMarket Telegram Bot.

## Обзор

MCP позволяет AI-агентам взаимодействовать с внешними сервисами через стандартизированный протокол.

## Настроенные серверы

### Основные

| Сервер | Назначение | Конфигурация |
|--------|------------|--------------|
| **github** | GitHub API для репозитория | `GITHUB_TOKEN` |
| **postgres** | PostgreSQL база данных | `DATABASE_URL` |
| **sqlite** | SQLite для разработки | Путь к файлу |
| **filesystem** | Доступ к файлам проекта | Локальные пути |

### AI/Memory

| Сервер | Назначение | Конфигурация |
|--------|------------|--------------|
| **supermemory** | Персистентная память | `SUPERMEMORY_API_KEY` |
| **memory** | Локальная память сессии | Встроенный |
| **sequential-thinking** | Улучшенное рассуждение | Встроенный |

### Trading

| Сервер | Назначение | Конфигурация |
|--------|------------|--------------|
| **dmarket-bot** | Инструменты DMarket (баланс, маркет, арбитраж, таргеты) | `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY` |
| **waxpeer-mcp** | Инструменты Waxpeer P2P и кросс-платформенный арбитраж | `WAXPEER_API_KEY` |
| **hummingbot** | AI-трейдинг автоматизация | `HUMMINGBOT_API_KEY` |
| **redis** | Кэш цен и rate limiting | `REDIS_URL` |

### Utilities

| Сервер | Назначение | Конфигурация |
|--------|------------|--------------|
| **context7** | Документация библиотек | Встроенный |
| **fetch** | HTTP запросы | Встроенный |

---

## SuperMemory

### Возможности
- Персистентная память между сессиями
- Запоминание предпочтений пользователей
- Хранение истории сделок
- Контекст для AI-рекомендаций

### Использование

```python
from src.utils.supermemory_client import get_supermemory_client

client = get_supermemory_client()

# Запомнить предпочтение
await client.remember_preference(
    user_id=123456,
    preference_type="game",
    value="csgo"
)

# Запомнить сделку
await client.remember_trade(
    user_id=123456,
    item_name="AK-47 | Redline",
    game="csgo",
    action="buy",
    price=12.50,
    profit=15.3
)

# Получить контекст для AI
context = await client.get_user_context(123456)
```

### Конфигурация

```bash
# .env
SUPERMEMORY_API_KEY=sm_your_key_here
SUPERMEMORY_ENABLED=true
```

---

## Redis MCP

### Возможности
- Быстрый кэш рыночных цен
- Rate limiting для API
- Session storage

### Конфигурация

```bash
# .env
REDIS_URL=redis://localhost:6379/0
```

---

## Hummingbot MCP

### Возможности
- AI-driven торговая автоматизация
- Арбитражные стратегии
- Интеграция с биржами

### Конфигурация

```bash
# .env
HUMMINGBOT_API_KEY=your_key
HUMMINGBOT_ENABLED=false  # ОСТОРОЖНО: может выполнять реальные сделки!
```

> [!CAUTION]
> Включайте `HUMMINGBOT_ENABLED=true` только после тщательного тестирования!

---

## Добавление нового MCP сервера

1. Добавить в `.mcp.json`:

```json
{
  "servers": {
    "new_server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@package/mcp-server"],
      "env": {
        "API_KEY": "${NEW_SERVER_API_KEY}"
      },
      "description": "Description of the server"
    }
  }
}
```

2. Добавить переменные в `.env.example`

3. Документировать в этом файле

---

## Ссылки

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [SuperMemory](https://supermemory.ai/)
- [Hummingbot](https://hummingbot.org/)
