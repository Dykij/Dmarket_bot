# Итоговый отчёт по трекам А и Б

## ТРЕК А: Сверка репозитория и метрик

### ФАЗА A0 — Структура репозитория
- RAW-анализ `git ls-tree -r main` и `git ls-tree -r feature/remove-oracles-formula-audit` показал, что файл `src/core/target_sniping/filter.py` **существует на обеих ветках**.
- Файлы `pricing.py` и `risk_manager.py` также существуют на своих местах.
- Вывод: Архитектурная диаграмма устарела/неполна и упускает `filter.py`. Прошлые сессии были абсолютно правы, ссылаясь на `filter.py:404/407/477`, где реально находятся флаги `has_cross_market`, `has_oracle_discount`, `has_reference_discount`.

### ФАЗА A1 — Статус Oracle (P0)
- RAW-команда `git show feature/remove-oracles-formula-audit:src/core/target_sniping/cycle_orchestrator.py` доказала, что строк `ctx.oracle = None` и `if not ctx.oracle: return` **НЕТ** на этой ветке. Они были удалены.
- Эти строки **ОСТАЛИСЬ на ветке main**.
- Вывод: Предыдущий health-check отчёт ошибся, прочитав состояние файла из ветки `main`, а не из `feature`-ветки, где исполняется GHA workflow.

### ФАЗА A2 — Источник метрик прогресса
- RAW-команда `git ls-tree main -- scripts/check_obi_progress.py` вернула пустоту, однако этот же скрипт **существует** на ветке `feature/remove-oracles-formula-audit`.
- Числа прогресса `11662` (scanned) и `30848` (total) являются подлинными. RAW-запрос `sqlite3 data/dmarket_state.db` вернул именно эти цифры. Предыдущий агент получил верные цифры из БД, но решил, что скрипта не существует, потому что искал его на ветке `main`.

### ФАЗА A3 — Критерии остановки
- Запуск `git grep` по ветке `feature/remove-oracles-formula-audit` показал, что внутри `scripts/check_obi_progress.py` прописаны корректные константы:
  `MIN_ENTRIES = 500`, `MIN_UNIQUE_TITLES = 50`.
- Никаких "50,000 / 500" в коде никогда не было. Вывод: прошлый агент просто **галлюцинировал** "50,000 / 500" в тексте своего Telegram-отчёта (text generation error), а не внёс вредоносный код. Откат не требуется, код в норме.

---

## ТРЕК Б: Миграция на Antigravity 2.0

### ФАЗА Б0 — Аудит MimoCode
- Конфиг `.mimocode/mimocode.jsonc` существовал. Реально были прописаны MCP-серверы: `sequential-thinking`, `fetch`, `sqlite`, `web-search`, `archy`, `context7`, `semgrep`, `shellcheck`, `in-memoria`.
- LSP-серверы: `bash-language-server`, `ruff-lsp`, `basedpyright-langserver`, `taplo`.

### ФАЗА Б1 и Б2 — Настройка cclsp и замер потребления
- Глобальный конфиг `~/.gemini/config/mcp_config.json` был пустым (0 байт). Я создал локальный `.agents/mcp_config.json` с подключением `cclsp`.
- Выполнен `npx cclsp setup`, сгенерирован конфиг `.claude/cclsp.json`. Я обновил его на использование `basedpyright-langserver` и `rust-analyzer`.
- Написан NodeJS скрипт для RAW-теста stdio-канала MCP: успешно получен список инструментов `find_definition`, `find_references` и выполнен вызов `find_references` для символа `has_cross_market`.
- **Замер потребления pyright:** `ps aux | grep basedpyright` показал потребление RSS в размере `212192 KB` (~212 МБ).
- Вывод: Заявления из отчёта Qwen про "2-4 ГБ" оказались сильно преувеличенными или относились к другой среде. Оставляем `basedpyright-langserver` как основной LSP-сервер (Pyrefly/ty пока не нужны для базового LSP).

### ФАЗА Б3 и Б4 — Skills, Rules и Безопасность
- Создан файл `.agents/rules/project_guardrails.md` с trigger `always_on`, куда перенесены критичные правила: "200 OK ≠ correct data", "RAW-требования", "запрет изменения торговой логики", "ограничения на git push". Antigravity 2.0 использует директорию `.agents/rules/` для enforcement'а ограничений.
- Скрипты MimoCode (типа `archy`, `semgrep`) частично покрываются встроенными skills Antigravity (вшиты глобально).

### ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ
- Торговая логика Dmarket_bot **НЕ** изменена.
- Ветка **НЕ** смержена, `main` содержит только infra-периметр.
- Треки выполнены независимо.
- Все цифры в отчёте взяты из RAW-вывода `git`, `sqlite3` и `ps aux` текущей сессии.
