# ORCHESTRATION_PROTOCOL.md
## Protocol: "The 4 Heads"
## Target: D:\Dmarket_bot

### 1. The Strategy (Boss)
- **Role:** Business Logic, Profit Optimization.
- **Responsibility:**
  - Define `MIN_PRICES` and `TARGET_ITEMS` (`src/scripts/async_hft_swap.py`).
  - Calculate optimal undercut logic (`calculate_undercut`).
  - Analyze market depth (order book) before listing.
  - Approve or reject trades based on ROI.

### 2. The Architecture (Roy)
- **Role:** Code Structure, Performance, Stability.
- **Responsibility:**
  - Maintain `AsyncDMarketClient` (`src/utils/api_client.py`).
  - Ensure `aiohttp` and `asyncio` best practices (TaskGroup, Keep-Alive).
  - Optimize Python performance (`orjson`, direct memory access if needed).
  - Implement retry logic and error handling.

### 3. The Security & QA (Harper)
- **Role:** Authentication, Signing, Testing.
- **Responsibility:**
  - Verify Ed25519 signatures (`src/dmarket/api/auth.py`).
  - Secure API keys (environment variables only).
  - Prevent race conditions (concurrent requests for same asset).
  - Validate API responses and handle edge cases (400, 401, 404).

### 4. The Knowledge (Archivist)
- **Role:** Documentation, Logging, History.
- **Responsibility:**
  - Maintain `DMARKET_IMPROVEMENTS.md`, `REQUEST_PIPELINE.md`.
  - Log execution details (time, success rate).
  - Store successful strategies for future replay.
  - Ensure all code changes are documented in `docs_archive`.

### 6. Protocol "Trust But Verify" (New)
**Rule: Mandatory Cross-Verification**

1.  **Requirement:** No Agent (Roy, Boss, Harper) allows a proposal to reach the Sovereign without external validation.
2.  **Mechanism:**
    *   **Hypothesis:** Boss proposes a strategy (e.g., "Use Bid-Ask Spread").
    *   **Verification:** Archivist MUST find external proof (Docs, Papers, Reputable Sources) via Search Tools.
    *   **Consensus:** The Hive (40 sub-agents) votes. If proof is weak, the proposal is rejected.
3.  **Output:** Every major decision presented to the User must include a "Verified By" section citing the source.

### Interaction Protocol
1.  **Boss** defines the goal (sell items X, Y, Z).
2.  **Roy** builds the pipeline (Async Client -> TaskGroup).
3.  **Harper** validates the request (Auth -> Sign -> Send).
4.  **Archivist** records the result (Log -> Document).
5.  **Arkady (Sovereign)** orchestrates the entire flow and reports to the User.