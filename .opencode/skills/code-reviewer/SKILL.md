---
name: code-reviewer
description: Use when the user asks to review, verify, audit, or double-check generated code. Trigger keywords: "review code", "проверь код", "code review", "audit code", "verify code", "ревью кода", "проревьюируй", "double-check".
---

# Code Reviewer

Perform a focused, structured review of code that was just generated or modified.

## Review Checklist

1. **Syntax & Compilation**
   - Does the code parse/compile in the target language?
   - Are imports, types, and function signatures correct?

2. **Correctness**
   - Does the change actually solve the stated problem?
   - Are there off-by-one errors, race conditions, null references, or unhandled exceptions?
   - Are edge cases handled (empty input, large input, errors)?

3. **Consistency**
   - Does the style match the surrounding codebase?
   - Are naming conventions, error handling, and logging consistent with existing files?

4. **Safety**
   - Are there any security issues (injection, unsafe eval, hardcoded secrets)?
   - Are file paths, shell commands, or network calls handled safely?

5. **Performance & Maintainability**
   - Are there unnecessary loops, allocations, or redundant operations?
   - Is the code readable and appropriately commented?

## Heavy Tasks: Decompose and Delegate to Subagents

If the review request involves a large feature, a refactor across many files, or a deep audit of a whole subsystem, do **not** try to review everything in one monolithic pass. Instead:

1. **Decompose** the review into focused sub-reviews, for example:
   - API/oracle layer review
   - Trading strategy logic review
   - Risk-management layer review
   - Data/analytics layer review
   - Control/Telegram layer review
   - Concurrency and security review

2. **Delegate each sub-review to a subagent** using the `task` tool with `subagent_type: explore`. Give each subagent a narrow scope and specific files to examine.

3. **Synthesize** the subagent findings into a single coherent report with:
   - Cross-cutting issues (e.g., inconsistent drawdown thresholds, duplicated DB logic)
   - File-by-file critical findings
   - Prioritized action items

4. **Escalate** any critical security or correctness issue immediately rather than burying it in a long list.

Use this decomposition whenever the user asks for:
- Full codebase audit
- Architecture review
- Refactor validation
- Post-incident root-cause analysis
- Multi-file PR review

## Output Format

Provide a concise review with:
- **Summary**: 1-2 sentences on overall quality.
- **Issues**: Bullet list of concrete problems, ordered by severity (critical / warning / nit).
- **Recommendations**: Specific code changes or refactors, if any.
- **Verdict**: `APPROVE`, `APPROVE WITH CHANGES`, or `NEEDS REWORK`.

If the code is correct and clean, explicitly say so instead of inventing issues.
