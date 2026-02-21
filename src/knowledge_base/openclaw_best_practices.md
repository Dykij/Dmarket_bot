# Platform Best Practices
*Harvested from the collective wisdom of pashov and mberman84.*

## Core Principles

### 1. Agent Sizing & Scope
- **Keep Agents Small:** Specialized agents outperform generalists. Spawn sub-agents for distinct, complex tasks rather than overloading one context.
- **Context Hygiene:** Clear `memory/` and session context regularly to prevent hallucination and token bloat.

### 2. File Operations
- **Read with Limits:** Always use `limit` and `offset` when reading unknown or potentially large files. Never `read` a whole repo at once.
- **Atomic Writes:** When possible, write to a temp file and rename, or ensure you have a backup before overwriting critical config files.

### 3. Execution Safety
- **Verify Output:** Never assume a command succeeded. Always check the output/exit code.
- **Timeout Management:** Use timeouts for network or long-running processes to prevent hanging agents.
- **Terminal Guard:** Use wrappers (like `utils/terminal.py`) to filter dangerous commands before execution.

### 4. Tool Usage
- **Precision:** Use `edit` for small changes in large files; use `write` for creating or overwriting small files.
- **Narration:** Only narrate complex logic. Routine tool calls should be silent to save tokens and reduce noise.

## specific "QA" & "Core" Protocols
- **QA (Security):** Whitelist/Blacklist checks are mandatory for shell execution.
- **Core (Coding):** Plan -> Code. No blind coding.
