---
name: to-tickets
description: Decompose a large implementation plan into small, sequential tickets that subagents can execute independently. Trigger keywords: "to tickets", "decompose plan", "разбей на задачи", "создай тикеты".
---

# /to-tickets — Decompose Plan into Agent-Ready Tasks

Break a large implementation plan into small, sequential tickets that subagents can execute independently.

## Usage
```
/to-tickets <plan or feature description>
```

## What it does
1. Takes a plan (from /grill-me or ad-hoc)
2. Decomposes into tickets of ≤50 lines each
3. Each ticket gets:
   - **ID**: `T-001`, `T-002`, ...
   - **Title**: Verb-first (e.g. "Add rate limiter to API client")
   - **Acceptance Criteria**: Concrete, testable
   - **Files**: Which files to touch
   - **Dependencies**: Blocked by T-xxx or none
   - **Tag**: `ready for agent`
4. Outputs tickets as a checklist

## Rules
- Each ticket must be independently testable
- No ticket should touch more than 3 files
- If a step is >50 lines, split it
- Dependencies must be acyclic (no circular blocks)
- Agent can pick up any `ready for agent` ticket without human input
