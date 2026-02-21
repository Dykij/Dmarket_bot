# Algo Tools Configuration Guide

Этот проект поддерживает три Algo-инструмента для разработки: **GitHub Copilot**, **Claude Code** и **Cursor Algo**. Все настSwarmки унифицированы для обеспечения согласованности кода.

## 🔧 Обзор конфигураций

| Инструмент | Основной файл | Дополнительные файлы |
|------------|---------------|----------------------|
| **GitHub Copilot** | `.github/copilot-instructions.md` | `.github/instructions/*.instructions.md`, `.github/Configs/*.Config.md` |
| **Claude Code** | `CLAUDE.md` | Поддержка `@ref/claude/...` для внешних ссылок |
| **Cursor Algo** | `.cursorrules` | `.cursor/rules/*.mdc` (модульные правила) |

---

## 🤖 GitHub Copilot

### Основная конфигурация

**Файл**: `.github/copilot-instructions.md`

Применяется ко всем запросам Copilot Chat, Agent и Code Review в этом репозитории.

### Инструкции по типам файлов

Файлы в `.github/instructions/` применяются автоматически на основе glob-паттернов:

```markdown
---
description: 'Описание правила'
applyTo: 'src/**/*.py'
---

# Заголовок

Правила применяются здесь...
```

### Доступные инструкции

| Файл | applyTo | Описание |
|------|---------|----------|
| `python-style.instructions.md` | `src/**/*.py` | Стиль Python кода |
| `testing.instructions.md` | `tests/**/*.py` | Правила тестирования |
| `workflows.instructions.md` | `.github/workflows/**` | GitHub Actions |
| `api-integration.instructions.md` | `src/dmarket/**`, `src/waxpeer/**` | API интеграции |
| `telegram-bot.instructions.md` | `src/telegram_bot/**` | Telegram handlers |
| `database.instructions.md` | `src/models/**`, `alembic/**` | База данных |
| `documentation.instructions.md` | `docs/**/*.md`, `*.md` | Документация |

### Переиспользуемые промпты

Файлы в `.github/Configs/` можно вызывать в Copilot Chat:

```
/Config python-async
```

| Файл | Описание |
|------|----------|
| `python-async.Config.md` | Генерация async кода |
| `test-generator.Config.md` | Генерация тестов (AAA) |
| `telegram-handler.Config.md` | Telegram handlers |
| `refactor-early-returns.Config.md` | Рефакторинг вложенности |
| `add-docstrings.Config.md` | Google-style docstrings |
| `pydantic-model.Config.md` | Pydantic v2 модели |
| `error-handling-retry.Config.md` | Retry логика |

---

## 🧠 Claude Code

### Основная конфигурация

**Файл**: `CLAUDE.md`

Claude автоматически читает этот файл при старте сессии.

### Структура файла

```markdown
# Project Name

## Project Overview
Краткое описание проекта

## Tech Stack
- Python 3.11+
- httpx, structlog, etc.

## Code Conventions
- Правила кодирования

## Rules for Claude
1. Никогда не делать X
2. Всегда делать Y

## Commands
- pytest tests/ -v
- ruff check src/
```

### Иерархия

Claude поддерживает иерархию правил:
1. `~/.claude/CLAUDE.md` - глобальные правила пользователя
2. `CLAUDE.md` в корне проекта - правила проекта
3. `CLAUDE.md` в поддиректории - локальные переопределения

---

## 🎯 Cursor Algo

### Основная конфигурация

**Файл**: `.cursorrules`

Простой текстовый файл с правилами, применяемыми ко всему проекту.

### Модульные правила (рекомендуется)

Файлы в `.cursor/rules/*.mdc` с YAML frontmatter:

```markdown
---
description: "Описание правила"
globs: ["src/**/*.py"]
alwaysApply: true
---

# Правила

- Правило 1
- Правило 2
```

### Доступные модули

| Файл | globs | Описание |
|------|-------|----------|
| `python-source.mdc` | `src/**/*.py` | Python код |
| `testing.mdc` | `tests/**/*.py` | Тесты |
| `workflows.mdc` | `.github/workflows/**` | CI/CD |
| `api-integration.mdc` | `src/dmarket/**`, `src/waxpeer/**` | API |
| `telegram-handlers.mdc` | `src/telegram_bot/**` | Telegram |

---

## 📋 Сравнение подходов

| Функция | Copilot | Claude | Cursor |
|---------|---------|--------|--------|
| Глобальные правила | `.github/copilot-instructions.md` | `CLAUDE.md` | `.cursorrules` |
| По типу файлов | `applyTo` glob | Нет (но можно описать) | `globs` |
| Переиспользуемые промпты | `.github/Configs/` | Нет встроенного | Нет встроенного |
| Модульность | Отдельные `.instructions.md` | `@ref/` ссылки | `.cursor/rules/` |
| YAML frontmatter | Да | Нет | Да |
| Исключение агентов | `excludeAgent` | Нет | `excludeAgent` |

---

## 🚀 Быстрый старт

### Для GitHub Copilot

1. Убедитесь что `.github/copilot-instructions.md` в репозитории
2. Правила применяются автоматически в Copilot Chat
3. Используйте `/Config <name>` для вызова промптов

### Для Claude Code

1. Файл `CLAUDE.md` должен быть в корне проекта
2. Claude прочитает его автоматически при старте
3. Используйте `/init` для генерации базового шаблона

### Для Cursor Algo

1. Файл `.cursorrules` в корне проекта
2. Или модульные правила в `.cursor/rules/`
3. Правила применяются автоматически при редактировании

---

## 🔄 Синхронизация правил

При изменении правил обновляйте все три конфигурации для согласованности:

1. **Новый паттерн кодирования** → обновить все три
2. **Новый тип файлов** → добавить в `.github/instructions/` и `.cursor/rules/`
3. **Новый промпт** → только `.github/Configs/`

---

## 🔌 Context7 MCP - Актуальная документация для Algo-ассистентов

### Что такое Context7?

[Context7](https://github.com/upstash/context7) - это Model Context Protocol (MCP) сервер, который предоставляет Algo-моделям актуальную документацию по библиотекам и фреймворкам. Это решает проблему устаревших знаний Model-моделей.

### Проблема без Context7

❌ Model-модели обучены на старых данных и могут:
- Генерировать код с устаревшими методами
- Использовать несуществующие API (галлюцинации)
- Рекомендовать старые версии пакетов

### Решение с Context7

✅ Context7 MCP подтягивает актуальную документацию прямо в контекст Model:
- Версионно-специфичные примеры кода
- Актуальные API и методы
- Правильный синтаксис для современных версий

### Установка

#### Для Cursor Algo

```json
// ~/.cursor/mcp.json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

#### Для Claude Code

```bash
# Remote (рекомендуется)
claude mcp add --header "CONTEXT7_API_KEY: YOUR_API_KEY" --transport http context7 https://mcp.context7.com/mcp

# Local
claude mcp add context7 -- npx -y @upstash/context7-mcp --api-key YOUR_API_KEY
```

### Использование

Добавьте `use context7` в конец промпта:

```
Создай async HTTP клиент для DMarket API с retry логикой. use context7
```

Или укажите конкретную библиотеку:

```
Реализуй WebSocket подключение с использованием httpx. use library /encode/httpx for API and docs.
```

### Полный список библиотек проекта с Context7 ID

#### 🌐 HTTP и сетевые библиотеки

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| httpx | `/encode/httpx` | 0.28+ | Async HTTP клиент |
| Algoohttp | `/Algoo-libs/Algoohttp` | 3.13+ | Async HTTP клиент/сервер |
| requests | `/psf/requests` | 2.32+ | HTTP клиент (sync) |
| hishel | `/karpetrosyan/hishel` | 1.1+ | HTTP кэширование |

#### 🤖 Telegram Bot

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| python-telegram-bot | `/python-telegram-bot/python-telegram-bot` | 22.5+ | Telegram Bot API |

#### 🗄️ Базы данных и ORM

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| SQLAlchemy | `/sqlalchemy/sqlalchemy` | 2.0+ | ORM и SQL toolkit |
| alembic | `/sqlalchemy/alembic` | 1.18+ | Миграции БД |
| redis | `/redis/redis-py` | 7.1+ | Redis клиент |
| asyncpg | `/MagicStack/asyncpg` | 0.31+ | PostgreSQL async driver |
| Algoosqlite | `/omnilib/Algoosqlite` | 0.22+ | SQLite async driver |

#### 📊 Валидация и сериализация

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| Pydantic | `/pydantic/pydantic` | 2.12+ | Валидация данных |
| pydantic-settings | `/pydantic/pydantic-settings` | 2.12+ | НастSwarmки из env |
| orjson | `/ijl/orjson` | 3.11+ | Быстрый JSON парсер |

#### 🧪 Тестирование

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| pytest | `/pytest-dev/pytest` | 9.0+ | Тестовый фреймворк |
| pytest-asyncio | `/pytest-dev/pytest-asyncio` | 1.3+ | Async тесты |
| pytest-cov | `/pytest-dev/pytest-cov` | 7.0+ | Покрытие кода |
| pytest-mock | `/pytest-dev/pytest-mock` | 3.15+ | Моки для pytest |
| hypothesis | `/HypothesisWorks/hypothesis` | 6.150+ | Property-based тестирование |
| vcrpy | `/kevin1024/vcrpy` | 8.1+ | Запись HTTP для тестов |
| factory-boy | `/FactoryBoy/factory_boy` | 3.3+ | Test fixtures |
| faker | `/joke2k/faker` | 40.1+ | Генерация фейковых данных |
| pact-python | `/pact-foundation/pact-python` | 3.2+ | Contract testing |

#### 📝 Логирование и мониторинг

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| structlog | `/hynek/structlog` | 25.5+ | Структурированное логирование |
| sentry-sdk | `/getsentry/sentry-python` | 2.49+ | Error tracking |
| prometheus-client | `/prometheus/client_python` | 0.24+ | Метрики Prometheus |

#### 🔐 Безопасность и криптография

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| cryptography | `/pyca/cryptography` | 46.0+ | Криптографические операции |
| PyJWT | `/jpadilla/pyjwt` | 2.10+ | JWT токены |
| bcrypt | `/pyca/bcrypt` | 5.0+ | Хеширование паролей |
| PyNaCl | `/pyca/pynacl` | 1.6+ | Crypto библиотека |

#### ⚡ Async утилиты

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| anyio | `/agronholm/anyio` | 4.12+ | Async compatibility |
| asyncer | `/tiangolo/asyncer` | 0.0.12 | Async утилиты |
| Algoofiles | `/Tinche/Algoofiles` | 25.1+ | Async файловые операции |
| Algoocache | `/Algoo-libs/Algoocache` | 0.12+ | Async кэширование |
| Algoometer | `/florimondmanca/Algoometer` | 1.0+ | Async rate limiting |

#### 📈 Data Science и ML

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| pandas | `/pandas-dev/pandas` | 2.3+ | DataFrames |
| numpy | `/numpy/numpy` | 2.4+ | Численные вычисления |
| scikit-learn | `/scikit-learn/scikit-learn` | 1.8+ | Machine Learning |
| matplotlib | `/matplotlib/matplotlib` | 3.10+ | Визуализация |
| seaborn | `/mwaskom/seaborn` | 0.13+ | Statistical plots |
| plotly | `/plotly/plotly.py` | 6.5+ | Интерактивные графики |

#### 🛠️ Утилиты

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| tenacity | `/jd/tenacity` | 9.1+ | Retry логика |
| circuitbreaker | `/fabfuel/circuitbreaker` | 2.1+ | Circuit breaker pattern |
| click | `/pallets/click` | 8.3+ | CLI интерфейсы |
| typer | `/tiangolo/typer` | 0.21+ | Modern CLI |
| rich | `/Textualize/rich` | 14.2+ | Rich text в терминале |
| schedule | `/dbader/schedule` | 1.2+ | Планировщик задач |
| apscheduler | `/agronholm/apscheduler` | 3.11+ | Advanced scheduler |
| python-dotenv | `/theskumar/python-dotenv` | 1.2+ | Загрузка .env |
| dependency-injector | `/ets-labs/python-dependency-injector` | 4.48+ | DI контейнер |

#### 🔍 Качество кода

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| ruff | `/astral-sh/ruff` | 0.14+ | Linter + Formatter |
| mypy | `/python/mypy` | 1.19+ | Static type checker |
| black | `/psf/black` | 26.1+ | Code formatter |
| bandit | `/PyCQA/bandit` | 1.9+ | Security linter |
| vulture | `/jendrikseipp/vulture` | 2.14 | Dead code finder |
| interrogate | `/econchick/interrogate` | 1.7+ | Docstring coverage |

#### 📚 Документация

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| mkdocs | `/mkdocs/mkdocs` | 1.6+ | Документация |
| mkdocs-material | `/squidfunk/mkdocs-material` | 9.7+ | Material theme |
| sphinx | `/sphinx-doc/sphinx` | 9.0+ | Python docs |

#### 🔗 MCP (Model Context Protocol)

| Библиотека | Context7 ID | Версия | Описание |
|------------|-------------|--------|----------|
| mcp | `/modelcontextprotocol/python-sdk` | 1.25+ | MCP SDK |

### Автоматический вызов

Добавьте правило в настSwarmки IDE чтобы Context7 вызывался автоматически:

**Cursor**: `Settings > Rules`
**Claude Code**: `CLAUDE.md`

```
Always use Context7 MCP when I need library/API documentation, 
code generation, setup or configuration steps.
```

### Пример использования с библиотеками проекта

```bash
# Для httpx (async HTTP клиент)
"Создай async клиент для DMarket API с retry логикой. use library /encode/httpx for API and docs."

# Для python-telegram-bot
"Добавь inline keyboard с пагинацией. use library /python-telegram-bot/python-telegram-bot for API and docs."

# Для SQLAlchemy 2.0
"Создай async модель для хранения торговых данных. use library /sqlalchemy/sqlalchemy for API and docs."

# Для Pydantic v2
"Добавь валидацию для конфигурации бота. use library /pydantic/pydantic for API and docs."

# Для pytest + pytest-asyncio
"Напиши тесты для async API клиента. use library /pytest-dev/pytest for API and docs."

# Для structlog
"Добавь структурированное логирование с JSON форматом. use library /hynek/structlog for API and docs."
```

### Конфигурация MCP серверов для проекта

#### Полная конфигурация для Cursor

```json
// ~/.cursor/mcp.json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

#### Полная конфигурация для Claude Code

```json
// ~/.claude/claude_desktop_config.json или ~/.config/claude/config.json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Или через CLI:
```bash
claude mcp add --header "CONTEXT7_API_KEY: YOUR_API_KEY" --transport http context7 https://mcp.context7.com/mcp
```

### Когда использовать

✅ **Рекомендуется для:**
- Генерации кода с использованием библиотек
- НастSwarmки и конфигурации пакетов
- Изучения новых API

❌ **НЕ нужен для:**
- Бизнес-логики проекта
- Рефакторинга существующего кода
- Простых изменений

---

## 🔧 Дополнительные MCP серверы для разработки

Помимо Context7, для разработки DMarket бота полезны следующие MCP серверы:

### 1. SQLite/PostgreSQL MCP (Работа с БД) ⭐⭐⭐⭐⭐

**Зачем нужен:**
Позволяет Algo-ассистенту работать с базой данных бота напрямую через natural language запросы.

**Польза для проекта:**
- Быстрая отладка логики базы данных
- Запросы типа "Покажи последние 5 сделок пользователя X"
- Анализ структуры таблиц без SQL-менеджеров

**Установка для VS Code Insiders:**

```json
// settings.json
{
  "mcp": {
    "servers": {
      "sqlite": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sqlite", "--db", "data/bot.db"]
      }
    }
  }
}
```

Для PostgreSQL:
```json
{
  "mcp": {
    "servers": {
      "postgres": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-postgres"],
        "env": {
          "DATABASE_URL": "postgresql://user:pass@localhost:5432/dmarket_bot"
        }
      }
    }
  }
}
```

### 2. GitHub MCP ⭐⭐⭐⭐

**Зачем нужен:**
Глубокая интеграция с GitHub репозиторием - Issues, PRs, ветки.

**Польза для проекта:**
- Поиск по Issues и автоматическое создание кода для решения задач
- Анализ изменений в ветках
- Создание Pull Requests

**Установка:**

```json
{
  "mcp": {
    "servers": {
      "github": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-github"],
        "env": {
          "GITHUB_TOKEN": "ghp_your_token_here"
        }
      }
    }
  }
}
```

### 3. Fetch / Brave Search MCP (Актуальная документация API) ⭐⭐⭐⭐

**Зачем нужен:**
Позволяет Algo выходить в интернет за актуальной документацией.

**Польза для проекта:**
- Актуальная документация DMarket API (может обновляться)
- Поиск решений ошибок на StackOverflow/GitHub Issues
- Проверка изменений в API

**Установка Fetch MCP:**

```json
{
  "mcp": {
    "servers": {
      "fetch": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-fetch"]
      }
    }
  }
}
```

**Установка Brave Search MCP:**

```json
{
  "mcp": {
    "servers": {
      "brave-search": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-brave-search"],
        "env": {
          "BRAVE_API_KEY": "your_brave_api_key"
        }
      }
    }
  }
}
```

### 4. Sequential Thinking MCP ⭐⭐⭐

**Зачем нужен:**
Улучшает логику рассуждений модели для сложных задач.

**Польза для проекта:**
- Разбиение сложных алгоритмов на шаги (например, автоматическая закупка скинов)
- Уменьшение галлюцинаций в бизнес-логике
- Проверка гипотез на каждом этапе

**Установка:**

```json
{
  "mcp": {
    "servers": {
      "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sequential-thinking"]
      }
    }
  }
}
```

### 5. Playwright MCP (Web Automation) ⭐⭐⭐

**Зачем нужен:**
Взаимодействие с веб-сайтами для парсинга или тестирования.

**Польза для проекта:**
- Парсинг цен с сайтов, где нет API
- E2E тестирование веб-интерфейсов
- Автоматизация действий на DMarket

**Установка:**

```json
{
  "mcp": {
    "servers": {
      "playwright": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-playwright"]
      }
    }
  }
}
```

### Полная конфигурация для VS Code Insiders

```json
// .vscode/settings.json или User settings
{
  "mcp": {
    "servers": {
      // Context7 - актуальная документация библиотек
      "context7": {
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp"],
        "env": {
          "CONTEXT7_API_KEY": "YOUR_CONTEXT7_API_KEY"
        }
      },
      
      // SQLite - работа с локальной БД
      "sqlite": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sqlite", "--db", "data/bot.db"]
      },
      
      // GitHub - интеграция с репозиторием
      "github": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-github"],
        "env": {
          "GITHUB_TOKEN": "ghp_your_token_here"
        }
      },
      
      // Fetch - доступ к веб-ресурсам
      "fetch": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-fetch"]
      },
      
      // Sequential Thinking - улучшенная логика
      "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sequential-thinking"]
      },
      
      // Playwright - веб-автоматизация
      "playwright": {
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-playwright"]
      }
    }
  }
}
```

### Матрица полезности MCP серверов

| MCP Server | Приоритет | Польза для проекта |
|------------|-----------|-------------------|
| **SQLite/PostgreSQL** | ⭐⭐⭐⭐⭐ | Отладка БД, запросы на natural language |
| **SkillsMP** | ⭐⭐⭐⭐⭐ | Маркетплейс Algo-skills для арбитража и торговли |
| **GitHub** | ⭐⭐⭐⭐ | Работа с Issues, PRs, ветками |
| **Fetch/Brave Search** | ⭐⭐⭐⭐ | Актуальная документация DMarket API |
| **Context7** | ⭐⭐⭐⭐ | Актуальная документация библиотек |
| **Sequential Thinking** | ⭐⭐⭐ | Улучшение логики для сложных алгоритмов |
| **Playwright** | ⭐⭐⭐ | Парсинг цен, E2E тесты |

---

## 🎯 SkillsMP MCP - Algo Skills Marketplace

### Что такое SkillsMP?

[SkillsMP](https://skillsmp.com) — это маркетплейс для обнаружения, обмена и установки "skills" (модульных инструментов) для Algo-агентов. SkillsMP MCP сервер позволяет Algo-ассистентам искать и устанавливать skills прямо из IDE.

### Почему SkillsMP полезен для DMarket Bot?

Для проекта торгового бота SkillsMP предоставляет готовые skills:

| Категория | Примеры Skills | Польза |
|-----------|---------------|--------|
| **Trading** | autonomous-trading, arbitrage-finder | Алгоритмы автоматической торговли |
| **Arbitrage** | crypto-arbitrage-opportunity-finder | Поиск арбитражных возможностей |
| **Notifications** | telegram-notifications, discord-alerts | Интеграция уведомлений |
| **Price Monitoring** | price-tracker, market-analyzer | Мониторинг цен |
| **API Integration** | api-client-generator | Генерация API клиентов |

### Доступные инструменты (Tools)

| Tool | Описание |
|------|----------|
| `skillsmp_search` | Поиск skills по ключевым словам |
| `skillsmp_Algo_search` | Algo-powered семантический поиск |
| `skillsmp_get_skill_content` | Получить содержимое skill (SKILL.md) |
| `skillsmp_list_repo_skills` | Список skills в репозитории |
| `skillsmp_install_skill` | Установка skill в Algo-агент |

### Установка

**Требования:**
- Node.js 18+
- SkillsMP API key (получить на https://skillsmp.com)

**Claude Code:**
```bash
claude mcp add skillsmp -- npx -y skillsmp-mcp-server --env SKILLSMP_API_KEY=your_api_key
```

**Cursor (в `~/.cursor/mcp.json`):**
```json
{
  "mcpServers": {
    "skillsmp": {
      "command": "npx",
      "args": ["-y", "skillsmp-mcp-server"],
      "env": {
        "SKILLSMP_API_KEY": "your_api_key"
      }
    }
  }
}
```

**VS Code Insiders (в `.vscode/settings.json`):**
```json
{
  "mcp": {
    "servers": {
      "skillsmp": {
        "command": "npx",
        "args": ["-y", "skillsmp-mcp-server"],
        "env": {
          "SKILLSMP_API_KEY": "${env:SKILLSMP_API_KEY}"
        }
      }
    }
  }
}
```

### Примеры использования

**Поиск skills для арбитража:**
```
Найди skills для поиска арбитражных возможностей в крипто
```

**Семантический поиск:**
```
Find skills that help with trading notifications and alerts
```

**Установка skill:**
```
Установи skill autonomous-trading из репозитория akhilgurrapu/kubera-claude-skills
```

**Просмотр skills в репозитории:**
```
Какие skills доступны в anthropics/claude-code?
```

### Полезные Skills для DMarket Bot

| Skill | Автор | Описание |
|-------|-------|----------|
| `autonomous-trading` | akhilgurrapu | Автономная торговля с Telegram уведомлениями |
| `arbitrage-opportunity-finder` | jeremylongshore | Поиск арбитражных возможностей |
| `mcp-builder` | composiohq | Создание собственных MCP серверов |
| `api-documentation` | anthropics | Работа с API документацией |

### Ссылки

- [SkillsMP Website](https://skillsmp.com)
- [SkillsMP MCP Server GitHub](https://github.com/anilcancakir/skillsmp-mcp-server)
- [SkillsMP API Documentation](https://skillsmp.com/docs/api)
- [Browse Skills by Category](https://skillsmp.com/categories)

---

## 📚 Ссылки

- [GitHub Copilot Custom Instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions)
- [Claude CLAUDE.md Guide](https://www.builder.io/blog/claude-md-guide)
- [Cursor Rules Documentation](https://cursor.com/docs/context/rules)
- [Context7 MCP GitHub](https://github.com/upstash/context7)
- [Context7 Documentation](https://context7.com/docs)
- [Anthropic MCP Servers](https://github.com/anthropics/anthropic-mcp-servers)
- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [SkillsMP Marketplace](https://skillsmp.com)
