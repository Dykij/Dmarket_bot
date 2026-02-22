# REQUEST_PIPELINE.md
## Protocol: HFT V2 (Pure Python)
## Target: D:\Dmarket_bot

### 1. Authentication (Security Layer)
- **Agent:** Harper (QA/Security)
- **Action:**
  - Retrieve ENV keys (DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY).
  - Generate Nonce (Unix Timestamp).
  - Build String-to-Sign: `METHOD + PATH + BODY + TIMESTAMP`.
  - Sign via Ed25519 (nacl.signing).
  - Inject Headers: `X-Api-Key`, `X-Sign-Date`, `X-Request-Sign`.

### 2. Throttling (Rate Limit Layer)
- **Agent:** Boss (Strategy)
- **Action:**
  - Token Bucket Algorithm (Internal).
  - Rate: 5 RPS (Configurable).
  - Backoff: Exponential on 429 (Retry-After or 2s fixed).
  - Circuit Breaker: Trip on consecutive 5xx errors.

### 3. Execution (Network Layer)
- **Agent:** Roy (Architect)
- **Action:**
  - Transport: `aiohttp.ClientSession`.
  - Connection: Keep-Alive (TTL 60s), DNS Cache (300s).
  - Timeouts: Connect (2s), Read (5s).
  - Serialization: `orjson` (Fast JSON).

### 4. Validation (Business Logic Layer)
- **Agent:** Archivist (Data Integrity)
- **Action:**
  - Parse Response Code (200 OK vs 400 Bad Request).
  - Validate JSON Schema (e.g., ensure `currency` field exists).
  - Check for specific business errors (e.g., "OverpricedItem").
  - Log result to `async_hft_swap.log`.

### 5. Final Report (Orchestrator Layer)
- **Agent:** Arkady (Sovereign)
- **Action:**
  - Aggregate success/fail counts.
  - Calculate total execution time.
  - Report to User (Telegram/Console).