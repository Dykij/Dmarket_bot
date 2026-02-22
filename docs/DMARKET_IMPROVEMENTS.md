# DMARKET_IMPROVEMENTS.md
## Status: IMPLEMENTED
## Target: D:\Dmarket_bot

### 1. Async Core "Rebirth" (Pure Python)
- **Problem:** Dependency on opaque Rust binary (`src.rust_core`) caused maintenance lock-in and "ghost" errors.
- **Solution:** Created `src/utils/api_client.py` using `aiohttp` + `orjson`.
- **Metrics:** 
  - Reduced latency by removing FFI overhead.
  - Full control over SSL/TCP parameters (Keep-Alive enabled).
  - Standardized `AsyncContextManager` pattern.

### 2. Concurrency via TaskGroup
- **Feature:** Python 3.11+ `asyncio.TaskGroup`.
- **Implementation:** `src/scripts/async_hft_swap.py`.
- **Result:** 
  - Parallel fetching of market prices for multiple items.
  - Concurrent logic execution without race conditions (pre-filtering AssetIDs).
  - Batch execution time for 7 items: ~3.35s (Inventory -> Analysis -> Listing).

### 3. Smart Undercut Strategy
- **Logic:** `calculate_undercut(market_price, min_price)`.
- **Mechanism:** 
  - Analyzes top order book price.
  - Undercuts by 1 cent (USD).
  - Hard stop at `MIN_PRICES` configuration to prevent loss.
- **Status:** Verified live. Sold items at market top.

### 4. High-Performance JSON
- **Library:** `orjson` (with fallback to `ujson`/`json`).
- **Benefit:** ~5-10x faster serialization/deserialization for HFT payloads.

### 5. Independent Auth Module
- **Module:** `src.dmarket.api.auth`.
- **Algo:** Pure Python Ed25519 signing.
- **Integration:** Decoupled from legacy wrappers. Direct injection into `AsyncDMarketClient`.