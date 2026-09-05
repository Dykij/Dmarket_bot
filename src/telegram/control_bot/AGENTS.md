# Telegram Control Bot Subsystem — Subsystem Knowledge

## Архитектура и Роли
Папка `src/telegram/control_bot/` содержит полноценного Telegram-бота для управления, мониторинга и настройки торгового демона в реальном времени.

**Ядро бота:**
- `bot.py` — конфигурация и инициализация `aiogram` бота и диспетчера.
- `lifecycle.py` — управление жизненным циклом (запуск, остановка демона).
- `__main__.py` — точка входа пакета.
- `state.py` — глобальное состояние (runtime state).

**Логика взаимодействия (UI):**
- `commands/` — папка с обработчиками команд (`control.py`, `views.py`, `test.py`, `utils.py`, `lifecycle.py`).
- `callbacks.py` — обработчики кнопок (inline callbacks).
- `callback_data.py` — структуры данных для коллбэков (фабрики).
- `keyboards.py` — генерация inline-клавиатур.
- `formatters.py` — форматирование текста сообщений (MarkdownV2).

**Механизмы надежности:**
- `error_handling.py` — глобальный перехват ошибок бота.
- `resilience.py` — механизмы отказоустойчивости.
- `filters.py` — фильтры сообщений (например, только для админов).
- `settings_fsm.py` — конечные автоматы (FSM) для настройки параметров через бота.

## Зависимости (Cross-Module)
*Связи подтверждены через RAW-grep и archy.*

**Входящие вызовы (Кто использует `control_bot`):**
- Прямых импортов из других бизнес-подсистем нет. Модуль запускается как самостоятельный процесс (`python -m src.telegram.control_bot`), а файл-фасад `src/telegram/control_bot.py` импортирует его для обратной совместимости.

**Исходящие вызовы (От чего зависит `control_bot`):**
- **Core / Trading:** `src.core.target_sniping.core` (`SnipingLoop`), `src.core.resale_pipeline` (`ResalePipeline`).
- **Infrastructure:** `src.config` (глобальный конфиг), `src.db.price_history` (база истории цен).
- **API:** `src.api.dmarket_api_client`.
- **Analytics:** `src.analytics.self_reflection`.
- **Utils:** `src.utils.clock_sync`, `src.utils.logging_setup`, `src.utils.vault`.
- **Telegram (внутренние):** `src.telegram.notifier` (отправка уведомлений об ошибках).

*Внутренняя структура (archy):* Архитектура бота плотно связана внутренними импортами (`commands` -> `keyboards`, `formatters`; `bot.py` -> `commands`, `callbacks`, `lifecycle` и т.д.). Отдельно стоит отметить, что `lifecycle.py` существует как в корне `control_bot/`, так и в `commands/lifecycle.py` для обработки UI-команд управления.

## Правила для агентов
- Бот использует асинхронный фреймворк (`aiogram`). Любые изменения в коллбэках должны учитывать `callback_data` (Factory).
- Модуль имеет прямой доступ к управлению `SnipingLoop` и `ResalePipeline` — все команды управления (`start`, `stop`, `force_sell`) должны строго проходить через фильтр администраторов (`filters.py`).

*Последнее обновление: 2026-09-01. Обновлять при каждом изменении в этой подсистеме.*
