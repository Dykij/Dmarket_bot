---
name: market-microstructure
description: "\u0418\u0441\u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u044C \u0434\u043B\u044F \u0430\u043D\u0430\u043B\u0438\u0437\u0430 \u043F\u043E\u0442\u043E\u043A\u0430 \u043E\u0440\u0434\u0435\u0440\u043E\u0432/\u043F\u0440\u0435\u0434\u043B\u043E\u0436\u0435\u043D\u0438\u0439 \u043D\u0430 DMarket \u0438 \u043C\u0438\u043A\u0440\u043E\u0441\u0442\u0440\u0443\u043A\u0442\u0443\u0440\u043D\u043E\u0433\u043E \u043F\u0430\u0439\u043F\u043B\u0430\u0439\u043D\u0430 \u0432 src/core/target_sniping/microstructure_pipeline.py. Use when analyzing level 2 order book data, order flow imbalance, or high-frequency trade execution dynamics using modern tick-level methods."
---
# Микроструктура ордербука DMarket

## Overview

Микроструктура рынка на DMarket (централизованный маркетплейс скинов CS2) принципиально отличается от традиционных финансов и криптовалютных DEX-бирж. Вместо пулов ликвидности здесь используется классическая модель ордербука (стакана), но со специфическими особенностями: низкой ликвидностью, высокой дисперсией цен на паттерны/флоат и значительной долей нерациональных участников. 

Анализ потока сделок (trade flow analysis) позволяет выявлять паттерны накопления (accumulation), дистрибуции (distribution) и потенциальных манипуляций.

## Особенности микроструктуры на DMarket

1. **Разреженность стакана (Sparsity)**: Стаканы по редким предметам могут быть пустыми на несколько десятков процентов вверх.
2. **Асимметрия информации**: Покупатели часто оценивают стикеры/паттерны, которые не отражаются в базовой цене API.
3. **Непрерывность (24/7)**: Отсутствие торговых сессий.

## Метрики давления покупателей/продавцов

### Cumulative Volume Delta (CVD)

CVD измеряет разницу между объемом покупок (инициатива покупателя) и объемом продаж (инициатива продавца) по истории сделок `trade_records`.

```python
from src.analysis.microstructure import compute_cvd

cvd_val = compute_cvd(trade_records)
# CVD > 0 указывает на преобладание рыночных покупок
```

### VPIN (Volume-Synchronized Probability of Informed Trading)

Оценка токсичности потока ордеров.

```python
from src.analysis.microstructure import compute_vpin

vpin_val = compute_vpin(trade_records, buckets=5)
# AUDIT: Log VPIN values to calibrate threshold for CS2 market
# Current threshold is from equity HFT literature — may be too high
```

## Оценка ликвидности и токсичности

### Kyle's Lambda (Price Impact)

Измеряет влияние объема сделки на изменение цены. Более высокая лямбда означает более сильное негативное влияние отбора (adverse selection) — рынок тонкий, крупные сделки сильно двигают цену.




See references/content.md for detailed formulas and extended documentation.
