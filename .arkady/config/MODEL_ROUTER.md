# MODEL ROUTER STRATEGY (ARKADY v1)

## 1. ROUTING LOGIC
- **Complexity > 8/10**: Route to `gemini-3-pro` (ARCHITECT).
- **Complexity < 8/10**: Route to `gemini-3-flash` (CODER/WATCHER).
- **Large Context Reading**: Always use `gemini-3-flash` with `cache_control`.

## 2. CACHE CONTROL POLICY
- **System Prompts**: 1 hour TTL (ephemeral).
- **Project Structure**: 30 min TTL.
- **Large Docs (>20k tokens)**: Manual cache trigger before processing.

## 3. ERROR 429 MITIGATION
- Max retry: 3.
- Backoff: Exponential (2s, 4s, 8s).
## 4. FUNCTION CALLING & JSON MODE
- **Config Generation**: Always use `response_mime_type: "application/json"`.
- **DMarket API interactions**: Mandatory use of Function Calling via `tool_definitions.py`.
- **Structured Data**: Any output intended for system consumption must be JSON-serialized.
