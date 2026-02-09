---
description: Workflow для тестирования - запуск тестов, анализ покрытия и качества тестов
---

# 🧪 Testing Agent Workflow

Этот workflow запускает суб-агента для комплексного тестирования репозитория.

## Быстрый старт

Для быстрой проверки используйте:

// turbo
```bash
# Smoke тесты - критический путь
python -m pytest tests/ -m "smoke or critical" -x --tb=short -q
```

## Полный workflow тестирования

### 1. Проверка зависимостей тестов

// turbo
```bash
# Убедиться что все dev-зависимости установлены
pip list | findstr pytest
```

### 2. Smoke тесты (быстрая проверка)

// turbo
```bash
# Критические тесты - должны проходить всегда
python -m pytest tests/ -m smoke -x --tb=short -q 2>&1 | Select-Object -First 30
```

### 3. Unit тесты

// turbo
```bash
# Unit тесты - быстрые, без внешних зависимостей
python -m pytest tests/unit -x --tb=short -q --durations=5 2>&1 | Select-Object -Last 50
```

### 4. Integration тесты

```bash
# Интеграционные тесты (требуют моки или реальные сервисы)
python -m pytest tests/integration -x --tb=short -q 2>&1 | Select-Object -Last 30
```

### 5. Анализ покрытия кода

```bash
# Генерация отчета Coverage
python -m pytest tests/ -x --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=50 2>&1 | Select-Object -Last 100
```

### 6. Проверка flaky тестов

// turbo
```bash
# Идентификация нестабильных тестов
python -m pytest tests/ -m flaky --reruns 3 --reruns-delay 1 -x --tb=short -q 2>&1 | Select-Object -Last 30
```

### 7. Тесты производительности

```bash
# Performance тесты
python -m pytest tests/performance -m performance --tb=short -q 2>&1 | Select-Object -Last 30
```

### 8. Property-based тесты (Hypothesis)

// turbo
```bash
# Property-based тесты
python -m pytest tests/ -m property_based --hypothesis-show-statistics -x --tb=short 2>&1 | Select-Object -Last 50
```

## Категории тестов

Доступные маркеры pytest (см. pyproject.toml):

| Маркер | Описание |
|--------|----------|
| `unit` | Быстрые unit-тесты без DB/API |
| `integration` | Требуют DB/Redis/API моки |
| `e2e` | Полные end-to-end тесты |
| `slow` | Медленные тесты |
| `smoke` | Критические smoke-тесты |
| `flaky` | Нестабильные тесты |
| `security` | Тесты безопасности |
| `performance` | Тесты производительности |
| `property_based` | Property-based (Hypothesis) |

## Запуск по категориям

```bash
# Только unit тесты
pytest tests/ -m unit

# Исключить медленные
pytest tests/ -m "not slow"

# Только критические
pytest tests/ -m critical

# Тесты безопасности
pytest tests/ -m security
```

## Анализ провалившихся тестов

### Детальный вывод ошибок

```bash
python -m pytest tests/path/to/test.py -vvv --tb=long -x
```

### Запуск конкретного теста

```bash
python -m pytest tests/path/to/test.py::TestClass::test_method -vvv
```

### Отладка в тесте

```python
# Добавить в тест
import pdb; pdb.set_trace()
# или
breakpoint()
```

## Отчеты

### HTML отчет покрытия

// turbo
```bash
# Открыть HTML отчет (после --cov-report=html)
start htmlcov/index.html
```

### XML отчет для CI/CD

```bash
python -m pytest tests/ --junitxml=test_results.xml -q
```

## Чек-лист качества тестов

- [ ] **Покрытие > 70%**: Критические модули покрыты
- [ ] **Все smoke тесты проходят**: Критический путь работает
- [ ] **Нет flaky тестов**: Тесты стабильны
- [ ] **Unit тесты быстрые**: < 5 сек на тест
- [ ] **Моки корректны**: Внешние зависимости изолированы
- [ ] **Fixtures переиспользуются**: Нет дублирования setup
- [ ] **Тесты независимы**: Порядок не важен

## Создание новых тестов

При создании тестов следуйте структуре:

```
tests/
├── unit/              # Быстрые изолированные тесты
├── integration/       # Тесты с зависимостями
├── e2e/              # End-to-end сценарии
├── performance/      # Нагрузочные тесты
├── security/         # Тесты безопасности
├── fixtures/         # Общие фикстуры
└── conftest.py       # Глобальные конфигурации
```
