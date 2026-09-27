# Root-Cause Analysis (2026-09-27)

## 1. usdAvailableToWithdraw
- **Причина**: DMarket Swagger Schema v2.0.0 (endpoint `/account/v1/balance`) явно задаёт тип `string` для полей `usd`, `usdAvailableToWithdraw`, `dmc`, `dmcAvailableToWithdraw` абсолютно симметрично. В корневом описании ответа (`summary`) указано: "The response format is in coins (cents for USD, dimoshi for DMC)". Из структуры схемы однозначно следует, что оба USD-поля используют единый формат (центы).
- **Связано с документацией/API DMarket**: ДА.
- **Следующее действие**: Считать формат (центы, тип string) подтверждённым официальной схемой. Парсить `usdAvailableToWithdraw` аналогично `usd` без необходимости ждать non-DRY_RUN теста на проде.

## 2. msgspec отсутствует в requirements.txt
- **Причина**: Пакет `msgspec` реально используется в коде для оптимизации (импорты в `src/api/dmarket_api_client/core.py`, `src/models/market.py`, `tests/unit/test_market_models.py`), однако история коммитов показывает, что он **никогда** не добавлялся в `requirements.txt`.
- **Связано с документацией/API DMarket**: НЕТ. Это локальная недоработка (забыли обновить список зависимостей при добавлении импорта).
- **Следующее действие**: Добавить `msgspec` в `requirements.txt`.

## 3. radon не установлен в .venv
- **Причина**: Зависимость `radon==6.0.1` явно прописана в файле `requirements-dev.txt`. Её отсутствие в `.venv` означает, что при пересоздании виртуального окружения не была выполнена установка dev-зависимостей (`pip install -r requirements-dev.txt`).
- **Связано с документацией/API DMarket**: НЕТ. Чисто локальная инфраструктурная ошибка (пропущенный шаг настройки окружения).
- **Следующее действие**: Выполнить `pip install -r requirements-dev.txt`.

## 4. stop-criteria-guard не вызывается
- **Причина**: Сравнение конфигураций (`agent.md`) показывает идентичный и корректный frontmatter, включая `subagent: true`. Строка про лимиты контекста взята **буквально из системного промпта** (блок `<subagents>`) текущей сессии:
  ```text
  The following items were excluded due to context budget limits: stop-criteria-guard

  After launching a subagent, you do NOT need to poll or check your inbox in a loop.
  ```
  Это не гипотеза, а явно задекларированное платформой состояние для данной сессии.
- **Связано с документацией/API DMarket**: НЕТ. Это ограничение платформы Antigravity.
- **Следующее действие**: Учитывать это платформенное ограничение; оптимизировать контекст сессии или вызывать его как отдельную сущность, если платформа позволит.

## 5. Hook runner молчит на реальных tool-call'ах
- **Причина**: Текущая версия платформы — `2.15.0`. RAW-запрос через `context7` (MCP) к базе документации `/websites/antigravity_google` по запросу `changelog releases version 2.16 2.17` вернул:
  ```text
  No documentation in "/websites/antigravity_google" matched this query.
  ```
  Запросы по ключевым словам `PreToolUse PostToolUse RAW_OUTPUT.log` находят только документацию формата хуков (в `hooks.md`), но без упоминания багфиксов. Таким образом, новой версии с потенциальным фиксом в публичном доступе не обнаружено.
- **Связано с документацией/API DMarket**: НЕТ.
- **Следующее действие**: Зафиксировать как открытый баг платформы Antigravity (ждёт апстрим-фикса). Оставить статус `ACCEPTED/UNRESOLVED`.

---

## Задачи, ожидающие решения пользователя (без анализа)
Следующие пункты из старого отчёта являются чистыми решениями и ждут выбора:
- **Пункт 3**: Незакоммиченное рабочее дерево (выбор: stash, commit или discard).
- **Пункт 4**: Два отключённых плагина (включить или оставить как есть).
- **Пункт 5**: Выбор варианта по H27.
