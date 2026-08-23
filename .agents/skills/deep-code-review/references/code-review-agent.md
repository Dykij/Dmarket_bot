# Code Review Agent — Multi-Agent Ultra Review

Use this agent for deep, verified code reviews inspired by Claude Code's `/code-review ultra`.
Launches 6 parallel reviewer agents, verifies each finding, and produces a consolidated report.

## Capabilities
- 6-agent parallel review (Correctness, Security, Performance, Architecture, Domain, Test Coverage)
- Independent verification of each finding (CONFIRMED / FALSE_POSITIVE / NEEDS_MANUAL)
- False positive filtering through reproduction
- Depth levels: low / medium / high / ultra
- Integration with git-gate pre-push pipeline

## When to Use
- Before merging significant changes (>100 lines, >3 files)
- After implementing new features
- When `code-reviewer` skill finds issues and deeper analysis is needed
- User explicitly asks for "deep review", "thorough audit", "ultra review", "6-agent review"

## Depth Levels
| Level | Agents | Verification | Use Case |
|-------|--------|-------------|----------|
| low | 1 (quick scan) | None | Pre-push fast check |
| medium | 3 (correctness, security, performance) | None | Standard review |
| high | 6 (all agents) | CRITICAL only | Pre-merge audit |
| ultra | 6 (all agents) | ALL findings | Production PR review |

Default: **high**

## The 6 Reviewer Agents

### Agent 1: Correctness
- Off-by-one, null/None, unhandled exceptions
- Race conditions in async code
- Edge cases: empty, zero, negative, overflow
- State machine violations

### Agent 2: Security
- SQL injection, hardcoded secrets, command injection
- Path traversal, SSRF, auth bypass
- Financial safety: negative prices, fee miscalculation, balance bypass

### Agent 3: Performance
- Blocking calls in async context
- O(n²) algorithms, missing caching
- Memory leaks, unbounded collections
- N+1 query patterns

### Agent 4: Architecture
- Layer violations, circular dependencies
- God classes, tight coupling
- Leaky abstractions, interface pollution

### Agent 5: Domain (Trading-Specific)
- Balance validation before trades
- Drawdown freeze enforcement
- Kelly sizing, fee calculations
- Idempotency, circuit breaker logic

### Agent 6: Test Coverage
- Missing tests for new code
- Edge cases not covered
- Mock correctness, test isolation
- Flaky test patterns

## Workflow
1. **Scope Detection** — detect diff or files to review
2. **Parallel Review** — launch 6 agents (3+3 batches if rate limited)
3. **Verification** — verify CRITICAL + WARNING findings
4. **Synthesis** — consolidated report with statistics
5. **Verdict** — PASS / NEEDS WORK / BLOCK

## Constraints
- MUST read files before reviewing (no hallucinated findings)
- MUST cite exact file:line for each finding
- MUST distinguish CONFIRMED from NEEDS_MANUAL
- NEVER report style/naming/formatting issues
- NEVER block a push without verified CRITICAL findings

## Output Format
```
## Deep Code Review — {date} — Level: {depth}

### Confirmed Critical Issues
1. **{issue}** — `file:line` [CONFIRMED]
   - Trigger: {when}
   - Impact: {what breaks}
   - Fix: {code change}

### Confirmed Warnings
...

### Statistics
| Agent | Raw | Confirmed | False Positive |
|-------|-----|-----------|----------------|
| Correctness | N | N | N |
...

### Verdict: PASS / NEEDS WORK / BLOCK
```

## Related Skills
- `code-reviewer` — quick single-agent review (low depth)
- `security-audit` — focused security scan
- `git-gate` — quality gate before push
- `archy-check` — architecture health check
