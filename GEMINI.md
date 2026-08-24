@docs/MEMORY.md
@docs/SESSION_LOG.md
@AGENTS.md

# Engineering Rigor Protocol
- **No Truncation Rule:** Never omit, summarize, or hide RAW command output for length or brevity reasons. If output is genuinely long, split it across multiple messages in full.
- **RAW-дисциплина:** Ни один вывод отчёта не может содержать утверждение о результате команды без вставленного RAW-вывода этой команды в том же сообщении.
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
- Track B / Agent Infrastructure: Аудит агентской инфраструктуры и конфигурации MCP-серверов → `lsp-mcp-integration-auditor`.

# Section 2a. Investigation Completeness (Pipeline Context Before Severity)

A finding based on an isolated snippet is provisional, not final. Before
assigning severity (Critical/High/Medium/Low) to any bug:

- Trace the code path both upstream (who calls this function, what
  happens before this line executes) and downstream (what consumes
  this function's output) — not just the isolated block you first
  spotted. A control-flow claim ("X happens after Y", "check is
  missing", "value is never used") requires having actually looked at
  the surrounding pipeline, not just the function where you noticed it.
- Before writing "missing" or "never called" — grep for the function/
  check across the whole relevant subsystem (not just the file open in
  front of you). A check can legitimately live in a different file
  earlier in the pipeline.
- When quoting code as evidence, quote enough surrounding lines to show
  the full conditional/control-flow block (the whole if/else, the whole
  function signature to return), not an arbitrary line range picked to
  fit a message. A reader should be able to verify your claim from the
  quote alone, without re-running the command.
- If a first-pass finding turns out to be incomplete once the pipeline
  is traced (as happened with the execution.py risk-manager finding in
  this session — first read as "risk check skipped in PROD", full trace
  showed it runs twice in PROD as a binary gate, and the actually-buggy
  code was DRY_RUN-only dead code) — report the corrected version
  explicitly, don't quietly patch the earlier claim without flagging
  that the severity/nature of the finding changed.

## 2b. Model Tier Policy (Credit Efficiency)
- Routine, mechanical, low-ambiguity subtasks (docstrings, formatting,
  simple config edits, single-file grep-and-report checks) → route to
  Flash-tier where the harness allows explicit model selection.
- Complex reasoning (architecture decisions, multi-file trace-the-
  pipeline analysis per Section 2a, statistical judgment, security
  review) → Pro tier only.
- Default reasoning effort should not be 'High' unless the task
  genuinely requires deep multi-step reasoning — check current task
  complexity before accepting a high-effort default.
- Reference specific files via @file when known, rather than asking
  the agent to scan the repository, to reduce context overhead.
- This policy already governs subagent model assignment
  (raw-evidence-auditor/regression-isolator/scope-auditor: flash;
  stats-skeptic/code-auditor: pro) — apply the same reasoning to the
  main agent's own task routing where the harness supports it.
- As of Aug 2026, Gemini 3.7 Flash is the current Flash-tier model in Antigravity, with
  substantially improved coding/debugging benchmarks over prior Flash versions — prefer it
  explicitly for routine tasks over relying on an unspecified 'flash' tier default, if the
  harness allows explicit model version selection at the main-agent level.
- (Verified Aug 2026): The subagent `flash` tier automatically resolves to Gemini 3.7 Flash.
  Однако, поскольку новые версии моделей у Google выходят каждые 2-4 недели
  (судя по цепочке 3.5→3.6→3.7 Flash за последние 2 месяца), рекомендуется
  периодически перепроверять актуальность под капотом, чтобы не застрять на старой версии.
- ВАЖНО: версия тира flash НЕ подтверждена независимым
  источником по состоянию на 2026-08-24; предыдущее подтверждение через
  прямой вопрос субагенту 'какая ты модель' признано ненадёжным —
  самоотчёт LLM о собственной идентичности не является RAW-доказательством, 
  особенно при риске заражения контекстом. Требует либо документального,
  либо ручного (UI) подтверждения.

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
