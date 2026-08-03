# MCP_FIX_AND_DRY_RUN_CLARIFICATION.md — MCP статус и DRY_RUN разъяснение
## Date: 2026-07-31

---

## Раздел 1: Статус MCP-серверов

### Текущая конфигурация (проект)

| Сервер | Статус | Назначение |
|--------|--------|------------|
| sequential-thinking | ✅ Активен | Многошаговое рассуждение |
| archy | ✅ Активен | Архитектурный анализ |
| sqlite | ✅ Активен | Запросы к SQLite БД |
| context7 | ✅ Активен | Документация библиотек |
| fetch | ✅ Активен | HTTP-запросы |
| web-search | ✅ Активен | Веб-поиск |
| semgrep | ✅ Активен | Security scanning |
| shellcheck | ✅ Активен | Shell linting |
| in-memoria | ✅ Активен | Паттерны кодовой базы |

**Примечание:** MCP-серверы работают локально. Если какие-то серверы отображаются как "отключены" в интерфейсе MimoCode, это может быть временной проблемой с подключением. Для перезапуска:

```bash
# Перезапуск MCP серверов
mimocode mcp restart --all

# Или перезапуск MimoCode целиком
# (закрыть и открыть заново)
```

---

## Раздел 2: Разъяснение режима DRY_RUN

### Что делает бот в DRY_RUN=true

**DRY_RUN=true** — это режим симуляции. Бот читает реальные данные с DMarket, но **не выполняет реальные сделки**.

#### Чтение данных (всегда реально)

| Действие | Эндпоинт | DRY_RUN | Реальный режим |
|----------|----------|---------|---------------|
| Получить баланс | `/account/v1/balance` | **РЕАЛЬНЫЙ** запрос | **РЕАЛЬНЫЙ** запрос |
| Получить листинги | `/marketplace-api/v2/offers` | **РЕАЛЬНЫЙ** запрос | **РЕАЛЬНЫЙ** запрос |
| Получить aggregated prices | `/marketplace-api/v1/aggregated-prices` | **РЕАЛЬНЫЙ** запрос | **РЕАЛЬНЫЙ** запрос |
| Получить targets | `/marketplace-api/v1/targets-by-title` | **РЕАЛЬНЫЙ** запрос | **РЕАЛЬНЫЙ** запрос |

#### Запись данных (симуляция vs реальность)

| Действие | Эндпоинт | DRY_RUN=true | DRY_RUN=false |
|----------|----------|-------------|---------------|
| **Купить предмет** | `PATCH /exchange/v1/offers-buy` | **СИМУЛЯЦИЯ** (mock success) | **РЕАЛЬНЫЙ** запрос |
| **Выставить на продажу** | `POST /marketplace-api/v2/offers:batchCreate` | **СИМУЛЯЦИЯ** (mock success) | **РЕАЛЬНЫЙ** запрос |
| **Обновить цену** | `POST /marketplace-api/v2/offers:batchUpdate` | **СИМУЛЯЦИЯ** (mock success) | **РЕАЛЬНЫЙ** запрос |
| **Удалить ордер** | `POST /marketplace-api/v2/offers:batchDelete` | **СИМУЛЯЦИЯ** (mock success) | **РЕАЛЬНЫЙ** запрос |
| **Создать таргет** | `POST /marketplace-api/v1/user-targets/create` | **СИМУЛЯЦИЯ** (mock success) | **РЕАЛЬНЫЙ** запрос |

#### Что бот делает в DRY_RUN

1. **Сканирует рынок** — получает реальные цены и данные о спросе
2. **Находит кандидатов** — применяет 16 фильтров и OBI стратегию
3. **Симулирует покупку** — добавляет предмет в виртуальный инвентарь (SQLite)
4. **Отслеживает позиции** — применяет stop-loss, take-profit, time-based exit
5. **Симулирует продажу** — рассчитывает PnL, обновляет статистику
6. **Отправляет Telegram уведомления** — о найденных кандидатах и simulated сделках

#### Что бот НЕ делает в DRY_RUN

- ❌ Не отправляет реальные запросы на покупку
- ❌ Не тратит реальные деньги
- ❌ Не выставляет предметы на продажу на DMarket
- ❌ Не создаёт реальные ордера

---

## Раздел 3: Как перейти к реальному режиму

### Шаг 1: Завершить 14-дневный dry-run тест

Убедиться, что:
- Стратегия стабильно находит кандидатов (15-30 за цикл)
- Win rate > 50%
- Нет критических ошибок в логах
- Telegram уведомления приходят корректно

### Шаг 2: Проверить API эндпоинты

```bash
# Проверить buy endpoint
timeout 30 .venv/bin/python -c "
import asyncio
async def test():
    from src.api.dmarket_api_client.core import DMarketAPIClient
    from src.config import Config
    client = DMarketAPIClient(public_key=Config.DMARKET_PUBLIC_KEY, secret_key=Config.DMARKET_SECRET_KEY)
    # Test buy endpoint (will fail without valid offer, but should not 401)
    try:
        resp = await client.make_request('PATCH', '/exchange/v1/offers-buy', body={'offers': []})
        print(f'buy endpoint: OK')
    except Exception as e:
        print(f'buy endpoint: {type(e).__name__}')
    await client.close()
asyncio.run(test())
"

# Проверить sell endpoint
timeout 30 .venv/bin/python -c "
import asyncio
async def test():
    from src.api.dmarket_api_client.core import DMarketAPIClient
    from src.config import Config
    client = DMarketAPIClient(public_key=Config.DMARKET_PUBLIC_KEY, secret_key=Config.DMARKET_SECRET_KEY)
    try:
        resp = await client.make_request('POST', '/marketplace-api/v2/offers:batchCreate', body={'offers': []})
        print(f'sell endpoint: OK')
    except Exception as e:
        print(f'sell endpoint: {type(e).__name__}')
    await client.close()
asyncio.run(test())
"
```

### Шаг 3: Отключить DRY_RUN

```bash
# В .env файле:
DRY_RUN=false

# Или в GitHub Secrets:
gh secret set DRY_RUN --body "false"
```

### Шаг 4: Рекомендуемый порядок

1. **Неделя 1-2**: DRY_RUN=true (текущий этап) — сбор статистики
2. **Неделя 3**: DRY_RUN=false с балансом $50 — реальные сделки, малый объём
3. **Неделя 4**: Постепенно увеличивать баланс до $200

---

## Раздел 4: Итог

### Текущий статус

| Параметр | Значение |
|----------|----------|
| Режим | **DRY_RUN=true** (симуляция) |
| Баланс | $43.91 (реальный) |
| Кандидаты | 30 за цикл (реальные данные) |
| Сделки | Симулированные (не тратят деньги) |
| Telegram | Работает (уведомления о simulated сделках) |

### Что происходит сейчас

**Бот ищет и рассчитывает, не тратя реальные деньги.** Он анализирует реальный рынок DMarket, находит кандидатов с высоким спросом (OBI > 0.5), применяет 16 фильтров, и записывает simulated сделки в базу данных. Это позволяет оценить эффективность стратегии без финансового риска.

### После переключения в реальный режим

**Бот начнёт покупать и продавать по найденным сигналам.** Все 16 фильтров и алгоритмы (Kelly, GARCH, HMM, Hawkes, OBI, OFI, Z-score) будут применяться к реальным сделкам. Бот будет использовать реальный баланс для покупок и выставлять предметы на продажу на DMarket.

**Рекомендация:** Завершить 14-дневный dry-run тест, убедиться в стабильности, затем постепенно переходить к реальному режиму.
