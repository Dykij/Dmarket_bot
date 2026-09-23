# Архитектурная карта и приоритизация находок (2026-09-24)

## 1. Обзор графа зависимостей и архитектурных метрик
В ходе анализа были применены инструменты `code-graph-mcp`, `pydeps`, `radon` и `archy`.
- **pydeps**: Дерево зависимостей (3868 связей) показывает высокую входящую связность (centrality) для модулей `src/core/target_sniping/core.py`, `src/config.py`, `src/api/dmarket_api_client/core.py` и `src/utils/logging_setup.py`. 
- **radon**: Средняя цикломатическая сложность по проекту оценивается как `A` (4.18), что является отличным показателем. В `src/api/dmarket_api_client/core.py` после фикса `make_request` (cc=8, B) остался только один метод класса C — `__init__` (cc=16).
- **archy (what_to_refactor_next)**: При запуске от абсолютного пути корня репозитория инструмент распознал git-контекст (`git_available: true`) и успешно сопоставил структурный риск с историей изменений (churn), выявив 10 горячих точек.
- **config.py**: Churn=42 объясняется легитимной эволюцией конфигурации (вынос захардкоженных лимитов, обновление списка `TRACKED_TITLES`), признаков "thrashing" (нестабильности) не обнаружено.

## 2. Таблица приоритизированных находок (Топ-хрупкость)

С учетом реальных данных о частоте изменений (churn) из git-истории, приоритеты рефакторинга выглядят следующим образом:

| Модуль | Метрика | Тип проблемы | Приоритет | Статус |
| --- | --- | --- | --- | --- |
| `src/core/target_sniping/filter.py` | Archy Hotspot #1 (churn: 47) / MI: B | Высокая сложность (cc=173) + Активное изменение кода | 🔴 High | Требует рефакторинга |
| `src/core/target_sniping/execution.py` | Archy Hotspot #2 (churn: 39) / MI: C | Высокая сложность (cc=191) + Активное изменение кода | 🔴 High | Требует рефакторинга |
| `src/api/dmarket_api_client/account.py` | Business Logic | Дублирование `balance` вместо `usdAvailableToWithdraw` | 🔴 High | Требует исправления логики |
| `src/api/dmarket_api_client/core.py` | Archy Hotspot #3 (churn: 31) | Остаточная сложность (`__init__` cc=16) + Аномальный Rate Limit (110 RPS для fee) | 🔴 High | Требует рефакторинга/Калибровки |
| `src/db/price_history/__init__.py` | Archy Edit-Risk | Высокий структурный риск редактирования (0.16) при fan_in=30 | 🟠 Medium | Снизить связность |
| `src/core/target_sniping/cycle_orchestrator.py` | Archy Hotspot #6 (churn: 28) | Сложность (cc=126) | 🟠 Medium | Требует рефакторинга |
| `src/db/price_history/core.py` | Archy Hotspot #5 (churn: 21) | Сложность x Churn | 🟠 Medium | Требует рефакторинга |
| `src/config.py` | Archy Hotspot #7 (churn: 42) | Высокий churn и огромный fan_in=55 (легитимно, но требует внимания) | 🟠 Medium | Под наблюдением |

## 3. Duplicate Method Scan (Скан на дубликаты)
По следам инцидента с дублированием методов в `execution.py`, был проведен AST-скан по директориям `src/core/target_sniping/`, `src/api/`, `src/risk/`.
**Результат:** Новых дубликатов методов внутри классов не найдено. Проблема в `execution.py` была единичной.

## 4. API Endpoint Audit (Сверка с DMarket API)
Полная сверка всех эндпоинтов, используемых в `src/api/dmarket_api_client/`.

| Эндпоинт | Используется в файле:строке | Статус | Доказательство (`documentation-grounding.md`) |
| --- | --- | --- | --- |
| `GET /account/v1/balance` | `account.py:41` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `GET /account/v1/balance` (найдено дословно). |
| `GET /exchange/v1/user-inventory` | `account.py:102,143` | ⚠️ Вероятно устарел | Не найден в swagger, существует `GET /marketplace-api/v2/user/inventory` (Cursor pagination). Требует миграции на v2. |
| `GET /marketplace-api/v1/user-offers/closed` | `offers.py:132` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `GET /marketplace-api/v1/user-offers/closed` (найдено дословно). |
| `GET /marketplace-api/v1/user-targets` | `targets.py:111` | ⚠️ Вероятно устарел | Не найден в swagger, существует `GET /marketplace-api/v2/user/targets` ("List user targets NEW"). Требует миграции на v2. |
| `GET /marketplace-api/v2/offers` | `market.py:51` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `GET /marketplace-api/v2/offers` (найдено дословно). |
| `GET /marketplace-api/v2/user/offers` | `offers.py:33,167` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `GET /marketplace-api/v2/user/offers` (найдено дословно). |
| `GET /trade-aggregator/v1/last-sales` | `market.py:131` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `GET /trade-aggregator/v1/last-sales` (найдено дословно). |
| `PATCH /exchange/v1/offers-buy` | `targets.py:100` | Подтверждён | URL: https://docs.dmarket.com/v1/swagger.html Цитата: `PATCH /exchange/v1/offers-buy` (найдено дословно). |

## 5. Security-раздел
- **Semgrep (297 правил)**: `0` находок. Основная кодовая база защищена от типовых инъекций, утечек секретов и небезопасных вызовов (`unsafe eval`). 
- Главный security/risk вектор сейчас — это бизнес-логика (отсутствие проверки замороженного баланса), а не технические уязвимости кода (OWASP).

## 6. Мёртвый код (Требует верификации)
- **vulture** (с порогом `min-confidence 60`) выдал **477 строк** кандидатов.
- **Примеры кандидатов**: неиспользуемые переменные в старых стратегиях (`src/_archived/pair_trading.py`), неиспользуемые классы (`RareValuationEngine`), методы байесовской статистики (`src/analysis/algo_pack/bayesian_stats.py: update_batch`).
- **Статус**: Необходима ручная/агентская сверка (в рамках отдельного `bug-hunt-loop`), чтобы отсеять ложноположительные срабатывания.

## Extended Documentation Cross-Check (Phase 1-2)
- **Scope**: Scanned entire `src/` (excluding `dmarket_api_client`) for direct HTTP calls and DMarket API payload fields (`trade_protected`, `FinalizationTime`, `priceCents`, `offerId`, etc.).
- **Findings**:
  - **No Undocumented Endpoints**: All API requests strictly route through `dmarket_api_client.make_request`. The only exception is `src/utils/clock_sync.py`, which correctly uses a safe `HEAD` request to `/account/v1/balance` to sync headers.
  - **Field Type Coercion**: [NOT_VERIFIED] The conclusion that "DMarket API correctly documents `priceCents` and `FinalizationTime` as strings" was based on a fetched document that has since been proven to be an alternative/anti-bot variant, not the canonical documentation. The factual observation about the codebase remains true: `priceCents` is safely cast via `int(...)` and `FinalizationTime` is stored via SQLite's `REAL` column affinity. However, whether the *actual* DMarket API schema types them as strings or numbers requires independent verification against the real documentation.
  - **Result**: No new API-related bugs found outside the API client layer. The abstraction holds.

## Updated Refactoring Priorities (Phase 3)
1. **`src/core/target_sniping/cycle_orchestrator.py`** 
   - **Status**: Pure Technical Debt (Complexity only)
   - **Complexity**: `_stage_scan` is E (34).
   - **Action**: High priority for decomposition. Split target matching logic.
2. **`src/db/price_history/core.py`**
   - **Status**: Pure Technical Debt
   - **Complexity**: `_init_schemas` is C (11).
   - **Action**: Medium priority. Schema initialization is lengthy but static; could be extracted to separate migration/schema scripts.
3. **`src/api/dmarket_api_client/core.py`**
   - **Status**: Skip for now
   - **Complexity**: `__init__` is C (16).
   - **Action**: Managing crypto keys (Ed25519) and conditional Rust imports in `__init__` creates high structural complexity but tearing it apart risks breaking state invariants. Low ROI for refactoring right now.
