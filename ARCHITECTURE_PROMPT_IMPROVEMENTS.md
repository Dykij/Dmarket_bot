# ARCHITECTURE_PROMPT_IMPROVEMENTS.md
## Анализ архитектуры MimoCode: MAX ↔ Compose Hunter
### Дата: 2026-07-27 | Контекст: DMarket Bot (204 файла, 199 модулей)

---

## 1. Заключение о совместимости MAX и Compose Hunter

### Можно ли запускать Compose внутри MAX?

**Технически — да.** MimoCode поддерживает вложенные workflow через `workflow()` API
(глубина до 8 уровней, настраивается через `workflow.maxDepth`). Агент в режиме MAX
может вызвать compose workflow как дочерний процесс.

### Стоит ли это делать?

**Нет.** Причины:

| Характеристика | MAX | Compose Hunter |
|----------------|-----|----------------|
| **Назначение** | Тотальная диагностика | Хирургическая коррекция |
| **Подход** | Параллельные кандидаты reasoning (5x) | Детерминированный pipeline spec→ship |
| **Контекст** | Весь проект одновременно | Один файл/модуль за раз |
| **Итерации** | Один проход анализа | Много итераций правок |
| **Токены** | ~5x от обычного (parallel candidates) | Экономный (целевая загрузка) |
| **Результат** | Отчёт о проблемах | Исправленный код |

**Конфликт:** MAX загружает весь контекст проекта для глобального анализа. Compose
загружает только релевантные файлы для конкретной задачи. Запуск Compose внутри MAX
означает, что контекст Compose будет переполнен данными MAX, что снизит качество
обоих режимов.

### Лучший подход: Гибридная связка MAX → Compose

```
┌─────────────────────────────────────────────────┐
│  Phase 1: MAX (диагностика)                      │
│  ┌───────────────────────────────────────────┐   │
│  │  5 parallel candidates × full scan        │   │
│  │  → AUDIT_REPORT.md с P0/P1/P2 багами     │   │
│  │  → DEPENDENCY_GRAPH.json                  │   │
│  └───────────────────────────────────────────┘   │
│                      ↓                            │
│  Phase 2: Compose (исправление)                   │
│  ┌───────────────────────────────────────────┐   │
│  │  Для каждого P0/P1 бага:                  │   │
│  │  compose.run({ task: "Fix P0-1: ..." })   │   │
│  │  → Изолированный worktree                 │   │
│  │  → TDD + верификация                      │   │
│  │  → Мерж в main                            │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Преимущества:**
- Каждый режим работает в оптимальном контексте
- MAX не тратит токены на итеративные правки
- Compose не тратит токены на сканирование всего проекта
- Результаты MAX сериализуются в файл → Compose читает только его

---

## 2. Анализ текущей реализации MimoCode

### Режим MAX (experimental.maxMode)

**Что делает:** Запускает N параллельных кандидатов reasoning на каждом шаге,
judge-модель выбирает лучший ответ.

**Текущая конфигурация:**
```jsonc
"experimental": {
  "maxMode": {
    "candidates": 5  // 5 параллельных кандидатов
  }
}
```

**Ограничения:**
- Нет фильтрации файлов — загружает всё подряд
- Нет сериализации промежуточных результатов
- Нет интеграции с внешними анализаторами (semgrep, radon, mypy)
- Контекст-окно заполняется быстро при 5x кандидатах

### Режим Compose

**Что делает:** Детерминированный pipeline spec→ship:
brainstorm → design → implement (TDD) → verify → review → merge

**Варианты запуска:**
1. `compose` workflow (детерминированный, автоматический)
2. `/compose-next` skill (интерактивный, с human-in-the-loop)
3. `compose` agent (legacy, через Tab)

**Ограничения:**
- Не принимает входной отчёт от MAX автоматически
- Нет фильтрации по приоритету (P0/P1/P2)
- Нет пакетной обработки списка багов

### MCP Серверы (9 активных)

| Сервер | Статус | Назначение |
|--------|--------|------------|
| sequential-thinking | ✅ | Многошаговое рассуждение |
| archy | ✅ | Архитектурный анализ |
| sqlite | ✅ | Запросы к БД |
| context7 | ✅ | Документация библиотек |
| fetch | ✅ | HTTP-запросы |
| web-search | ✅ | Веб-поиск |
| semgrep | ✅ | Security scanning |
| shellcheck | ✅ | Shell linting |
| in-memoria | ✅ | Паттерны кодовой базы |

---

## 3. Дорожная карта улучшений

### Улучшение 1: Умная загрузка для режима MAX

**Проблема:** MAX загружает все 330 файлов, расходуя контекст на документацию
и неиспользуемый код. При 5x кандидатах это ~1.6M токенов на шаг.

**Решение:** Добавить в `mimocode.json` настройку `max_load_depth`:

```jsonc
"experimental": {
  "maxMode": {
    "candidates": 5,
    "load_strategy": "imports_only"  // NEW: загружать только файлы с релевантными связями
  }
}
```

**Алгоритм:**
1. Первый проход: построить граф импортов через `archy` (уже есть)
2. Определить "hot modules" — файлы с fan-in > 3 или fan-out > 5
3. Загрузить только hot modules + их непосредственных соседей (1 hop)
4. Остальные файлы — только заголовки и сигнатур

**Выгода:** ~60% экономия контекста → больше места для глубокого анализа.

**Реализуемость сейчас:** Частично. Можно эмулировать через skill, который
сначала запускает `archy graph`, затем формирует список файлов для загрузки.

### Улучшение 2: Сериализация состояния для долгих сессий

**Проблема:** Если агент прерван на 60% анализа, при следующем запуске начинает
с нуля. Все предыдущие findings потеряны.

**Решение:** Внедрить `state.json` для режима MAX:

```jsonc
// .mimocode/state/max-audit-state.json
{
  "run_id": "audit-2026-07-27",
  "started_at": "2026-07-27T15:47:00Z",
  "phase": "analysis",
  "completed_modules": [
    "src/core/target_sniping/*",
    "src/api/dmarket_api_client/*",
    "src/db/price_history/*"
  ],
  "pending_modules": [
    "src/risk/*",
    "src/analysis/*",
    "src/telegram/*"
  ],
  "findings": [
    {"file": "src/core/target_sniping/filter.py", "line": 501, "severity": "P1", "desc": "..."}
  ],
  "token_usage": 450000,
  "context_fill_pct": 72
}
```

**Алгоритм:**
1. В начале сессии: проверить наличие `state.json`
2. Если есть: загрузить `completed_modules` и `findings`, пропустить обработанные
3. После каждого модуля: обновить `state.json`
4. При прервании: состояние сохранено в файле

**Выгода:** Возможность возобновления долгих аудитов. Экономия токенов при
повторных запусках.

**Реализуемость сейчас:** Да, через skill с ручной логикой чтения/записи state.json.

### Улучшение 3: Интеграция удаленных MCP-серверов

**Проблема:** Все MCP-серверы запускаются локально через `npx`/`uvx`. На Steam Deck
это消耗 CPU и RAM. Некоторые задачи (arXiv поиск, web research) лучше отдавать
удалённым узлам.

**Решение:** Добавить поддержку удаленных MCP-хостов в `mimocode.json`:

```jsonc
"mcp": {
  "web-search": {
    "type": "remote",
    "url": "https://mcp-search.example.com/sse",
    "headers": {
      "Authorization": "Bearer ${MCP_SEARCH_TOKEN}"
    },
    "enabled": true
  },
  "arxiv": {
    "type": "remote",
    "url": "https://mcp-arxiv.example.com/sse",
    "enabled": true
  }
}
```

**Выгода:**
- Снижение нагрузки на локальную машину
- Доступ к высокопроизводительным узлам для тяжёлых задач
- Масштабирование без изменения локальной конфигурации

**Реализуемость сейчас:** Частично. MimoCode уже поддерживает `type: "remote"`
для MCP (config.md: "remote (url/headers/oauth)"). Нужно только настроить
конкретные серверы.

### Улучшение 4: Встроенные плагины статического анализы для MAX

**Проблема:** MAX использует только LLM-based анализ. Внешние утилиты (semgrep,
radon, mypy) запускаются вручную через bash.

**Решение:** Добавить в MAX автоматический pipeline предварительного анализа:

```jsonc
"experimental": {
  "maxMode": {
    "candidates": 5,
    "pre_analysis": {
      "enabled": true,
      "tools": [
        {"name": "semgrep", "config": "auto", "scope": "src/", "output": "findings.json"},
        {"name": "ruff", "args": ["check", "src/", "--select=E,F,W"], "output": "lint.json"},
        {"name": "archy", "args": ["score"], "output": "architecture.json"}
      ],
      "merge_strategy": "inject_as_context"  // результаты добавляются в контекст MAX
    }
  }
}
```

**Алгоритм:**
1. Перед запуском MAX: запустить все утилиты параллельно
2. Собрать результаты в структурированный JSON
3. Инжектировать как контекст в первый шаг MAX
4. MAX анализирует код с учётом уже найденных проблем

**Выгода:**
- MAX не тратит токены на поиск того, что уже нашли утилиты
- Фокус LLM на интерпретации и приоритизации, а не на поиске
- Более точные результаты (semgrep > LLM для security patterns)

**Реализуемость сейчас:** Да, через skill-обёртку, которая запускает утилиты
и формирует промпт для MAX.

---

## 4. Пример конфигурации (реализуемо сейчас)

```jsonc
{
  "$schema": "https://mimo.xiaomi.com/mimocode/config.json",

  // ─── MAX Mode ─────────────────────────────────────────────────
  "experimental": {
    "maxMode": {
      "candidates": 5
    },
    "predict_next_prompt": true
  },

  // ─── Remote MCP (Улучшение 3) ────────────────────────────────
  "mcp": {
    // ... существующие серверы ...
    "arxiv-remote": {
      "type": "remote",
      "url": "https://mcp-arxiv.glama.ai/sse",
      "enabled": false,
      "description": "Remote arXiv search — offloads local CPU"
    }
  },

  // ─── Workflow (Улучшение 1+2) ────────────────────────────────
  "workflow": {
    "maxConcurrentAgents": 4,
    "maxDepth": 4
  }
}
```

### Skill-обёртка для MAX + Pre-Analysis (Улучшение 4)

Файл: `.mimocode/skills/max-audit/SKILL.md`

```markdown
# MAX Audit Skill

## Workflow
1. Run `archy score` → capture architecture baseline
2. Run `semgrep scan --config auto src/` → capture security findings
3. Run `ruff check src/ --select=E,F,W` → capture lint issues
4. Merge all findings into `PRE_ANALYSIS.md`
5. Inject PRE_ANALYSIS.md as context for MAX reasoning
6. MAX produces final AUDIT_REPORT.md with prioritized findings

## Trigger
"audit", "full scan", "max audit", "полный аудит"
```

### Skill для MAX → Compose Pipeline (Гибридная связка)

Файл: `.mimocode/skills/audit-and-fix/SKILL.md`

```markdown
# Audit & Fix Pipeline

## Phase 1: MAX Audit
1. Load max-audit skill
2. Run MAX analysis → AUDIT_REPORT.md

## Phase 2: Compose Fix
For each P0/P1 finding in AUDIT_REPORT.md:
1. Parse finding (file, line, description)
2. Run compose workflow with task: "Fix {finding.desc} in {finding.file}:{finding.line}"
3. Verify fix with ruff + py_compile
4. Merge to main

## Trigger
"audit and fix", "найди и исправь", "full audit cycle"
```

---

## 5. Итоговая матрица приоритетов

| Улучшение | Сложность | Влияние | Статус |
|-----------|-----------|---------|--------|
| 1. Умная загрузка MAX | Средняя | Высокое (60% экономия токенов) | Можно эмулировать через skill |
| 2. Сериализация состояния | Низкая | Среднее (возобновление аудитов) | Можно реализовать через skill |
| 3. Удалённые MCP | Низкая | Среднее (снижение нагрузки) | Уже поддерживается, нужна настройка |
| 4. Pre-analysis pipeline | Низкая | Высокое (фокус LLM на интерпретации) | Можно реализовать через skill |

**Все 4 улучшения реализуемы уже сейчас** через существующие механизмы MimoCode
(skills, workflows, remote MCP). Изменения в ядре MimoCode не требуются.

---

## 6. Рекомендации для проекта DMarket Bot

### Текущий статус
- MAX активирован (`candidates: 5`)
- 9 MCP-серверов работают
- 3 аудита завершены (FULL AUDIT, DEPENDENCY AUDIT, INTER-MODULE)
- Все P0/P1 баги исправлены

### Следующие шаги
1. Создать skill `max-audit` с pre-analysis pipeline (Улучшение 4)
2. Создать skill `audit-and-fix` для гибридной связки MAX → Compose
3. Настроить удалённый MCP для arXiv поиска (Улучшение 3)
4. Добавить state.json логику в max-audit skill (Улучшение 2)

### Ожидаемый эффект
- **-60% токенов** на аудит (умная загрузка + pre-analysis)
- **+100% возобновляемость** (state.json)
- **+30% точность** (semgrep + ruff + archy перед MAX)
- **-80% ручной работы** (автоматический MAX → Compose pipeline)
