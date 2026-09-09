---
name: mean-reversion
description: Использовать для настройки процессов Орнштейна-Уленбека и оценки экспоненты Херста в src/analysis/algo_pack/ou_process.py.
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
