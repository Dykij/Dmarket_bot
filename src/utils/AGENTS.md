# Utils Subsystem — Subsystem Knowledge

## Архитектура и Роли
Папка `src/utils/` содержит вспомогательные утилиты, кросс-системные инструменты и инфраструктурный код, используемый во всём приложении. 
Все модули здесь утилитарны, не содержат бизнес-логики и могут вызываться из любого места.

**Основные утилиты:**
- `charts.py` — инструменты для построения графиков.
- `clock_sync.py` — синхронизация времени (важно для API-запросов и подписей).
- `config_watcher.py` — отслеживание изменений конфигурации.
- `database.py` — базовая обертка над БД (исторически или для общих нужд).
- `decimal_helpers.py` — помощники для точных вычислеваний с `Decimal`.
- `exceptions.py` — единая иерархия исключений бота (CircuitBreakerOpen, RateLimitExceeded, TradingError и т.д.).
- `fee_utils.py` — утилиты для расчета комиссий DMarket.
- `health_server.py` — HTTP/FastAPI сервер для health-чеков (Docker/K8s).
- `logging_setup.py` — конфигурация логирования (structlog или стандартный logging).
- `query_profiler.py` — профилировщик SQL-запросов.
- `vault.py`, `vault_client.py` — интеграция с Vault для управления секретами и ключами API.

## Зависимости (Cross-Module)
*В папке отсутствует `__init__.py`, из-за чего автоматический анализ `archy` пропускает эту директорию (`nodes: []`). Связи подтверждены через RAW-grep.*

**Входящие вызовы (Кто использует `utils`):**
- **Главная точка входа:** `src/__main__.py`.
- **Target Sniping:** Множество вызовов из `src/core/target_sniping/` (`resale_dry.py`, `cycle_orchestrator.py`, `telemetry.py`, `demand_strategy.py`, `position_guard.py`, `filter.py`, `ranking.py`, `resale_prod.py`).
- **Базовые циклы:** `src/core/shadow_engine.py`, `src/core/resale_pipeline.py`, `src/core/autonomous_scanner.py`.
- **API & Risk:** `src/risk/fatal_errors.py` (исключения), `src/api/dmarket_api_client/core.py`.
- **Telegram Bot:** `src/telegram/control_bot/` (`formatters.py`, `__main__.py`, `commands/utils.py`, `commands/views.py`, `resilience.py`).

**Исходящие вызовы (От чего зависит `utils`):**
- **Infrastructure:** `src.config`, `src.db.price_history` (из `charts.py`).
- *Внутренние зависимости:* `vault.py` импортирует `vault_client.py`. В остальном утилиты независимы.

## Правила для агентов
- **Не добавлять бизнес-логику:** Эта директория только для чистых функций и изолированных классов-помощников.
- **Минимум внешних зависимостей:** Утилиты не должны зависеть от API или торговых модулей (кроме конфигов).
- При добавлении новых исключений, добавлять их только в `exceptions.py`, чтобы сохранять единую иерархию (важно для перехвата в `risk/fatal_errors.py`).

*Последнее обновление: 2026-09-01. Обновлять при каждом изменении в этой подсистеме.*
