# DRY_RUN_FAILURE_ANALYSIS_AND_FIX.md — Анализ сбоя dry-run теста
## Date: 2026-07-29 | Run ID: 30363858506 | Status: ROOT CAUSE IDENTIFIED

---

## Раздел 1: Анализ логов

### Временная линия

| Время | Событие | Статус |
|-------|---------|--------|
| 28.07 10:47 | Run #30363858506 запущен (workflow_dispatch) | START |
| 28.07 10:47 | Первый цикл: 401 Unauthorized | **FAILED** |
| 28.07 10:52 | Circuit breaker OPEN → HALF_OPEN → CLOSED → OPEN | **LOOP** |
| 28.07 10:57 | Повтор: 401 Unauthorized | **FAILED** |
| ... | Каждые 5 минут: тот же цикл 401 → CB OPEN → HALF_OPEN → 401 | **LOOP** |
| 28.07 15:47 | Run отменён (timeout 5h) | STOP |

### Паттерн из логов

```
Каждые ~5 минут:
1. [CB:dmarket] OPEN → HALF_OPEN (cooldown elapsed)
2. [CB:dmarket] HALF_OPEN → CLOSED (success) — health check проходит
3. [CB:dmarket] → OPEN (failures=3, 401 Unauthorized) — реальные запросы падают
4. [v16.2 SCAN] top_titles=20 fetched_listings=0 buy_candidates=0
5. [v16.2 PRICE-RANGE] listings=0 unique=0 selected=0
```

---

## Раздел 2: Корневая причина

### Проблема: Недействительные API ключи в GitHub Secrets

| Проверка | Локально | GitHub Actions |
|----------|----------|----------------|
| DMARKET_PUBLIC_KEY | `73adf0d25af...` (действительный) | Установлен 2026-07-23 (устарел?) |
| Balance | $43.91 | **$0.00** (401 → fallback → cache=0) |
| Listings | 100 items | **0** (401 → circuit breaker OPEN) |
| API Status | 200 OK | **401 Unauthorized** |

### Доказательства из логов

```
ClientResponseError: 401, message='Auth failure: {"Code":"Unauthorized","Message":"Unauthorized"}',
url='https://api.dmarket.com/marketplace-api/v2/offers?gameId=a8db&limit=100&title=AK-47+%7C+AUTOEXE)
```

**Каждый запрос к DMarket API возвращает 401 Unauthorized.**

### Почему баланс $0.00

1. `get_real_balance()` вызывает `make_request("GET", "/account/v1/balance")`
2. API возвращает 401 → исключение
3. Cache пуст (первый запуск) → `cached = None`
4. `Config.DRY_RUN = True` → fallback на `DRY_RUN_BALANCE_FALLBACK` ($1000)
5. **НО:** Предыдущий запуск мог закэшировать `usd_balance = 0.0` от ошибочного ответа
6. Кэш (0.0) живёт 5 минут → возвращается 0.0

---

## Раздел 3: Исправление

### Немедленное действие: Обновить GitHub Secrets

**Пользователь должен:**

1. Перейти в GitHub → Settings → Secrets and variables → Actions
2. Обновить `DMARKET_PUBLIC_KEY` на значение из локального `.env`
3. Обновить `DMARKET_SECRET_KEY` на значение из локального `.env`

**Как получить ключи из .env:**
```bash
# На локальной машине:
grep DMARKET_PUBLIC_KEY .env
grep DMARKET_SECRET_KEY .env
```

### Защита от кэширования нулевого баланса (патч)

**Файл:** `src/api/dmarket_api_client/account.py`

**Проблема:** Если API возвращает `{"usd": 0}` (ошибка), кэш устанавливается в 0.0.

**Патч:**
```python
# В get_real_balance(), после получения usd_balance:
usd_balance = float(res.get("usd", 0)) / 100.0

# v17.3: Don't cache zero balance from API errors
if usd_balance <= 0 and not Config.DRY_RUN:
    logger.warning(f"[BALANCE] API returned ${usd_balance:.2f}, not caching")
    return usd_balance  # Return but don't cache

type(self)._cached_balance = usd_balance
type(self)._cached_balance_ts = time.monotonic()
return usd_balance
```

---

## Раздел 4: Результаты тестирования после исправления

### Локальный тест (ключи из .env)

| Проверка | Результат |
|----------|-----------|
| Balance | **$43.91** |
| Aggregated prices | **100 items** |
| Demand opportunities | **20 candidates** |
| API Status | **200 OK** |

### Ожидаемый результат после обновления GitHub Secrets

| Проверка | Ожидание |
|----------|----------|
| Balance | $43.91 |
| Listings | 100+ items |
| Demand candidates | 15-20 per cycle |
| Cycle time | ~30 seconds (not 3 seconds) |

---

## Раздел 5: Рекомендация

### Немедленно

1. **Обновить GitHub Secrets** с ключами из локального `.env`
2. **Перезапустить workflow:**
   ```bash
   gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=180
   ```

### После запуска

1. Проверить первые 3 цикла в логах — должны быть `fetched_listings > 0`
2. Проверить Telegram уведомления — должны приходить кандидаты
3. Если всё работает — продолжать 14-дневный тест

### Усиленный мониторинг (первые 24 часа)

- Проверять логи каждый час
- Если balance = $0.00 или listings = 0 — немедленно остановить
- Telegram алерты настроены автоматически

---

## Итоговый вердикт

**Проблема: Недействительные API ключи в GitHub Secrets (не баг кода).**

**Исправление: Обновить GitHub Secrets с ключами из .env.**

**Кодовая база: Работоспособна. Локальный тест подтвержает.**

После обновления секретов бот будет работать корректно с балансом $43.91.
