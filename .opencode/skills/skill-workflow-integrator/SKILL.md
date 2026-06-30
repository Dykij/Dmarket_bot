---
name: skill-workflow-integrator
description: Use when orchestrating multiple existing skills for a complex task. Trigger keywords: "pipeline", "orchestrate skills", "run gate", "execute workflow", "все проверки", "запусти pipeline". Automatically chains skills in the correct order based on task type.
license: MIT
---

# Skill Workflow Integrator

Chains your existing skills in the correct order for common workflows. This prevents you from having to remember which skill to run first.

## Pre-Defined Workflows

### Workflow: Deploy Gate (Full)

Use when user wants to deploy, go live, or make production changes.

```
Step 1: git-gate
        ↓ (light checks: syntax, diff review, lint, secrets)
Step 2: full-test-suite
        ↓ (pytest + sandbox + simulation)
Step 3: pre-deploy-audit
        ↓ (security, config, DRY_RUN check)
Step 4: code-reviewer
        ↓ (AI review of all changes)
Step 5: commit-changelog
        ↓ (conventional commit + CHANGELOG update)
Step 6: git-gate push
        ↓ (worktree tests, security, push to origin)
```

**Trigger phrases:** "deploy", "go live", "production", "push to origin", "release"

### Workflow: API Change

Use when user changes API endpoints or DMarket integration.

```
Step 1: api-migration
        ↓ (check for deprecated endpoints, migrate to v2)
Step 2: full-test-suite
        ↓ (ensure no regressions)
Step 3: code-reviewer
        ↓ (review API changes)
Step 4: git-gate commit + push
```

**Trigger phrases:** "update API", "API v2", "update endpoint", "миграция API"

### Workflow: Telegram Feature

Use when user adds or modifies Telegram bot functionality.

```
Step 1: telegram-module-dev
        ↓ (implement handler/command/keyboard)
Step 2: code-reviewer
        ↓ (review Telegram code)
Step 3: full-test-suite (unit tests)
        ↓
Step 4: git-gate commit + push
```

**Trigger phrases:** "telegram", "add command", "new button", "keyboard", "добавить команду"

### Workflow: Rust Build

Use when user modifies Rust parser or PyO3 bindings.

```
Step 1: rust-build
        ↓ (zig linker, maturin develop, verify)
Step 2: full-test-suite
        ↓ (verify Python-Rust integration)
Step 3: code-reviewer
        ↓ (review unsafe blocks, bindings)
Step 4: git-gate commit + push
```

**Trigger phrases:** "rebuild Rust", "собери Rust", "compile Rust", "maturin"

### Workflow: Strategy Update

Use when user modifies trading strategy or risk parameters.

```
Step 1: strategy-validate
        ↓ (sandbox + profitability report)
Step 2: code-reviewer
        ↓ (review strategy logic)
Step 3: full-test-suite
        ↓ (risk tests, pump detector)
Step 4: git-gate commit + push
```

**Trigger phrases:** "validate strategy", "check strategy", "стратегия", "profitability", "sandbox"

## Rules for Workflow Execution

1. **Always respect gates**: If any step fails, STOP the pipeline. Do not proceed to next step.

2. **Never skip the gate**: Even for "urgent" fixes, at minimum run LIGHT checks (syntax, diff review).

3. **Log all findings**: Write gate results to `memory/YYYY-MM-DD.md` for accountability.

4. **Parallel where possible**: 
   - `api-migration` + `code-reviewer` can run in parallel after changes are staged
   - `full-test-suite` + `strategy-validate` can run in parallel (different processes)
   Default concurrency: 2 parallel subagents.

5. **Escalation**: If the user demands to skip a step ("just push it"):
   - Warn about risks
   - Require explicit confirmation with reason
   - Log the bypass to memory