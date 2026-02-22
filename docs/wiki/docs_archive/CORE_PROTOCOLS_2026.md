# CORE PROTOCOLS 2026 (SACS-2026 Compliant)
## 1. Architecture & Hierarchy
- **System Orchestrator (Arkady):**
  - **Model:** `google-vertex/gemini-3-pro-preview`
  - **Role:** High-level logic, architecture design, complex refactoring, final decision making.
  - **Constraint:** Minimize direct file I/O on large datasets to conserve high-value tokens.

- **Sub-Agents (The Swarm):**
  - **Model:** `google-vertex/gemini-3-flash-preview`
  - **Role:** Execution, file scanning, log analysis, syntax validation, "grunt work".
  - **Directive:** MUST be used for any task involving >3 file reads or recursive directory scans.

## 2. Operational Protocols
### Protocol: `sessions_spawn`
1. **Trigger:** Any request involving "audit", "scan", "check logs", or "validate syntax".
2. **Configuration:**
   - `model`: ALWAYS `google-vertex/gemini-3-flash-preview`.
   - `task`: Clear, step-by-step imperative instructions.
3. **Output:** Sub-agents must return a structured summary. No "chitchat".

### Protocol: `Hotfix Deployment`
1. **Validation:** No code is written to `main` without a Flash-sub-agent dry-run or syntax check if complexity > 50 lines.
2. **Backup:** Critical configs (`openclaw.json`) are backed up before write.

## 3. Project: MyClawDev_bot
- **GCP Project:** `arkady-bot-dev`
- **Region:** `global`
- **Stack:** Python (Native), Vertex AI SDK.
- **Constraints:**
  - No legacy Anthropic/Claude libraries.
  - No `langchain` unless explicitly requested (prefer native SDK).

## 4. Error Handling
- **API Failures:** If Vertex AI returns 429/500, wait 5s and retry.
- **Hallucinations:** If a model references "Claude", "GPT-4", or "OpenAI", immediately self-correct via `MEMORY.md` lookup.
