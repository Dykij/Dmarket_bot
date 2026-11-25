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
- **Check Call Sites First (Dead Code Prevention):** Before performing a deep audit or refactoring of a module or function (especially optimized paths like Rust extensions), you MUST first confirm via `ast-grep` or `code-graph-mcp` AND production logs that the code is actually invoked in the runtime path, not just present in the codebase.

## 2b. Model Policy (single model)
- The owner uses one model: Gemini 4 Hydrogen (decision 2026-11-25).
  Every subagent in .agents/agents/ has `model: inherit`, the documented
  default of the `model` field (values: inherit, flash, pro;
  https://antigravity.google/docs/subagents). Expected effect: subagents
  run on the main agent's model — not independently verified.
- Do not set `flash` or `pro`: the docs do not say which model each tier
  maps to, and Gemini 3.8 Flash and Gemini 4 Argon are removed on
  2026-11-30 (https://antigravity.google/docs/models).
- A subagent's answer about which model it is, is not RAW evidence
  (LLM self-reports of identity are unreliable).
- Default reasoning effort should not be 'High' unless the task
  genuinely requires deep multi-step reasoning — check current task
  complexity before accepting a high-effort default.
- Reference specific files via @file when known, rather than asking
  the agent to scan the repository, to reduce context overhead.
