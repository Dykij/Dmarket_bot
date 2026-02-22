# 🔍 ПОЛНЫЙ АУДИТ ПРОЕКТА D:\Dmarket_bot

**Дата аудита:** 2026-02-22  
**Роль:** Senior DevOps & System Architect  
**Цель:** Выявить мусор, дубли, мёртвые модули и угрозы безопасности

---

## 📋 1. ГЛОБАЛЬНАЯ КАРТА ПРОЕКТА (Root Level Map)

### 📁 Корневые директории (20 штук)

| Папка | Назначение | Статус | Рекомендация |
|-------|-----------|--------|-------------|
| `src/` | Основной код бота (32 подпакета) | ✅ Активна | Ядро проекта |
| `tests/` | Тесты (37 подпапок, 37 файлов) | ⚠️ Раздуто | Ревизия нужна |
| `config/` | YAML конфиги, фильтры, промтеус | ✅ Активна | OK |
| `data/` | ML модели, persistence | ✅ Активна | OK, но см. ниже |
| `logs/` | 1 файл: `cold_cycle.log` (2 KB) | ✅ Чисто | OK |
| `docs/` | 35 документов + `knowledge/` | ⚠️ Раздуто | Архивация legacy |
| `docs-site/` | MkDocs сайт документации | 🔶 Сомнительно | Не используется |
| `docs_archive/` | SYSTEM_FLOW.md + Mermaid диаграммы | 🔶 Архив | Можно убрать |
| `scripts/` | 68 скриптов автоматизации | ⚠️ КРИТИЧЕСКИ РАЗДУТО | Чистка |
| `alembic/` | Миграции БД (Alembic) | ✅ Активна | OK |
| `grafana/` | Dashboards + provisioning | 🔶 Инфра | OK если мониторинг нужен |
| `k8s/` | Kubernetes манифесты | 🔶 Инфра | OK если деплоите в k8s |
| `n8n/` | N8n workflows | 🔶 Сомнительно | Проверить нужность |
| `nginx/` | nginx.conf + SSL папка | 🔶 Инфра | OK если reverse proxy |
| `examples/` | 3 примера кода | 🔶 Dev | Можно архивировать |
| `dev_tools/` | 1 PowerShell скрипт | ❌ Почти пуста | На удаление |
| `memory/` | `checkpoints/` - ПУСТО | ❌ Пуста | На удаление |
| `venv_debug/` | Виртуальное окружение для отладки (4.7 MB) | ❌ Мусор | На удаление |
| `.github/` | CI/CD + Dependabot | ✅ Активна | OK |
| `.mypy_cache/` | Кеш mypy | ❌ Кеш | На удаление |
| `__pycache__/` | Python bytecode кеш в корне | ❌ Кеш | На удаление |

### 📄 Корневые файлы (46 штук)

| Файл | Размер | Статус | Рекомендация |
|------|--------|--------|-------------|
| **⚠️ `history_dump.txt`** | **116 MB** | ❌ МУСОР | **УДАЛИТЬ НЕМЕДЛЕННО** |
| `openapi.json` | 118 KB | 🔶 Справка | Перенести в docs/ |
| `poetry.lock` | 222 KB | ⚠️ Конфликт | Конфликт с requirements.txt |
| `requirements.txt` | 11.5 KB | ✅ Активен | OK |
| `requirements.in` | 5 KB | ✅ Активен | OK |
| `pyproject.toml` | 163 B | ✅ Активен | OK |
| `Makefile` | 21 KB | ✅ Активен | OK |
| `Dockerfile` | 3.9 KB | ✅ Активен | OK |
| `Dockerfile.dev` | 2.5 KB | ✅ Активен | OK |
| `docker-compose.yml` | 583 B | ✅ Активен | OK |
| `docker-compose.prod.yml` | 7.2 KB | ✅ Активен | OK |
| `docker-compose.monitoring.yml` | 1.8 KB | ✅ Активен | OK |
| `alembic.ini` | 3.5 KB | ✅ Активен | OK |
| `pytest.ini` | 499 B | ✅ Активен | OK |
| `.pre-commit-config.yaml` | 7.2 KB | ✅ Активен | OK |
| `.gitignore` | 651 B | ✅ Активен | OK |
| `.dockerignore` | 1.8 KB | ✅ Активен | OK |
| `.editorconfig` | 928 B | ✅ Активен | OK |
| `.ruff.toml` | 58 B | ✅ Активен | OK |
| `.secrets.baseline` | 1.7 KB | ✅ Активен | OK |
| `skillkit.yaml` | 48 B | 🔶 Неясно | Проверить |
| `.env` | 368 B | ⚠️ БЕЗОПАСНОСТЬ | Содержит реальные ключи! |
| `.env.example` | 17 KB | ✅ Шаблон | OK |
| **Debug-файлы (7 штук):** | | | |
| `debug_auth_python.py` | 2.5 KB | ❌ Мусор | Удалить |
| `debug_auth_v2.py` | 2.4 KB | ❌ Мусор | Удалить |
| `debug_auth_v3.py` | 3.3 KB | ❌ Мусор | Удалить |
| `debug_dmarket.py` | 3 KB | ❌ Мусор | Удалить |
| `debug_env_trace.py` | 660 B | ❌ Мусор | Удалить |
| **Fix-файлы (4 штуки):** | | | |
| `fix_ai_damage.py` | 1.9 KB | ❌ Мусор | Удалить |
| `fix_ai_damage_final.py` | 2.1 KB | ❌ Мусор | Удалить |
| `fix_ai_damage_v2.py` | 1.3 KB | ❌ Мусор | Удалить |
| `fix_rust_damage.py` | 1 KB | ❌ Мусор | Удалить |
| **Другие одноразовые:** | | | |
| `cleanup_v2.py` | 1.7 KB | ❌ Мусор | Удалить |
| `test_error.py` | 122 B | ❌ Мусор | Удалить |
| `test_results.xml` | 1.7 KB | ❌ Артефакт | Удалить |
| `verify_keys.py` | 874 B | ❌ Мусор | Удалить |
| `adaptive_controller.py` | 3 KB | ⚠️ Вне src/ | Перенести или удалить |
| `ai.py` | 1.8 KB | ⚠️ Вне src/ | Перенести или удалить |
| `bot.py` | 1.8 KB | ⚠️ Вне src/ | Перенести или удалить |
| `dmarket_api.py` | 3.5 KB | ⚠️ Вне src/ | Перенести или удалить |

---

## 🔍 2. ПОИСК СКРЫТЫХ ДУБЛЕЙ

### 2.1 Дублирующиеся конфигурации (3 штуки!)

| Файл | Роль | Конфликт |
|------|------|----------|
| `src/core/config.py` | Константы (Fees, Games, Trading thresholds) | Жёсткие значения |
| `src/core/config_manager.py` | Singleton загрузчик .env | Простой dict |
| `src/utils/config.py` | **800+ строк** полной конфигурации (dataclasses) | ОСНОВНОЙ конфиг |
| `config/config.yaml` | YAML с настройками | Файл-конфигурация |
| `src/telegram_bot/config_data.py` | Конфигурация Telegram бота | Отдельный |

**⚠️ ПРОБЛЕМА:** Три разных конфиг-системы (`Config`, `ConfigManager`, `AppConfig`) пересекаются. `src/main.py` использует `ConfigManager`, а `containers.py` использует `Config` из `src/utils/config.py`. Это рецепт для рассинхронизации.

**Рекомендация:** Оставить ТОЛЬКО `src/utils/config.py` как Single Source of Truth. `config_manager.py` — удалить или рефакторить как обёртку.

### 2.2 Дублирующиеся папки

| Дубль 1 | Дубль 2 | Проблема |
|---------|---------|----------|
| `src/arbitrage/` | `src/dmarket/arbitrage/` | **ДВА арбитражных модуля!** |
| `src/integration/` | `src/integrations/` | **Две папки интеграций!** |
| `src/dashboard/` | `src/web_dashboard/` | **Два дашборда!** + `src/tui/` |
| `scripts/` (корень) | `src/scripts/` | **Два набора скриптов!** |
| `src/mcp_server/skillsmp_client.py` | `src/integrations/skillsmp_client.py` | **Идентичные файлы!** |

### 2.3 Кеш-директории (87 шт. `__pycache__` = ~9.75 MB)

Найдено **87 папок `__pycache__`** по всему проекту, суммарно ~10 MB. Содержат `.pyc` кеши для Python 3.11 и 3.14 одновременно (значит, проект запускался на разных версиях).

**Нет `.pytest_cache`** — чисто. **Нет `.idea`** — чисто.

---

## 🧪 3. АНАЛИЗ НЕИСПОЛЬЗУЕМЫХ МОДУЛЕЙ

### 3.1 Мёртвые модули (НЕ импортируются в основном коде)

| Модуль | Файлы | Импортируется из основного кода? | Вердикт |
|--------|-------|--------------------------------|---------|
| `src/tui/` | `dashboard.py` (Textual TUI) | ❌ НЕТ | 🔴 МЁРТВЫЙ |
| `src/web_dashboard/` | `app.py` (FastAPI stub) | ❌ НЕТ | 🔴 МЁРТВЫЙ |
| `src/dashboard/` | `app.py` (Streamlit dash) | ❌ НЕТ | 🔴 МЁРТВЫЙ |
| `src/mcp_server/` | 4 файла MCP серверов | ❌ НЕТ (0 импортов) | 🔴 МЁРТВЫЙ |
| `src/knowledge_base/` | 6 md файлов + history | ❌ НЕТ (данные, не код) | 🟡 Знания |
| `src/strategies/` | `pairs_trading.py` | ❌ Проверить | 🟡 Возможно мёртвый |
| `src/testing/` | `prompt_testing.py` | ❌ Dev-утилита | 🟡 Dev |
| `src/copilot_sdk/` | 7 файлов | ✅ Из `src/cli/copilot_cli.py` | 🟢 Активен (CLI) |

### 3.2 Активные модули (используются в HFT-цикле)

| Модуль | Импортируется из | Роль в HFT |
|--------|-----------------|------------|
| `src/ml/` | `price_analyzer.py`, `ai_brain_handler.py`, `autopilot_orchestrator.py` | ML-предсказания |
| `src/dmarket/` | Ядро бота | API клиент, арбитраж |
| `src/core/` | Везде | Конфиг, события, безопасность |
| `src/utils/` | Везде | Утилиты, БД, кеш |
| `src/telegram_bot/` | Точка входа | Бот-интерфейс |
| `src/arbitrage/` | AI Unified Arbitrage | Арбитражная логика |
| `src/waxpeer/` | Кросс-платформа | P2P арбитраж |
| `src/monitoring/` | Мониторинг | Prometheus метрики |
| `src/trading/` | Торговля | Ордера, исполнение |

---

## 🔐 4. БЕЗОПАСНОСТЬ И КОНФИГИ

### ⚠️ КРИТИЧЕСКАЯ ПРОБЛЕМА: `.env` в РЕПОЗИТОРИИ

```
DMARKET_PUBLIC_KEY=b4674c401c4466f729e5ab7ce9f257be159b5bb2e97e97947449bca19cf16a95
DMARKET_SECRET_KEY=09ebba7b8f51b13f50d82fd9bb49f16ac23bdb783189c8957675e44932e4d3aa...
TELEGRAM_BOT_TOKEN=8294400223:AAGDPOpuZ6hvcOEVtjNZ0y2xpRfHbutISx0
TELEGRAM_CHAT_ID=458765683
```

**Хотя `.env` в `.gitignore`**, файл СУЩЕСТВУЕТ локально с **реальными ключами API и токеном Telegram**.

**Рекомендации по безопасности:**
1. ✅ `.gitignore` содержит `.env` — хорошо
2. ✅ `.secrets.baseline` присутствует (detect-secrets) — хорошо
3. ⚠️ Убедитесь, что `.env` **НИКОГДА** не попадал в git history
4. ⚠️ `nginx/ssl/` — папка пуста (заглушка под сертификаты), OK
5. ✅ Нет `.key` или `.pem` файлов в проекте
6. ⚠️ `data/bot_persistence.pickle` — потенциальное pickle-injection, если из ненадёжного источника

---

## 🗂️ 5. ПОДРОБНЫЙ АНАЛИЗ КЛЮЧЕВЫХ ПАПОК

### 5.1 `data/` — Данные

| Файл | Размер | Назначение |
|------|--------|-----------|
| `bot_persistence.pickle` | 132 B | Состояние Telegram бота |
| `label_encoder.pkl` | 659 B | ML LabelEncoder |
| `price_model.pkl` | 95 KB | ML модель цен |
| `ml_training/real_data/` | Пуста | Заготовка для тренировочных данных |
| `notifications/` | Пуста | Заготовка для нотификаций |

### 5.2 `logs/` — Логи

Всего 1 файл: `cold_cycle.log` (2 KB). **Ротация чистая.** `.gitignore` исключает `*.log` и `logs/`.

### 5.3 `docs/` — Документация (35 файлов)

**Актуальные (12):**
- `ARBITRAGE.md` (29 KB) — спецификация арбитража
- `DMARKET_API_FULL_SPEC.md` (45 KB) — полная спецификация API
- `QUICK_START.md` (36 KB) — гайд по запуску
- `SECURITY.md` (25 KB) — безопасность
- `TROUBLESHOOTING.md` (18 KB) — устранение проблем
- `CONTRACT_TESTING.md` (15 KB) — контрактные тесты
- `DATABASE_MIGRATIONS.md` (17 KB) — миграции
- `DEPENDENCY_INJECTION.md` (11 KB) — DI система
- `TELEGRAM_BOT_API.md` (47 KB) — Telegram API
- `STEAM_API_REFERENCE.md` (23 KB) — Steam API
- `WAXPEER_API_SPEC.md` (17 KB) — Waxpeer API
- `WEBSOCKET_FALLBACK.md` (6 KB) — WebSocket фоллбэк

**Legacy/Архивировать (12):**
- `ARCHITECTURE.md`, `ARCHITECTURE_MANIFESTO.md`, `ARCHITECTURE_V5.md` — устаревшие архитектуры
- `PROTOCOL_V5.1.md` — старый протокол
- `HISTORY.md`, `DEVELOPER_LOG.md`, `LAST_SESSION_REPORT.md` — исторические заметки
- `FINAL_AUDIT_REPORT.md`, `SUMMARY_AUDIT.md` — старые аудиты
- `AUTONOMOUS_BACKLOG.md` — бэклог
- `v3_shared_memory_arch.md` — устаревшая архитектура v3
- `SYSTEM_MANIFEST.json` — старый манифест

**Под вопросом (11):**
- `AGENTS_ROSTER.md`, `agents.md`, `CLAUDE.md` — агенты
- `MCP_SERVERS_GUIDE.md`, `SKILLSMP_IMPLEMENTATION.md` — MCP (мёртвые модули)
- `TEMPORAL_WORKFLOWS.md` — Temporal (используется?)
- `API_COMPLETE_REFERENCE.md` — дубль с DMARKET_API_FULL_SPEC?
- `DMARKET_API_V1_SPEC.md` — старая v1, заменена на полную
- `deployment.md`, `project_structure.md` — инфра

### 5.4 `tests/` — КРИТИЧЕСКИ РАЗДУТО

**37 подпапок тестов** — это ненормально. Многие содержат заброшенные тесты:

| Подпапка | Статус | Комментарий |
|----------|--------|------------|
| `api/`, `core/`, `dmarket/`, `trading/`, `telegram_bot/`, `utils/` | ✅ | Основные unit-тесты |
| `unit/`, `integration/`, `e2e/`, `smoke/` | ✅ | Стандартные категории |
| `bdd/`, `contracts/`, `property_based/` | 🟡 | Продвинутые, но проверить |
| `perf/`, `performance/` | ⚠️ **ДУБЛЬ!** | Две папки перфоманса |
| `load/`, `stress_v4_system.py`, `endurance_test.py` | ⚠️ | Нагрузочные (3 дубля?) |
| `comprehensive/`, `comprehensive_system_audit.py` | ⚠️ | Аудит-скрипты |
| `copilot_sdk/`, `mcp_server/`, `web_dashboard/` | ❌ | Тесты МЁРТВЫХ модулей |
| `ml/`, `analytics/`, `models/`, `portfolio/` | 🟡 | ML тесты — проверить |
| `regression/`, `reliability/`, `production/` | 🟡 | Проверить актуальность |
| `reporting/`, `monitoring/`, `security/` | 🟡 | Проверить актуальность |
| `waxpeer/` | ✅ | Тесты Waxpeer |
| `scripts/` | ⚠️ | Тесты скриптов |
| `data/`, `fixtures/`, `cassettes/` | ✅ | Тестовые данные |

Одноразовые скрипты в корне `tests/`:
- `kamikaze.py` (14 байт!) — пустой
- `arkady_pydantic_test.py` — одноразовый
- `omega_test.py` — одноразовый
- `stress_v4_system.py` — одноразовый
- `validate_phase7.py` — одноразовый
- `reload_sandbox.py` — одноразовый

### 5.5 `scripts/` — 68 СКРИПТОВ (КРИТИЧЕСКИ РАЗДУТО)

**Необходимые для жизненного цикла (12):**
- `run_bot.py`, `restart_bot.py` — запуск бота
- `health_check.py`, `check_health.ps1` — здоровье системы
- `backup_database.py` — бэкапы БД
- `init_db.py`, `init_db.sql`, `init_cross_platform_db.sql` — инициализация БД
- `create_env_file.py` — создание .env
- `rotate_keys.py`, `encrypt_secrets.py` — безопасность ключей
- `deploy.sh` — деплой

**Полезные утилиты (10):**
- `check_balance.py`, `check_offers.py` — проверки API
- `check_dependencies.py`, `validate_config.py` — валидация
- `generate_changelog.py` — генерация CHANGELOG
- `safe_migrate.py`, `migrate_users.py` — миграции
- `log_compressor.py` — сжатие логов
- `monitor_performance.py`, `performance_benchmark.py` — перфоманс

**Одноразовые / мусорные (46):**
- `analyze_improvements.py`, `analyze_prices.py` — анализы
- `auto_fix.py`, `restructure.py` — рефакторинг
- `broadcast_log.py`, `live_logger.py` — логгирование
- `check_cyrillic.py` — поиск кириллицы
- `clear_bot_updates.py` — одноразовая очистка
- `collect_ml_training_data.py`, `train_ml_model.py` — ML пайплайн (нужен ли?)
- `coverage_check.py`, `mutation_testing.py` — тестирование (CI уже делает?)
- `debug_suite.py` — отладка
- `find_long_functions.py`, `generate_refactoring_todo.py` — рефакторинг
- `generate_skills_report.py`, `validate_skills.py`, `validate_all_skills.py` — Skills (нужны?)
- `get_chat_id.py` — одноразовый
- `github_actions_monitor.py` (32 KB!), `github_forge.py`, `github_sync.py` — GitHub
- `init_session.ps1` — одноразовый
- `memory_overload.py` — отладка
- `migrate_to_secrets.py` — одноразовая миграция
- `native_audit.py`, `nightly_council.py` — аудит
- `profile_scanner.py` — профилирование
- `run_archivist.py` — архивация
- `run_module_tests.py`, `skills_test_runner.py` — тесты (pytest уже!)
- `rust_benchmark.py` — Rust бенчмарк
- `safe_commit.py`, `self_check.py`, `exec_guard.py` — утилиты
- `security_scan_skills.py`, `storm_security.py` — безопасность
- `sentry_cleanup.py` — Sentry
- `skills_cli.py`, `skills_composition.py` — Skills
- `system_health_audit.py` — аудит
- `validate_marketplace.py` — маркетплейс
- `generate_test_template.py` — генерация тестов
- `pre_commit_check.sh`, `run_monitor.sh` — shell (CI?)

### 5.6 `src/rust_core/` — Rust компиляция

| Файл | Размер | Комментарий |
|------|--------|------------|
| `target/` | **572 MB** | ⚠️ Артефакты компиляции |
| `Cargo.lock` | 63 KB | Lock-файл |
| `Cargo.toml` | 611 B | Конфигурация |
| `src/rust_core.pyd` | 4.7 MB | Скомпилированный модуль |

**`target/` = 572 MB — это 95% веса проекта!** Содержит только `release/` (1835 файлов). Нужно чистить `cargo clean` после каждой успешной сборки, или добавить `target/` в `.gitignore` (уже есть: `src/rust_core/target/` ✅).

---

## 🧹 ИТОГОВЫЙ ОТЧЁТ (Clean-Up List)

### 🔴 СПИСОК "НА УДАЛЕНИЕ" (100% не нужны)

**Корневые файлы (экономия: ~116 MB):**
```
❌ history_dump.txt              # 116 MB (!) — дамп истории
❌ debug_auth_python.py          # Отладочный скрипт
❌ debug_auth_v2.py              # Отладочный скрипт
❌ debug_auth_v3.py              # Отладочный скрипт
❌ debug_dmarket.py              # Отладочный скрипт
❌ debug_env_trace.py            # Отладочный скрипт
❌ fix_ai_damage.py              # Одноразовый fix
❌ fix_ai_damage_v2.py           # Одноразовый fix
❌ fix_ai_damage_final.py        # Одноразовый fix
❌ fix_rust_damage.py            # Одноразовый fix
❌ cleanup_v2.py                 # Одноразовый cleanup
❌ test_error.py                 # Пустой тест
❌ test_results.xml              # Артефакт тестов
❌ verify_keys.py                # Одноразовая проверка
❌ adaptive_controller.py        # Вне src/ — дубль или заброшен
❌ ai.py                         # Вне src/ — дубль или заброшен
❌ bot.py                        # Вне src/ — дубль или заброшен
❌ dmarket_api.py                # Вне src/ — дубль или заброшен
```

**Директории (экономия: ~587 MB):**
```
❌ venv_debug/                   # 4.7 MB — отладочный venv
❌ memory/                       # Пустая папка
❌ dev_tools/                    # 1 скрипт, бесполезен
❌ __pycache__/ (в корне)        # Кеш
❌ .mypy_cache/                  # Кеш mypy
❌ src/rust_core/target/         # 572 MB — артефакты Rust
```

**Кеш — массовая очистка (экономия: ~10 MB):**
```
❌ Все 87 папок __pycache__/     # Python bytecode кеш
```

**Мёртвые модули в src/ (если подтвердите):**
```
❌ src/tui/                      # 1 файл, не используется
❌ src/web_dashboard/            # 1 файл (FastAPI stub), не используется
❌ src/dashboard/                # 1 файл (Streamlit), не используется
❌ src/mcp_server/               # 4 файла, 0 импортов из основного кода
❌ src/knowledge_base/           # Markdown файлы, не код
❌ src/strategies/               # 1 файл, проверить использование
```

**Мёртвые тесты для мёртвых модулей:**
```
❌ tests/copilot_sdk/            # Тесты для copilot_sdk (если удаляете SDK)
❌ tests/mcp_server/             # Тесты для MCP (мёртвый модуль)
❌ tests/web_dashboard/          # Тесты для web_dashboard (мёртвый модуль)
❌ tests/kamikaze.py             # 14 байт, пустой файл
❌ tests/arkady_pydantic_test.py # Одноразовый тест
❌ tests/omega_test.py           # Одноразовый тест
❌ tests/stress_v4_system.py     # Одноразовый нагрузочный тест
❌ tests/validate_phase7.py      # Одноразовый тест
❌ tests/reload_sandbox.py       # Одноразовый скрипт
❌ tests/comprehensive_system_audit.py  # Аудит (не pytest тест)
```

### 🟡 СПИСОК "НА АРХИВАЦИЮ" (Историческая ценность)

```
📦 docs/ARCHITECTURE.md              → docs_archive/
📦 docs/ARCHITECTURE_MANIFESTO.md    → docs_archive/
📦 docs/ARCHITECTURE_V5.md           → docs_archive/
📦 docs/PROTOCOL_V5.1.md             → docs_archive/
📦 docs/HISTORY.md                   → docs_archive/
📦 docs/DEVELOPER_LOG.md             → docs_archive/
📦 docs/LAST_SESSION_REPORT.md       → docs_archive/
📦 docs/FINAL_AUDIT_REPORT.md        → docs_archive/
📦 docs/SUMMARY_AUDIT.md             → docs_archive/
📦 docs/AUTONOMOUS_BACKLOG.md        → docs_archive/
📦 docs/v3_shared_memory_arch.md     → docs_archive/
📦 docs/SYSTEM_MANIFEST.json         → docs_archive/
📦 docs/DMARKET_API_V1_SPEC.md       → docs_archive/ (заменён FULL_SPEC)
📦 docs/MCP_SERVERS_GUIDE.md         → docs_archive/ (мёртвый модуль)
📦 docs/SKILLSMP_IMPLEMENTATION.md   → docs_archive/ (мёртвый модуль)
📦 docs/TEMPORAL_WORKFLOWS.md        → docs_archive/
📦 examples/                         → docs_archive/examples/
📦 docs_archive/ (текущая)           → Объединить со всем выше
📦 openapi.json                      → docs/ или docs_archive/
```

### 🟢 РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ

#### 1. Структура проекта — убрать хаос

```
ТЕКУЩЕЕ СОСТОЯНИЕ:
├── 16 .py файлов в корне (мусор)
├── 3 дашборда (tui/ + web_dashboard/ + dashboard/)
├── 2 арбитражных модуля (arbitrage/ + dmarket/arbitrage/)
├── 2 integration папки (integration/ + integrations/)
├── 2 scripts папки (scripts/ + src/scripts/)
├── 3 config системы (config.py + config_manager.py + utils/config.py)

ЦЕЛЕВОЕ СОСТОЯНИЕ:
├── src/                        # Только код
│   ├── core/                   # Конфиг, события, безопасность
│   ├── dmarket/                # DMarket API + арбитраж
│   ├── ml/                     # ML предсказания
│   ├── telegram_bot/           # UI через Telegram
│   ├── trading/                # Торговая логика
│   ├── utils/                  # Утилиты
│   ├── waxpeer/                # P2P арбитраж
│   └── monitoring/             # Метрики
├── tests/                      # Только тесты
├── config/                     # Все конфиги
├── scripts/                    # Только нужные скрипты
├── docs/                       # Актуальная документация
└── infra/                      # Объединить grafana/ + k8s/ + nginx/ + n8n/
```

#### 2. Rust компиляция — оптимизировать

```bash
# После успешной сборки:
cargo clean --manifest-path src/rust_core/Cargo.toml

# Или добавить в Makefile:
rust-clean:
    cd src/rust_core && cargo clean

# Оставлять только .pyd файл для runtime
```

#### 3. Конфигурация — Единая точка

Оставить **один** конфиг-менеджер: `src/utils/config.py` (уже самый полный, 800 строк). Удалить `src/core/config_manager.py` (58 строк, базовый) и обновить все импорты.

#### 4. scripts/ — Оставить только 12 жизненно необходимых

```
scripts/
├── run_bot.py
├── restart_bot.py
├── health_check.py
├── backup_database.py
├── init_db.py
├── init_db.sql
├── create_env_file.py
├── rotate_keys.py
├── deploy.sh
├── safe_migrate.py
├── validate_config.py
└── check_balance.py
```

#### 5. Массовая очистка кешей

```powershell
# PowerShell команда для очистки всех __pycache__:
Get-ChildItem -Path "D:\Dmarket_bot" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Удалить .mypy_cache:
Remove-Item -Recurse -Force "D:\Dmarket_bot\.mypy_cache"

# Rust артефакты:
cargo clean --manifest-path "D:\Dmarket_bot\src\rust_core\Cargo.toml"
```

#### 6. poetry.lock vs requirements.txt

Проект использует **оба** пакетных менеджера. Определитесь: либо Poetry (`pyproject.toml` + `poetry.lock`), либо pip (`requirements.in` + `requirements.txt`). Текущий `pyproject.toml` минимальный (163 байта), значит скорее всего основной — pip.

**Рекомендация:** Удалить `poetry.lock` (223 KB) если не используете Poetry.

---

## 📊 СВОДКА ЭКОНОМИИ

| Категория | Размер |
|-----------|--------|
| `history_dump.txt` | ~116 MB |
| `src/rust_core/target/` | ~572 MB |
| `venv_debug/` | ~4.7 MB |
| `87 × __pycache__/` | ~10 MB |
| Мусорные файлы корня | ~0.5 MB |
| `poetry.lock` | ~0.2 MB |
| **ИТОГО экономия** | **~704 MB** |

---

## 🎯 ПРИОРИТЕТЫ ДЕЙСТВИЙ

1. **🔴 СРОЧНО:** Удалить `history_dump.txt` (116 MB)
2. **🔴 СРОЧНО:** Очистить `src/rust_core/target/` (572 MB)
3. **🟡 ВАЖНО:** Удалить 16 мусорных `.py` файлов из корня
4. **🟡 ВАЖНО:** Удалить `venv_debug/`, `memory/`, `dev_tools/`
5. **🟡 ВАЖНО:** Очистить все `__pycache__/`
6. **🟢 ПЛАНОВО:** Решить проблему 3 конфиг-систем
7. **🟢 ПЛАНОВО:** Объединить дублирующиеся папки (`arbitrage`, `integration`, `dashboard`)
8. **🟢 ПЛАНОВО:** Сократить `scripts/` с 68 до ~12
9. **🟢 ПЛАНОВО:** Удалить мёртвые модули (`tui`, `web_dashboard`, `dashboard`, `mcp_server`)
10. **🟢 ПЛАНОВО:** Архивировать legacy документацию
