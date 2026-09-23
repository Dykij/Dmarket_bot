---
name: Investigation Rigor
description: Rules for thorough investigation, pipeline tracing, and model tier selection.
trigger: always_on
---

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
- **Check Call Sites First (Dead Code Prevention):** Before performing a deep audit or refactoring of a module or function (especially optimized paths like Rust extensions), you MUST first confirm via `grep` or `cclsp find_references` AND production logs that the code is actually invoked in the runtime path, not just present in the codebase.

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
