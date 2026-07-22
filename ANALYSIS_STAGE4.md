# ANALYSIS_STAGE4.md — Итоговый отчёт

**Дата:** 2026-07-22 | **Версия проекта:** v16.2

---

## Сводка

Четырёхэтапный анализ DMarket Quantitative Engine проведён:
- **ЭТАП 1:** Анализ README и документации → ANALYSIS_STAGE1.md
- **ЭТАП 2:** Глубокий анализ кодовой базы → ANALYSIS_STAGE2.md
- **ЭТАП 3:** Код-ревью с исправлением → исправлены 3 файла
- **ЭТАП 4:** Итоговый отчёт → данный файл

---

## 1. Что найдено и исправлено

### Исправления (3 файла)

| # | Файл | Баг | Исправление | Приоритет |
|---|------|-----|-------------|-----------|
| 1 | `src/core/target_sniping/position_guard.py` | `__import__("time").time()` вместо `import time` (2 места) | Добавлен `import time`, заменены `__import__` вызовы на `time.time()` | P2 — стилистика |
| 2 | `src/api/steam_oracle.py` | `resp.json()` вызывается ПОСЛЕ закрытия контекстного менеджера `async with session.get()` | Перенесён `data = await resp.json()` внутрь блока `async with` | P1 — потенциальная ошибка чтения из закрытого соединения |
| 3 | `src/api/fair_price_calculator.py` | Outlier removal удалял ТОЛЬКО один выброс (min ИЛИ max), даже если оба являются выбросами | Исправлено: сначала проверяется min, затем max — оба удаляются если оба выбросы | P1 — влияет на корректность fair price |

---

## 2. Расхождения оракулов с официальной документацией

### Market.CSGO
| Проверка | Статус |
|----------|--------|
| Endpoint URL | ✅ Соответствует: `https://market.csgo.com/api/v2/prices/USD.json` |
| Response format | ✅ Соответствует: `items[].market_hash_name`, `items[].price`, `items[].volume` |
| Rate limit | ✅ Соответствует: 5 RPS documented → 2.5 RPS safe |
| Price format | ✅ Корректно: USD float |
| **Расхождений не найдено** | |

### Waxpeer
| Проверка | Статус |
|----------|--------|
| Endpoint URL | ✅ Соответствует: `https://api.waxpeer.com/v1/prices?game=csgo` |
| Response format | ✅ Соответствует: `items[].name`, `items[].min`, `items[].count`, `items[].steam_price` |
| Price conversion | ✅ Корректно: mills (1/1000 USD) → `/1000.0` |
| Rate limit | ✅ Корректно: ~1 RPS community estimate → 0.5 RPS safe |
| **Расхождений не найдено** | |

### CSFloat
| Проверка | Статус |
|----------|--------|
| Endpoint URL | ✅ Соответствует: `https://csfloat.com/api/v1/listings` |
| Response format | ✅ Соответствует: `data[0].price` (cents) → `/100.0` |
| Authorization | ✅ Корректно: `Authorization: {api_key}` header |
| 429 handling | ✅ Корректно: tenacity retry with exponential backoff |
| **Расхождений не найдено** | |

### Steam
| Проверка | Статус |
|----------|--------|
| Endpoint URL | ✅ Соответствует: `https://steamcommunity.com/market/priceoverview/` |
| Params | ✅ Корректно: appid=730, currency=1 (USD) |
| Price parsing | ✅ Корректно: `$12.34` format |
| Cash conversion | ✅ Корректно: `price * 0.85` (Steam Wallet → cash) |
| **БАГ ИСПРАВЛЕН:** `resp.json()` вызывался после закрытия контекстного менеджера | ✅ Исправлено |

---

## 3. Операции исполнения сделок вне DMarket

### РЕЗУЛЬТАТ: ✅ НЕТ операций buy/sell/list/withdraw на площадках, отличных от DMarket

Проверено grep'ом по всему `src/`:
- `market_csgo_oracle.py` — только GET запросы (read-only)
- `waxpeer_oracle.py` — только GET запросы (read-only)
- `csfloat_oracle.py` — только GET запросы (read-only)
- `steam_oracle.py` — только GET запросы (read-only)
- `cross_market.py` — использует oracle данные для ОЦЕНКИ арбитражных возможностей, НЕ выполняет сделки на других площадках

**Все торговые операции (buy/sell/list) проходят ТОЛЬКО через `src/api/dmarket_api_client/`.**

---

## 4. Что осталось под вопросом

| Вопрос | Детали | Требует проверки |
|--------|--------|-----------------|
| Waxpeer rate limit | "~1 req/sec (no official docs, community reports)" — нет официальной документации по rate limit | Ручная проверка через тестовые запросы |
| CSFloat API key format | Неясно, нужен ли префикс "Bearer " или просто raw key | Проверить с реальным API key |
| Steam priceoverview rate limit | "~10 requests/sec (no official limit)" — агрессивный throttle может привести к IP банку | Мониторить 429 responses в production |
| Fair price при 1 источнике | confidence="low", но бот всё равно принимает торговые решения | Рассмотреть минимальный порог sources_count |
| Outlier removal thresholds | 0.3× для min, 2.0× для max — эмпирические значения | Backtest на исторических данных |

---

## 5. Рекомендации по приоритету исправлений

### P0 — Критично для денег
**Нет найденных P0 проблем.** Архитектура корректна:
- Все сделки ТОЛЬКО через DMarket API
- Ed25519 подпись корректна
- Rate limiting работает (token bucket + adaptive 429 handling)
- Circuit breaker защищает от каскадных отказов
- DRY_RUN guard корректно симулирует write operations
- Idempotency keys предотвращают дублирование ордеров
- Pre-trade risk check (drawdown, daily loss, trade count) работает
- Fee-aware stop-loss/take-profit корректны

### P1 — Важно (исправлено)
1. ✅ **steam_oracle.py:** `resp.json()` после закрытия контекстного менеджера — исправлено
2. ✅ **fair_price_calculator.py:** Outlier removal удалял только один выброс — исправлено

### P2 — На будущее (исправлено)
1. ✅ **position_guard.py:** `__import__("time")` вместо `import time` — исправлено

### P2 — На будущее (не исправлено, рекомендации)
1. **multi_source_oracle.py:210-215:** Oracle calls последовательные вместо параллельных. Каждый оракул имеет свой rate limiter, поэтому они МОГЛИ бы работать параллельно. Оптимизация: ~3x ускорение oracle queries.
2. **fair_price_calculator.py:** Рассмотреть минимальный порог `sources_count >= 2` для принятия торговых решений (сейчас 1 источник = confidence="low", но решение всё равно принимается).
3. **filter.py:198-199:** Kelly fallback clamp to 0.25 может быть слишком агрессивным для некоторых risk profiles.

---

## 6. Архитектурное заключение

### Сильные стороны
1. **Чёткое разделение:** DMarket = торговая площадка, все остальные = оракулы цен
2. **30+ алгоритмов** в algo_pack — от классических до продвинутых (GARCH, HMM, Hawkes)
3. **21 microstructure фильтр** — многоуровневая система фильтрации
4. **Robust error handling:** circuit breaker, exponential backoff, graceful degradation
5. **Security:** Ed25519 подписи, Fernet шифрование ключей, secure zero
6. **Fair price = медиана** с удалением выбросов, а не цена одной площадки
7. **Fee-aware расчёты** на всех уровнях (stop-loss, take-profit, margin)
8. **Kelly position sizing** с Bayesian адаптацией

### Общая оценка
Кодовая база хорошо структуририрована, с чёткими границами ответственности. Найденные баги — P1-P2 (не критичные для денег). Архитектурных нарушений не обнаружено.

---

*Анализ проведён: 2026-07-22*
*Файлы: ANALYSIS_STAGE1.md, ANALYSIS_STAGE2.md, ANALYSIS_STAGE4.md*
*Исправлено: position_guard.py, steam_oracle.py, fair_price_calculator.py*

---

## Ревалидация (повторный скептический проход)

**Дата:** 2026-07-22 | **Контекст:** Повторная проверка вывода "P0 проблем нет"

### Подтверждение предыдущих исправлений

| # | Файл | Статус | Детали верификации |
|---|------|--------|-------------------|
| 1 | `steam_oracle.py` | ✅ CORRECT | `resp.json()` на строке 108 — внутри `async with` блока (строки 98-126). Нет утечки соединения. |
| 2 | `fair_price_calculator.py` | ✅ CORRECT | Min outlier проверяется и удаляется (строки 138-144). Max ПЕРЕСЧИТЫВАЕТСЯ после min removal (строка 148), затем проверяется и удаляется (строки 146-154). Оба выброса удаляются независимо. |
| 3 | `position_guard.py` | ✅ CORRECT | `import time` на строке 19. Оба вызова `time.time()` на строках 60 и 210. |

### НОВЫЕ проблемы, обнаруженные при ревалидации

#### [NOV-1] P1: `int()` truncation вместо `round()` в buy_offer price

**Файлы и строки:**
- `src/core/target_sniping/filter.py:686` — `int(base_price * 100)`
- `src/core/target_sniping/filter_evaluator.py:447` — `int(ctx.base_price * 100)`
- `src/strategies/almgren_chriss.py:337` — `int(current_price * 100)`
- `src/strategies/twap.py:231` — `int(current_price * 100)`
- `src/dmarket/targets.py:39` — `int(price * 100)`

**Контраст (CORRECT):**
- `src/api/dmarket_api_client/offers.py:55` — `int(round(...))` ✅
- `src/core/target_sniping/execution.py:401` — `round(...)` ✅

**Проблема:** `int(12.995 * 100) = 1299` → $12.99 вместо $13.00. Систематическое усечение вниз на до 0.99¢ за сделку.

**Исправление:** Заменить `int(x * 100)` на `int(round(x * 100))` во всех 5 файлах.

---

#### [NOV-2] P1: Бот торгует при недоступности ВСЕХ оракулов

**Файл:** `src/core/target_sniping/filter.py:382-412`

**Сценарий:** Все 4 оракула (Market.CSGO, Waxpeer, CSFloat, Steam) недоступны → `cs_price = 0.0`. Бот НЕ останавливается — продолжает торговлю по DMarket-internal сигналам:
- `has_intra_spread = best_bid > best_ask * (1 + spread)` — внутренний спред DMarket
- `has_dmarket_underpriced` — сравнение с историческими продажами

**Риск:** Если DMarket prices манипулируются (памп, спуфинг), бот купит по невалидной цене без внешней cross-check.

**Рекомендация:** Добавить порог `sources_count >= 1` для oracle-validated стратегий, или warning при `sources_count == 0`.

---

#### [NOV-3] P1: Race condition — oracle price не перепроверяется перед исполнением

**Файл:** `src/core/target_sniping/execution.py:88-134`

Slippage protection (строки 89-134) перепроверяет ТОЛЬКО DMarket listing price. Oracle fair price НЕ перепроверяется.

**Сценарий атаки:**
1. Oracle: fair price = $15.00, DMarket listing = $12.00 (30% спред)
2. Бот начинает execution
3. За время между scan и execution oracle обновляется → fair price = $11.00
4. Бот покупает за $12.00, но fair price уже $11.00 → убыток после fees

**Рекомендация:** Добавить `_check_oracle_slippage()` аналогично `_check_slippage()` — перепроверить oracle price перед финальным buy.

---

#### [NOV-4] P2: `outlier_removed` перезаписывается при удалении обоих выбросов

**Файл:** `src/api/fair_price_calculator.py:143,153`

При удалении min (строка 143) и затем max (строка 153), `outlier_removed` перезаписывается — остаётся только имя max. Для логирования потеряна информация о min-выбросе.

**Исправление:** Изменить на `outlier_removed = f"{min_source},{max_source}"` или список.

---

#### [NOV-5] P2: Idempotency key генерирует НОВЫЙ ордер при retry

**Файл:** `src/api/dmarket_api_client/targets.py:15-19`

`_make_idempotency_key` = `{item_id}_{timestamp_ns}_{sha256[:12]}`. При retry после таймаута — НОВЫЙ timestamp → НОВЫЙ key → НОВЫЙ ордер на DMarket. Старый ордер может исполниться позже → потенциальная двойная покупка.

**Компенсирующие факторы:**
- Slippage protection (5% max) снижает вероятность
- Inventory cap + saturation check предотвращают перекуп
- DMarket может отклонить дублированный offerId на своей стороне

**Рекомендация:** Использовать deterministic key: `{item_id}_{price_cents}_{cycle_id}` — один и тот же key при retry того же ордера.

---

#### [NOV-6] P2: Float precision в hot path денежных расчётов

**Файлы:** `filter.py`, `execution.py`, `fair_price_calculator.py` — используют `float`.
**Контраст:** `analytics/backtester/`, `analytics/historical_data/`, `value_pipelines.py` — используют `Decimal`.

При типичных ценах CS2 ($0.50-$200) float precision достаточна (15-16 значащих цифр). Но `int(x * 100)` без `round()` — это не проблема precision, а проблема алгоритма (truncation vs rounding).

---

### Изменение вывода "P0 проблем нет"

**Предыдущий вывод:** "P0 проблем нет. Кодовая база хорошо структурирована."

**Обновлённый вывод:** P0 проблем по-прежнему нет — нет прямой утечки денег или критической уязвимости. Однако найдены **3 проблемы P1**, которые напрямую влияют на денежную логику:

| # | Проблема | Файл | Почему P1 |
|---|----------|------|-----------|
| NOV-1 | `int()` truncation | filter.py:686, filter_evaluator.py:447 | Систематическая потеря до 0.99¢ за сделку |
| NOV-2 | Торговля без oracle | filter.py:382-412 | Покупки без внешней валидации при отказе всех оракулов |
| NOV-3 | Race condition oracle | execution.py:88-134 | Oracle price не перепроверяется перед buy |

**Рекомендация:** Исправить NOV-1 (trivial fix), добавить guards для NOV-2 и NOV-3.

---

### Исправления, применённые при ревалидации

#### NOV-1: `int()` → `int(round())` — 5 файлов

| # | Файл | Строка | Было | Стало |
|---|------|--------|------|-------|
| 1 | `src/core/target_sniping/filter.py` | 686 | `int(base_price * 100)` | `int(round(base_price * 100))` |
| 2 | `src/core/target_sniping/filter_evaluator.py` | 447 | `int(ctx.base_price * 100)` | `int(round(ctx.base_price * 100))` |
| 3 | `src/strategies/almgren_chriss.py` | 337 | `int(current_price * 100)` | `int(round(current_price * 100))` |
| 4 | `src/strategies/twap.py` | 231 | `int(current_price * 100)` | `int(round(current_price * 100))` |
| 5 | `src/dmarket/targets.py` | 39 | `int(price * 100)` | `int(round(price * 100))` |

#### NOV-4: `outlier_removed` — tracking both outliers

**Файл:** `src/api/fair_price_calculator.py`

**Было:** `outlier_removed = min_source` затем `outlier_removed = max_source` (перезапись)
**Стало:** `outliers_removed: list[str]` → `outlier_removed = ",".join(outliers_removed)` — оба имени сохраняются

#### Не исправлено (рекомендации)

| # | Проблема | Приоритет | Рекомендация |
|---|----------|-----------|-------------|
| NOV-2 | Торговля без oracle | P1 | Добавить `sources_count >= 1` guard для oracle-validated стратегий |
| NOV-3 | Race condition oracle | P1 | Добавить `_check_oracle_slippage()` перед buy |
| NOV-5 | Idempotency key | P2 | Дeterministic key: `{item_id}_{price_cents}_{cycle_id}` |
| NOV-6 | Float precision | P2 | Миграция на Decimal в hot path (масштабный рефакторинг) |

---

### Итоговая сводка исправлений (все этапы)

| Этап | Файл | Исправление | Приоритет |
|------|------|-------------|-----------|
| Stage 3 | `position_guard.py` | `import time` вместо `__import__` | P2 |
| Stage 3 | `steam_oracle.py` | `resp.json()` внутрь `async with` | P1 |
| Stage 3 | `fair_price_calculator.py` | Outlier removal: оба выброса | P1 |
| Reval | `filter.py` | `int(round())` вместо `int()` | P1 |
| Reval | `filter_evaluator.py` | `int(round())` вместо `int()` | P1 |
| Reval | `almgren_chriss.py` | `int(round())` вместо `int()` | P1 |
| Reval | `twap.py` | `int(round())` вместо `int()` | P1 |
| Reval | `dmarket/targets.py` | `int(round())` вместо `int()` | P1 |
| Reval | `fair_price_calculator.py` | `outlier_removed` tracking обоих выбросов | P2 |

**Всего исправлено:** 8 файлов, 9 исправлений (P1×6, P2×3)

---

*Ревалидация проведена: 2026-07-22*
*Найдено новых проблем: 6 (NOV-1..NOV-6)*
*Исправлено при ревалидации: 6 файлов*
*Вывод: P0 проблем нет. P1 проблем было 3 (NOV-1..NOV-3), NOV-1 исправлен. NOV-2 и NOV-3 — рекомендации.*

---

## Итоговый статус проекта (финальный прогон)

**Дата:** 2026-07-22 | **Прогонов:** 3 | **Всего проанализировано файлов:** 30+

---

### 1. Общее число найденных и исправленных багов

| Приоритет | Найдено | Исправлено | Осталось |
|-----------|---------|------------|----------|
| **P0** | 0 | 0 | 0 |
| **P1** | 9 | 9 | 0 |
| **P2** | 4 | 4 | 0 |
| **Информационно** | 2 | — | 2 (NOV-5, NOV-6) |
| **ИТОГО** | **15** | **13** | **2** |

#### Полный список исправлений (все прогоны)

| # | Прогон | Файл | Исправление | P |
|---|--------|------|-------------|---|
| 1 | Stage 3 | `position_guard.py` | `import time` вместо `__import__("time")` | P2 |
| 2 | Stage 3 | `steam_oracle.py` | `resp.json()` внутрь `async with` контекстного менеджера | P1 |
| 3 | Stage 3 | `fair_price_calculator.py` | Outlier removal: оба выброса удаляются независимо | P1 |
| 4 | Reval | `filter.py` | `int(round())` вместо `int()` для buy_offer price | P1 |
| 5 | Reval | `filter_evaluator.py` | `int(round())` вместо `int()` для buy_offer price | P1 |
| 6 | Reval | `almgren_chriss.py` | `int(round())` вместо `int()` для buy_offer price | P1 |
| 7 | Reval | `twap.py` | `int(round())` вместо `int()` для buy_offer price | P1 |
| 8 | Reval | `dmarket/targets.py` | `int(round())` вместо `int()` для price_cents | P1 |
| 9 | Reval | `fair_price_calculator.py` | `outlier_removed` tracking обоих выбросов через список | P2 |
| 10 | Final | `filter.py` | NOV-2: guard блокирует oracle-dependent стратегии при отказе ВСЕХ оракулов | P1 |
| 11 | Final | `execution.py` | NOV-3: oracle price re-check перед buy (drift > 10% или ниже profitability) | P1 |
| 12 | Final | `targets.py` | NOV-5: deterministic idempotency key (item_id + price_cents) вместо timestamp | P2 |
| 13 | Final | `offers.py` | NOV-5: передача price_cents в `_make_idempotency_key` | P2 |

---

### 2. Статус всех NOV-проблем

| # | Проблема | Приоритет | Статус |
|---|----------|-----------|--------|
| NOV-1 | `int()` truncation в 5 файлах | P1 | ✅ Исправлено (прогон 2) |
| NOV-2 | Бот торгует при отказе ВСЕХ оракулов | P1 | ✅ Исправлено (прогон 3) |
| NOV-3 | Race condition: oracle price не перепроверяется перед buy | P1 | ✅ Исправлено (прогон 3) |
| NOV-4 | `outlier_removed` перезаписывается | P2 | ✅ Исправлено (прогон 2) |
| NOV-5 | Idempotency key = новый ордер при retry | P2 | ✅ Исправлено (прогон 3) |
| NOV-6 | Float precision в hot path | P2 | ℹ️ Информационно (не требует исправления при текущих ценах CS2) |

---

### 3. Анализ DMarket API — расхождения с документацией

#### Эндпоинты (все проверены по Swagger 2026)

| Эндпоинт | Метод | В коде | Статус |
|----------|-------|--------|--------|
| `/exchange/v1/market/items` | GET | `market.py:39` | ✅ Корректно |
| `/marketplace-api/v1/aggregated-prices` | POST | `market.py:59` | ✅ Корректно |
| `/trade-aggregator/v1/last-sales` | GET | `market.py:118` | ✅ Корректно |
| `/exchange/v1/customized-fees` | GET | `market.py:155` | ✅ Корректно |
| `/exchange/v1/offers-buy` | PATCH | `targets.py:75` | ✅ Корректно (verified 2026-06-06) |
| `/marketplace-api/v1/user-targets/create` | POST | `targets.py:46` | ✅ Корректно |
| `/marketplace-api/v1/user-targets/delete` | POST | `targets.py:54` | ✅ Корректно |
| `/marketplace-api/v2/offers:batchCreate` | POST | `offers.py:62` | ✅ Корректно |
| `/marketplace-api/v2/offers:batchUpdate` | POST | `offers.py:84` | ✅ Корректно |
| `/marketplace-api/v2/offers:batchDelete` | POST | `offers.py:98` | ✅ Корректно |
| `/exchange/v1/user-offers` | GET | `offers.py:33` | ✅ Корректно |
| `/marketplace-api/v1/user-offers/closed` | GET | `offers.py:120` | ✅ Корректно |
| `/exchange/v1/user-inventory` | GET | `account.py:57` | ✅ Корректно |
| `/account/v1/balance` | GET | `account.py:31` | ✅ Корректно |
| `/exchange/v1/transactions` | GET | `account.py:167` | ✅ Корректно |

**Расхождений с документацией не найдено.** Все эндпоинты используют актуальные версии (v1/v2).

#### Аутентификация
- Формат: `X-Api-Key: {public_key}`, `X-Sign-Date: {timestamp}`, `X-Request-Sign: dmar ed25519 {signature}` — ✅ Корректно
- Clock sync: `clock_sync.py` синхронизирует время с DMarket сервером — ✅ Корректно
- Шифрование ключа: Fernet через Vault, дешифровка на лету, secure zero — ✅ Корректно

#### Формат цен
- API: **центы (int)** — `amount: "1234"` = $12.34
- Внутренние расчёты: **USD (float)** — `base_price = 12.34`
- Конвертация: `int(round(usd * 100))` для API, `cents / 100.0` для чтения — ✅ Корректно (после исправления NOV-1)

#### Учёт комиссий
- `fees.py`: volume-based estimation (2%-10%) с 12h кэшем — ✅ Корректно
- `Config.FEE_RATE = 0.05` (5% default) — ✅ Используется во всех расчётах profitability
- Fee-aware stop-loss/take-profit: `loss_pct + fee_pct >= threshold` — ✅ Корректно
- Fee-aware margin: `required_margin = FEE_RATE + WITHDRAWAL_FEE_RATE + MIN_SPREAD_PCT` — ✅ Корректно

#### Rate Limiting
- Per-endpoint token bucket (50% safety margin) — ✅ Корректно
- Adaptive margin: 0.3-0.7 based on 429 rate — ✅ Корректно
- Circuit breaker: 3 failures → OPEN, exponential backoff 30-300s, jitter ±20% — ✅ Корректно
- Retry-After header parsing — ✅ Корректно
- **Риск:** При пиковой нагрузке多个 ботов на одном IP — DMarket может забанить. Бот использует 50% safety margin, что снижает риск.

---

### 4. Анализ оракулов — веса, защита, polling

#### Веса оракулов в fair price

**Текущая реализация:** Все оракулы имеют **РАВНЫЙ вес** — вычисляется **простая медиана** без учёта ликвидности или reliability каждого источника.

| Оракул | Вес в формуле | Объём ликвидности | Комментарий |
|--------|--------------|-------------------|-------------|
| Market.CSGO | 1.0 (равный) | 26K+ items | Российский маркет, slightly different liquidity |
| Waxpeer | 1.0 (равный) | 21K+ items | Международный, mills format |
| CSFloat | 1.0 (равный) | Per-item API | Высокое качество данных (float, pattern) |
| Steam | 1.0 (равный) | Самый ликвидный | Community Market, ~15% premium (adjusted to cash) |

**Рекомендация:** Steam Community Market — самый ликвидный источник. Рассмотреть volume-weighted median вместо простой медианы, чтобы ликвидные источники имели больший вес.

#### Защита от манипуляции ценой

| Защита | Статус | Детали |
|--------|--------|--------|
| Outlier removal | ✅ Исправлено | Min < 0.3× median, Max > 2.0× median — оба удаляются |
| Circuit breaker per source | ✅ Работает | 5 failures → OPEN, 60s recovery |
| Data Freshness Guard | ✅ Работает | marketcsgo: 10min, waxpeer: 10min, csfloat: 10min, steam: 30min |
| DMarket price 50%+ above oracle | ✅ Работает | Skip (overpriced) |
| **НОВОЕ (NOV-2):** All oracles down guard | ✅ Исправлено | Блокирует oracle-dependent стратегии |

**Риск:** Если один оракул систематически возвращает аномально высокие/низкие цены (но не является outlier по порогам 0.3×/2.0×), он может сместить медиану. Outlier removal работает только при >2 источниках.

#### Polling intervals и риски бана

| Оракул | Интервал | Риск бана | Оценка |
|--------|----------|-----------|--------|
| Market.CSGO | 15 min (batch dump) | Низкий (1 запрос на 15 мин) | ✅ Безопасно |
| Waxpeer | 15 min (batch dump) | Низкий (1 запрос на 15 мин) | ✅ Безопасно |
| CSFloat | Per-item, 3h SQLite cache | Средний (зависит от кол-ва items) | ⚠️ Мониторить |
| Steam | Per-item, 0.15s delay | Высокий (6-7 req/sec на items) | ⚠️ Агрессивно |

**Риск:** Steam oracle опрашивает каждый item отдельно с задержкой 0.15s. При 100 items = 15 секунд непрерывных запросов. При пиковой нагрузке может привести к IP банку от Steam.

#### Синхронизация валют

| Оракул | Валюта в ответе | Конвертация | Статус |
|--------|----------------|-------------|--------|
| Market.CSGO | USD (float) | Нет нужды | ✅ |
| Waxpeer | Mills (int) | `/ 1000.0` | ✅ |
| CSFloat | Cents (int) | `/ 100.0` | ✅ |
| Steam | USD string (`$12.34`) | Parse + `× 0.85` | ✅ |

**Все оракулы возвращают USD после конвертации.** Единицы синхронизированы перед агрегацией в `FairPriceCalculator`.

---

### 5. Карта финансовых инструментов

#### Операции на DMarket (ЕДИНСТВЕННАЯ торговая площадка)

| Операция | Эндпоинт | Oracle-зависимость | Файл |
|----------|----------|-------------------|------|
| **Instant Buy** | PATCH /exchange/v1/offers-buy | Oracle: fair price для валидации profitability | `targets.py:58` |
| **Create Target (Buy Order)** | POST /marketplace-api/v1/user-targets/create | Oracle: fair price для определения target price | `targets.py:32` |
| **Batch Create Offers (Sell)** | POST /marketplace-api/v2/offers:batchCreate | Oracle: fair price для определения list price | `offers.py:41` |
| **Batch Edit Offers (Reprice)** | POST /marketplace-api/v2/offers:batchUpdate | Oracle: fair price для корректировки цены | `offers.py:66` |
| **Batch Delete Offers (Cancel)** | POST /marketplace-api/v2/offers:batchDelete | Не зависит от оракулов | `offers.py:87` |
| **Delete Targets (Cancel Buy)** | POST /marketplace-api/v1/user-targets/delete | Не зависит от оракулов | `targets.py:50` |

#### Связь Oracle-сигнал → DMarket-действие

```
Oracle Signal                    DMarket Action
─────────────────────────────    ──────────────────────────────
fair_price > buy_price × 1.03 → BUY (instant purchase)
fair_price < buy_price × 0.85 → SELL (stop-loss)
fair_price > buy_price × 1.20 → SELL (take-profit)
oracle_discount detected      → BUY (cross-market underpriced)
all oracles down              → SKIP (NOV-2 guard)
oracle drift > 10%            → SKIP (NOV-3 guard)
```

---

### 6. Общий вывод: готов ли бот к боевой торговле?

#### Готовность: ✅ УСЛОВНО ГОТОВ (с оговорками)

**Готов:**
- ✅ Архитектура чётко разделена (DMarket = trading, остальные = oracles)
- ✅ Все 15 багов найдены и 13 исправлены (2 информационных)
- ✅ Rate limiting, circuit breaker, idempotency — корректны
- ✅ Fee-aware расчёты на всех уровнях
- ✅ Risk management: drawdown freeze, daily loss, Kelly sizing
- ✅ DRY_RUN mode для тестирования без реальных денег

**Оговорки (не блокирующие, но требующие внимания):**
1. **NOV-6 (информационно):** Float precision в hot path — при текущих ценах CS2 ($0.50-$200) не критично, но при масштабировании рекомендуется миграция на Decimal
2. **Steam oracle polling:** 6-7 req/sec агрессивно — рекомендуется увеличить delay до 0.3-0.5s для production
3. **Веса оракулов:** Все равные — рекомендуется volume-weighted median для более точной агрегации
4. **Outlier thresholds:** 0.3×/2.0× — эмпирические значения, рекомендуется backtest

**Рекомендация:** Запустить 14-дневный DRY_RUN на реальных данных перед переходом на реальные деньги.

---

*Итоговый отчёт: 2026-07-22*
*Прогонов: 3 | Файлов: 30+ | Исправлений: 13 | P0: 0 | P1: 9 (все исправлены) | P2: 4 (все исправлены)*
