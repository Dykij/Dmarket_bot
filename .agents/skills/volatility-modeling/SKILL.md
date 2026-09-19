---
name: volatility-modeling
description: "\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u044C \u0434\u043B\u044F GARCH/EWMA \u043A\u0430\u043B\u0438\u0431\u0440\u043E\u0432\u043A\u0438 \u0432 \u043C\u043E\u0434\u0443\u043B\u0435 algo_pack \u0431\u043E\u0442\u0430 (src/analysis/algo_pack/), \u0430\u043A\u0442\u0438\u0432\u0438\u0440\u0443\u0435\u0442\u0441\u044F \u043F\u0440\u0438 \u0434\u0435\u0442\u0435\u043A\u0442\u0438\u0440\u043E\u0432\u0430\u043D\u0438\u0438 \u0440\u0435\u0436\u0438\u043C\u0430 \u0432\u043E\u043B\u0430\u0442\u0438\u043B\u044C\u043D\u043E\u0441\u0442\u0438 \u0432 ranking.py. Use when modeling GARCH, EWMA, or implied volatility surfaces for risk management and options pricing."
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


See references/content.md for detailed formulas and extended documentation.
