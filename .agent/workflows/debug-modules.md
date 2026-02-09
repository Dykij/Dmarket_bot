---
description: Workflow для глубокого анализа логики и ошибок во всех модулях проекта
---

# 🔬 Module Logic Analyzer Agent Workflow

Этот workflow запускает суб-агента для глубокого анализа логики работы всех модулей и выявления ошибок.

## Стратегия анализа

Анализ проводится по слоям архитектуры:
1. **Core** - ядро приложения
2. **DMarket API** - интеграция с DMarket
3. **Telegram Bot** - обработчики бота
4. **ML/Analytics** - машинное обучение и аналитика
5. **Utils** - утилиты и хелперы

## Шаги анализа

### 1. Проверка импортов и зависимостей

// turbo
```bash
# Поиск битых импортов
python -c "
import sys
sys.path.insert(0, 'src')
import importlib
import pkgutil

errors = []
for importer, modname, ispkg in pkgutil.walk_packages(['src'], prefix='src.'):
    try:
        importlib.import_module(modname.replace('src.', ''))
    except Exception as e:
        errors.append(f'{modname}: {type(e).__name__}: {e}')

for err in errors[:20]:
    print(err)
print(f'Total import errors: {len(errors)}')
" 2>&1 | Select-Object -First 30
```

### 2. Статический анализ типов (MyPy)

// turbo
```bash
python -m mypy src --ignore-missing-imports --show-error-codes 2>&1 | Select-Object -First 50
```

### 3. Анализ Core модулей

// turbo
```bash
# Проверка core модулей
python -m py_compile src/core/__init__.py src/core/app_lifecycle.py 2>&1
python -c "from src.core import *; print('Core modules OK')" 2>&1
```

### 4. Анализ DMarket модулей

// turbo
```bash
# Проверка dmarket модулей
python -c "
import sys
sys.path.insert(0, '.')
errors = []
modules = [
    'src.dmarket.api_client',
    'src.dmarket.arbitrage.core',
    'src.dmarket.market_analysis',
    'src.dmarket.price_analyzer',
    'src.dmarket.smart_scanner',
]
for mod in modules:
    try:
        __import__(mod)
        print(f'✓ {mod}')
    except Exception as e:
        print(f'✗ {mod}: {e}')
" 2>&1 | Select-Object -First 20
```

### 5. Анализ Telegram Bot модулей

// turbo
```bash
# Проверка telegram_bot модулей
python -c "
import sys
sys.path.insert(0, '.')
modules = [
    'src.telegram_bot.bot_v2',
    'src.telegram_bot.handlers',
    'src.telegram_bot.command_center',
    'src.telegram_bot.notifications',
]
for mod in modules:
    try:
        __import__(mod)
        print(f'✓ {mod}')
    except Exception as e:
        print(f'✗ {mod}: {e}')
" 2>&1
```

### 6. Анализ ML модулей

// turbo
```bash
# Проверка ML модулей
python -c "
import sys
sys.path.insert(0, '.')
modules = [
    'src.ml.price_predictor',
    'src.ml.anomaly_detection',
    'src.ml.smart_recommendations',
    'src.ml.model_tuner',
]
for mod in modules:
    try:
        __import__(mod)
        print(f'✓ {mod}')
    except Exception as e:
        print(f'✗ {mod}: {e}')
" 2>&1
```

### 7. Поиск runtime ошибок (через тесты)

// turbo
```bash
# Быстрые smoke тесты для выявления runtime ошибок
python -m pytest tests/unit -x --tb=short -q --ignore=tests/unit/test_mcp_server.py 2>&1 | Select-Object -Last 30
```

### 8. Анализ async/await паттернов

// turbo
```bash
# Поиск потенциальных проблем с async
Select-String -Path "src\**\*.py" -Pattern "asyncio.create_task\(" | Select-Object -First 15 | ForEach-Object { "$($_.Filename):$($_.LineNumber)" }
```

// turbo
```bash
# Поиск blocking calls в async функциях
Select-String -Path "src\**\*.py" -Pattern "time\.sleep\(" | Select-Object -First 10
```

### 9. Анализ обработки ошибок

// turbo
```bash
# Поиск голых except
Select-String -Path "src\**\*.py" -Pattern "except\s*:" | Measure-Object
```

// turbo
```bash
# Поиск игнорирования исключений
Select-String -Path "src\**\*.py" -Pattern "except.*:\s*pass" | Select-Object -First 10
```

### 10. Проверка конфигурации

// turbo
```bash
# Проверка загрузки конфигурации
python -c "
import sys
sys.path.insert(0, '.')
try:
    from src.dmarket.config import settings
    print('Config loaded OK')
    print(f'DMarket API: {bool(getattr(settings, \"DMARKET_API_KEY\", None))}')
except Exception as e:
    print(f'Config error: {e}')
" 2>&1
```

## Категории ошибок

### 🔴 Критические (блокируют работу)
- ImportError / ModuleNotFoundError
- SyntaxError
- Отсутствие обязательных зависимостей
- Неправильная конфигурация

### 🟡 Важные (могут вызвать сбои)
- TypeError в runtime
- AttributeError
- Необработанные исключения
- Race conditions в async

### 🟢 Незначительные (качество кода)
- Неиспользуемые импорты
- Типовые несоответствия
- Deprecated API

## Шаблон отчёта об ошибках

```markdown
## Модуль: src/[path]/[module].py

### Ошибка #1
- **Тип**: ImportError / TypeError / etc.
- **Строка**: XX
- **Описание**: Что именно сломано
- **Влияние**: Как это влияет на работу бота
- **Решение**: Как исправить

### Ошибка #2
...
```

## Автоматические исправления

После анализа можно применить автофиксы:

```bash
# Исправление импортов
python -m ruff check src --select=I --fix

# Исправление простых ошибок
python -m ruff check src --fix

# Форматирование
python -m ruff format src
```
