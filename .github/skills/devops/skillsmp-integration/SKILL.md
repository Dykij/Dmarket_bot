---
name: "SkillsMP.com Integration"
description: "Интеграция с SkillsMP.com marketplace для auto-discovery и управления AI-навыками"
version: "1.0.0"
author: "DMarket Bot Team"
license: "MIT"
category: "DevOps"
subcategories: ["Development", "Tools", "Integration"]
tags: ["skills-marketplace", "integration", "mcp-server", "ai-tools", "automation"]
status: "approved"
team: "@core-team"
approver: "Dykij"
approval_date: "2026-01-25"
review_required: true
last_review: "2026-01-25"
python_version: ">=3.11"
main_module: null
dependencies:
  - "httpx>=0.28"
  - "pydantic>=2.5"
optional_dependencies:
  - "aiofiles"
ai_compatible: true
allowed_tools:
  - "github-copilot"
  - "claude-code"
  - "chatgpt"
---

# Skill: SkillsMP.com Integration

## Описание

Модуль интеграции с экосистемой SkillsMP.com для автоматического обнаружения, установки и управления AI-навыками (skills) для MCP сервера.

## Категория

- **Primary**: DevOps, Development
- **Secondary**: Tools, Integration
- **Tags**: `skills-marketplace`, `integration`, `mcp-server`, `ai-tools`, `automation`

## Возможности

- ✅ Автоматическое обнаружение skills из SkillsMP.com
- ✅ Одно-командная установка через marketplace.json
- ✅ Регистрация skills в MCP сервере
- ✅ Управление зависимостями
- ✅ Версионирование и обновления
- ✅ Категоризация и поиск skills
- ✅ Интеграция с GitHub для community skills

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│       SkillsMPIntegration                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  SkillsMP.com API                                   │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Skills Discovery    │                           │
│  │ - Category filter   │                           │
│  │ - Search           │                           │
│  │ - Quality filter    │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Skill Downloader    │                           │
│  │ - SKILL.md          │                           │
│  │ - marketplace.json  │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ Dependency Manager  │                           │
│  │ (pip install)       │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  ┌─────────────────────┐                           │
│  │ MCP Server          │                           │
│  │ Registration        │                           │
│  └─────────────────────┘                           │
│        │                                            │
│        ▼                                            │
│  Skill Ready for Use                                │
└─────────────────────────────────────────────────────┘
```

## Требования

### Обязательные зависимости
- Python 3.11+
- httpx 0.28+
- pydantic 2.5+
- structlog 24.1+

## Установка

```bash
pip install -e src/mcp_server/
```

## Использование

### Базовое использование

```python
from src.mcp_server.skillsmp_integration import SkillsMPIntegration

# Инициализация
skills_mp = SkillsMPIntegration()

# Поиск skills по категории
skills = await skills_mp.discover_skills(category="Data & AI")

print(f"Found {len(skills)} skills:")
for skill in skills[:5]:
    print(f"- {skill['name']} (⭐ {skill['stars']})")

# Установка skill
success = await skills_mp.install_skill("ai-arbitrage-predictor")
if success:
    print("✅ Skill installed successfully")
```

### Поиск skills

```python
# Поиск по ключевым словам
results = await skills_mp.search_skills(
    query="machine learning trading",
    category="Data & AI",
    min_stars=2
)

# Фильтрация по категориям
categories = [
    "Data & AI",
    "DevOps",
    "Testing & Security",
    "Development"
]

for category in categories:
    skills = await skills_mp.discover_skills(category=category)
    print(f"{category}: {len(skills)} skills")
```

### Установка и управление

```python
# Установка skill
await skills_mp.install_skill("telegram-nlp-handler")

# Обновление skill
await skills_mp.update_skill("telegram-nlp-handler", version="1.1.0")

# Удаление skill
await skills_mp.uninstall_skill("telegram-nlp-handler")

# Список установленных skills
installed = await skills_mp.list_installed_skills()
for skill in installed:
    print(f"{skill['name']} v{skill['version']}")
```

## API Reference

### `class SkillsMPIntegration`

#### `async discover_skills(category: str = None, min_stars: int = 2)`

Обнаруживает доступные skills из SkillsMP.com.

**Parameters:**
- `category` (str, optional): Категория фильтрации
- `min_stars` (int): Минимальное количество звезд

**Returns:**
- `list[dict]`: Список обнаруженных skills

#### `async install_skill(skill_name: str, version: str = "latest")`

Устанавливает skill из marketplace.

**Parameters:**
- `skill_name` (str): Название skill
- `version` (str): Версия для установки

**Returns:**
- `bool`: True если успешно

## Производительность

| Метрика | Значение |
|---------|----------|
| **Время поиска** | <500ms |
| **Время установки** | 5-30 seconds |
| **Кэш skills** | 1 hour |

## Примеры использования

### Пример 1: Автоматическая установка рекомендованных skills

```python
recommended_skills = [
    "ai-arbitrage-predictor",
    "telegram-nlp-handler",
    "portfolio-risk-assessor"
]

for skill_name in recommended_skills:
    print(f"Installing {skill_name}...")
    success = await skills_mp.install_skill(skill_name)
    if success:
        print(f"✅ {skill_name} installed")
    else:
        print(f"❌ Failed to install {skill_name}")
```

### Пример 2: Обновление всех skills

```python
installed = await skills_mp.list_installed_skills()

for skill in installed:
    latest_version = await skills_mp.get_latest_version(skill['name'])
    if latest_version != skill['version']:
        print(f"Updating {skill['name']} from {skill['version']} to {latest_version}")
        await skills_mp.update_skill(skill['name'], latest_version)
```

## Зависимости

### Внутренние модули
- `src/mcp_server/` - MCP сервер для AI инструментов

### Внешние API
- SkillsMP.com API - для поиска и загрузки skills

## Лицензия

MIT License

## Changelog

### v1.0.0 (2026-01-19)
- ✅ Первый релиз
- ✅ Интеграция с SkillsMP.com API
- ✅ Автоматическая установка skills
- ✅ Управление зависимостями

---

**Last Updated**: 2026-01-19  
**Status**: ✅ Production Ready  
**Skill Type**: DevOps, Development
