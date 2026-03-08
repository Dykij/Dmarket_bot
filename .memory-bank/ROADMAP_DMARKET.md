# 💰 ROADMAP DMARKET — Торговая Бригада
> Дата: 2026-03-05 | ToS Audit: ✅ PASSED | DRY_RUN: True

---

## ⚖️ ToS Compliance Notice
Все улучшения в этом роадмапе работают **ИСКЛЮЧИТЕЛЬНО** через официальный DMarket API.  
Запрещённые методы (браузерная автоматизация, Steam Market scraping, обход rate limits) **НЕ ИСПОЛЬЗУЮТСЯ**.

---

## 🔴 Приоритет: КРИТИЧЕСКИЙ

### 1. Robust Async Rate Limiter
**Файл:** `src/utils/api_client.py` (строки 93-106)  
**Проблема:** Наивный `_throttle()` с одним `asyncio.Lock` — не поддерживает burst, не разделяет read/write.  
**Решение:** `aiolimiter.AsyncLimiter` — Token Bucket с burst support.  
- Read operations: 5 RPS (burst up to 5)  
- Write operations: 2 RPS (burst up to 2)  
- Logging при каждом throttle event  
**Зависимость:** `pip install aiolimiter`  
**Статус:** 🟡 Запланировано

### 2. Pydantic Response Validators
**Файл:** `src/models.py` (НОВЫЙ)  
**Проблема:** Ответы API парсятся как raw dict. Неожиданный формат → KeyError → бот падает.  
**Решение:** Pydantic BaseModel с `ConfigDict(extra="ignore")`:
- `AggregatedPriceItem` — title, orderBestPrice, offerBestPrice  
- `TargetItem` / `TargetResponse`  
- `InventoryItem` / `InventoryResponse`
- `BalanceResponse`  
**Зависимость:** `pip install pydantic` (скорее всего уже установлен)  
**Статус:** 🟡 Запланировано

### 3. Resilient Error Handling + Circuit Breaker
**Файлы:** `scanner.py`, `trader.py`, `sales.py`  
**Проблема:** Голые `except Exception` маскируют критические ошибки. Нет circuit breaker.  
**Решение:**
- Гранулярные exceptions: `aiohttp.ClientResponseError`, `asyncio.TimeoutError`, `ValidationError`  
- Circuit Breaker: 3 consecutive failures → 60s cooldown  
- Structured error logging с полным traceback  
**Статус:** 🟡 Запланировано

---

## 🟡 Приоритет: ВАЖНЫЙ

### 4. Profit Tracking SQLite
**Проблема:** Нет истории сделок для анализа.  
**Решение:** SQLite DB с таблицами `trades`, `inventory_snapshots`. Auto-создание при первом запуске.  
**ToS:** ✅ Легально — локальное хранение данных.

### 5. Telegram Notifications
**Проблема:** Нет уведомлений о сделках в реальном времени.  
**Решение:** aiogram-backend для отправки alerts: BUY executed, SELL listed, error occurred.  
**ToS:** ✅ Легально — не касается DMarket API.

### 6. Dynamic Spread Adjustment
**Проблема:** `MIN_SPREAD_PCT = 7.0` статичен.  
**Решение:** Adaptive spread на основе 24h volume и volatility из API данных.  
**ToS:** ✅ Легально — использует только существующие API endpoints.

---

## 🟢 Приоритет: БЭКЛОГ

### 7. Multi-game Support (Dota 2, Rust)
Расширение `Config.GAME_ID` на массив + per-game стратегии.

### 8. ML Price Prediction (Lightweight)
Простая linear regression на исторических данных для прогноза spread.  
⚠️ Ограничение: AMD RX 6600 — только CPU-инференс для ML.

### 9. WebSocket Real-time Feed
Проверить наличие WS endpoint в DMarket API docs. Если есть — заменить polling.  
⚠️ ToS: Требует проверки endpoint авторизации.
