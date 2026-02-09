---
description: Workflow для анализа улучшений - поиск технического долга, оптимизаций и улучшений архитектуры
---

# 🔍 Improvement Analysis Agent Workflow

Этот workflow запускает суб-агента для анализа возможных улучшений в репозитории.

## Быстрый анализ

// turbo
```bash
# Общая статистика репозитория
echo "=== Статистика кода ===" && find src -name "*.py" | wc -l && echo "Python файлов" && find src -name "*.py" -exec cat {} + | wc -l && echo "строк кода"
```

## Полный workflow анализа

### 1. Анализ безопасности (Security)

// turbo
```bash
# Bandit - анализ безопасности
python -m bandit -r src -f txt -q 2>&1 | Select-Object -First 50
```

// turbo
```bash
# Проверка уязвимостей зависимостей
pip-audit --progress-spinner off 2>&1 | Select-Object -First 30
```

### 2. Анализ качества кода (Code Quality)

// turbo
```bash
# Полный Ruff анализ
python -m ruff check src --output-format=grouped --statistics 2>&1 | Select-Object -First 80
```

// turbo
```bash
# Поиск TODO/FIXME/HACK комментариев
rg -i "(TODO|FIXME|HACK|XXX|BUG)" src --type py -c 2>$null; rg -i "(TODO|FIXME|HACK|XXX|BUG)" src --type py -n 2>&1 | Select-Object -First 30
```

### 3. Анализ сложности (Complexity)

// turbo
```bash
# McCabe complexity через Ruff
python -m ruff check src --select=C901 --output-format=text 2>&1 | Select-Object -First 30
```

// turbo
```bash
# Большие файлы (>400 строк)
Get-ChildItem -Path src -Filter "*.py" -Recurse | ForEach-Object { $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines; if($lines -gt 400) { "$lines`t$($_.FullName)" } } | Sort-Object -Descending
```

### 4. Анализ документации

// turbo
```bash
# Проверка docstrings через interrogate (если установлен)
python -m interrogate src -vv 2>&1 | Select-Object -First 30
```

// turbo
```bash
# Файлы без docstrings (поиск def без """)
rg "^(class|def) " src --type py -l 2>&1 | Select-Object -First 20
```

### 5. Анализ типов

// turbo
```bash
# MyPy статистика
python -m mypy src --ignore-missing-imports 2>&1 | Select-Object -Last 30
```

### 6. Анализ зависимостей

// turbo
```bash
# Неиспользуемые зависимости (примерный поиск)
pip list --format=freeze | Select-Object -First 30
```

### 7. Анализ архитектуры

// turbo
```bash
# Поиск циклических зависимостей (через импорты)
rg "^from src\." src --type py -o | Sort-Object | Get-Unique | Select-Object -First 30
```

### 8. Performance анализ

// turbo
```bash
# Поиск потенциальных performance issues
python -m ruff check src --select=PERF --output-format=text 2>&1 | Select-Object -First 30
```

## Категории улучшений

### 🔴 Критические (исправить немедленно)

- **Уязвимости безопасности** (Bandit HIGH)
- **Уязвимые зависимости** (pip-audit)
- **Критические баги** в тестах
- **Утечки учетных данных**

### 🟡 Важные (планировать исправление)

- **Высокая сложность** (McCabe > 15)
- **Большие файлы** (> 500 строк)
- **Отсутствие типов** в публичных API
- **Низкое покрытие тестами** (< 50%)

### 🟢 Улучшения (при возможности)

- **TODO/FIXME** комментарии
- **Устаревший код** (deprecated APIs)
- **Стилистические проблемы**
- **Документация**

## Общие рекомендации по улучшению

### Архитектура

```
✓ Разделение на слои (domain, application, infrastructure)
✓ Dependency Injection для тестируемости
✓ Интерфейсы для внешних сервисов
✓ Конфигурация через environment
```

### Производительность

```
✓ Async/await для I/O операций
✓ Connection pooling для DB/HTTP
✓ Кэширование частых запросов
✓ Batch операции вместо поштучных
```

### Безопасность

```
✓ Валидация входных данных
✓ Секреты в environment variables
✓ Rate limiting для API
✓ Аудит логирование
```

### Тестируемость

```
✓ Dependency Injection
✓ Интерфейсы для моков
✓ Fixtures для тестовых данных
✓ Integration tests с VCR
```

## Генерация отчета

После анализа создайте сводный отчет:

```markdown
# Отчет анализа - [Дата]

## Критические проблемы
- [ ] Проблема 1: описание и файл

## Важные улучшения
- [ ] Улучшение 1: описание и приоритет

## Рекомендации
- Рекомендация 1
- Рекомендация 2

## Метрики
- Покрытие тестами: XX%
- Сложность: X функций > 15
- Безопасность: X предупреждений
- Документация: XX% покрытие
```

## Полезные команды для глубокого анализа

### Поиск потенциальных проблем

```bash
# Поиск hardcoded secrets
rg "(password|secret|api_key|token)\s*=" src --type py -i

# Поиск широких except
rg "except\s*:" src --type py

# Поиск print вместо logging
rg "print\(" src --type py -c

# Поиск закомментированного кода
rg "^\s*#.*def |^\s*#.*class " src --type py
```

### Анализ структуры проекта

```bash
# Структура модулей
tree src -L 2 -d

# Размер модулей
du -sh src/*/
```
