---
name: skill-workflow-integrator
description: "Use when orchestrating multiple existing skills for a complex task. Trigger keywords: pipeline, orchestrate skills, run gate, execute workflow, все проверки, запусти pipeline. Automatically chains skills in the correct order based on task type."
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

### Workflow: Strategy Calibration

Use when the user wants to adapt the strategy based on the current market volatility regime, cointegration candidates, and trend strength.

```
Step 1: volatility-modeling (GARCH/EWMA calibration)
        ↓
Step 2: cointegration-analysis (pair validity check)
        ↓
Step 3: mean-reversion (Hurst/half-life on candidate pairs)
        ↓
Step 4: quant-analyst (существующий, Kelly sizing)
        ↓
Step 5: strategy-validate (существующий тест)
```

**Trigger phrases:** "calibrate strategy", "market regime calibration", "калибровка"

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

## Multi-Agent Orchestration (Enhanced)

### Specialized Agent Types

For complex workflows, delegate tasks to specialized agents:

```
trading-agent: Trading strategy and risk management tasks
test-agent: Test execution and validation tasks  
deploy-agent: Deployment and infrastructure tasks
review-agent: Code review and security audit tasks
```

### Parallel Execution Pattern

When tasks are independent, execute in parallel:

```markdown
Task: Deploy with full validation

Step 1 (Parallel):
  - Agent A: checkpoint-manager (create checkpoint)
  - Agent B: git-gate (light validation)
  - Agent C: code-reviewer (security scan)

Step 2 (Sequential):
  - full-test-suite (run all tests)
  
Step 3 (Parallel):
  - Agent A: browser-test (UI validation)
  - Agent B: strategy-validate (trading validation)
  
Step 4: Deploy (if all pass)
```

### Conditional Branching

Route workflows based on file changes:

```markdown
IF file_changed("*.py") THEN
  Step 1: python-asyncio-check
  Step 2: code-reviewer
ELSE IF file_changed("*.rs") THEN
  Step 1: rust-build
  Step 2: code-reviewer  
ELSE IF file_changed("src/telegram/*") THEN
  Step 1: telegram-module-dev
  Step 2: code-reviewer
ELSE
  Step 1: code-reviewer
END IF
```

### Agent Coordination Rules

1. **Shared Context**: All agents share access to `memory/` and project files
2. **Isolation**: Each agent has its own context window (no cross-contamination)
3. **Synchronization**: Use checkpoints as sync points between agents
4. **Failure Handling**: If any agent fails, halt the entire workflow

### Performance Optimization

- **Cache Results**: Store agent outputs in memory for reuse
- **Batch Operations**: Group similar tasks for efficiency
- **Progressive Loading**: Load only necessary context for each agent