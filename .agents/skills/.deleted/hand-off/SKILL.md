---
name: hand-off
description: Prepare a clean context snapshot for handoff to another agent or session. Summarizes current state, decisions, and next steps. Trigger keywords: "hand off", "context transfer", "передай контекст".
---

# /hand-off — Context Transfer

Prepare a clean context snapshot for handoff to another agent or session.

## Usage
```
/hand-off [session-id | agent-name]
```

## What it does
1. Summarizes current state:
   - What was done (last 5 actions)
   - What's in progress (blocked tasks)
   - What's next (pending tasks)
2. Lists relevant file changes (git diff --stat)
3. Writes snapshot to `memory/handoff-{timestamp}.md`
4. If session-id provided, attempts to resume that session with the snapshot

## Output Format
```markdown
## Handoff Snapshot — {timestamp}

### Completed
- [list]

### In Progress
- [list with blocker]

### Next Steps
- [list]

### Changed Files
- [file: change description]

### Key Decisions Made
- [decision → reasoning]
```

## Rules
- Always include git diff --stat for traceability
- Never handoff with uncommitted secrets
- If handoff-ing to a subagent, include the specific ticket ID
