# FINAL_DRY_RUN_LAUNCH_REPORT.md — Запуск 14-дневного dry-run теста
## Date: 2026-07-31 | Version: v17.11 | Status: READY TO LAUNCH

---

## Раздел 1: Найденные и исправленные проблемы

### Проблема: Telegram показывает нулевые метрики

**Корневая причина:** В `core.py` ранний `return` в `run_cycle()` когда `ctx.items` пуст (после time filter) предотвращал запуск demand expansion и `_stage_postprocess()`. В результате `_last_balance`, `_last_listings`, `_last_candidates` никогда не устанавливались, и Telegram reporter всегда получал 0.

**Исправление (v17.11):** Изменено условие с `not ctx.agg_prices or not ctx.items` на `not ctx.agg_prices and not ctx.items`. Теперь если `agg_prices` существует, demand expansion запускается даже когда `ctx.items` пуст.

---

## Раздел 2: Все версии (v17.0 — v17.11)

| Версия | Описание |
|--------|----------|
| v17.0 | Demand strategy (OBI) |
| v17.1 | OBI integration (normalized, OFI, Z-score) |
| v17.2 | Dynamic stop-loss + peak avoidance |
| v17.3 | OBI improvements (EWMA, history cache) |
| v17.4 | Advanced microstructure (5 instruments) |
| v17.5 | JWT auth + time filter + dynamic liquidity |
| v17.6 | Spread entropy + PVC + OLS backtest |
| v17.7 | Algorithm integration (Kelly+OFI, GARCH+PVC, HMM+VPIN) |
| v17.8 | Age filter 72h + demand fallback |
| v17.9 | Demand expansion from agg_prices |
| v17.10 | targets-by-title endpoint |
| **v17.11** | **Fix early return (Telegram zero metrics)** |

---

## Раздел 3: Активные фильтры (16 штук)

| # | Фильтр/Интеграция | Статус |
|---|-------------------|--------|
| 1 | Spread entropy (hard >20%) | **АКТИВНО** |
| 2 | Spread entropy (soft >10%) | **АКТИВНО** |
| 3 | PVC trend multiplier | **АКТИВНО** |
| 4 | Dynamic liquidity | **АКТИВНО** |
| 5 | Time filter (72h) | **АКТИВНО** |
| 6 | OBI risk-gate (<-0.3) | **АКТИВНО** |
| 7 | OFI momentum | **АКТИВНО** |
| 8 | Z-score calibration | **АКТИВНО** |
| 9 | Peak avoidance | **АКТИВНО** |
| 10 | Dynamic stop-loss | **АКТИВНО** |
| 11 | Kelly + OFI boost | **АКТИВНО** |
| 12 | GARCH + PVC | **АКТИВНО** |
| 13 | HMM + VPIN | **АКТИВНО** |
| 14 | Hawkes + Entropy | **АКТИВНО** |
| 15 | Demand expansion | **АКТИВНО** |
| 16 | targets-by-title | **АКТИВНО** |

---

## Раздел 4: Результаты тестирования

| Метрика | Значение |
|---------|----------|
| Balance | **$43.91** |
| Aggregated items | **100** |
| Demand opportunities | **14** |
| Telegram metrics | **Исправлены** (v17.11) |

---

## Раздел 5: Команда для запуска

```bash
gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=180
```

---

## Раздел 6: Рекомендации по мониторингу

- **Первые 48 часов**: Не вмешиваться, только наблюдать
- **Если кандидаты = 0 более 12 часов**: Остановить и проанализировать
- **Если ошибки 401**: Обновить GitHub Secrets
- **Telegram команды**: `/status`, `/positions`, `/pnl`

---

## Финальный вердикт

**Все старые тесты удалены, новый 14-дневный dry-run тест запущен с актуальной версией v17.11. Бот будет работать в симуляционном режиме, собирая статистику. Реальных покупок не происходит. После завершения теста вы сможете перейти к реальной торговле.**
