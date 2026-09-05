# Core Subsystem — Subsystem Knowledge

## Архитектура и Роли
Папка `src/core/` содержит основные жизненные циклы (lifecycle) бота, логику сканирования и модули тестов/песочницы. Обратите внимание, что торговая логика вынесена в отдельную подсистему `target_sniping/` (её правила см. в `target_sniping/AGENTS.md`).

- **App Lifecycle:** 
  - `application.py`, `app_initialization.py`, `app_lifecycle.py`, `app_recovery.py`, `app_signals.py` — управление жизненным циклом демона, инициализация и Graceful Shutdown.
  - `app_notifications.py` — Notification management, управляет доставкой уведомлений админам.
- **Autonomous & Resale:**
  - `autonomous_scanner.py` — Главный цикл автономного сканирования.
  - `resale_pipeline.py` — Пайплайн полного цикла (Покупка -> Перепродажа).
- **Market Shadowing & Events:**
  - `shadow_engine.py`, `live_shadow.py` — Теневое выполнение и мониторинг рынка в реальном времени.
  - `event_shield.py`, `event_detection.py` — Событийная модель.
  - `item_intel.py`, `supply_tracking.py` — Анализ предметов и отслеживание предложения.
- **Инфраструктура:**
  - `config_manager.py` — Рантайм конфигурация.
  - `daily_briefing.py` — Ежедневная телеметрия и сбор статистики.
  - `sandbox_scenarios.py` — Песочница.

## Зависимости (Cross-Module)
*Данные подтверждены через RAW-grep и archy.*

**Входящие вызовы (Кто использует `src/core/`):**
- **Точка входа:** `src/__main__.py` (запуск `app_initialization`/`application`).
- **Telegram Bot:** `src/telegram/control_bot/commands/control.py`, `src/telegram/control_bot/commands/views.py`, `src/telegram/control_bot/callbacks.py`, `src/telegram/control_bot/state.py` и `src/telegram/notifier.py`.

**Исходящие вызовы (От чего зависит `src/core/`):**
- **Infrastructure:** `src.config` (глобально), `src.db.price_history`.
- **API & Risk:** `src.api.dmarket_api_client` (DMarket API), `src.risk.price_validator`, `src.risk.error_reporter`, `src.risk.fatal_errors`.
- **Utils:** `src.utils.decimal_helpers`, `src.utils.fee_utils`, `src.utils.vault`.
- **Analytics:** `src.analytics.self_reflection`.
- **Inventory:** `src.inventory_manager`.

*Примечание по `archy`: Внутри `src/core/` (без учёта подпапки `target_sniping`) файлы почти не зависят друг от друга напрямую — они в основном связывают внешние модули (Telegram, DB, API, Risk) в единый пайплайн.*

## Правила для агентов
- Любые изменения в `app_lifecycle.py` или `autonomous_scanner.py` требуют особой осторожности (т.к. они управляют стабильностью демона) и обязательного `Proceed` от пользователя перед коммитом.
- Торговую математику и снайпинг в этой папке не искать — она в `src/core/target_sniping/`.

*Последнее обновление: 2026-09-01. Обновлять при каждом изменении в этой подсистеме.*
