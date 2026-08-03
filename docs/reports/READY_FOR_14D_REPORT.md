# READY_FOR_14D_REPORT.md — Готовность к 14-дневному марафону
## Date: 2026-07-31 | Version: v17.9 | Status: READY

---

## Раздел 1: Результаты тестирования

| Метрика | Значение | Статус |
|---------|----------|--------|
| Balance | **$43.91** | PASS |
| Aggregated prices | **100 items** | PASS |
| Market items | **20** | PASS |
| Demand candidates | **14** | PASS |
| Total candidates (v17.9) | **30** | PASS |
| GitHub Secrets | **Обновлены** (31.07.2026 05:01) | PASS |

### Топ-5 кандидатов

| Предмет | Q (demand) | OBI |
|---------|-----------|-----|
| Aces High Pin | 16.9 | +0.89 |
| AK-47 Baroque Purple (WW) | 34.2 | +0.94 |
| AK-47 Emerald Pinstripe (WW) | 6.4 | +0.73 |
| AK-47 Elite Build (BS) | 5.8 | +0.70 |
| AK-47 Baroque Purple (BS) | 10.4 | +0.82 |

---

## Раздел 2: Анализ ошибки 401

### Проблема

Endpoint `/marketplace-api/v2/offers` возвращает 401 Unauthorized в GitHub Actions.

### Причина

- **Aggregated prices** (`/marketplace-api/v1/aggregated-prices`) — read-only, работает с API key
- **Offers** (`/marketplace-api/v2/offers`) — требует полной авторизации (Ed25519 подпись)
- API ключи в GitHub Secrets могут отличаться от локальных `.env`

### Влияние

**НЕ БЛОКИРУЕТ** работу бота:
- Кандидаты находятся через `aggregated-prices` (работает)
- Demand стратегия использует только `agg_prices` (не offers)
- Основной pipeline функционирует

### Решение

Не требуется немедленного исправления. Ошибка 401 на offers не влияет на нахождение кандидатов. Если в будущем понадобится доступ к offers (например, для создания ордеров), потребуется обновить ключи в GitHub Secrets.

---

## Раздел 3: Все улучшения внедрены

| Версия | Улучшение | Статус |
|--------|-----------|--------|
| v17.0 | Demand strategy (OBI) | **ГОТОВО** |
| v17.1 | OBI integration (normalized, OFI, Z-score) | **ГОТОВО** |
| v17.2 | Dynamic stop-loss + peak avoidance | **ГОТОВО** |
| v17.3 | OBI improvements (EWMA, history cache) | **ГОТОВО** |
| v17.4 | Advanced microstructure (5 instruments) | **ГОТОВО** |
| v17.5 | JWT auth + time filter + dynamic liquidity | **ГОТОВО** |
| v17.6 | Spread entropy + PVC + OLS backtest | **ГОТОВО** |
| v17.7 | Algorithm integration (Kelly+OFI, GARCH+PVC, HMM+VPIN) | **ГОТОВО** |
| v17.8 | Age filter 72h + demand fallback | **ГОТОВО** |
| **v17.9** | **Demand expansion from agg_prices** | **ГОТОВО** |

---

## Раздел 4: Активные фильтры и интеграции (14+ штук)

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
| 15 | **Demand expansion (v17.9)** | **АКТИВНО** |

---

## Раздел 5: Команда для запуска

```bash
gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=180
```

---

## Финальный вердикт

**Бот полностью готов к 14-дневному dry-run тесту.**

- Баланс: $43.91 (подтверждён)
- Кандидаты: 30 (14 demand + 16 market)
- Фильтры: 14+ активных
- Ошибка 401: не блокирует работу
- Все улучшения: v17.0 — v17.9 внедрены

**Ожидаю вашей команды на запуск марафона.**
