---
name: grill-me
description: Requirements alignment before starting non-trivial tasks. Asks clarifying questions to ensure agent and human are aligned on scope, constraints, and acceptance criteria. Trigger keywords: "grill me", "align requirements", "уточни требования".
---

# /grill-me — Requirements Alignment

Before starting any non-trivial task, use this command to align requirements between human and agent.

## Usage
```
/grill-me <task description>
```

## What it does
1. Reads the task description
2. Asks up to 3 clarifying questions about scope, constraints, and expected output
3. Produces a shared "Task Brief" with:
   - **Goal**: One sentence
   - **Acceptance Criteria**: Bullet list
   - **Out of Scope**: What NOT to do
   - **Risks**: Potential blockers
4. Human confirms or adjusts the brief
5. Only then work begins

## Rules
- Max 3 questions per grill session
- If uncertain after 3 questions, proceed with best assumption and note it
- Never start work without a confirmed brief (except trivial fixes)
- Store brief in `memory/YYYY-MM-DD.md` for traceability
