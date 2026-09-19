### PVC (Price Volume Correlation)

В боте корреляционный анализ используется в связке с `dynamic_manager.py` и `ranking.py`.

```python
# Пример концептуального применения в боте (pseudo-code)
# Не покупать скин, если портфель уже перегружен высококоррелированными предметами
def check_portfolio_correlation(new_item_title: str, current_inventory: list[str]) -> float:
    # 1. Извлечь базовое оружие (напр. "AK-47")
    base_weapon = extract_base_weapon(new_item_title)
    
    # 2. Подсчитать долю этого оружия в инвентаре
    weapon_exposure = sum(1 for item in current_inventory if extract_base_weapon(item) == base_weapon)
    
    # 3. Штрафовать скоринг, если превышен лимит концентрации
    if weapon_exposure > MAX_EXPOSURE_PER_WEAPON:
        return 0.5  # Уменьшение позиции
    return 1.0
```

## Интеграция с другими модулями

- **`volatility-modeling`**: Ковариационная матрица строится на основе волатильностей и корреляций для оценки VaR.
- **`cointegration-analysis`**: Для статистического арбитража (например, парный трейдинг между M4A4 и M4A1-S) требуется коинтеграция, а не просто корреляция.
- **`src/config.py` (`TRACKED_TITLES`)**: Анализ должен ограничиваться разрешенным списком предметов.

