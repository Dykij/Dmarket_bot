---
name: statistical-rigor
description: Guidelines for statistical honesty and reporting metrics.
---

# Statistical Rigor

## Statistical Honesty
При отчётах с числами/метриками указывать размер выборки (sample size), погрешность и проверять однородность.
- Не делать выводов на основе единичных наблюдений (N=1).
- Использовать p-value для проверки статистической значимости там, где это применимо.
- Избегать round numbers без указания дисперсии (variance/stddev).
- Любые изменения в формулах `pricing.py` или `demand_strategy.py` требуют валидации на историческом датасете (backtest) с указанием ключевых метрик (Sharpe, drawdown, VaR).
