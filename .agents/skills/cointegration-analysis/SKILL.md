---
name: cointegration-analysis
description: Использовать для анализа парной коинтеграции и спред-трейдинга в модуле target_sniping.
---

# Коинтеграционный анализ пар (DMarket)

Коинтеграция — статистическое свойство двух временных рядов, при котором их линейная комбинация является стационарной. В контексте CS2/DMarket это означает, что цены двух разных предметов связаны фундаментальной экономической зависимостью и не могут расходиться бесконечно далеко.

## Кандидаты для пар (Pairs Trading) на CS2

1. **Взаимозаменяемое оружие (Substitutes)**: M4A1-S vs M4A4 (классический пример спреда, сходящегося после каждого патча от Valve).
2. **Скины разного износа**: Factory New (FN) vs Minimal Wear (MW) одного и того же скина (например, AK-47 | Redline).
3. **Предметы одной коллекции (Collections)**: Разные предметы одинаковой редкости из коллекции, снятой с дропа (Cobblestone, Gods and Monsters).
4. **Кейс и его топ-скин**: Отношение цены кейса к ожидаемой стоимости выпадения (EV).

## Реализация (algo_pack)

Калибровка коинтеграции (Cointegration Calibration) в боте:

```python
from src.analysis.algo_pack import PairTrading, calibrate

# Проверка, образуют ли два предмета коинтегрированную пару
# Если returns_a и returns_b высоко коррелируют, но не коинтегрированы -> false
params = pair_trading.calibrate(returns_ak47_fn, returns_ak47_mw)

if params.is_cointegrated:
    print(f"Пара торгуема, Z-score спреда: {params.current_z_score}")
```

## Интеграция

- Используется для статистического арбитража.
- Требует проверки `test_calibrate_detects_cointegration` и `test_calibrate_low_correlation_not_cointegrated` (`tests/test_new_algo_modules.py`).
- Опирается на `TRACKED_TITLES` из `src/config.py` для отбора валидных пар.
