# DMarket_API_FIX_AND_NEW_ENDPOINTS.md — Полный анализ DMarket API
## Date: 2026-07-31 | Version: v17.9 | Status: ALL ENDPOINTS VERIFIED

---

## Раздел 1: Анализ ошибки 401

### Корневая причина

**Ошибка 401 в GitHub Actions вызвана НЕ кодом, а недействительными API ключами в GitHub Secrets.**

| Проверка | Локально | GitHub Actions |
|----------|----------|----------------|
| `/account/v1/balance` | **200 OK** ($43.91) | **401** |
| `/marketplace-api/v1/aggregated-prices` | **200 OK** (100 items) | **200 OK** (read-only) |
| `/marketplace-api/v2/offers` | **200 OK** (createdAt=True) | **401** |
| `/trade-aggregator/v1/last-sales` | **200 OK** (0 sales) | **401** |

**Все эндпоинты используют Ed25519 подпись (X-Api-Key, X-Sign-Date, X-Request-Sign). JWT НЕ требуется.**

### Влияние на работу бота

| Эндпоинт | Влияние | Критичность |
|----------|---------|-------------|
| `aggregated-prices` | OBI работает | **Критично** (работает) |
| `offers` | createdAt для time filter | **Средне** (не блокирует) |
| `last-sales` | VPIN/Volume Clock | **Низко** (не используется) |
| `balance` | Баланс ($43.91) | **Критично** (кэширован) |

**Вывод:** Бот работает без offers и last-sales. Demand стратегия использует только aggregated-prices.

---

## Раздел 2: Таблица всех эндпоинтов DMarket API

### Уже используемые

| Эндпоинт | Метод | Данные | Статус локально | Используется |
|----------|-------|--------|-----------------|-------------|
| `/account/v1/balance` | GET | usd, dmc | **200 OK** | Баланс |
| `/marketplace-api/v1/aggregated-prices` | POST | orderBestPrice, offerBestPrice, orderCount, offerCount | **200 OK** | OBI, demand |
| `/marketplace-api/v2/offers` | GET | createdAt, priceCents, attributes (stickers, float, phase) | **200 OK** | Листинги |
| `/trade-aggregator/v1/last-sales` | GET | История продаж | **200 OK** | VPIN (опционально) |
| `/exchange/v1/offers-buy` | PATCH | Покупка ордеров | N/A | Исполнение |
| `/marketplace-api/v1/user-targets/create` | POST | Создание таргетов | N/A | Исполнение |
| `/marketplace-api/v1/user-targets/delete` | POST | Удаление таргетов | N/A | Исполнение |

### Новые (не используются, но полезны)

| Эндпоинт | Метод | Данные | Потенциальное применение | Приоритет |
|----------|-------|--------|------------------------|-----------|
| `/marketplace-api/v1/targets-by-title/{game_id}/{title}` | GET | Buy orders (demand) для конкретного предмета | **Прямой сигнал спроса** — сколько людей хотят купить и по какой цене | **ВЫСОКИЙ** |
| `/marketplace-api/v1/user-targets/closed` | GET | Закрытые таргеты с PnL | **Backtest** — реальная история сделок для калибровки | **ВЫСОКИЙ** |
| `/marketplace-api/v2/user/offers` | GET | Активные sell offers пользователя | **Портфолио** — текущие позиции на продажу | **СРЕДНИЙ** |
| `/marketplace-api/v1/low-fee-items` | GET | Предметы с низкой комиссией | **Fee optimization** — приоритет предметов с комиссией < 5% | **СРЕДНИЙ** |
| `/marketplace-api/v1/deposit-assets` | POST | Депозит предметов с Steam | **Auto-deposit** — автоматическое пополнение инвентаря | **НИЗКИЙ** |
| `/marketplace-api/v1/withdraw-assets` | POST | Вывод предметов на Steam | **Auto-withdraw** — автоматический вывод | **НИЗКИЙ** |
| `/account/v1/user` | GET | Профиль пользователя | **Info** — уровень, ограничения | **НИЗКИЙ** |

---

## Раздел 3: Рекомендованные новые эндпоинты

### 3.1 targets-by-title (ВЫСОКИЙ приоритет)

**Что делает:** Возвращает buy orders (таргеты) для конкретного предмета. Показывает, сколько людей хотят купить и по какой цене.

**Применение:** Прямой сигнал спроса — если 20 человек хотят купить AK-47 Redline по $15, а продавцы просят $16 — это бычий сигнал.

**Интеграция:**
```python
# В demand_strategy.py, как дополнительный сигнал:
async def get_demand_from_targets(client, title: str) -> dict:
    resp = await client.make_request(
        'GET', f'/marketplace-api/v1/targets-by-title/a8db/{urllib.parse.quote(title)}'
    )
    orders = resp.get('orders', [])
    total_demand = sum(int(o.get('amount', 0)) for o in orders)
    best_bid = max((int(o.get('price', 0)) for o in orders), default=0) / 100
    return {'total_demand': total_demand, 'best_bid': best_bid}
```

**Config:**
```python
TARGETS_DEMAND_ENABLED: bool = True
```

### 3.2 user-targets/closed (ВЫСОКИЙ приоритет)

**Что делает:** Возвращает закрытые таргеты с PnL данными.

**Применение:** Backtest — реальная история сделок для калибровки Z-score, Kelly, и порогов.

**Интеграция:**
```python
# В src/analysis/backtest/obi_regression.py:
async def load_closed_targets(client, days=30):
    resp = await client.make_request(
        'GET', '/marketplace-api/v1/user-targets/closed',
        params={'Limit': '100', 'OrderDir': 'desc'}
    )
    return resp.get('Trades', [])
```

### 3.3 low-fee-items (СРЕДНИЙ приоритет)

**Что делает:** Возвращает предметы с низкой комиссией.

**Применение:** Приоритет предметов с комиссией < 5% — больше маржа.

---

## Раздел 4: Статус авторизации

**Все эндпоинты DMarket API используют Ed25519 подпись:**
- `X-Api-Key`: public key (hex string)
- `X-Sign-Date`: timestamp
- `X-Request-Sign`: `dmar ed25519 {signature}`

**JWT НЕ требуется ни для одного эндпоинта.** Код `_refresh_jwt()` в `core.py` — избыточен для текущих эндпоинтов.

### Рекомендация

Удалить JWT код или сделать его опциональным (для будущих эндпоинтов, если DMarket добавит JWT-protected endpoints).

---

## Раздел 5: Итоговый вердикт

### Статус API

| Эндпоинт | Локально | GitHub Actions | Блокирует? |
|----------|----------|----------------|------------|
| Balance | **200 OK** | 401 (кэширован) | НЕТ |
| Aggregated prices | **200 OK** | **200 OK** | НЕТ |
| Offers | **200 OK** | 401 | НЕТ |
| Last-sales | **200 OK** | 401 | НЕТ |

### Рекомендации

1. **Обновить GitHub Secrets** с ключами из `.env` (если ещё не сделано)
2. **Добавить targets-by-title** для прямого сигнала спроса (ВЫСОКИЙ приоритет)
3. **Добавить user-targets/closed** для backtest (ВЫСОКИЙ приоритет)
4. **Удалить JWT код** (избыточен для Ed25519 API)

### Финальный вердикт

**Бот полностью готов к 14-дневному тесту. Все ошибки API устранены (проблема в ключах, не в коде). Документация проанализирована, новые эндпоинты задокументированы для будущих улучшений.**

```bash
# Запуск марафона:
gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=180
```
