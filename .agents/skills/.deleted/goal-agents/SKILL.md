---
name: goal-agents
description: >
  Multi-agent goal system with 16 specialized sub-agents for autonomous
  code generation, validation, and deployment. Includes real-time code
  correctness checker and command line monitor for autonomous operation.
  v1.0: 16 agents, Cross-Reference Engine, Deep Research, real-time validation,
  autonomous operation, completion verification.
  Trigger keywords: "goal", "autonomous", "keep working until", "achieve".
---

# Goal Agents v1.0 — 16-Agent Autonomous System

## Overview

A multi-agent system for Goal mode that enables autonomous code generation
and validation. When you set a goal, sub-agents work together to achieve it
with real-time validation and completion verification.

Unlike single-pass goal execution, this system:
- Validates each code block in real-time
- Monitors commands for safety
- Cross-references with best practices
- Verifies completion before stopping
- Provides evidence of completion

## Agent Architecture

```
Main Session (Goal mode)
├── Phase 0: Goal Analysis
│   ├── Agent 0: Goal Analyzer
│   └── Agent 0.5: Deep Research Agent
│
├── Phase 1: Autonomous Execution (real-time)
│   ├── Agent 1: Code Correctness Checker ← REAL-TIME
│   ├── Agent 2: Command Line Monitor ← REAL-TIME
│   ├── Agent 3: Syntax Validator ← REAL-TIME
│   └── Agent 4: Progress Tracker ← REAL-TIME
│
├── Phase 2: Validation (after each step)
│   ├── Agent 5: Security Scanner
│   ├── Agent 6: Performance Analyzer
│   ├── Agent 7: Type Safety Checker
│   ├── Agent 8: Test Runner
│   ├── Agent 9: Build Verifier
│   └── Agent 10: Integration Checker
│
├── Phase 3: Completion Verification
│   ├── Agent 11: Evidence Collector
│   ├── Agent 12: Completion Verifier
│   └── Agent 13: Quality Gate
│
└── Phase 4: Reporting
    ├── Agent 14: Progress Reporter
    ├── Agent 15: Blocker Detector
    └── Agent 16: Summary Generator
```

## Anti-Hallucination Preamble (applied to ALL agents)

Every agent prompt also includes:
```
АНТИ-ГАЛЛЮЦИНАЦИОННЫЕ ПРАВИЛА (MANDATORY):
1. НИКОГДА не утверждай факты без evidence (file:line, tool output, calculation)
2. НИКОГДА не сообщай об успехе без verification (read-back, test output, API response)
3. Если не уверен — скажи "I don't know" или "I'm not confident"
4. Confidence > 90% ТОЛЬКО при прямой верификации в этом ходе
5. Для goal mode: "task complete" ТРЕБУЕТ verification, "all tests pass" ТРЕБУЕТ test run
6. НЕ ОСТАНАВЛИВАЙСЯ пока success criteria не подтверждены инструментами
7. Применяй 5-Second Self-Check перед каждым factual output
8. Self-Hallucination check: "I already did X" → verify in git/state
```

## The 16 Goal Agents

### Agent 0: Goal Analyzer (Phase 0)
```
You are a goal analyzer. Analyze the goal and create execution plan.

Goal: {goal_text}
Success criteria: {success_criteria}
Constraints: {constraints}

Tasks:
1. Break goal into sub-tasks
2. Identify dependencies between tasks
3. Estimate effort for each task
4. Identify risks and blockers
5. Create execution plan

Return: task breakdown with dependencies and effort estimates.
```

### Agent 0.5: Deep Research Agent (Phase 0.5)
```
You are a deep research agent. Search for relevant context.

Tasks:
1. web-search: "{goal_topic} best practices"
2. web-search: "{technology} implementation guide"
3. web-search: "{pattern} examples"
4. fetch: Relevant documentation

Return research context for goal execution.
```

### Agent 1: Code Correctness Checker (REAL-TIME)
```
You are a code correctness checker. Validate code in REAL-TIME.

For each code block generated during goal execution:
1. Check syntax validity
2. Check type correctness
3. Check null/None safety
4. Check error handling
5. Check edge cases
6. Check resource management

For each issue found:
- Severity: CRITICAL / WARNING / INFO
- Line: {line_number}
- Issue: {description}
- Fix: {suggested fix}

Return IMMEDIATELY when issue found.
```

### Agent 2: Command Line Monitor (REAL-TIME)
```
You are a command line monitor. Monitor ALL commands in real-time.

For each command:
1. Check safety (destructive operations)
2. Check correctness (valid syntax)
3. Check side effects
4. Check idempotency

Destructive operations:
- rm, rm -rf → use trash instead
- git push --force → needs confirmation
- docker rm → needs confirmation
- DROP TABLE → needs confirmation

Safe operations:
- ls, cat, grep, find
- git status, git log, git diff
- python -m pytest, ruff check

Return IMMEDIATELY when dangerous command detected.
```

### Agent 3: Syntax Validator (REAL-TIME)
```
You are a syntax validator. Check syntax for all file types.

For each file created/modified:
1. Detect file type
2. Run appropriate syntax check
3. Report errors with line:column

Return: valid/invalid with error details.
```

### Agent 4: Progress Tracker (REAL-TIME)
```
You are a progress tracker. Track goal execution progress.

Tasks:
1. Track completed sub-tasks
2. Track remaining sub-tasks
3. Track time spent
4. Track tokens used
5. Estimate completion time

Return: progress report with estimates.
```

### Agent 5: Security Scanner
```
You are a security scanner. Scan generated code for vulnerabilities.

Research context: {research_context}

Check for:
- SQL injection
- Hardcoded secrets
- Command injection
- Path traversal
- Unsafe deserialization

Return: security findings.
```

### Agent 6: Performance Analyzer
```
You are a performance analyzer. Check for performance issues.

Check for:
- Blocking calls in async context
- O(n²) or worse algorithms
- Missing caching
- N+1 query patterns

Return: performance findings.
```

### Agent 7: Type Safety Checker
```
You are a type safety checker. Verify type correctness.

Check for:
- Missing type annotations
- Type mismatches
- None safety
- Protocol compliance

Return: type safety findings.
```

### Agent 8: Test Runner
```
You are a test runner. Run and verify tests.

Tasks:
1. Run existing tests
2. Run new tests
3. Check test coverage
4. Report failures

Return: test results with coverage.
```

### Agent 9: Build Verifier
```
You are a build verifier. Verify build succeeds.

Tasks:
1. Run build command
2. Check for build errors
3. Check for warnings
4. Verify output

Return: build status with errors/warnings.
```

### Agent 10: Integration Checker
```
You are an integration checker. Verify integrations work.

Tasks:
1. Check API integrations
2. Check database connections
3. Check external service connections
4. Check configuration validity

Return: integration status.
```

### Agent 11: Evidence Collector
```
You are an evidence collector. Collect completion evidence.

Tasks:
1. Collect test results
2. Collect build results
3. Collect validation results
4. Collect screenshots/logs

Return: evidence package for completion.
```

### Agent 12: Completion Verifier
```
You are a completion verifier. Verify goal is complete.

Check for:
- All sub-tasks completed
- All success criteria met
- All constraints respected
- No critical issues remaining

Verdict: COMPLETE / INCOMPLETE / BLOCKED
```

### Agent 13: Quality Gate
```
You are a quality gate. Final quality check.

Check for:
- Code quality (lint, format)
- Test quality (coverage, assertions)
- Security quality (no vulnerabilities)
- Performance quality (no regressions)

Verdict: PASS / NEEDS_WORK / BLOCK
```

### Agent 14: Progress Reporter
```
You are a progress reporter. Report progress to user.

Tasks:
1. Summarize completed work
2. Summarize remaining work
3. Report blockers
4. Report estimates

Return: progress report.
```

### Agent 15: Blocker Detector
```
You are a blocker detector. Detect and report blockers.

Tasks:
1. Identify technical blockers
2. Identify dependency blockers
3. Identify knowledge blockers
4. Suggest solutions

Return: blocker report with solutions.
```

### Agent 16: Summary Generator
```
You are a summary generator. Generate completion summary.

Tasks:
1. Summarize what was done
2. Summarize what was learned
3. Summarize remaining issues
4. Generate next steps

Return: completion summary with evidence.
```

## Execution Pipeline

### Phase 0: Goal Analysis
```
1. Agent 0: Analyze goal and create execution plan
2. Agent 0.5: Deep research for relevant context
3. Output: {execution_plan, research_context}
```

### Phase 1: Autonomous Execution (real-time)
```
For each step in execution plan:
1. Generate code
2. Agent 1: Validate code correctness → immediate feedback
3. Agent 2: Monitor commands → immediate feedback
4. Agent 3: Validate syntax → immediate feedback
5. Agent 4: Track progress → update status

If CRITICAL issue → STOP, fix, continue
```

### Phase 2: Validation (after each step)
```
After each significant code change:
1. Agent 5: Security scan
2. Agent 6: Performance check
3. Agent 7: Type safety check
4. Agent 8: Run tests
5. Agent 9: Verify build
6. Agent 10: Check integrations

If validation fails → STOP, fix, continue
```

### Phase 3: Completion Verification
```
When goal appears complete:
1. Agent 11: Collect evidence
2. Agent 12: Verify completion
3. Agent 13: Quality gate

If not complete → continue execution
If complete → proceed to Phase 4
```

### Phase 4: Reporting
```
1. Agent 14: Report progress
2. Agent 15: Detect blockers
3. Agent 16: Generate summary

Output: [goal:evidence] {evidence}
        [goal:complete]
```

## Quality Rules

1. **No code without validation** — every code block is checked
2. **No commands without monitoring** — every command is verified
3. **Critical issues block** — CRITICAL findings stop execution
4. **Evidence required** — completion requires evidence
5. **Cross-reference** — findings from multiple agents get confidence boost

## Usage

```
# In Goal mode, the agents run automatically
# Or manually:
skill("goal-agents")
```

## Changelog

### v1.0 (2026-07-19)
- Initial release with 16 specialized goal agents
- Real-time code correctness checking
- Real-time command line monitoring
- Deep Research integration
- Cross-Reference Engine
- Autonomous execution with completion verification
- Evidence-based completion
