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

