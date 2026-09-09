---
name: volatility-modeling
description: Использовать для GARCH/EWMA калибровки в модуле algo_pack бота (src/analysis/algo_pack/), активируется при детектировании режима волатильности в ranking.py.
---

# Моделирование волатильности (DMarket)

Анализ и прогнозирование волатильности цен на предметы CS2 (DMarket). В отличие от акций, цены на скины подвержены как резким патчевым скачкам (jump diffusion), так и периодам стагнации из-за низкой ликвидности.

## Режимы волатильности

В `src/analysis/microstructure/volatility.py` реализована функция `classify_volatility_regime`, оценивающая аннуализированную волатильность (через Parkinson estimator):

- **Low**: < 20%
- **Medium**: 20% – 50%
- **High**: > 50% (Обычно приводит к блокировке покупки: `check_vol_regime` в `validations.py` отбрасывает предметы при высокой волатильности).

## GARCH(1,1)

Прогнозирование условной дисперсии (conditional variance) реализовано в `src/analysis/algo_pack/garch.py` (`class GARCHParams`).

```python
from src.analysis.algo_pack.garch import GARCHEstimator

garch = GARCHEstimator()
params = garch.calibrate(returns)
# Уравнение: h_t = ω + α*r_{t-1}^2 + β*h_{t-1}
```

Конфигурация бота применяет штрафы к волатильности при негативных макро-факторах:
`GARCH_PVC_FACTOR = 1.2` — если PVC (Price Volume Correlation) негативна, прогнозируемая волатильность искусственно увеличивается на 20% для запаса прочности.

## EWMA (Exponentially Weighted Moving Average)

Используется для быстрой оценки ковариации и волатильности без необходимости сложной нелинейной оптимизации GARCH. Конфигурируется через настройки `EWMA`.

## Интеграция

- `validations.py`: `check_vol_regime` отклоняет аномально волатильные предметы.
- `ranking.py`: Волатильность участвует в формировании скора Риск/Прибыль (Sharpe-like ratio).
- `dynamic_manager.py`: Динамическая корректировка размера позиции на основе GARCH прогноза.

