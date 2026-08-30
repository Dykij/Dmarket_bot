---
name: raw-discipline
description: Strict guidelines for RAW command execution and output quoting.
---

# RAW Discipline

## Investigation Completeness (Pipeline Context Before Severity)
A finding based on an isolated snippet is provisional, not final. Before assigning severity (Critical/High/Medium/Low) to any bug:
- Trace the code path both upstream (who calls this function, what happens before this line executes) and downstream (what consumes this function's output) — not just the isolated block you first spotted. A control-flow claim ("X happens after Y", "check is missing", "value is never used") requires having actually looked at the surrounding pipeline, not just the function where you noticed it.
- Before writing "missing" or "never called" — grep for the function/check across the whole relevant subsystem (not just the file open in front of you). A check can legitimately live in a different file earlier in the pipeline.
- When quoting code as evidence, quote enough surrounding lines to show the full conditional/control-flow block (the whole if/else, the whole function signature to return), not an arbitrary line range picked to fit a message. A reader should be able to verify your claim from the quote alone, without re-running the command.
- If a first-pass finding turns out to be incomplete once the pipeline is traced (as happened with the execution.py risk-manager finding in this session — first read as "risk check skipped in PROD", full trace showed it runs twice in PROD as a binary gate, and the actually-buggy code was DRY_RUN-only dead code) — report the corrected version explicitly, don't quietly patch the earlier claim without flagging that the severity/nature of the finding changed.

## Tool-First Investigation
When a more precise tool is configured and applicable, using it is not optional — plain grep is a fallback, not a default:
- Finding all callers/usages of a function or class → cclsp find_references, not grep (grep misses aliased imports, dynamic dispatch, and gives false positives on substring matches).
- Security/vulnerability patterns (injection, unsafe eval, missing bounds/sign checks, unchecked return values) → run semgrep BEFORE manual code review, and report its findings alongside manual review, not instead of grep alone.
- Architecture/circular-dependency/module-coupling questions → archy, not manual file-by-file tracing.
- Library/API usage questions (is this the correct current signature) → context7, not memory or assumption.
- If a configured tool fails or is unavailable for the task, say so explicitly and name which tool was skipped and why — do not silently fall back to grep without disclosing the downgrade in confidence.

## Actions & Changes
When citing code as evidence for a finding, include the full relevant block (complete function or complete conditional branch), not a minimal snippet — enough that severity and control-flow claims can be verified from the quote alone.
