---
name: audit-handoff
description: Use when delegating code safety and correctness verification to subagents. Ensures correct verdict format.
trigger keywords: audit handoff, pass to auditor, request verification
---

When delegating to an auditor subagent, always provide the explicit `AUDIT_TARGET: <hash>` they need to verify.
The auditor must reply with `FINAL_VERDICT: PASS` or `FINAL_VERDICT: FAIL` on separate lines, along with `RISK: <details>` if failed.
See references for the full payload format.
