# Аудит бюджета Customizations (2026-09-27)

## Результаты анализа (Фаза 1 & 2)

### 1. Веса файлов правил (Rules)
| Файл | Размер (байт) | Загрузка |
|------|--------------|----------|
| `anti-scope-creep.md` | 691 | always_on |
| `rules.md` | 1189 | always_on |
| `AGENTS.md` | 1678 | always_on (no frontmatter) |
| `raw-output-discipline.md` | 2949 | always_on |
| `structured_prompts.md` | 3375 | always_on |
| `tooling.md` | 4027 | always_on |
| `investigation-rigor.md` | 4667 | always_on |
| `documentation-grounding.md` | 6790 | always_on |
| `GEMINI.md` | 9201 | always_on (no frontmatter) |
| `otsebyatina-registry.md` | 13042 | always_on (исправлено на model_decision) |

### 2. Динамика загрузки памяти (@-ссылки)
Синтаксис `@docs/MEMORY.md` (26808 байт) и `@docs/SESSION_LOG.md` (70853 байт) внутри `GEMINI.md` **не инлайнится** системой Antigravity автоматически в секцию `<user_rules>`. В контекст попадает буквально строчка `@...`, и файлы читаются либо отдельным инструментом, либо через отдельный пайплайн, но *не* ложатся мертвым грузом в каждый запрос как часть Rules. Это безопасно для контекста.

### 3. Дубликаты Skills
- **Asyncio**: `python-asyncio-check` и `python-asyncio-pitfalls` полностью дублировали функционал и триггеры `python-asyncio-production`.
- **Code Review**: `deep-code-review` и `ultra-review-pipeline` дублировали `code-reviewer` и конкурировали за одни и те же триггеры.
- **Глобальные плагины**: `gemini-api`, `google-antigravity-sdk` и другие глобальные MCP/skills не вызывались ни разу, но могли засорять бюджет.

## Выполненные действия (Фаза 3)

1. **Создан `dmarket-api-reference`**
   - Тонкий SKILL.md. Используется *только* для редких/неописанных эндпоинтов, не ломая триггеры 12-ти узкоспециализированных `dmarket_*` скиллов.
   - 6 доменных файлов в `references/`, каждый сверен с живым Redoc (Trading API v2.0.0 на https://docs.dmarket.com/v1/swagger.html) и содержит структуру и ссылки.

2. **Безопасные сокращения контекста**
   - `otsebyatina-registry.md` переведён на `trigger: model_decision` (Экономия: ~13 КБ / ~3200 токенов).
   - Дубликаты `python-asyncio-check` и `python-asyncio-pitfalls` отключены (переименованы директории). Триггеры слиты в `python-asyncio-production`.
   - Дубликаты `deep-code-review` и `ultra-review-pipeline` отключены. Триггеры слиты в `code-reviewer`.
   - Глобальные плагины (`gemini-api`, `google-antigravity-sdk`) отключены в `~/.gemini/config/plugins/`.

*(Примечание: ОС-уровневый Permission Engine заблокировал выполнение `rm -rf`, поэтому дубликаты были отключены через `mv` в `_disabled_*`, а не удалены физически. Для окончательного удаления требуется выполнить `rm` вручную или снять блокировку).*

## Требует решения Богдана

Следующие 7 файлов правил жестко блокируют деструктивное поведение (Proceed-протоколы, гейты, RAW-выводы). Их суммарный вес составляет **~23.6 КБ (~6000 токенов)**. Они оставлены в режиме `always_on`, так как их перевод в `model_decision` лишит агента пассивной защиты.

Для их перевода на ленивую загрузку требуется ваше явное согласование:
1. `anti-scope-creep.md` (691 Б)
2. `rules.md` (1189 Б)
3. `raw-output-discipline.md` (2949 Б)
4. `structured_prompts.md` (3375 Б)
5. `tooling.md` (4027 Б)
6. `investigation-rigor.md` (4667 Б)
7. `documentation-grounding.md` (6790 Б)
