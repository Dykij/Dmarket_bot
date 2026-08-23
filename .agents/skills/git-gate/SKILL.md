---
name: git-gate
description: Use ONLY when git operations (commit, push, merge) are attempted. Trigger keywords: "git commit", "git push", "git merge", "закоммить", "запушить", "git gate", "no-mistakes", "quality gate". Enforces mandatory validation pipeline before any code reaches origin.
license: MIT
---

# Git Gate — No-Mistakes Workflow

This skill enforces a validation pipeline **before any git commit or push** can proceed. It combines the best of no-mistakes (AI review, tests, linting in worktree) with your existing skill-based checks.

## When to Use

- Before any `git commit` or `git push` operation
- When user says "commit", "push", "закоммить", "запушить"
- When user wants to merge or create a PR
- When code review or quality gate is requested

## Core Principle

**No code reaches `origin` without passing the gate.**

The pipeline runs in a **disposable worktree** (isolated from your working directory), so your work is never blocked.

## Git Operation Flow

### Phase 1: Pre-Commit Checks (LIGHT — fast, local)

Run immediately on any `git commit` attempt:

```bash
# 1. Diff review
> git diff --cached --stat
# ↳ User must review (AGENTS.md rule: never commit unreviewed code)

# 2. Syntax check (only changed files)
> git diff --cached --name-only --diff-filter=ACM | grep '\.py$' | xargs -r python -m py_compile

# 3. Fast lint (fatal only)
> ruff check src/ --select=F,E --output-format=concise --quiet

# 4. No secrets (basic scan)
> git diff --cached | grep -i "password\|secret\|token" && echo "WARNING: potential secret"
```

**If any LIGHT check fails → BLOCK commit, show errors.**

### Phase 2: Pre-Push Pipeline (FULL — worktree-based)

When `git push` is attempted (or `git-gate push` command), create a disposable worktree:

```bash
# 1. Create isolated worktree
> git worktree add /tmp/gate-$(git rev-parse --short HEAD) --detach
> cd /tmp/gate-$(git rev-parse --short HEAD)

# 2. Install dependencies
> source .venv/bin/activate  # or create isolated venv

# 3. Run AI Code Review (your code-reviewer skill)
# Review all changed files for correctness, safety, style

# 4. Run Full Test Suite (your full-test-suite skill)
> python -m pytest tests/ -x -q --tb=short

# 5. Run sandbox validation (your strategy-validate skill)
> ENCRYPTION_KEY="test" python -m tests.sandbox_full_cycle

# 6. Run pre-deploy audit (your pre-deploy-audit skill)
# Checks: security, config, DRY_RUN, encryption keys

# 7. Run Rust build (if rust files changed)
# maturin develop --features pyo3/extension-module
```

**If any FULL check fails → show findings, user fixes and re-runs.**

### Phase 3: Clean Merge

After all checks pass:
- Branch is pushed to `origin`
- Clean PR is opened (auto-generated title from conventional commits)
- CI runs on PR (as backup, not primary gate)

## Workflow Summary

```
User: git push origin my-branch
      │
      ▼
┌────────────────────────────────────────────────────────┐
│  GIT GATE                                              │
│  1. Pre-commit checks (LIGHT) → block if fail          │
│  2. Create worktree                                     │
│  3. AI code review (code-reviewer skill)              │
│  4. Tests (full-test-suite skill)                       │
│  5. Sandbox (strategy-validate skill)                  │
│  6. Security audit (pre-deploy-audit skill)            │
│  7. Rust build (rust-build skill, if needed)           │
│  8. Push to origin + Open clean PR                      │
└────────────────────────────────────────────────────────┘
```

## Integration with Existing Skills

This skill **orchestrates** your existing skills:

| Step | Existing Skill | What It Does |
|------|---------------|-------------|
| AI Review | `code-reviewer` | Structured code review for correctness and safety |
| Tests | `full-test-suite` | pytest + sandbox + simulation |
| Strategy | `strategy-validate` | Sandbox run and profitability report |
| Security | `pre-deploy-audit` | ENCRYPTION_KEY, DRY_RUN, config checks |
| Rust | `rust-build` | PyO3 extension compilation |
| API | `api-migration` | Endpoint deprecation check (if api/ changed) |
| Commit | `commit-changelog` | Conventional commit format, CHANGELOG update |
| Reflexion | `src/reflexion/` | State/Snapshot + rollback for safe code changes |
| Workflow | `src/workflow/` | Async pipeline orchestration (Parser→Coder→Tester) |
| Sandbox | `src/sandbox/` | Safe bash execution with timeout + security |
| CoT Audit | `src/cot_audit/` | Chain-of-Thought formatting + metadata cache |

## Commands

### `git-gate commit <msg>`
Runs LIGHT checks + commits with conventional format.

### `git-gate push`
Runs FULL pipeline in worktree, then pushes if green.

### `git-gate status`
Shows current gate status (which checks passed/failed).

### `git-gate skip`
**DANGER: Bypass gate (requires confirmation).** Logs reason to `memory/YYYY-MM-DD.md`.

## Error Handling

- **Syntax error**: Stop immediately, show line + fix suggestion
- **Test failure**: Show failed test name + output
- **Sandbox fail**: Show profitability report (if strategy unprofitable)
- **Security audit fail**: Show which check failed (never allow push)
- **AI review finding**: Show severity (critical/warning/nit) + recommendation

## Philosophy

**This is a gate, not a replacement for thinking.**

The gate catches:
- Broken code (syntax, tests)
- Unreviewed changes (diff check)
- Security mistakes (secrets, debug flags)
- Strategy regressions (unprofitable sandboxes)

It does NOT:
- Write code for you
- Guarantee profitability (that's strategy-validate's job)
- Replace architecture decisions

## Related Files

- `opencode.json` — Permission config (blocks raw `git push` via OpenCode)
- Skills: `code-reviewer`, `full-test-suite`, `pre-deploy-audit`, `strategy-validate`, `rust-build`, `commit-changelog`
- New modules: `reflexion/`, `workflow/`, `sandbox/`, `cot_audit/`
- Based on: https://github.com/kunchenguid/no-mistakes
- SkillsMP: https://skillsmp.com