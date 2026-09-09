---
name: market-microstructure-traditional
description: Использовать для анализа Order Book Imbalance (OBI), процесса Хоукса и спреда Ролла в src/analysis/microstructure/.
---

# Традиционные микроструктурные модели в DMarket

Перевод академических концепций микроструктуры в практический код бота для парсинга ордербука CS2.

## Модель Эффективного Спреда (Roll, 1984)

Из-за скрытых ордеров и задержек API видимый спред DMarket не всегда отражает реальные издержки (effective spread). Модель Ролла оценивает спред по серийной ковариации изменения цен.

Реализация в `src/analysis/microstructure/volatility.py`:
```python
from src.analysis.microstructure.volatility import roll_effective_spread
# s = 2 * sqrt(-cov(Delta p_t, Delta p_{t-1}))
spread = roll_effective_spread(prices)
```

## Дисбаланс ордербука (Order Book Imbalance, OBI)

Соотношение давления лимитных ордеров покупателей и продавцов на вершине стакана. 
Реализация находится в `src/analysis/microstructure/obi.py`. Влияет на микроструктурный скоринг.

## Процесс Хоукса (Hawkes Process)

Модель кластеризации сделок (сделки порождают новые сделки). На DMarket используется для детектирования "ажиотажа" (frenzy) вокруг предмета, когда интенсивность покупок резко возрастает (например, после твита киберспортсмена или обновления игры).

Реализация влияет на веса в `src/analysis/microstructure/signals.py` (`hawkes_activity`):

```python
# Из signals.py:
hawkes_scores = {"quiet": 1.0, "normal": 0.8, "elevated": 0.4, "frenzy": 0.0}
components["hawkes"] = hawkes_scores.get(hawkes_activity, 0.5)
# Ажиотаж (frenzy) имеет высокий вес штрафа, чтобы избегать покупки на пике хайпа
```

## Price Impact (Kyle's Lambda)

См. основной скилл `market-microstructure`.

## VWAP (Volume-Weighted Average Price)

Бенчмарк для оценки качества исполнения ордеров бота. Покупка дешевле VWAP за период = положительное проскальзывание (positive slippage).
