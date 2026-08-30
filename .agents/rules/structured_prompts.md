---
name: Structured Prompt Execution
description: Enforces strict adherence to user-provided checklists and forces Planning Mode for structured prompts.
trigger: always_on
---

# Structured Prompt Execution Rule

When the user provides a structured prompt containing a checklist (e.g., `- [ ]`), phases, or explicit step-by-step instructions (like the "Разобрать незакоммиченный хвост" template), you MUST adhere to the following strict protocol:

1. **Mandatory Planning Mode & Tasks Artifact**: 
   - You MUST immediately enter Planning Mode.
   - You MUST create a `task.md` artifact (or update the existing one) copying the user's EXACT checklist verbatim.
   - Do NOT summarize, abbreviate, or merge the user's steps. Every single `- [ ]` item from the user's prompt must become a distinct `- [ ]` item in your `task.md`.

2. **Strict Sequential Execution**:
   - Execute the tasks strictly in the order they are written.
   - Do not attempt to run multiple phases or groups simultaneously unless explicitly permitted.

3. **RAW Output Adherence (No Summarization)**:
   - For every task that requests a command (e.g., `RAW: git status --porcelain`), you must execute the command and paste the **FULL, unedited RAW output** in your response to the user.
   - Never use phrases like "output hidden for brevity", "the output was clean", or "I checked and it's fine". Show the evidence.

4. **Stop Criteria Anti-Drift**:
   - You are not allowed to mark a task as `[x]` in `task.md` until the RAW evidence has been shown to the user and the specific criteria of that line item are fully met.
   - If a step requires delegating to a subagent (e.g., `code-auditor`, `raw-evidence-auditor`), you must wait for their explicit verdict before proceeding.
