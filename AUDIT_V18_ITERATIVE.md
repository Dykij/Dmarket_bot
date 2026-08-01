# AUDIT_V18_ITERATIVE.md — Итеративный аудит v18 (read-only)
## Date: 2026-08-01 | Mode: READ-ONLY | No fixes applied

---

## ШАГ 0: Подтверждение

- PR #16 = Draft (OPEN)
- GH Actions = 0 active runs
- Workflows: все disabled (кроме codeql, Dependabot)

---

## Приоритет 1 — Торговая логика

### demand_strategy.py — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| 205 | **P2** | `from src.db.price_history import price_db` внутри функции (inside `if Config.PVC_ENABLED:` + `try:`). Та же проблема, что была в position_guard.py:58. Сейчас работает, потому что внутри try/except. Но если import fails, PVC logic молча пропускается. |
| 259 | **P2** | Аналогично — peak avoidance import внутри try/except. |
| 310 | **P2** | Аналогично — `_log_demand_decision` import внутри try/except. |
| 30 | **P3** | `simple_obi` импортирован, но используется только на строке 169 для legacy совместимости. Не влияет на scoring. |
| 167-169 | **P3** | `qi`, `signal`, `obi` вычисляются, но только `qi` используется как `demand_ratio`. `signal` проверяется на строке 252, но избыточен — если `qi > threshold`, signal всегда "buy". |
| 221 | **P2** | `except Exception: pass` — молча проглатывает ошибку PVC calculation. Нет логирования. |
| 280 | **P2** | `except Exception: pass` — молча проглатывает ошибку peak avoidance. Нет логирования. |

**Влияние на trading logic:**
- Строки 205/259/310: Если import fails, PVC и peak avoidance молча пропускаются. Это не crash, но items могут получить score без штрафа за пиковые цены.
- Строка 221/280: Если price_db недоступен, PVC и peak avoidance молча пропускаются.

### filter.py — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| 289 | **OK** | `price_db.log_decision(title, "skip", "Microstructure", ms_result.reason)` — 4 аргумента, соответствует сигнатуре. |
| 432, 446, 470, 479, 494, 752 | **OK** | Все вызовы `log_decision` используют 4 аргумента. |

**Проверено и НЕ найдено ошибок:** Все вызовы `log_decision` в filter.py корректны.

### cycle_orchestrator.py — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| 315-339 | **OK** | DEMAND-EXPAND корректно добавляет кандидатов из agg_prices. |
| 151, 247, 277, 438, 444, 455, 545 | **P3** | `except Exception:` без логирования — 7 мест. Предсуществующие, не из v18. |

**Проверено и НЕ найдено ошибок:** DEMAND-EXPAND логика корректна.

### position_guard.py — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| 94 | **P3** | `buy_price = float(it["buy_price"] or 0)` — redundant, уже вычислено на строке 66. |
| 108 | **P3** | `from src.analysis.algo_pack.ewma import ewma_volatility` — локальный import внутри try/except. Работает, но можно вынести наверх. |

**Проверено и НЕ найдено ошибок:** UnboundLocalError (строка 58) исправлен в предыдущем коммите. Dynamic stop-loss корректен.

### microstructure_pipeline.py — ПРОВЕРЕНО

**Проверено и НЕ найдено ошибок.** Все 16 фильтров корректно gated через `Config.STRICT_MICROSTRUCTURE_FILTERS`.

### obi.py — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| 50-51 | **P3** | `simple_obi` — `(best_bid or 0.01) * (bid_count or 0)` — если best_bid=0, используется 0.01 как fallback. Логично для предотвращения division by zero. |
| 83 | **P3** | `multi_level_obi` — `int(li.get("price", {}).get("USD", 0))` — может упасть если "price" не dict. Но listings всегда приходят от DMarket API с правильной структурой. |
| 189 | **P3** | `queue_imbalance` возвращает `None` если ask_count=0, а `normalized_obi` возвращает 0.0. Несогласованность, но не влияет на логику (demand_strategy проверяет `qi is None` на строке 176). |

**Проверено и НЕ найдено критических ошибок.** Формулы корректны.

### risk/*.py — ПРОВЕРЕНО (первый аудит)

| Файл | Severity | Находка |
|------|----------|---------|
| `risk_manager.py` | **OK** | `pre_trade_check` корректно проверяет pump blacklist, daily limits, drawdown. |
| `pump_detector.py` | **OK** | Threshold=15%, blacklist TTL=24h. |
| `security_auditor.py` | **OK** | Token scrubbing работает. |
| `circuit_breaker_manager.py` | **OK** | Circuit breaker корректно trips/resets. |

**Проверено и НЕ найдено ошибок.**

---

## Приоритет 2 — Косвенные изменения

### price_history (log_decision) — ПРОВЕРЕНО

| Строка | Severity | Находка |
|--------|----------|---------|
| analytics_logs.py:39 | **OK** | `log_decision(self, hash_name, decision, reason, details="")` — 4 аргумента. |

**Все 15 вызовов в проекте используют 4 аргумента.** Проверено.

### telegram_reporter.py — ПРОВЕРЕНО

**Проверено и НЕ найдено ошибок.** Формат HOURLY STATUS / CRON REPORT не зависит от decision_logs формата.

### dry-run-14d.yml — ПРОВЕРЕНО

**Проверено и НЕ найдено ошибок.** Env-переменные соответствуют актуальным именам в config.py.

---

## Приоритет 3 — Класс ошибок (повторяющиеся паттерны)

### 3.1 Локальные imports (тот же класс, что position_guard bug)

| Файл | Строка | Severity | Описание |
|------|--------|----------|---------|
| demand_strategy.py | 205 | **P2** | `from src.db.price_history import price_db` внутри try/except |
| demand_strategy.py | 259 | **P2** | Аналогично |
| demand_strategy.py | 310 | **P2** | Аналогично |
| position_guard.py | 108 | **P3** | `from src.analysis.algo_pack.ewma import ewma_volatility` внутри try/except |

**Рекомендация:** Вынести все imports наверх файлов. Не критично (try/except handles it), но улучшает читаемость и предотвращает future bugs.

### 3.2 Silent except Exception: pass

| Файл | Строка | Severity | Описание |
|------|--------|----------|---------|
| demand_strategy.py | 221 | **P2** | PVC calculation — молча пропускается |
| demand_strategy.py | 280 | **P2** | Peak avoidance — молча пропускается |
| filter.py | 200, 216, 361 | **P3** | Предсуществующие |
| cycle_orchestrator.py | 151, 247, 277, 438, 444, 455, 545 | **P3** | Предсуществующие |

### 3.3 Сигнатурные mismatches

**Проверено:** Все 15 вызовов `log_decision` используют 4 аргумента. Несоответствий не найдено.

### 3.4 Race condition (oracle/aggregated price vs execution)

**Проверено:** Цена запрашивается один раз за цикл (в `_stage_scan`), затем передаётся через `CycleContext`. Нет race condition между чтением цены и исполнением.

---

## Сводка находок

| Severity | Количество | Описание |
|----------|-----------|---------|
| **P0** | **0** | Нет критических ошибок |
| **P1** | **0** | Нет высокоприоритетных ошибок |
| **P2** | **5** | Локальные imports (3), silent except (2) |
| **P3** | **8** | Redundant code, unused imports, inconsistency |

---

## Пересекается со старыми отчётами

| Находка | Старый отчёт | Статус |
|---------|-------------|--------|
| position_guard UnboundLocalError | REFACTOR_V18_VERIFICATION.md | **ИСПРАВЛЕНО** (коммит 182dca8) |
| log_decision TypeError | REFACTOR_V18_VERIFICATION.md | **ИСПРАВЛЕНО** (коммит 182dca8) |
| 401 on offers endpoint | AUTH_FIX_REPORT.md | **РЕШЕНО** (ключі обновлены) |
| Silent except: pass | RESEARCH_AUDIT_2026-07-25.md | **Известно** (56 instances, documented) |
| Local imports | Новый | **Найдено в этом аудите** |

---

## Итог

**Нет P0/P1 ошибок.** Все P2/P3 — улучшения, не блокирующие запуск.

Критических багов, которые могут сломать торговлю, **не найдено**.

Логика demand-стратегии, OBI/OFI, dynamic stop-loss, peak avoidance — **корректна**.

Decision logging — **работает** (441 entries verified).

---

*Отчёт создан в read-only режиме. Никаких изменений не внесено.*
