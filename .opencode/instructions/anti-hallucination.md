# Anti-Hallucination & Tool-First Rules

## Mandatory Tool-First Workflow
- **ALWAYS** read files before editing (read → analyze → edit)
- **NEVER** answer "what should I change?" — read the file first, then propose concrete diff
- **MAX 3 clarifying questions** per task, then act
- If user asks "update README" → `read README.md` → `edit` with diff → run checks → commit
- Text-only responses without tool calls = FAILURE

## Anti-Analysis-Paralysis
- Do not ask "what exactly to change?" — read the file, propose concrete edits
- Do not write status reports instead of using tools
- One tool call per thought minimum

## Decision Making
- If uncertain → read more files, don't ask user
- Max 1 clarifying question per turn
- Prefer action over clarification

## Output Discipline
- Concise responses (< 4 lines unless detail requested)
- No preamble/postamble ("Here is what I'll do...")
- Tool output speaks for itself