# ANALYSIS_ARCHITECTURE.md — Архитектурный аудит

**Дата:** 2026-07-22 | **Версия проекта:** v16.2 | **Архитектурный score (archy):** 0.55

---

## Сводка

Трёхэтапный архитектурный аудит: документация vs фактический код после всех исправлений за сессию.

**Главный вывод:** Архитектурная документация **существенно устарела** (v15.8 vs v16.2). За 4 минорных версии добавлено 60+ модулей, которые не отражены ни в одном документе. При этом **фактическая архитектура кода здорова** — нет критических структурных проблем.

---

## ЭТАП 1 — Анализ документации vs фактический код

### 1.1 Состояние документов

| Документ | Версия | Актуальность | Статус |
|----------|--------|-------------|--------|
| `docs/ARCHITECTURE.md` | v15.8 | **4 версии назад** | КРИТИЧЕСКИ устарел |
| `SYSTEM_FLOW.md` | v15.8 | **4 версии назад** | КРИТИЧЕСКИ устарел |
| `AGENTS.md` (footer) | v15.7 | **5 версий назад** | Устарел |
| `README.md` | v16.2 | Текущая | ✅ Актуален |
| `ANALYSIS_STAGE4.md` | v16.2 | Текущая | ✅ Актуален |
| `DATABASE_ANALYSIS.md` | ~v15.1 | Устарел | 6 таблиц + 12 индексов не задокументированы |

### 1.2 Архитектурный score (archy)

| Компонент | Score | Оценка |
|-----------|-------|--------|
| **Overall** | 0.55 | Средний |
| Modularity | 0.71 | Хорошо |
| Acyclicity | 0.98 | Отлично (5 циклов — все `__init__` re-exports) |
| Depth | 0.36 | Глубокое дерево (max depth 14) |
| Equality | 0.32 | Неравномерное распределение (несколько god objects) |
| Complexity | 0.63 | Средний (cc_max=161 в core.py) |

### 1.3 Топ-5 god objects

| Модуль | Fan-in | Fan-out | Edit Risk |
|--------|--------|---------|-----------|
| `src/config.py` | 49 | 1 | 0.12 |
| `src/db/price_history/` | 38 | 9 | **0.20** (highest!) |
| `src/api/dmarket_api_client/core.py` | 21 | 10 | 0.17 |
| `src/core/target_sniping/core.py` | 7 | **24** | 0.13 |
| `src/telegram/notifier.py` | 11 | 0 | 0.00 |

---

## ЭТАП 2 — Глубокий анализ (4 параллельных субагента)

### 2.1 Structure Mapper — полная карта модулей

**Фактическая структура:** 239 Python-модулей в 15+ пакетах.

**Модули, отсутствующие в ARCHITECTURE.md (60+):**

Ключевые незадокументированные модули:
- `src/core/target_sniping/cycle_orchestrator.py` — оркестрация 6-стадийного пайплайна
- `src/core/target_sniping/filter_evaluator.py` — per-candidate evaluation
- `src/core/target_sniping/microstructure_pipeline.py` — пайплайн из 15+ фильтров
- `src/core/target_sniping/validations.py` — 520 строк валидаций
- `src/core/target_sniping/ranking.py` — ранжирование кандидатов
- `src/core/target_sniping/value_pipelines.py` — dual-signal VALUE+SPREAD
- `src/core/target_sniping/position_guard.py` — fee-aware stop-loss/take-profit
- `src/api/fair_price_calculator.py` — median-based fair price
- `src/api/steam_oracle.py` — Steam oracle
- `src/analysis/algo_pack/` — 16 алгоритмов (GARCH, HMM, OU, Hawkes и т.д.)
- `src/analysis/microstructure/` — OBI, OFI, VWAP, VPIN и т.д.
- `src/risk/` — 14 модулей (лишь 3 упомянуты в ARCHITECTURE.md)
- `src/strategies/almgren_chriss.py` — оптимальное исполнение
- `src/models/`, `src/types/`, `src/monitoring/` — не упомянуты

**Модуль, упомянутый в ARCHITECTURE.md, но НЕ существующий:**
- `src/api/oracle_cache.py` — **НЕ СУЩЕСТВУЕТ**. Кэширование встроено в `multi_source_oracle.py`

**Dead code (9 файлов с нулевым импортом):**
- `src/strategies/canary_mode.py`, `src/strategies/almgren_chriss.py`, `src/strategies/cross_market.py`
- `src/analytics/knowledge_base.py`, `src/db/profit_tracker.py`
- `src/utils/query_profiler.py`, `src/utils/retry_decorator.py`, `src/utils/database.py`

**Zombie-пакеты (5 пустых директорий):**
- `src/dmarket/api/`, `src/dmarket/arbitrage/`, `src/dmarket/filters/`, `src/dmarket/scanner/`, `src/dmarket/targets/`

**Дублирование API-клиентов:**
- `src/api/dmarket_api_client/` (основной, mixin-based) + `src/dmarket/dmarket_api.py` (standalone, httpx)

### 2.2 Data Flow Audit — трассировка данных

**Фактический пайплайн (подтверждён кодом):**

```
Oracle Sources (Market.CSGO, Waxpeer, CSFloat, Steam)
  │  [circuit breaker + freshness guard per source]
  ▼
MultiSourceOracle.get_fair_price()          [multi_source_oracle.py:168]
  │  [dynamic TTL cache 5-30min, sequential queries]
  ▼
FairPriceCalculator.calculate()             [fair_price_calculator.py:85]
  │  [outlier removal → median → margin tiers by volume]
  ▼
CycleOrchestrator._stage_prefetch()         [cycle_orchestrator.py:190]
  │  [batch oracle fetch → cs_snapshots]
  ▼
_FilterMixin._evaluate_candidate()          [filter.py:71]
  │  [30+ filters: bait→Kelly→microstructure→oracle→spread→value→fees→caps]
  │  [NOV-2: blocks oracle-dependent strategies when ALL oracles fail]
  ▼
ExecutionMixin._execute_instant_buys()      [execution.py:50]
  │  [slippage check + NOV-3 oracle re-check + risk gate + inventory cap]
  ▼
DMarketAPIClient.buy_items()                [targets.py:73]
  │  PATCH /exchange/v1/offers-buy          ✅ CONFIRMED
  ▼
auto_resale() → resale_prod.py              [resale.py:54]
  │  [oracle pricing → A-S reservation → VWAP bands → DOM gap]
  ▼
create_sell_offers_batch()                  [offers.py:123]
  │  POST /marketplace-api/v2/offers:batchCreate
```

**Расхождения с документацией:**

| Что говорит документация | Факт | Статус |
|--------------------------|------|--------|
| "21 microstructure filters" | **30+ distinct checks** в filter.py | Недооценка |
| Oracle → Fair Price → Filter | ✅ Соответствует | OK |
| PATCH /exchange/v1/offers-buy | ✅ Подтверждено в targets.py:97 | OK |
| Пайплайн: Scanner → Rank → Filter → Kelly → Execute | ✅ Соответствует | OK |

**Незадокументированные компоненты в data flow:**
- Avellaneda-Stoikov reservation price (resale_prod.py)
- TWAP executor для крупных ордеров (execution.py)
- Sell optimizer ternary search (filter_evaluator.py)
- Sell endpoints: `POST /marketplace-api/v2/offers:batchCreate`, `batchUpdate`, `batchDelete`

### 2.3 DB Schema Check

**4 базы данных, 19 таблиц:**

| БД | Таблиц | Назначение |
|----|--------|------------|
| `dmarket_state.db` | 11 | OLTP: инвентарь, таргеты, решения, equity |
| `dmarket_history.db` | 3 | OLAP: цены, торговая история |
| `dmarket_trading.db` | 2 | P&L трекинг |
| `dmarket_shadow.db` | 3 | Shadow trading |

**Все БД:** WAL mode ✅, parameterized queries ✅, busy_timeout=5000 ✅, file permissions 0o600 ✅

**Расхождения с DATABASE_ANALYSIS.md:**
- 6 таблиц не задокументированы: `schema_version`, `missed_opportunities`, `decision_logs`, `equity_snapshots`, `risk_events`
- Shadow DB (3 таблицы) полностью не задокументирована
- 12+ индексов не задокументированы (документ говорит "5 индексов", реально 17+)
- `ThreadPoolExecutor max_workers` документирован как 2, реально 4
- `schema_version` (миграции) документировано как "отсутствует", реально работает с v15.1

### 2.4 Security Architecture

**Общая оценка: STRONG** 🟢

| Severity | Count | Детали |
|----------|-------|--------|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 3 | Oracle re-check fails open, stale inventory snapshot, silent agg price failure |
| LOW | 3 | Idempotency key collision (теор.), suppress(Exception) в risk recording, SC2016 в shell |

**Проверено и PASS:**
- SQL injection — все запросы параметризованы
- Secret exposure — нет утечек в логах
- Vault encryption — Fernet в production
- Idempotency keys — детерминированные SHA256-based
- TOCTOU protection — cumulative tracking в batch
- Fail-closed на критических проверках

**MEDIUM-1 (рекомендация):** Oracle re-check в execution.py:161-163 при исключении логирует на DEBUG и proceeds (fail-open). Рассмотреть WARNING level для мониторинга.

---

## ЭТАП 3 — Заключение и рекомендации

### 3.1 Устарела ли документация?

**ДА, существенно.**

| Документ | Что устарело | Критичность |
|----------|-------------|-------------|
| `docs/ARCHITECTURE.md` | Версия v15.8 вместо v16.2. Описывает ~30% фактических модулей. Упоминает несуществующий `oracle_cache.py`. Не описывает 60+ модулей, DB слой, strategies, algo_pack | **ВЫСОКАЯ** — вводит в заблуждение при онбординге |
| `SYSTEM_FLOW.md` | Версия v15.8. Не описывает microstructure pipeline (30+ фильтров), value detection layers, oracle re-check, NOV-2/NOV-3 fixes | **ВЫСОКАЯ** — не отражает текущий пайплайн |
| `DATABASE_ANALYSIS.md` | 6 таблиц + 12 индексов не задокументированы. Shadow DB отсутствует. Неверные значения ThreadPool и миграций | **СРЕДНЯЯ** — фактическая БД здорова, но документация не соответствует |
| `AGENTS.md` footer | Версия v15.7 | **НИЗКАЯ** — косметическое |

### 3.2 Нужен ли ARCHITECTURE.md?

**ARCHITECTURE.md уже существует** (`docs/ARCHITECTURE.md`), но его нужно **полностью переписать** для v16.2. Дополнять AGENTS.md архитектурными деталями не нужно — там уже есть торговая архитектура и правила. Нужен отдельный актуальный `docs/ARCHITECTURE.md`.

### 3.3 Архитектурные проблемы в коде

| # | Проблема | Серьёзность | Рекомендация |
|---|----------|-------------|-------------|
| 1 | **Duplicate DMarket API clients** (`src/api/dmarket_api_client/` + `src/dmarket/dmarket_api.py`) | СРЕДНЯЯ | Удалить `src/dmarket/` (dead code + zombie dirs) |
| 2 | **Dead code** (9 файлов с нулевым импортом) | СРЕДНЯЯ | Удалить или пометить deprecated |
| 3 | **God object: config.py** (49 fan-in) | НИЗКАЯ | Неизбежно для централизованного конфига — приемлемо |
| 4 | **God object: target_sniping/core.py** (24 fan-out) | СРЕДНЯЯ | Уже разбит на 20+ mixin-файлов — дальнейшее разбиение не нужно |
| 5 | **Zombie packages** (5 пустых dirs в src/dmarket/) | НИЗКАЯ | Удалить |
| 6 | **Missing __init__.py** в risk/, strategies/, utils/ | НИЗКАЯ | Работает через implicit namespace — не критично |
| 7 | **Stub app_initialization.py** (10+ pass methods) | НИЗКАЯ | Артефакт — можно удалить |

### 3.4 Приоритизация рекомендаций

**Прямо сейчас (перед следующим деплоем):**
1. Обновить `docs/ARCHITECTURE.md` до v16.2 (полный пересмотр)
2. Обновить `SYSTEM_FLOW.md` до v16.2
3. Обновить `DATABASE_ANALYSIS.md` (добавить 6 таблиц, 12 индексов, shadow DB)

**Можно отложить (не блокирует работу):**
4. Удалить dead code (9 файлов) и zombie packages (5 dirs)
5. Удалить дублированный API-клиент в `src/dmarket/`
6. Обновить версию в footer AGENTS.md
7. Рассмотреть WARNING level для oracle re-check failures (MEDIUM-1)

**Не требует исправления:**
- God objects (config.py, core.py) — приемлемы при текущей архитектуре
- Missing __init__.py — работает через namespace packages
- 5 self-loop cycles в archy — это `__init__` re-exports, не реальные циклы

---

## Архитектурные метрики (archy baseline)

```
Overall:      0.55
Modularity:   0.71
Acyclicity:   0.98
Depth:        0.36
Equality:     0.32
Complexity:   0.63

Modules:      239
Edges:        458
Cycles:       5 (all __init__ re-exports)
Max depth:    14
Functions:    1707
CC total:     6762
CC max:       161 (target_sniping/core.py)
CC mean:      3.96
```

---

🦅 *Architecture Audit | v16.2 | 2026-07-22*
