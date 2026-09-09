---
name: market-microstructure
description: Использовать для анализа потока ордеров/предложений на DMarket и микроструктурного пайплайна в src/core/target_sniping/microstructure_pipeline.py.
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

```python
from src.analysis.microstructure.volatility import kyle_lambda

lam = kyle_lambda(sales)
# lambda approx mean(|Delta price| / volume) over the trade sequences.
```

### Режимы волатильности (Volatility Regime)

Адаптация параметров торговой стратегии в зависимости от текущего рыночного режима волатильности (Parkinson realized volatility).

```python
from src.core.target_sniping.validations import check_vol_regime

vol_result = check_vol_regime(title, trade_records)
if not vol_result["pass"]:
    print(f"Rejected due to high vol: {vol_result['annual_vol']}")
else:
    print(f"Current regime: {vol_result['regime']}")
```

## Взаимодействие со стаканом

1. **Глубина стакана (Orderbook Depth)**: Анализ `ask_count` и `bid_count` для оценки уровней поддержки и сопротивления.
2. **Эффективный спред (Effective Spread)**: Измерение реальных затрат на транзакцию с учетом скрытой ликвидности и комиссий DMarket.

## Интеграция с кодовой базой

- `src/analysis/microstructure/volatility.py`: Расчет `kyle_lambda`, `realized_vol_parkinson`, `classify_volatility_regime`.
- `src/core/target_sniping/microstructure_pipeline.py`: Основной пайплайн, агрегирующий микроструктурные метрики (CVD, VPIN, HMM Regime).
- `src/core/target_sniping/validations.py`: Жесткие проверки (gates), такие как `check_vol_regime`.
- `src/analysis/microstructure/signals.py`: Генерация весов для итогового скоринга на основе микроструктурных сигналов.

