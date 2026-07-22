# ANALYSIS_STAGE3.md — Код-ревью с исправлениями

**Дата:** 2026-07-22 | **Версия проекта:** v16.2

---

## Проведённые исправления

### Исправление 1: `src/core/target_sniping/position_guard.py`

**Баг:** `__import__("time").time()` использовался вместо `import time` (2 места: строки 59 и 209).

**Причина:** `time` не был импортирован в начале файла. Разработчик использовал `__import__` как workaround.

**Исправление:**
- Добавлен `import time` в imports (строка 19)
- Заменены оба `__import__("time").time()` на `time.time()`

**Влияние:** P2 — стилистика, не влияет на логику работы.

---

### Исправление 2: `src/api/steam_oracle.py`

**Баг:** `data = await resp.json()` вызывался ПОСЛЕ закрытия контекстного менеджера `async with session.get()`.

**Детали:**
```python
# БЫЛО (строки 98-108):
async with session.get(self.BASE_URL, params=params) as resp:
    if resp.status == 429:
        ...
        continue
    if resp.status != 200:
        ...
        return 0.0
# Контекстный менеджер ЗАКРЫТ здесь — соединение закрыто
data = await resp.json()  # ← ОШИБКА: чтение из закрытого соединения
```

**Исправление:** Перенесён `data = await resp.json()` и вся последующая логика внутрь блока `async with`.

**Влияние:** P1 — потенциальная ошибка чтения из закрытого соединения. В aiohttp это может привести к `ClientResponseError` или чтению пустых данных.

---

### Исправление 3: `src/api/fair_price_calculator.py`

**Баг:** Outlier removal удалял ТОЛЬКО один выброс (min ИЛИ max), даже если оба являются выбросами.

**Детали:**
```python
# БЫЛО (строки 133-150):
if len(adjusted) > 2:
    min_source = min(adjusted, key=adjusted.get)
    max_source = max(adjusted, key=adjusted.get)
    
    others = {k: v for k, v in adjusted.items() if k != min_source}
    if others:
        others_median = statistics.median(others.values())
        if adjusted[min_source] < others_median * 0.3:
            outlier_removed = min_source
            del adjusted[min_source]
        elif len(adjusted) > 2:  # ← ТОЛЬКО если min НЕ выброс
            others = {k: v for k, v in adjusted.items() if k != max_source}
            if others:
                others_median = statistics.median(others.values())
                if adjusted[max_source] > others_median * 2.0:
                    outlier_removed = max_source
                    del adjusted[max_source]
```

**Проблема:** Если min является выбросом (удаляется), то max НЕ проверяется (ветка `elif`).

**Исправление:**
```python
# СТАЛО:
if len(adjusted) > 2:
    min_source = min(adjusted, key=adjusted.get)
    max_source = max(adjusted, key=adjusted.get)
    
    # Remove min outlier if < 0.3× median of others
    others = {k: v for k, v in adjusted.items() if k != min_source}
    if others:
        others_median = statistics.median(others.values())
        if adjusted[min_source] < others_median * 0.3:
            outlier_removed = min_source
            del adjusted[min_source]
    
    # Remove max outlier if > 2.0× median of others (re-check after min removal)
    if len(adjusted) > 2:
        max_source = max(adjusted, key=adjusted.get)
        others = {k: v for k, v in adjusted.items() if k != max_source}
        if others:
            others_median = statistics.median(others.values())
            if adjusted[max_source] > others_median * 2.0:
                outlier_removed = max_source
                del adjusted[max_source]
```

**Влияние:** P1 — влияет на корректность fair price calculation. Если оба выброса присутствуют, медиана будет искажена.

---

## Проверенные файлы (без найденных проблем)

### DMarket API Client
- `core.py` — Ed25519 подпись, rate limiting, circuit breaker, DRY_RUN guard ✅
- `targets.py` — buy_items, batch_create_targets, idempotency ✅
- `offers.py` — batch_create/edit/delete_offers_v2 ✅
- `rate_limiter.py` — token bucket, adaptive 429 handling ✅
- `backoff.py` — circuit breaker implementation ✅

### Oracle Integrations
- `market_csgo_oracle.py` — endpoint, parsing, rate limiting ✅
- `waxpeer_oracle.py` — endpoint, parsing, rate limiting ✅
- `csfloat_oracle.py` — endpoint, parsing, rate limiting ✅
- `multi_source_oracle.py` — circuit breaker, freshness guard ✅

### Trading Logic
- `filter.py` — candidate evaluation, Kelly sizing, microstructure pipeline ✅
- `execution.py` — slippage protection, inventory cap, balance tracking ✅
- `cycle_orchestrator.py` — 6-stage pipeline ✅
- `resale_prod.py` — auto-resale, oracle pricing ✅
- `risk_manager.py` — drawdown freeze, daily loss, trade count ✅

### Risk Management
- `price_validator.py` — volatility validation ✅
- `pump_detector.py` — pump detection + blacklist ✅
- `concentration_risk.py` — portfolio concentration ✅

---

## Архитектурная проверка

### Операции вне DMarket: ✅ НЕТ

Проверено:
- `grep -r "buy|sell|list|withdraw" src/api/market_csgo_oracle.py` — только read-only
- `grep -r "buy|sell|list|withdraw" src/api/waxpeer_oracle.py` — только read-only
- `grep -r "buy|sell|list|withdraw" src/api/csfloat_oracle.py` — только read-only
- `grep -r "buy|sell|list|withdraw" src/api/steam_oracle.py` — только read-only
- `src/strategies/cross_market.py` — использует oracle данные для ОЦЕНКИ, не выполняет сделки

**Все торговые операции проходят ТОЛЬКО через `src/api/dmarket_api_client/`.**

---

*Ревью проведено: 2026-07-22*
*Исправлено: 3 файла, 3 бага (P1×2, P2×1)*
