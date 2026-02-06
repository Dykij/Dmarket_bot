# 📚 DMarket Telegram Bot

<!-- Badges: Project Info -->
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/Dykij/DMarket-Telegram-Bot?color=green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Dykij/DMarket-Telegram-Bot?style=social)](https://github.com/Dykij/DMarket-Telegram-Bot/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/Dykij/DMarket-Telegram-Bot?style=social)](https://github.com/Dykij/DMarket-Telegram-Bot/network/members)

<!-- Badges: CI/CD Status -->
[![CI Status](https://img.shields.io/github/actions/workflow/status/Dykij/DMarket-Telegram-Bot/ci.yml?branch=main&label=CI&logo=github)](https://github.com/Dykij/DMarket-Telegram-Bot/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/Dykij/DMarket-Telegram-Bot/python-tests.yml?branch=main&label=Tests&logo=pytest)](https://github.com/Dykij/DMarket-Telegram-Bot/actions/workflows/python-tests.yml)
[![Code Quality](https://img.shields.io/github/actions/workflow/status/Dykij/DMarket-Telegram-Bot/code-quality.yml?branch=main&label=Code%20Quality&logo=ruff)](https://github.com/Dykij/DMarket-Telegram-Bot/actions/workflows/code-quality.yml)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/Dykij/DMarket-Telegram-Bot/codeql.yml?branch=main&label=CodeQL&logo=github)](https://github.com/Dykij/DMarket-Telegram-Bot/security/code-scanning)

<!-- Badges: Activity -->
[![Last Commit](https://img.shields.io/github/last-commit/Dykij/DMarket-Telegram-Bot?logo=git&logoColor=white)](https://github.com/Dykij/DMarket-Telegram-Bot/commits/main)
[![GitHub Issues](https://img.shields.io/github/issues/Dykij/DMarket-Telegram-Bot?logo=github)](https://github.com/Dykij/DMarket-Telegram-Bot/issues)
[![GitHub PRs](https://img.shields.io/github/issues-pr/Dykij/DMarket-Telegram-Bot?logo=github)](https://github.com/Dykij/DMarket-Telegram-Bot/pulls)

<!-- Badges: Tech Stack -->
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot_API_9.2-blue?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![DMarket](https://img.shields.io/badge/DMarket-API_v1.1-orange?logo=steam&logoColor=white)](https://docs.dmarket.com/)
[![Async](https://img.shields.io/badge/async-httpx_0.28%2B-purple?logo=fastapi&logoColor=white)](https://www.python-httpx.org/)

<!-- Badges: Development Environment -->
[![Open in GitHub Codespaces](https://img.shields.io/badge/Open%20in-Codespaces-blue?logo=github)](https://codespaces.new/Dykij/DMarket-Telegram-Bot)
[![Dev Container](https://img.shields.io/badge/Dev%20Container-Ready-brightgreen?logo=docker)](https://containers.dev/)

---

> 🤖 **Автоматизированная система для торговли игровыми предметами** на платформе DMarket с поддержкой многоуровневого арбитража, системы таргетов и real-time мониторинга.

## 📋 Обзор проекта

| Метрика              | Значение                   |
| -------------------- | -------------------------- |
| **Версия**           | 1.0.0                      |
| **Python**           | 3.11+ (3.12 рекомендуется) |
| **Тестов**           | 7654+                      |
| **Покрытие тестами** | 85%+ (цель: 90%)           |
| **Лицензия**         | MIT                        |

## 🎯 Основные возможности

- 🎮 **Multi-game поддержка** - CS:GO/CS2, Dota 2, TF2, Rust
- 📊 **Многоуровневый арбитраж** - 5 уровней торговли (от разгона до профессионала)
- 🤖 **Система таргетов** - автоматические buy orders на DMarket
- 📈 **Real-time мониторинг** - отслеживание цен через WebSocket
- 🔔 **Умные уведомления** - фильтрация, дайджесты, алерты
- 🌐 **Локализация** - RU, EN, ES, DE
- 🔒 **Безопасность** - шифрование API ключей, DRY_RUN режим
- 🛡️ **Circuit Breaker** - защита от каскадных сбоев API
- 📡 **Sentry интеграция** - мониторинг ошибок в production

---

## 🆕 Модульная архитектура Skills (NEW!)

**Проект теперь поддерживает модульные AI-расширения на основе стандарта SKILL.md** 🎉

### Что это такое?

Модульные навыки (skills) - это переиспользуемые, самодокументируемые компоненты с четкой структурой:

- 📦 **SKILL.md** - стандартизированное описание функциональности
- 🔧 **marketplace.json** - метаданные для автоматической установки
- 🤖 **AI-совместимость** - интеграция с Claude Code, Copilot, ChatGPT
- 🌟 **Community-driven** - открытое развитие через GitHub

### Доступные Skills

| Skill | Категория | Описание | Статус |
|-------|-----------|----------|--------|
| **[AI Arbitrage Predictor](src/dmarket/SKILL_AI_ARBITRAGE.md)** | Data & AI | ML-прогнозирование арбитража (точность 78%) | ✅ Готов |
| **[NLP Command Handler](src/telegram_bot/SKILL_NLP_HANDLER.md)** | Data & AI | Обработка естественного языка (4 языка) | ✅ Готов |
| **[Portfolio Risk Assessment](src/portfolio/SKILL_RISK_ASSESSMENT.md)** | Business & AI | AI-оценка рисков портфеля | ✅ Готов |
| **[SkillsMP Integration](src/mcp_server/SKILL_SKILLSMP_INTEGRATION.md)** | DevOps | Интеграция с SkillsMP.com marketplace | ✅ Готов |

### Быстрый старт со Skills

```bash
# Установка skill из marketplace
pip install -e src/dmarket/

# Использование AI Arbitrage Predictor
from src.dmarket.ai_arbitrage_predictor import AIArbitragePredictor
predictor = AIArbitragePredictor(ml_model)
opportunities = await predictor.predict_best_opportunities(items, balance, 'medium')

# Использование NLP Handler
from src.telegram_bot.nlp_handler import NLPCommandHandler
nlp = NLPCommandHandler()
result = await nlp.parse_user_intent("Найди арбитраж в CS:GO до $10", user_id=123)
```

### Документация Skills

📚 **Руководство**: [docs/SKILLSMP_IMPLEMENTATION.md](docs/SKILLSMP_IMPLEMENTATION.md)

Руководство содержит:
- 🎯 Детальный анализ концепции SkillsMP.com
- 📦 Рекомендации по улучшению всех модулей
- 🚀 Фазированный план внедрения (4 фазы)
- 💡 Примеры использования и Best Practices
- 📊 Ожидаемые результаты (+15-25% ROI)

---

## 🚀 Быстрый старт

### 📝 Настройка API ключей (3 шага)

```bash
# 1. Скопируйте .env.example в .env (или используйте созданный .env)
cp .env.example .env

# 2. Откройте .env и заполните обязательные поля:
#    - TELEGRAM_BOT_TOKEN (получите у @BotFather)
#    - DMARKET_PUBLIC_KEY (https://dmarket.com/account/api-settings)
#    - DMARKET_SECRET_KEY (https://dmarket.com/account/api-settings)

# 3. Запустите бота
python -m src.main
```

📖 **Подробная инструкция**: [docs/QUICK_START.md](docs/QUICK_START.md)

### Для начинающих

- **[Быстрый старт](docs/QUICK_START.md)** - Запуск бота за 5 минут
- **[Архитектура проекта](docs/ARCHITECTURE.md)** - Понимание структуры проекта

### Для разработчиков

- **[🚀 GitHub Codespaces](.devcontainer/README.md)** - Разработка в облаке (рекомендуется!)
- **[🤖 Copilot Space](.github/COPILOT_SPACE_CONFIG.md)** - Настройка GitHub Copilot Space
- **[Руководство по разработке](CONTRIBUTING.md)** - Как помочь проекту

---

## 📖 Основная документация

### 🚀 Интерфейс бота

- **[Арбитраж и Таргеты](docs/ARBITRAGE.md)** - Основные функции:
  - 🔍 Арбитраж (все игры сразу или ручной режим)
  - 🎯 Таргеты (ручной и автоматический)

### Торговля и арбитраж

- **[Полное руководство по арбитражу](docs/ARBITRAGE.md)** - Всё об арбитраже:
  - Многоуровневое сканирование (5 уровней)
  - Автоматический арбитраж
  - Система таргетов (Buy Orders)
  - Анализ продаж и ликвидности
  - Фильтры по играм
  - Стратегии торговли

### API и интеграции

- **[API Reference](docs/API_COMPLETE_REFERENCE.md)** - Справочник API методов
- **[DMarket API Спецификация](docs/DMARKET_API_FULL_SPEC.md)** - Полная спецификация DMarket API v1.1.0
- **[Telegram Bot API](docs/TELEGRAM_BOT_API.md)** - Справочник Telegram Bot API 9.2
- **[Фильтры игр](docs/ARBITRAGE.md#фильтры-по-играм)** - Фильтры для CS:GO, Dota 2, TF2, Rust
- **[SkillsMP Integration](docs/SKILLSMP_IMPLEMENTATION.md)** 🆕⭐ - Модульная AI-архитектура на основе SkillsMP.com

### Разработка и инфраструктура

- **[Структура проекта](docs/project_structure.md)** - Организация файлов и модулей
- **[База данных](docs/DATABASE_MIGRATIONS.md)** - Миграции Alembic
- **[Развертывание](docs/deployment.md)** - Деплой (Docker, Heroku, AWS, GCP)
- **[Безопасность](docs/SECURITY.md)** - Защита ключей и данных
- **[Проблемы](docs/TROUBLESHOOTING.md)** - Решение проблем

---

## 🎯 Руководства по использованию

### Основные функции

#### 1. Многоуровневый арбитраж

Система предлагает 5 уровней торговли:

| Уровень    | Цены        | Прибыль | Баланс | Для кого      |
| ---------- | ----------- | ------- | ------ | ------------- |
| 🚀 Boost    | $0.50-$3    | 1.5-3%  | $10    | Начинающие    |
| ⭐ Standard | $3-$10      | 3-7%    | $50    | С опытом      |
| 💰 Medium   | $10-$30     | 5-10%   | $150   | Опытные       |
| 💎 Advanced | $30-$100    | 7-15%   | $500   | Профессионалы |
| 🏆 Pro      | $100-$1000+ | 10%+    | $2000  | Эксперты      |

Подробнее: [docs/ARBITRAGE.md](docs/ARBITRAGE.md)

#### 2. Система таргетов (Buy Orders)

Автоматические заявки на покупку предметов:

- ✅ Покупка по вашей цене
- ✅ Автоматическое исполнение
- ✅ Приоритет покупки
- ✅ Умные таргеты

Подробнее: [docs/ARBITRAGE.md#система-таргетов](docs/ARBITRAGE.md)

#### 3. Фильтры по играм

Поддерживаемые игры:

- 🎮 CS:GO / CS2
- 🎮 Dota 2
- 🎮 Team Fortress 2
- 🎮 Rust

Подробнее: [docs/ARBITRAGE.md#фильтры-по-играм](docs/ARBITRAGE.md#фильтры-по-играм)

---

## 🛠️ Для разработчиков

### Настройка окружения

```bash
# Клонирование репозитория
git clone https://github.com/Dykij/DMarket-Telegram-Bot.git
cd DMarket-Telegram-Bot

# Виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка .env
cp .env.example .env
# Отредактировать .env с вашими ключами

# Запуск бота
python -m src.main
```

### Качество кода

```bash
# Форматирование
ruff format src/ tests/

# Линтинг с автофиксом
ruff check src/ tests/ --fix

# Проверка типов
mypy src/

# Тесты с покрытием
pytest --cov=src --cov-report=html
```

Подробнее: [CONTRIBUTING.md](CONTRIBUTING.md)

### Структура проекта

```
DMarket-Telegram-Bot/
├── src/
│   ├── dmarket/             # DMarket API клиент
│   │   ├── api/             # Модульный API (auth, market, inventory, etc.)
│   │   ├── scanner/         # Сканер арбитража
│   │   ├── targets/         # Управление таргетами
│   │   ├── arbitrage/       # Арбитражная логика
│   │   └── filters/         # Фильтры по играм
│   ├── telegram_bot/        # Telegram бот
│   │   ├── commands/        # Обработчики команд
│   │   ├── handlers/        # Message/callback handlers
│   │   ├── keyboards/       # Inline клавиатуры
│   │   └── notifications/   # Система уведомлений
│   ├── analytics/           # Аналитика и бэктестинг
│   ├── portfolio/           # Управление портфелем
│   ├── web_dashboard/       # Веб-дашборд
│   ├── mcp_server/          # MCP Server для AI инструментов
│   ├── models/              # Модели данных (SQLAlchemy 2.0)
│   └── utils/               # Утилиты (cache, rate limiter, etc.)
├── tests/                   # Тесты (372 файла)
├── docs/                    # Документация (19+ файлов)
├── alembic/                 # Миграции БД
└── config/                  # Конфигурация
```

Подробнее: [docs/project_structure.md](docs/project_structure.md)

---

## 📊 API Reference

### DMarket API Client

```python
from src.dmarket.dmarket_api import DMarketAPI

api = DMarketAPI(public_key, secret_key)

# Получить баланс
balance = await api.get_balance()

# Получить предметы рынка
items = await api.get_market_items(game="csgo", limit=100)

# Купить предмет
result = await api.buy_item(item_id, price)
```

Подробнее: [docs/API_COMPLETE_REFERENCE.md](docs/API_COMPLETE_REFERENCE.md)

### Arbitrage Scanner

```python
from src.dmarket.arbitrage_scanner import ArbitrageScanner

scanner = ArbitrageScanner(api)

# Сканировать уровень
results = await scanner.scan_level("standard", game="csgo")

# Сканировать все уровни
all_results = await scanner.scan_all_levels(game="csgo")
```

Подробнее: [docs/ARBITRAGE.md](docs/ARBITRAGE.md)

---

## 🔒 Безопасность

### Хранение секретов

**✅ Правильно:**

```python
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

**❌ Неправильно:**

```python
TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."  # НЕ ДЕЛАЙТЕ ТАК!
```

### Шифрование API ключей

```python
from src.utils.encryption import EncryptionManager

manager = EncryptionManager()
encrypted = manager.encrypt_api_key(api_key)
decrypted = manager.decrypt_api_key(encrypted)
```

Подробнее: [docs/SECURITY.md](docs/SECURITY.md)

---

## 🐳 Docker

### Быстрый запуск

```bash
# Сборка образа
docker-compose build

# Запуск всех сервисов (бот, postgres, redis)
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

Подробнее: [docs/deployment.md](docs/deployment.md)

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Конкретный модуль
pytest tests/dmarket/test_arbitrage_scanner.py

# В параллель
pytest -n auto
```

### Структура тестов

```
tests/
├── integration/          # Интеграционные тесты
├── e2e/                  # End-to-end тесты
├── models/               # Тесты моделей
├── utils/                # Тесты утилит
├── dmarket/              # Тесты DMarket API
├── telegram_bot/         # Тесты Telegram бота
└── fixtures/             # Общие фикстуры
```

Подробнее: [docs/CONTRACT_TESTING.md](docs/CONTRACT_TESTING.md)

---

## 📈 Мониторинг и логирование

### Структурированное логирование

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "arbitrage_scan_completed",
    game="csgo",
    opportunities_found=15,
    scan_duration_ms=1250
)
```

### Уровни логирования

- `DEBUG` - Детальная отладка
- `INFO` - Общая информация
- `WARNING` - Предупреждения
- `ERROR` - Ошибки
- `CRITICAL` - Критические ошибки

Подробнее: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 🤝 Как помочь проекту

1. **Fork** репозитория
2. **Создайте ветку** для вашей функции (`git checkout -b feature/amazing-feature`)
3. **Сделайте коммит** (`git commit -m 'feat: add amazing feature'`)
4. **Push** в ветку (`git push origin feature/amazing-feature`)
5. **Создайте Pull Request**

Подробнее: [CONTRIBUTING.md](CONTRIBUTING.md)

### Соглашения о коммитах

- `feat:` - новая функция
- `fix:` - исправление бага
- `docs:` - изменения в документации
- `test:` - добавление тестов
- `refactor:` - рефакторинг кода
- `style:` - форматирование
- `chore:` - обслуживание

---

## 📞 Поддержка

- 📖 **Документация**: [docs/](docs/)
- 🐛 **Issues**: [GitHub Issues](https://github.com/Dykij/DMarket-Telegram-Bot/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/Dykij/DMarket-Telegram-Bot/discussions)

---

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE).

---

## 🛠️ Технологический стек

| Категория         | Технологии                        |
| ----------------- | --------------------------------- |
| **Язык**          | Python 3.11+ (3.12 рекомендуется) |
| **Async**         | asyncio, httpx 0.28+              |
| **Bot Framework** | python-telegram-bot 22.0+         |
| **ORM**           | SQLAlchemy 2.0+                   |
| **Validation**    | Pydantic 2.5+                     |
| **Linting**       | Ruff 0.14+                        |
| **Type Checking** | MyPy 1.19+                        |
| **Testing**       | pytest 8.4+, VCR.py, Hypothesis   |
| **Database**      | PostgreSQL 14+, Redis 7+          |
| **Deployment**    | Docker, docker-compose            |
| **Monitoring**    | Sentry, Prometheus                |

---

**Последнее обновление**: 4 февраля 2026 г.
