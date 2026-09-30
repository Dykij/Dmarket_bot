---
name: verify-loop
description: Loop for getting audit verification before committing.
trigger: run verify loop
---

# Verify Loop Workflow

1. Update `task.md` with your progress to ensure no uncompleted tasks block the gate.
2. Collect raw files (diffs, test outputs) that represent the change.
3. Invoke the `code-auditor` or `raw-evidence-auditor` subagent with a neutral question (e.g. "Review these files for safety"). DO NOT pass your own conclusions or "PASS" strings to the subagent.
4. Wait for the subagent's verdict.
5. If the subagent returns `RISK`, read their findings and fix the code. Repeat up to 3 times.
6. If the subagent returns `FINAL_VERDICT: PASS`, you may proceed with the commit/push.
