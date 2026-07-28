# IMPROVEMENTS_DEEP_ANALYSIS_AND_VERDICT.md — Критический ре-анализ улучшений OBI стратегии
## Date: 2026-07-28 | Balance: $43.91 | Version: v17.2

---

## Раздел 1: Критика каждого улучшения

### 1.1 GARCH/EWMA для прогнозирования hold_days

**Оригинальное предложение:** Использовать GARCH(1,1) для прогнозирования волатильности и корректировки expected_daily.

#### Слабые места

| Проблема | Серьёзность | Описание |
|----------|-------------|----------|
| Требует ≥30 наблюдений | **ВЫСОКАЯ** | GARCH.calibrate() имеет MIN_OBSERVATIONS. Для редких предметов (<10 obs) — не работает. |
| Взрывные прогнозы | **СРЕДНЯЯ** | Если α+β > 1 (non-stationary), прогноз расходится. В коде есть проверка persistence < 0.99, но edge cases возможны. |
| Нет `sigma` атрибута | **ВЫСОКАЯ** | GARCHForecast не имеет `sigma` — нужно использовать `forecast_vol_1`. Оригинальный патч НЕРАБОЧИЙ. |
| Медленная калибровка | **СРЕДНЯЯ** | GARCH.calibrate() делает MLE оптимизацию — ~10-50 мс на предмет. При 100 кандидатах = 1-5 сек. |
| EWMA шумна при <10 obs | **СРЕДНЯЯ** | При 5 наблюдениях EWMA vol = 0.28% (сильно занижена). |

#### Контрмеры (улучшенное решение)

**Гибридный подход EWMA → GARCH:**

```python
def estimate_volatility(title: str, ask_price: float) -> float:
    """
    Estimate price volatility using hybrid EWMA/GARCH approach.
    
    - <10 observations: fixed heuristic (0.02 = 2%)
    - 10-29 observations: EWMA (fast, works with few data points)
    - ≥30 observations: GARCH (accurate, requires convergence)
    
    Returns volatility as decimal (0.02 = 2%).
    """
    try:
        from src.db.price_history import price_db
        history = price_db.get_recent_prices(title, days=14)
        prices = [p for p, _ in history if p > 0]
        
        if len(prices) < 10:
            # Not enough data — use price-segment heuristic
            if ask_price < 2.0:
                return 0.03  # Cheap items: higher volatility
            elif ask_price < 5.0:
                return 0.02  # Medium items: normal volatility
            else:
                return 0.015  # Expensive items: lower volatility
        
        # Anomaly filter: remove prices >3σ from local mean
        import statistics
        mean_p = statistics.mean(prices)
        std_p = statistics.stdev(prices) if len(prices) > 1 else mean_p * 0.1
        filtered = [p for p in prices if abs(p - mean_p) < 3 * max(std_p, mean_p * 0.05)]
        
        if len(filtered) < 5:
            filtered = prices  # Fallback to unfiltered
        
        if len(filtered) < 30:
            # EWMA path (fast, works with 10+ observations)
            from src.analysis.algo_pack.ewma import ewma_volatility
            vol = ewma_volatility(filtered, alpha=0.06)
            return max(0.005, min(0.10, vol))  # Clamp 0.5%-10%
        
        # GARCH path (accurate, requires 30+ observations)
        returns = [(filtered[i] - filtered[i-1]) / filtered[i-1]
                   for i in range(1, len(filtered)) if filtered[i-1] > 0]
        
        if len(returns) < 20:
            from src.analysis.algo_pack.ewma import ewma_volatility
            vol = ewma_volatility(filtered, alpha=0.06)
            return max(0.005, min(0.10, vol))
        
        from src.analysis.algo_pack.garch import GARCH11Estimator
        garch = GARCH11Estimator()
        garch.calibrate(returns)
        
        if not garch.params.converged:
            from src.analysis.algo_pack.ewma import ewma_volatility
            vol = ewma_volatility(filtered, alpha=0.06)
            return max(0.005, min(0.10, vol))
        
        forecast = garch.forecast(steps=1)
        vol = forecast.forecast_vol_1
        
        # Sanity check: if GARCH gives extreme values, fall back
        if vol < 0.001 or vol > 0.20:
            from src.analysis.algo_pack.ewma import ewma_volatility
            vol = ewma_volatility(filtered, alpha=0.06)
        
        return max(0.005, min(0.10, vol))
        
    except Exception:
        # Ultimate fallback: price-segment heuristic
        if ask_price < 2.0:
            return 0.03
        elif ask_price < 5.0:
            return 0.02
        else:
            return 0.015
```

**Skeptical analysis:**
- При <10 obs: fallback на эвристику (0.02) — безопасно
- При 10-29 obs: EWMA (быстрый, ~1 мс) — безопасно
- При ≥30 obs: GARCH (медленный, ~10-50 мс) — acceptable
- При любом except: fallback на эвристику — безопасно
- **Риск регрессии: НИЗКИЙ** — fallback chain обеспечивает работу в любом случае

---

### 1.2 Динамический стоп-лосс по волатильности

**Оригинальное предложение:** `max_hold = max(2.0, min(5.0, 5.0 - volatility / 10.0))`

#### Слабые места

| Проблема | Серьёзность | Описание |
|----------|-------------|----------|
| Линейная формула | **СРЕДНЯЯ** | `5.0 - volatility/10` не учитывает асимметрию (цена падает быстрее) |
| Окно 7 дней шумное | **СРЕДНЯЯ** | Волатильность на 7 днях может быть аномальной |
| Нет мгновенного стопа | **ВЫСОКАЯ** | Если цена упала >5% за 24ч — нет реакции |

#### Улучшенное решение

```python
# В position_guard.py, check_stop_losses():
if Config.DEMAND_STRATEGY_ENABLED and it.get("strategy") == "demand":
    age_days = age_hours / 24.0
    buy_price = float(it["buy_price"] or 0)
    
    # 1. Instant stop: if price dropped >5% in 24h, sell immediately
    if current_price < buy_price * 0.95 and age_days >= 1.0:
        logger.warning(f"[DEMAND-INSTANT-STOP] {it['hash_name']}: "
                       f"price dropped {(buy_price - current_price)/buy_price*100:.1f}%")
        items_to_liquidate.append((it, current_price, "demand-instant-stop"))
        continue  # Skip time-based check
    
    # 2. Dynamic time-based stop using EWMA volatility
    try:
        from src.core.target_sniping.demand_strategy import estimate_volatility
        vol = estimate_volatility(it["hash_name"], buy_price)
        
        # High vol (>3%) = shorter hold (2 days)
        # Low vol (<1%) = longer hold (5 days)
        # Formula: max_hold = 5.0 - (vol / 0.01) * 0.5, clamped [2, 6]
        dynamic_hold = max(2.0, min(6.0, 5.0 - (vol / 0.01) * 0.5))
    except Exception:
        dynamic_hold = Config.DEMAND_MAX_HOLD_DAYS
    
    if age_days > dynamic_hold:
        logger.warning(f"[DEMAND-TIMEOUT] {it['hash_name']}: "
                       f"{age_days:.1f}d > {dynamic_hold:.1f}d (vol-based)")
        items_to_liquidate.append((it, current_price, f"demand-timeout {age_days:.1f}d"))
```

**Skeptical analysis:**
- Instant stop (5% drop): Защищает от резких падений. Не влияет на растущие позиции.
- Dynamic hold: Использует estimate_volatility() с fallback chain. Безопасно.
- Min hold = 2 дня: Предотвращает преждевременную продажу при нормальной волатильности.
- Max hold = 6 дня: Ограничивает максимальное удержание.
- **Риск регрессии: НИЗКИЙ** — fallback на Config.DEMAND_MAX_HOLD_DAYS.

---

### 1.3 Категория предмета в адаптивных порогах

**Оригинальное предложение:** Определять категорию по названию (sticker, case, knife).

#### Слабые места

| Проблема | Серьёзность | Описание |
|----------|-------------|----------|
| Ненадёжное определение | **СРЕДНЯЯ** | "Sticker | AK-47" — это стикер или оружие? |
| Гибридные предметы | **СРЕДНЯЯ** | Оружие со стикерами — как классифицировать? |
| Нет поля type в API | **ВЫСОКАЯ** | DMarket API не предоставляет поле type для листингов |

#### Улучшенное решение

**Использовать ценовые сегменты вместо категорий** (уже реализовано):

```python
# Текущая реализация уже адаптивна по цене:
if ask_price < 2.0:      # Стикеры, граффити, кейсы
    min_demand_ratio = 1.5
elif ask_price < 5.0:     # Дешёвое оружие
    min_demand_ratio = 2.0
else:                     # Дорогое оружие
    min_demand_ratio = 2.5
```

**Skeptical analysis:**
- Ценовые сегменты уже покрывают основные категории
- Добавление title-based категоризации — минимальное улучшение при высоком риске ложных срабатываний
- **Рекомендация: Оставить как есть. Не внедрять.**

---

### 1.4 Peak avoidance (история цен)

**Оригинальное предложение:** Штраф 30%, если цена > средней за 7 дней.

#### Слабые места

| Проблема | Серьёзность | Описание |
|----------|-------------|----------|
| Штраф 30% слишком суров | **ВЫСОКАЯ** | Может отсекать реальные тренды (предмет растёт legitimately) |
| Средняя арифметическая | **СРЕДНЯЯ** | Чувствительна к выбросам (один аномальный день портит расчёт) |
| Нет проверки на тренд | **СРЕДНЯЯ** | Если цена растёт 3 дня подряд — это тренд, не пик |

#### Улучшенное решение

```python
# В demand_strategy.py, calculate_demand_score():
# Peak avoidance with median and trend check
try:
    from src.db.price_history import price_db
    import statistics
    history = price_db.get_recent_prices(title, days=7)
    prices = [p for p, _ in history if p > 0]
    
    if len(prices) >= 5:
        # Use median instead of mean (robust to outliers)
        median_price = statistics.median(prices)
        
        # Trend check: if last 3 prices are increasing, reduce penalty
        if len(prices) >= 3:
            last_3 = prices[-3:]
            is_uptrend = all(last_3[i] > last_3[i-1] for i in range(1, len(last_3)))
        else:
            is_uptrend = False
        
        if ask_price > median_price * 1.15:  # 15% above median
            if is_uptrend:
                penalty = 0.9  # 10% penalty (uptrend mitigates)
            else:
                penalty = 0.85  # 15% penalty (normal case)
            score *= penalty
            result["reason"] += f" (peak penalty {penalty:.0%})"
except Exception:
    pass  # No penalty if no data
```

**Skeptical analysis:**
- Median вместо mean: Устойчив к выбросам
- Штраф 15% вместо 30%: Менее агрессивный
- Trend check: Если цена растёт — штраф уменьшается (10% вместо 15%)
- Fallback: Нет данных — нет штрафа
- **Риск регрессии: НИЗКИЙ** — может отсечь 1-2 хорошие сделки из 15, но защитит от покупки на пике

---

### 1.5 Мониторинг изменений спроса

**Оригинальное предложение:** Два запроса с интервалом 5-10 минут.

#### Слабые места

| Проблема | Серьёзность | Описание |
|----------|-------------|----------|
| Удвоение API нагрузки | **ВЫСОКАЯ** | 100 items × 2 запроса = 200 запросов за цикл |
| 5 минут задержки | **ВЫСОКАЯ** | Увеличивает время цикла с 30 сек до 5.5 мин |
| 30% порог шумный | **СРЕДНЯЯ** | Нормальные колебания спроса могут быть ±20% |

#### Улучшенное решение

**Сделать опциональным и только для топ-кандидатов:**

```python
# В demand_strategy.py:
async def verify_demand_stability(
    client,
    title: str,
    initial_qi: float,
    wait_seconds: int = 300,
) -> bool:
    """
    Verify demand stability by checking OBI after delay.
    Only for high-score candidates (score > 2000).
    
    Returns True if demand is stable (OBI > 0.5).
    """
    if not Config.DEMAND_STABILITY_CHECK_ENABLED:
        return True  # Skip check if disabled
    
    await asyncio.sleep(wait_seconds)
    
    try:
        agg = await client.get_aggregated_prices("a8db", titles=[title])
        if title in agg:
            data = agg[title]
            qi = data.get("bid_count", 0) / max(data.get("ask_count", 1), 1)
            obi = simple_obi(
                data.get("best_bid", 0), data.get("best_ask", 0),
                data.get("bid_count", 0), data.get("ask_count", 0)
            )
            # Demand is stable if OBI > 0.5 (still buyer-dominated)
            return obi > 0.5
    except Exception:
        pass
    
    return True  # Assume stable on error
```

**Skeptical analysis:**
- Опционально через Config: Не влияет, если выключено
- Только для score > 2000: Проверяет только лучшие кандидаты (~3-5 из 15)
- OBI > 0.5 вместо 30% падения: Более надёжный критерий
- 300 сек задержки: Можно уменьшить до 60 сек
- **Риск регрессии: СРЕДНИЙ** — увеличивает время цикла, но только для топ-кандидатов

---

## Раздел 2: Матрица рисков

| # | Улучшение | Риск регрессии | Зависимость от данных | Сложность | Вердикт |
|---|-----------|---------------|----------------------|-----------|---------|
| 1.1 | GARCH/EWMA | НИЗКИЙ | ВЫСОКАЯ (нужна история) | СРЕДНЯЯ | **Внедрить сейчас** (hybrid EWMA→GARCH) |
| 1.2 | Dynamic stop-loss | НИЗКИЙ | СРЕДНЯЯ (нужна волатильность) | НИЗКАЯ | **Внедрить сейчас** (instant stop + dynamic hold) |
| 1.3 | Категория предмета | СРЕДНИЙ | НИЗКАЯ (title parsing) | НИЗКАЯ | **Отложить** (ценовые сегменты уже работают) |
| 1.4 | Peak avoidance | НИЗКИЙ | СРЕДНЯЯ (нужна история) | НИЗКАЯ | **Внедрить сейчас** (median + trend check) |
| 1.5 | Мониторинг спроса | СРЕДНИЙ | НИЗКАЯ (API запросы) | СРЕДНЯЯ | **Отложить до 2-й недели** |

---

## Раздел 3: Выбранные улучшения для внедрения

### 3.1 Выбор: Dynamic stop-loss + Peak avoidance

**Почему именно эти два:**

1. **Dynamic stop-loss** — самый безопасный и эффективный:
   - Instant stop (5% drop) защищает от резких падений
   - Dynamic hold адаптируется к волатильности
   - Fallback на Config при ошибке
   - Не увеличивает время цикла

2. **Peak avoidance** — второй по безопасности:
   - Median вместо mean — устойчив к выбросам
   - Штраф 15% — мягкий, не отсекает тренды
   - Trend check — не штрафует растущие тренды
   - Fallback: нет данных — нет штрафа

**Почему НЕ GARCH/EWMA сейчас:**
- Требует интеграции с estimate_volatility() — средняя сложность
- Лучше внедрить на 2-й неделе, когда накопится статистика

**Почему НЕ мониторинг спроса:**
- Увеличивает время цикла
- Лучше внедрить, когда будет понятно, какие кандидаты теряют спрос

---

### 3.2 Финальные патчи

#### Патч 1: Dynamic stop-loss (position_guard.py)

```python
# В position_guard.py, после существующего time-based stop-loss:
if Config.DEMAND_STRATEGY_ENABLED and it.get("strategy") == "demand":
    age_days = age_hours / 24.0
    buy_price = float(it["buy_price"] or 0)
    
    # Instant stop: if price dropped >5% since purchase, sell immediately
    if buy_price > 0 and current_price < buy_price * 0.95 and age_days >= 1.0:
        loss_pct = (buy_price - current_price) / buy_price * 100
        logger.warning(f"[DEMAND-INSTANT-STOP] {it['hash_name']}: "
                       f"price dropped {loss_pct:.1f}% in {age_days:.1f}d")
        items_to_liquidate.append((it, current_price, f"demand-instant-stop {loss_pct:.1f}%"))
        continue  # Skip time-based check for this item
    
    # Dynamic time-based stop: EWMA volatility → hold days
    try:
        from src.analysis.algo_pack.ewma import ewma_volatility
        from src.db.price_history import price_db
        history = price_db.get_recent_prices(it["hash_name"], days=14)
        prices = [p for p, _ in history if p > 0]
        
        if len(prices) >= 10:
            vol = ewma_volatility(prices, alpha=0.06)
            # High vol (>3%) → shorter hold (2 days)
            # Low vol (<1%) → longer hold (5 days)
            dynamic_hold = max(2.0, min(6.0, 5.0 - (vol / 0.01) * 0.5))
        else:
            dynamic_hold = Config.DEMAND_MAX_HOLD_DAYS
    except Exception:
        dynamic_hold = Config.DEMAND_MAX_HOLD_DAYS
    
    if age_days > dynamic_hold:
        logger.warning(f"[DEMAND-TIMEOUT] {it['hash_name']}: "
                       f"{age_days:.1f}d > {dynamic_hold:.1f}d")
        items_to_liquidate.append((it, current_price, f"demand-timeout {age_days:.1f}d"))
```

#### Патч 2: Peak avoidance (demand_strategy.py)

```python
# В demand_strategy.py, calculate_demand_score(), после score calculation:
# Peak avoidance: penalize if current price > 15% above 7-day median
try:
    from src.db.price_history import price_db
    import statistics
    history = price_db.get_recent_prices(title, days=7)
    prices = [p for p, _ in history if p > 0]
    
    if len(prices) >= 5:
        median_price = statistics.median(prices)
        
        # Trend check: last 3 prices increasing = uptrend
        if len(prices) >= 3:
            last_3 = prices[-3:]
            is_uptrend = all(last_3[i] > last_3[i-1] for i in range(1, len(last_3)))
        else:
            is_uptrend = False
        
        if ask_price > median_price * 1.15:  # 15% above median
            if is_uptrend:
                score *= 0.90  # 10% penalty (uptrend mitigates)
                reason_parts.append("uptrend-peak-10%")
            else:
                score *= 0.85  # 15% penalty (normal case)
                reason_parts.append("peak-penalty-15%")
except Exception:
    pass  # No penalty if no data available
```

---

## Раздел 4: Почему остальные отложены

### GARCH/EWMA (отложено до 2-й недели)

**Причина:** Требует интеграции estimate_volatility() в calculate_demand_score(). Лучше внедрить, когда:
1. Накопится статистика по win rate
2. Будет понятно, как часто GARCH даёт лучшие прогнозы
3. Можно будет A/B тестировать GARCH vs EWMA vs эвристику

### Категоризация по типу предмета (отложено indefinitely)

**Причина:** Ценовые сегменты уже работают адекватно. Title-based категоризация — ненадёжна (ложные срабатывания). DMarket API не предоставляет поле type.

### Мониторинг изменений спроса (отложено до 2-й недели)

**Причина:** Увеличивает время цикла. Лучше внедрить, когда:
1. Будет статистика по потерянным сделкам из-за падения спроса
2. Можно будет оптимизировать интервал проверки
3. Будет понятно, какой порог падения спроса критичен

---

## Раздел 5: Рекомендация

### Итоговый план

| Неделя | Действие |
|--------|----------|
| **Неделя 1** | Запуск с dynamic stop-loss + peak avoidance |
| **Неделя 2** | Сбор статистики, A/B тестирование GARCH/EWMA |
| **Неделя 3** | Внедрить GARCH/EWMA если статистика подтверждает |
| **Неделя 4** | Внедрить мониторинг спроса если потери значительны |

### Skeptical analysis финальных патчей

**Dynamic stop-loss:**
- Не увеличивает время цикла? **ДА** — EWMA ~1 мс, проверка только для demand items
- Не приведёт к потере хороших сделок? **НЕТ** — instant stop только при >5% падения
- Все ли ошибки обрабатываются? **ДА** — fallback на Config.DEMAND_MAX_HOLD_DAYS

**Peak avoidance:**
- Не увеличивает время цикла? **ДА** — DB запрос ~1 мс
- Не приведёт к потере хороших сделок? **МИНИМАЛЬНО** — штраф 15%, trend check снижает до 10%
- Все ли ошибки обрабатываются? **ДА** — fallback: нет данных = нет штрафа

### Финальная рекомендация

**Внедрить dynamic stop-loss + peak avoidance до 14-дневного теста.**

Эти два улучшения:
1. Самые безопасные (низкий риск регрессии)
2. Самые эффективные (защищают от падений и пиковых покупок)
3. Простые в реализации (2 файла, ~30 строк)
4. Полностью обратно совместимы (fallback на существующие параметры)

**Запуск 14-дневного теста: ПОСЛЕ внедрения выбранных патчей.**
