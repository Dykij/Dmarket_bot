---
description: Workflow для реструктуризации и очистки - удаление ненужных файлов и папок
---

# 🧹 Cleanup & Restructuring Agent Workflow

Этот workflow запускает суб-агента для очистки репозитория от ненужных файлов и реструктуризации.

## Быстрый анализ

// turbo
```bash
# Общий обзор структуры проекта
Get-ChildItem -Directory | Select-Object Name, @{N='Items';E={(Get-ChildItem $_.FullName -Recurse | Measure-Object).Count}} | Sort-Object Items -Descending | Format-Table
```

## Полный workflow очистки

### 1. Поиск пустых директорий

// turbo
```bash
# Пустые папки
Get-ChildItem -Directory -Recurse | Where-Object { (Get-ChildItem $_.FullName -Force).Count -eq 0 } | Select-Object FullName
```

### 2. Поиск кэшей и временных файлов

// turbo
```bash
# Кэши Python
Get-ChildItem -Recurse -Directory -Name "__pycache__" | Measure-Object
```

// turbo
```bash
# .pyc файлы
Get-ChildItem -Recurse -Filter "*.pyc" | Measure-Object
```

### 3. Поиск дублирующихся конфигураций AI-ассистентов

// turbo
```bash
# Проверка папок AI-ассистентов (часто дублируют друг друга)
Get-ChildItem -Directory -Filter ".*" | Where-Object { $_.Name -match "cursor|claude|copilot|gemini|arkady" } | ForEach-Object { "$($_.Name): $((Get-ChildItem $_.FullName -Recurse | Measure-Object).Count) files" }
```

### 4. Анализ больших файлов

// turbo
```bash
# Файлы > 1MB (не включая .git и venv)
Get-ChildItem -Recurse -File | Where-Object { $_.Length -gt 1MB -and $_.FullName -notmatch "\.git|venv|node_modules" } | Select-Object @{N='SizeMB';E={[math]::Round($_.Length/1MB,2)}}, FullName | Sort-Object SizeMB -Descending | Select-Object -First 20
```

### 5. Поиск устаревших/неиспользуемых файлов

// turbo
```bash
# Бекапы и временные файлы
Get-ChildItem -Recurse -File | Where-Object { $_.Name -match "\.(bak|backup|old|orig|tmp|temp)$" } | Select-Object FullName
```

// turbo
```bash
# Логи и дампы
Get-ChildItem -Recurse -File | Where-Object { $_.Extension -in ".log", ".dump" } | Select-Object FullName
```

### 6. Анализ документации

// turbo
```bash
# Markdown файлы в корне (возможно лишние)
Get-ChildItem -Filter "*.md" | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}}
```

### 7. Поиск неиспользуемого кода

// turbo
```bash
# Файлы без импортов в других модулях (потенциально мертвый код)
$pyFiles = Get-ChildItem src -Recurse -Filter "*.py" | Select-Object -ExpandProperty BaseName
$pyFiles | ForEach-Object {
    $name = $_
    $imports = Select-String -Path "src\**\*.py" -Pattern "from.*$name|import.*$name" -Quiet
    if (-not $imports -and $name -ne "__init__" -and $name -ne "__main__") { $name }
} | Select-Object -First 20
```

## Папки для проверки/удаления

### AI-ассистенты (обычно можно удалить или объединить)
- `.cursor/` - Cursor IDE конфигурация
- `.claude/` - Claude AI настройки
- `.arkady/` - Arkady агент (если есть дублирование)
- `.copilot/` - GitHub Copilot

### Обычно безопасно удалять
- `__pycache__/` - Python кэш (автогенерируется)
- `.pytest_cache/` - Pytest кэш
- `.mypy_cache/` - MyPy кэш
- `.ruff_cache/` - Ruff кэш
- `htmlcov/` - Coverage HTML отчеты
- `.hypothesis/` - Hypothesis кэш
- `*.pyc` - Скомпилированный Python

### Требуют анализа
- `venv_debug/` - Debug виртуальное окружение
- `backups/` - Бекапы (проверить актуальность)
- `logs/` - Логи (архивировать или удалить старые)
- `data/` - Данные (проверить использование)

## Команды очистки

### Очистка Python кэшей

```bash
# Удаление __pycache__ (безопасно)
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

### Очистка .pyc файлов

```bash
# Удаление .pyc файлов (безопасно)
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
```

### Очистка кэшей инструментов

```bash
# Удаление кэшей линтеров (безопасно)
Remove-Item -Recurse -Force .pytest_cache, .mypy_cache, .ruff_cache -ErrorAction SilentlyContinue
```

## Чек-лист очистки

- [ ] Удалены пустые директории
- [ ] Удалены `__pycache__` и `.pyc`
- [ ] Удалены кэши инструментов
- [ ] Удалены дублирующиеся конфигурации AI
- [ ] Архивированы/удалены старые логи
- [ ] Удалены временные и бекап файлы
- [ ] Проверены неиспользуемые модули
- [ ] Обновлен .gitignore

## Паттерны реструктуризации

### Объединение конфигураций AI-ассистентов

Вместо множества папок (`.cursor/`, `.claude/`, etc.) можно использовать единую:
```
.agent/
├── workflows/       # Общие workflows
├── settings.json    # Общие настройки
└── prompts/         # Системные промпты
```

### Очистка документации

Консолидировать markdown файлы:
```
docs/
├── README.md        # Главный README
├── CONTRIBUTING.md  # Как контрибьютить
├── CHANGELOG.md     # История изменений
└── architecture/    # Архитектурная документация
```
