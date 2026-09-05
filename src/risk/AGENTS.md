# Risk Subsystem — Subsystem Knowledge

## Архитектура и Роли
Папка `src/risk/` содержит все модули, отвечающие за управление рисками, обнаружение аномалий (пампов), управление портфелем и обработку инцидентов. 

**Центральный оркестратор:**
- `risk_manager.py` — главный класс `RiskManager`, который объединяет проверки из остальных модулей и вызывается в горячем контуре перед покупкой.

**Модули защиты и проверок:**
- `pump_detector.py` — алгоритмы выявления пампа цен (чтобы не купить раздутый предмет).
- `price_validator.py` — проверка арбитражного окна и расчет ожидаемого профита.
- `liquidity_manager.py` — отслеживание ликвидности предметов.
- `concentration_risk.py` — контроль доли одинаковых предметов в портфеле.
- `portfolio_optimizer.py` — оптимизация общего портфеля.
- `dynamic_manager.py`, `dynamic_fee.py` — динамическое управление комиссиями и ставками.

**Обработка сбоев и инцидентов:**
- `circuit_breaker_manager.py` — автоматическая остановка (circuit breaker) при серии ошибок.
- `incident_manager.py` — управление инцидентами.
- `error_reporter.py` — репортинг ошибок и сохранение exit-state.
- `fatal_errors.py` — классификация фатальных ошибок, связь с `utils.exceptions`.
- `lock_tracker.py` — отслеживание блокировок предметов (trade locks).
- `security_auditor.py` — аудит безопасности.

## Зависимости (Cross-Module)
*В папке отсутствует `__init__.py`, из-за чего автоматический анализ `archy` пропускает эту директорию. Связи подтверждены через RAW-grep.*

**Входящие вызовы (Кто использует `src/risk/`):**
- Точка входа `src/__main__.py`.
- Базовые модули `src/core/` (`resale_pipeline.py`, `autonomous_scanner.py`).
- Логика снайпинга `src/core/target_sniping/` (`core.py`, `scheduler.py`, `filter.py`, `validations.py`, `execution.py`, `resale_prod.py`).
- Модуль логов `src/utils/logging_setup.py`.

**Исходящие вызовы (От чего зависит `src/risk/`):**
- **Infrastructure:** `src.config` (через отложенные импорты), `src.db.price_history`.
- **API:** `src.api.dmarket_api_client` (вызовы API и ошибки CircuitOpenError).
- **Utils:** `src.utils.exceptions` (Unified exception hierarchy).

## Правила для агентов
- Все импорты внешних систем (Config, API, DB) внутри `risk` делаются локально в функциях или под `TYPE_CHECKING`, чтобы избежать циклических зависимостей, так как многие подсистемы импортируют сам `risk`.
- Не удалять и не отключать проверки в `risk_manager.py` и `pump_detector.py` — они критически важны для защиты капитала.

*Последнее обновление: 2026-09-01. Обновлять при каждом изменении в этой подсистеме.*
