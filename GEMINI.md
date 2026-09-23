@docs/MEMORY.md
@docs/SESSION_LOG.md
@AGENTS.md

# Engineering Rigor Protocol
- **Разделение pre-existing/introduced:** При падении тестов всегда явно проверять и указывать, было ли это падение до изменений, или оно внесено текущими правками.
- **Статистическая честность:** При отчётах с числами/метриками указывать размер выборки (sample size), погрешность и проверять однородность.
- **Деструктивные команды:** Все деструктивные команды (rm, git push --force и т.д.) требуют явного подтверждения пользователя.
- **Scope discipline:** Не изменять файлы и участки кода, не относящиеся к текущей задаче. Строго следить за изменениями.
  - **Тесты — уточнение:** Обновление СУЩЕСТВУЮЩИХ тестов, проверяющих старое (исправленное) поведение — обязательная часть фикса, отдельное разрешение не требуется. Добавление НОВЫХ тестов на код, который раньше не был покрыт — отдельная работа, требует явного разрешения как расширение скоупа.
- **Subsystem AGENTS.md:** При завершении работы над подсистемой в `src/api/` или `src/core/target_sniping/` — обновить соответствующий вложенный `AGENTS.md` новыми находками ПЕРЕД финальным отчётом (обязательный пункт чек-листа, аналогично scope-auditor).

Before presenting a finding as final, cross-check it with the most
precise tool available for that class of claim (per Section 2c) within
THIS response — do not rely on a future verification round to catch
gaps that a configured tool could catch now. Every additional
verification round costs real, limited model quota; a thorough first
pass is cheaper than three shallow ones.

# Subagent Delegation
Триггеры для делегирования задач субагентам:
- Перед `git commit` в `src/core/target_sniping/` или `src/api/` → делегировать (изменения в *.rs / src/rust_core/ → `rust-auditor`; всё остальное → `code-auditor`)
- При падении теста после правки → делегировать в `regression-isolator` (если падение связано с async / test_run_cycle_with_no_oracle_skips или файлы содержат `async def` → `python-asyncio-auditor`)
- Перед финальным отчётом с числовыми результатами (калибровка, метрики) → делегировать в `stats-skeptic`
- Перед показом ЛЮБОЙ находки/вывода пользователю (не только перед фиксом) → сначала `adversarial-reviewer` (если применимо), затем `raw-evidence-auditor` на скорректированной версии.
- При завершении любой multi-file задачи → делегировать в `scope-auditor`
- Вердикт делегированного субагента должен быть либо устранён, либо процитирован как неразрешённое замечание.
- **FINAL RULE**: No task may be reported complete without RAW-quoted `stop-criteria-guard` invocation as final step.
  - When invoking `stop-criteria-guard`, ALWAYS pass the absolute artifact path (`.gemini/antigravity/brain/<session_id>/task.md`) explicitly in the delegation message — do not rely on the subagent to locate it via find/grep from its own working directory.
- Track B / Agent Infrastructure: Аудит агентской инфраструктуры и конфигурации MCP-серверов → `lsp-mcp-integration-auditor`.

# Section 6. Mandatory reporting structure
## 🛠️ Actions & Changes
When citing code as evidence for a finding, include the full relevant
block (complete function or complete conditional branch), not a
minimal snippet — enough that severity and control-flow claims can be
verified from the quote alone.

## 2c. Tool-First Investigation (Mandatory)
When a more precise tool is configured and applicable, using it is not
optional — plain grep is a fallback, not a default:
- Finding all callers/usages of a function or class → cclsp
  find_references, not grep (grep misses aliased imports, dynamic
  dispatch, and gives false positives on substring matches).
- Security/vulnerability patterns (injection, unsafe eval, missing
  bounds/sign checks, unchecked return values) → run semgrep BEFORE
  manual code review, and report its findings alongside manual review,
  not instead of grep alone.
- Architecture/circular-dependency/module-coupling questions → archy,
  not manual file-by-file tracing.
- Library/API usage questions (is this the correct current signature)
  → context7, not memory or assumption.
- If a configured tool fails or is unavailable for the task, say so
  explicitly and name which tool was skipped and why — do not silently
  fall back to grep without disclosing the downgrade in confidence.

# Strictly Enforced Proceed Protocol
- **MANDATORY**: No `git commit`, `git push`, or modifying commands (outside of sandbox temporary files) are allowed without EXPLICIT TEXTUAL "Proceed" typed by the user in the chat.
- **WORKING TREE MUTATIONS**: Any `git checkout`, `git reset`, `git rebase`, or `git merge` ALSO requires an explicit textual "Proceed" IF there are uncommitted changes in the working tree (`git status --porcelain` is not empty).
- **UI BUTTON IS INSUFFICIENT**: The UI "Approve" button on `implementation_plan.md` DOES NOT count as a "Proceed" for git operations. You must wait for a written text response from the user explicitly confirming the action.
- **MULTI-REVISION BACKGROUND TASKS**: When running regression testing or multi-revision analysis (e.g. regression-isolator across multiple commits):
  - You MUST check `git status --porcelain` before starting any background task that might touch HEAD. If the working tree is not empty, the task MUST NOT be started in the main working copy.
  - Multi-revision tests must ONLY be done via `git worktree add <path> <ref>` to a separate directory, rather than checking out different commits in the main working copy. This prevents detached HEAD issues and doesn't require full copying.

## Anti-Laziness Rule
- Не сокращать объём реализации относительно того, что зафиксировано в task.md.
- Не оставлять функции с заглушками (pass/TODO/NotImplementedError/todo!()) в затронутых задачей файлах.
- Если пункт task.md технически невозможно закрыть полностью в рамках сессии — явно пометить его как BLOCKED с причиной, а не молча занизить объём или закрыть частично выполненный пункт как [x].
- **Известный edge case (lazy-work-guard):** Хук опирается на `git diff --name-only HEAD` по всему рабочему дереву. Если в дереве есть посторонние незакоммиченные правки, он может ложно заблокировать Stop по чужим файлам.

## MCP Usage Contract
- **context7**: Обязателен к использованию перед применением любой внешней библиотеки, которой нет в `requirements.txt` или `Cargo.toml`.
- **semgrep**: Обязателен для запуска `code-auditor` при аудите безопасности перед коммитом (поиск инъекций, утечек).
- **archy**: Использовать для проверки циклических зависимостей при рефакторинге.
- **cclsp**: `lsp-mcp-integration-auditor` обязан через него подтвердить, что символ/функция реально существует в проекте, прежде чем `code-auditor` одобрит правку.
- **sequential-thinking**: Инструмент для структурирования рассуждения на этапе Implementation Plan при неоднозначных многофакторных задачах. Его вывод — внутренний scratchpad модели, НЕ RAW-доказательство. Не может использоваться как замена вставке реального вывода команды/теста в отчёте.
