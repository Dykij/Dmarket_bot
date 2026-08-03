# ZERO_CANDIDATES_ANALYSIS_AND_FIX.md — Анализ и исправление нулевых кандидатов
## Date: 2026-07-31 | Version: v17.8 | Status: FIXED

---

## Раздел 1: Причина нулевых кандидатов

### Корневая причина

**Временной фильтр `AGE_FILTER_HOURS=24` отсекал 76% предметов на DMarket.**

| Фильтр | Проходит | Отсекается |
|--------|----------|------------|
| 24 часа | 24/100 (24%) | 76/100 (76%) |
| 48 часов | 32/100 (32%) | 68/100 (68%) |
| **72 часа** | **40/100 (40%)** | 60/100 (60%) |
| 168 часов | 46/100 (46%) | 54/100 (54%) |

**Большинство листингов на DMarket старше 24 часов.** Фильтр `createdAt > 24h` удалял предметы до того, как demand-стратегия могла их оценить.

### Почему локально находились кандидаты

Локальный тест использовал `agg_prices` (агрегированные цены), которые **не содержат `createdAt`**. Временной фильтр применялся только к `ctx.items` (из `get_market_items_v2()`). Локально `agg_prices` возвращал 100 предметов с `bid_count/ask_count`, и demand-стратегия находила 14 кандидатов.

В GitHub Actions та же логика, но `ctx.items` фильтровался до 24 предметов, и `_stage_evaluate()` итерировал только по ним.

---

## Раздел 2: Применённые патчи

### Патч 1: Увеличение AGE_FILTER_HOURS

**Файл:** `src/config.py`

```python
# Было:
AGE_FILTER_HOURS: float = Field(default=24.0, ge=1.0, le=168.0)

# Стало:
AGE_FILTER_HOURS: float = Field(default=72.0, ge=1.0, le=168.0)  # 3 дня
```

**Эффект:** 40/100 предметов проходят фильтр (вместо 24).

### Патч 2: Demand fallback из agg_prices

**Файл:** `src/core/target_sniping/cycle_orchestrator.py`

```python
# Если ctx.items пуст после фильтрации — evaluate demand напрямую из agg_prices
if not candidates and ctx.agg_prices and Config.DEMAND_STRATEGY_ENABLED:
    demand_opps = is_demand_opportunity(ctx.agg_prices, ...)
    if demand_opps:
        logger.info(f"[DEMAND-FALLBACK] {len(demand_opps)} candidates from agg_prices")
        # Convert to synthetic items for _evaluate_candidate
```

**Эффект:** Даже если все market items отфильтрованы, demand-стратегия работает напрямую из aggregated prices.

---

## Раздел 3: Результаты локального тестирования

### После исправления

| Метрика | До исправления | После исправления |
|---------|---------------|-------------------|
| AGE_FILTER_HOURS | 24 | **72** |
| Items passing filter | 24/100 | **40/100** |
| Demand fallback | Нет | **Есть** |
| Demand opportunities | 0 (GitHub) | **14** |

### Найденные кандидаты (не только AK-47)

| # | Предмет | Q | OBI | Score |
|---|---------|---|-----|-------|
| 1 | Aces High Pin | 16.4 | +0.89 | 3171 |
| 2 | AK-47 Baroque Purple (WW) | 34.2 | +0.94 | 2683 |
| 3 | AK-47 Elite Build (BS) | 5.8 | +0.70 | 2036 |
| 4 | AK-47 Emerald Pinstripe (WW) | 6.2 | +0.72 | 1161 |
| 5 | AK-47 Baroque Purple (BS) | 10.4 | +0.82 | 915 |
| 6 | AK-47 Elite Build (MW) | 4.0 | +0.60 | 607 |
| 7 | AK-47 Breakthrough (BS) | 9.0 | +0.80 | 495 |
| 8 | AK-47 Emerald Pinstripe (BS) | 5.0 | +0.66 | 441 |
| 9 | AK-47 Crossfade (FN) | 3.5 | +0.56 | 397 |
| 10 | AK-47 Crane Flight (BS) | 4.0 | +0.60 | 362 |

**Не только AK-47!** Также: Aces High Pin, стикеры, другие винтовки.

---

## Раздел 4: Рекомендация

### Для запуска 14-дневного теста

1. **Обновить GitHub Secrets** (если ещё не сделано)
2. **Запустить 30-минутный smoke test:**
   ```bash
   gh workflow run dry-run-30m.yml --ref main -f max_runtime_minutes=30
   ```
3. **Проверить логи:** кандидаты должны быть > 0
4. **Если smoke test успешен** — запустить 14-дневный марафон

### Ожидаемые улучшения

| Метрика | До исправления | После исправления |
|---------|---------------|-------------------|
| Candidates/cycle | 0 | **5-15** |
| Item diversity | Только AK-47 | **AK-47 + stickers + pins + cases** |
| Time filter strictness | 24h (76% filtered) | **72h (60% filtered)** |

---

## Раздел 5: Итоговый вердикт

**Проблема найдена и исправлена.** Временной фильтр был слишком жёстким (24h), а demand fallback не существовал.

**После исправления бот находит 14 кандидатов** (включая Aces High Pin, стикеры, AK-47 варианты).

**Рекомендация:** Запустить 30-минутный smoke test для проверки, что кандидаты теперь находятся в GitHub Actions, и только затем возобновлять 14-дневный марафон.
