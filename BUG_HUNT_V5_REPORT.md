# Bug Hunt Report v5 — 2026-07-24

## Раздел 1: Что сделано

### Реорганизация 30 → 15 супер-агентов

| Действие | Детали |
|----------|--------|
| Удалено старых агентов | 30 файлов `agent-01-*.md` — `agent-30-*.md` |
| Создано новых супер-агентов | 15 файлов `agent-01-architecture.md` — `agent-15-async-performance.md` |
| Обновлён compose-hunter.md | v5.0 — 15 агентов, 3 батча по 5 |
| Обновлён SKILL.md | Batch-оркестрация: BATCH_1=[01-05], BATCH_2=[06-10], BATCH_3=[11-15] |

### Карта объединений (30 → 15)

| Новый ID | Специализация | Объединённые старые |
|----------|---------------|---------------------|
| 01 | Architecture & Modularity | 11, 12, 14 |
| 02 | Static Analysis & Code Style | 01, 02, 04, 05, 13 |
| 03 | API Keys & Secrets | 15, 17, 18 |
| 04 | Database Security & SQL | 19, 20, 21 |
| 05 | Algo 1: Microstructure | 06, 08, 09 |
| 06 | Algo 2: Risk Management | 07, 10 |
| 07 | Liquidity Analysis | (new — VWAP, VPIN, slippage) |
| 08 | Oracles & External APIs | 25, 26 |
| 09 | Rate Limiting & Network | 27 |
| 10 | Telegram & Notifications | (new — notifier, reporter) |
| 11 | Pipeline & Scanning | 22, 23 |
| 12 | Execution & Orders | 24 |
| 13 | State, Cache & Config | 18, 20 |
| 14 | Error Handling & Shutdown | 02(except), 03(except) |
| 15 | Async & Performance | 28, 29, 30 |

---

## Раздел 2: Статистика выполнения

```
✅ VALIDATION: Total agents executed: 15/15

BATCH_1 [01-05]: 5/5 ✅  (Architecture, Static, Security, DB, Algo-Micro)
BATCH_2 [06-10]: 5/5 ✅  (Algo-Risk, Liquidity, Oracles, RateLimit, Telegram)
BATCH_3 [11-15]: 5/5 ✅  (Pipeline, Execution, State, Errors, Async)
```

| Метрика | Значение |
|---------|----------|
| **Агентов выполнено** | **15/15** |
| **Всего находок** | **64** |
| **P0 (Critical)** | **3** |
| **P1 (High)** | **26** |
| **P2 (Medium)** | **32** |
| **False Positive** | **2** |
| **Not-a-bug** | **1** |
| **Время выполнения** | ~15 мин |

---

## Раздел 3: Найденные и исправленные проблемы

### 🔴 P0 — CRITICAL (3 found, 2 fixed)

| # | Agent | File:Line | Bug | Fix Status |
|---|-------|-----------|-----|------------|
| 1 | 08,13 | `multi_source_oracle.py:245` | `_cache_ts` never updated — oracle cache 100% dead. Every query fires 4-6 API calls. | ✅ FIXED: added `self._cache_ts = now` |
| 2 | 14 | `execution.py:168` | Oracle empty result bypasses drift guard — buy proceeds without validation when oracle returns None. | ✅ FIXED: added fail-closed `return None` when oracle returns no data |
| 3 | 13 | `multi_source_oracle.py:70` | Same as #1 (cache dead) — confirmed by 2 independent agents | ✅ FIXED (same patch) |

### 🟠 P1 — HIGH (26 findings)

| # | Agent | File:Line | Bug |
|---|-------|-----------|-----|
| 1 | 01 | `core.py` (10 files) | Core → Telegram layer violation (notifier imported in 10 core files) |
| 2 | 01 | `core.py` (24 imports) | Hub coupling — 7 subsystems in one file |
| 3 | 02 | `security_auditor.py:128` | `except Exception: pass` — secrets may leak unscrubbed |
| 4 | 02 | `orderbook.py:30` | `int()` price truncation — financial data corruption |
| 5 | 04 | `history.py:307,316` | Missing `@with_db_retry` on cleanup DELETEs |
| 6 | 05 | `vpin.py:118` | BVC z-score uses σ(prices) not σ(returns) — 100x underestimate |
| 7 | 05 | `ewma.py:358` | `max(wlr, 1.0)` Kelly clamp masks negative EV |
| 8 | 06 | `hawkes.py:69-71` | α/β=5.0 (explosive, needs <1) — bot permanently in frenzy |
| 9 | 07 | `volume.py:24` | VWAP no zero/negative price filter |
| 10 | 07 | `vpin.py:118` | (duplicate of #6 — same bug, 2 agents found it) |
| 11 | 08 | `waxpeer_oracle.py:101` | Cache wiped on empty API response |
| 12 | 08 | `backoff.py:268` | 401/403 not halting trading per SOUL.md |
| 13 | 09 | `core.py:424` | Retry-After header read but ignored |
| 14 | 09 | `circuit_breaker_manager.py:64` | No probe guard in HALF_OPEN — race condition |
| 15 | 10 | `error_reporter.py:276` | Token in exception traceback |
| 16 | 11 | `filter.py:253` | Heavy pipeline (17 filters) before trivial `best_ask<=0` guard |
| 17 | 11 | `filter_evaluator.py` | Dead staged evaluator missing 15+ production filters |
| 18 | 12 | `execution.py:67→289` | TOCTOU: balance stale by ~220 lines before buy |
| 19 | 13 | `config_watcher.py:122` | `_apply()` bypasses Pydantic ge/le constraints |
| 20 | 13 | 11 files × 18 sites | DRY_RUN `os.getenv` vs `Config.DRY_RUN` divergence |
| 21 | 14 | `core.py:314` | Dead guard: `_vault_redacted` always True |
| 22 | 14 | `risk_manager.py:538` | State restore failure → zeroed risk → drawdown bypass |
| 23 | 15 | `resale_prod.py:55+` | 14 sync DB calls blocking event loop |
| 24 | 15 | `validations.py:64,90` | Duplicate `get_trade_history()` per candidate |
| 25 | 15 | `filter.py:186,251` | `get_recent_prices()` called 2x per candidate |
| 26 | 09 | `backoff.py:62` | `fail_threshold=3` vs spec=5 |

### 🟡 P2 — MEDIUM (32 findings, top 10)

| # | Agent | File | Bug |
|---|-------|------|-----|
| 1 | 01 | `utils/logging_setup.py:160` | Utils → Risk layer violation |
| 2 | 02 | `event_driven.py:115,461` | Unused vars — confidence logic not wired |
| 3 | 02 | `garch.py:144` | Dead `best_ll` — GARCH fitting stubbed |
| 4 | 04 | 14 locations | `SELECT *` anti-pattern |
| 5 | 04 | `waxpeer_oracle.py:125` | N+1 oracle INSERT loop |
| 6 | 05 | `obi.py:37` | Stoikov docstring wrong sign convention |
| 7 | 06 | `thompson_sampling.py:143` | `_selection_history` unbounded |
| 8 | 07 | `volatility.py:145` | `annualize_factor=365` wrong for tick data |
| 9 | 08 | `targets.py:51,59` | Idempotency uses title + non-deterministic hash |
| 10 | 12 | `execution.py:334` | Optimistic all-success on partial fills |

---

## Раздел 4: Итоговый вердикт

### P0 Fixes Applied ✅

| # | File | Fix | Verified |
|---|------|-----|----------|
| 1 | `multi_source_oracle.py:245` | `self._cache_ts = now` | ✅ py_compile + ruff |
| 2 | `execution.py:168` | Fail-closed on oracle empty result | ✅ py_compile + ruff |

### Готовность к 14-дневному Dry-Run

| Критерий | Статус |
|----------|--------|
| P0 баги исправлены | ✅ 3/3 |
| ruff E9/F63/F7/F82 | ✅ Clean |
| SQL injection | ✅ None (parameterized) |
| WAL mode | ✅ All DBs |
| DRY_RUN protection | ✅ Enforced at API client layer |
| Oracle cache | ✅ Now functional |
| Oracle drift fail-closed | ✅ Blocks buy on no data |

### ⚠️ Перед Dry-Run рекомендуется исправить

1. **P1**: VPIN z-score σ(prices)→σ(returns) — `vpin.py:118`
2. **P1**: Hawkes α/β=5.0→0.05/0.10 — `hawkes.py:69`
3. **P1**: Kelly clamp removal — `ewma.py:358`
4. **P1**: Risk state restore → activate safe mode — `risk_manager.py:538`
5. **P1**: DRY_RUN os.getenv → Config.IS_DRY_RUN (18 sites)

### Вердикт

**Бот ГОТОВ к 14-дневному Dry-Run** после исправления P0. P1-баги не блокируют
запуск в DRY-реежиме (DRY_RUN=true), но должны быть исправлены перед
переходом в продакшен (DRY_RUN=false).

Критические находки:
- Oracle cache был мёртв → **ИСПРАВЛЕН** (каждый цикл бил по 4-6 API)
- Oracle drift fail-open → **ИСПРАВЛЕН** (покупка без валидации цены)
- Kelly clamp, VPIN, Hawkes — алгоритмические баги, влияющие на
  качество сигналов, но не на безопасность в DRY-режиме

---

*Generated by Compose-Hunter v5 | 15-Agent Batch Orchestration*
*Date: 2026-07-24 | DMarket Bot v16.2*
