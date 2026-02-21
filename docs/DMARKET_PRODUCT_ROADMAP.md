# DMARKET PRODUCT ROADMAP (THE MUSCLE)
> **Manifesto:** "План развития Торгового Изделия. Цель: Максимальная прибыль при соблюдении ToS. Скорость через архитектуру, а не спам."

## Phase 1: HFT Core (Rust Foundation)
*   `[PRODUCT_DMARKET]` **Zero-Allocation Memory:** Integrate `bumpalo` arenas to eliminate malloc overhead during Order Book updates.
*   `[PRODUCT_DMARKET]` **Token Bucket Limiter:** Implement `governor` (Rust) for nanosecond-precision rate limiting compliant with DMarket headers.
*   `[PRODUCT_DMARKET]` **SIMD JSON Parsing:** Switch to `simd-json` (Rust) for parsing massive order books using AVX2 instructions.
*   `[PRODUCT_DMARKET]` **SmallVec Optimization:** Replace standard Vectors with `smallvec` to keep hot data on the stack.

## Phase 2: Market Microstructure (The Eyes)
*   `[PRODUCT_DMARKET]` **Order Book Imbalance (OBI):** Real-time calculation of Bid/Ask pressure with `ndarray`.
*   `[PRODUCT_DMARKET]` **Trade Flow Imbalance (TFI):** Tracking aggressive buyer vs aggressive seller volume to predict short-term moves.
*   `[PRODUCT_DMARKET]` **Spoofing Detection:** Algorithmic filter to ignore "fake walls" that disappear when touched.
*   `[PRODUCT_DMARKET]` **Volatility Adjustment:** Dynamic spread adjustment based on `std_dev` of last 100 ticks.

## Phase 3: Statistical Arbitrage (The Brain)
*   `[PRODUCT_DMARKET]` **Pairs Trading Engine:** `src/strategies/pairs.rs`. Tracking correlations (e.g., AK-47 Redline FT vs MW).
*   `[PRODUCT_DMARKET]` **Cointegration Tests:** Automatic Engel-Granger test running in background thread to find new pairs.
*   `[PRODUCT_DMARKET]` **Mean Reversion Logic:** Trading Z-Score deviations > 2.0 with auto-stop at mean.
*   `[PRODUCT_DMARKET]` **Latency Arbitrage:** Comparing DMarket "Instant" prices vs Steam "Buy Order" depth to catch laggy updates.

## Phase 4: Execution & Safety (The Shield)
*   `[PRODUCT_DMARKET]` **Rust Network Layer:** `reqwest` + `tokio` with connection pooling and TCP_NODELAY.
*   `[PRODUCT_DMARKET]` **Circuit Breaker v2:** Rust-native state machine handling 429/500/502 errors without GC pauses.
*   `[PRODUCT_DMARKET]` **Position Sizing:** Kelly Criterion implementation to optimize bet size based on probability of profit.
*   `[PRODUCT_DMARKET]` **Kill Switch:** Hardware-interrupt listener to flatten all positions instantly.

## Phase 5: Infrastructure (The Factory)
*   `[PRODUCT_DMARKET]` **TUI Dashboard:** `ratatui` (Rust) interface for zero-latency monitoring via SSH.
*   `[PRODUCT_DMARKET]` **Backtesting Engine:** Replay engine using historical order book snapshots (Parquet format).
*   `[PRODUCT_DMARKET]` **Strategy Optimizer:** Genetic algorithm to tune Z-Score thresholds on historical data.
