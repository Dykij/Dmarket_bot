---
name: mean-reversion
description: "\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u044C \u0434\u043B\u044F \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043F\u0440\u043E\u0446\u0435\u0441\u0441\u043E\u0432 \u041E\u0440\u043D\u0448\u0442\u0435\u0439\u043D\u0430-\u0423\u043B\u0435\u043D\u0431\u0435\u043A\u0430 \u0438 \u043E\u0446\u0435\u043D\u043A\u0438 \u044D\u043A\u0441\u043F\u043E\u043D\u0435\u043D\u0442\u044B \u0425\u0435\u0440\u0441\u0442\u0430 \u0432 src/analysis/algo_pack/ou_process.py. Use when backtesting or modeling mean-reversion trading strategies, Ornstein-Uhlenbeck processes, or statistical arbitrage pairs."
---
# Возврат к среднему (Mean Reversion)

Алгоритмы выявления предметов, временно отклонившихся от своей справедливой цены (long-term mean), и расчета оптимального времени удержания (half-life) для маркетплейса DMarket.

## Экспонента Хёрста (Hurst Exponent)

Вычисляется через Rescaled Range (R/S) анализ в `regime_detector.py`. 
- `H < 0.5`: Ряд возвращается к среднему (подходит для OU).
- `H = 0.5`: Случайное блуждание (стратегия не работает).
- `H > 0.5`: Трендовый ряд (моментум).

## Процесс Орнштейна-Уленбека (OU Process)

Моделирование динамики цен (логарифмов цен): `dX = θ(μ - X)dt + σdW`

Реализован в `src/analysis/algo_pack/ou_process.py` (`class OUProcessEstimator`).

### Калибровка (OLS)

```python
from src.analysis.algo_pack.ou_process import OUProcessEstimator

ou = OUProcessEstimator()
# dt_hours=0.5 для 30-минутных циклов бота
params = ou.calibrate(prices, dt_hours=0.5)

print(f"θ (скорость возврата): {params.theta}")
print(f"μ (справедливая лог-цена): {params.mu}")
print(f"Half-life: {params.half_life_hours} часов")
```

### Генерация сигналов (OUSignal)

Сигнал генерируется на основе текущего `Z-score` отклонения цены от `μ`:

```python
signal = ou.update(current_price)

if signal.action == "buy":
    # Покупаем, если z_score < ENTRY_Z_SCORE и confidence > 0.2
    print(f"Покупаем. Ожидаемая доходность (E[r]): {signal.expected_return_pct}%")
elif signal.action == "stop_loss":
    # Экстренный выход, если z_score < STOP_Z_SCORE
    pass
```

Параметры `ENTRY_Z_SCORE` и `STOP_Z_SCORE` жестко зашиты в конфигурации. Сигнал опирается на статистическую значимость (R-squared).
