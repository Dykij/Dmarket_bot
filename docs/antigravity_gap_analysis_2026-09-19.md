# Antigravity Gap Analysis (2026-09-19)

## 1. Skills и триггеры субагентских скиллов
`GAP [severity: major]: Наличие триггеров и структура описаний — доки говорят "Write clear descriptions (3rd person, specific keywords), Include decision trees" (документация недоступна напрямую, цитата из прошлого чеклиста), реальность: большинство из 45+ скиллов не имеют триггерных слов, а у многих (напр., trading-agent, ultra-review-pipeline) описание является многострочным YAML без формата "Use when". → расхождение: Отсутствие стандартизированных триггеров ломает механизм автоматического вызова скиллов.`

## 2. Промтинг и его построение
`GAP [severity: major]: Отсутствие frontmatter в правилах — доки говорят "Правила должны иметь frontmatter и поле trigger" (подразумевается архитектурой), реальность: файлы .agents/rules/anti-scope-creep.md, .agents/rules/otsebyatina-registry.md, .agents/rules/rules.md физически не имеют frontmatter и поля trigger: (RAW: строки 1-10 не содержат ---). → расхождение: Критические правила проекта не подгружаются контекстным движком.`

`GAP [severity: major]: RAW-per-step дисциплина — доки говорят "Любая команда... перенаправляется в файл... затем wc -l" (.agents/rules/raw-output-discipline.md), реальность: систематические нарушения агентом (включая попытки симуляции верификации H18) из-за сломанной инфраструктуры хуков. → расхождение: Дисциплина заявлена в правилах, но фактически игнорируется на уровне исполнения.`

## 3. Субагенты и их работа
`GAP [severity: critical]: Схема frontmatter субагентов — доки говорят "exact frontmatter schema name, description, tools[], model, commandExecutionPolicy, mcpServers, skills/plugins" (Known Issue: Specifying an unmapped or misspelled tool name... may cause the subagent process to hang), реальность: ни один из 9 субагентов в .agents/agents/*/agent.md не содержит обязательные поля mcpServers и skills/plugins. → расхождение: Потенциальный отказ или зависание субагентов из-за неполной схемы фронтматтера.`

## 4. Общая архитектура/структура Antigravity в проекте
`GAP [severity: critical]: Работоспособность Hook-скриптов — доки говорят "Хуки должны выполняться согласно hooks.json", реальность: 6 из 9 скриптов физически отсутствуют в репозитории (ls: невозможно получить доступ к 'scripts/validate_skills_frontmatter.sh', 'scripts/verdict_gate.sh', 'scripts/raw_output_logger.sh', 'scripts/pre_bypass_gate.sh', 'scripts/session_init.sh', 'scripts/checkpoint_guard.sh'). → расхождение: Полный отказ защитной пайплайн-инфраструктуры, заявленной в hooks.json.`

`GAP [severity: minor]: Отсутствующие нативные фичи (Sidecars, Scheduled Tasks) — доки говорят "Sidecars, Scheduled Tasks" (поиск в features), реальность: настройки для них отсутствуют в mcp_config.json и settings.json. → расхождение: Фичи не используются в проекте.`

`GAP [severity: minor]: Доступность документации — доки говорят "официальная документация Antigravity", реальность: страница https://antigravity.google/docs/features/ содержит только 4 базовые ссылки (на главную, download, remote control), разделы Hooks, Skills, Subagents и др. отсутствуют в списке. → расхождение: Невозможность провести полный аудит доков из-за их недоступности по указанному URL.`

`SAFE: Permission Engine настроен и активен (в .antigravity/settings.json прописан deny на sudo, rm -rf, curl .*, .git/, и .env).`
`SAFE: MCP-серверы корректно сконфигурированы (mcp_config.json содержит 9 активных серверов, включая sequential-thinking и archy).`
`SAFE: 3 hook-скрипта (pre_danger_gate.sh, stop_gate.sh, difftastic_gate.sh) существуют и имеют права на исполнение.`

## 5. Дополнительная проверка документации (Direct URLs)
`NOT_VERIFIED: страница рендерится клиентским JS, WebFetch не видит контент. Попытки обратиться напрямую к https://antigravity.google/docs/hooks/ и https://antigravity.google/changelog/ возвращают лишь HTML-скелет (Astro/Starlight) без текстового содержимого разделов.`

## 2026-09-19: Document Scan and Changelog Update (Phase E)

**NOT_VERIFIED:** `https://antigravity.google/docs/hooks/`
- Страница рендерится клиентским JS (Astro Starlight), WebFetch видит только пустой skeleton: `"Skip to contentGoogle Antigravity DocsSearchCtrlKCancel"`. Прямое сканирование контента хуков невозможно без браузера.

**SAFE / RISK:** `https://antigravity.google/changelog/`
- **SAFE**: Версия 2.15.0 (September 18, 2026) содержит изменения для custom agents: *"Custom agents can now switch off the default prompt sections and default tools and add back only the tools they need."* Это может пересекаться с проблемой пустого `mcpServers/skills`, так как явно введено управление отсутствием дефолтных тулзов.
- **RISK**: Ни 2.15.0, ни 2.14.0 не содержат упоминаний фиксов для "sbox-сертификат", "tools[]-hang" (напрямую), "catch-22 хуков" или новых событий жизненного цикла ("SubagentStop").


### Phase 0-4 Audits (2026-09-19 19:00+)

*   **GAP [severity: high]:** Hooks did not execute on real `run_command` and `write_to_file` calls. End-to-end testing showed logs remaining empty. The hook dispatcher might have a caching issue or routing bug for dynamically updated `hooks.json`. (Status: NOT_VERIFIED, requires further diagnosis of the hook runner).
*   **GAP [severity: medium]:** `scripts/` duplicate files were outdated stubs except for `difftastic_gate.sh` and `pre_danger_gate.sh`. The root directory contained a mix of core infrastructure, setup scripts, and hook duplicates. (Status: RESOLVED by merging `difftastic_gate.sh` logic into `.agents/scripts/` and scheduling duplicates for deletion).
*   **GAP [severity: medium]:** `validate_skills_frontmatter.sh` was incorrectly bound to a non-existent `SessionStart` hook event. It also printed raw stdout instead of the required `injectSteps` array. (Status: RESOLVED by switching to `PreInvocation` and reformatting the output).
*   **GAP [severity: low]:** `.antigravity/settings.json` used `command(curl .*)` instead of the correct `command(regex:curl .*)` schema format. (Status: RESOLVED).
*   **GAP [severity: low]:** Several `commandExecutionPolicy` fields in subagents were set to an invalid `false` instead of `ask`. (Status: RESOLVED).
*   **GAP [severity: low]:** `cclsp` MCP server was registered but not available/installed. (Status: RESOLVED by removing it from `mcp_config.json`).

### Phase 5 Final Review (2026-09-19 19:20+)
*   **GAP [severity: critical, status: ACCEPTED/UNRESOLVED]:** hook-раннер не перехватывает PreToolUse/PostToolUse на реальных tool-call'ах ни в одной из проверенных сессий; причина не найдена; все hook-based guardrails (checkpoint-guard, pre-danger-gate, pre-bypass-gate, difftastic-gate) считать недействующими до дальнейшего расследования. 
    *   **Fallback:** OS-level Permission Engine (`.antigravity/settings.json`) подтверждён рабочим независимо от hooks.json (это отдельный механизм) — он остаётся единственной реально действующей линией защиты от `sudo`/`rm -rf`/`.env`/`.git` прямо сейчас (deny-паттерны в settings.json статически корректны по документации, но живой перехват rm -rf этой сессией не подтверждён).

    *   **Примечание по сессиям:** Тест через subagent не был чистым повтором (subagent не имел write-доступа), и вывод о глухоте хук-раннера опирается исключительно на ретест в текущей сессии.