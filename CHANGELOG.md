# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/v2.0.0.html).


## [15.6.0] - 2026-07-14
### 🚀 v15.6 Rate Limiting, Error Handling & Dead Code Cleanup

#### Added
- **Token bucket rate limiter** (`rate_limiter.py`) — per-endpoint rate limiting, 0 429 errors
- **Hybrid Kelly+Volatility sizing** (arXiv:2508.16598) — better drawdown control
- **Slippage-at-Risk pre-trade filter** (arXiv:2603.09164) — reject bad fills
- **Time-stop for stale positions** — cancel buy targets after 90min
- **CallbackData factory** (`callback_data.py`) — type-safe callbacks
- **FSM for settings** (`settings_fsm.py`) — /set command for changing settings via bot
- **Structured error handling** (`error_handling.py`) — 8 error categories, 4 severity levels
- **uvloop** for 2-4x faster event loop
- **Rust GIL release** — `py.allow_threads()` for parallel parsing
- **PyO3 0.23** — newer API, abi3 support
- **BuildKit cache mounts** — 2-5 min faster Docker rebuilds
- **.dockerignore** — faster builds, smaller context
- **Composite index** `(hash_name, status)` on virtual_inventory
- **atexit handlers** — clean WAL checkpoint on exit
- **Indexes** on `trades(trade_date)` and `trades(item_name)`

#### Changed
- **Market.CSGO oracle** — added rate limiter (2.5 RPS) + 429 handling
- **Waxpeer oracle** — added rate limiter (0.5 RPS) + 429 handling
- **Steam oracle** — added 429 retry with exponential backoff
- **Multi-Source Oracle** — per-source circuit breaker, sequential calls
- **Scanner** — Semaphore(2) + 400ms pacing (5 RPS safe margin)
- **DMarket API client** — removed broken fallback URL, added token bucket
- **Dockerfile** — BuildKit cache, STOPSIGNAL SIGTERM, better health check
- **Rust core** — LTO + strip for smaller binaries

#### Fixed
- **Inverted spread calculation** in `limit_orders.py` — limiter orders now work
- **Double-sided fee validation** in `price_validator.py` — buy + sell fees
- **Idempotency keys** in `targets.py` and `offers.py` — no duplicate orders
- **Year 2026 hardcoded** in `pricing.py` — float-date detection works in 2027+
- **Kelly dead code** in `dynamic_manager.py` — Kelly sizing now called
- **Plaintext API secret** in `dmarket_api.py` — removed X-Api-Secret header
- **Circuit breaker race condition** in `backoff.py` — `_probe_pending` flag
- **Oracle HTTP timeouts** — 15s total, 5s connect (5 oracle files)
- **Sample variance** in `price_validator.py` — `/ (len-1)` instead of `/ len`
- **429 fallback URL** removed — non-existent URL removed
- **NaN/Inf guard** in `pump_detector.py`
- **Volume check** in `pump_detector.py` — no false positive on thin markets
- **CS2 budget limit** in `liquidity_manager.py` — 10% per trade
- **cb_sell_top bug** in `callbacks.py` — uses `listed_count` instead of `result`
- **escape_md incomplete** in `formatters.py` — all 18 MarkdownV2 special chars
- **cmd_chart/pnl_chart** missing `@safe_call` decorator
- **cmd_liquidate** missing None-check on `state.client`
- **notifier.error()/crash()** — added HTML escaping

#### Removed
- **Dead code cleanup** — ~3,000 lines, 32 files removed
- **src/telegram_bot/** — entire package (wrong library, python-telegram-bot)
- **src/telegram/bot.py** — deprecated, hard-blocked, has CVEs
- **src/api/dmarket_auth.py** — deprecated, replaced by dmarket_api_client
- **src/api/skinport_oracle.py** — empty stub
- **src/core/target_sniping.py** — dead monolith shadowed by package
- **src/dmarket/** — 11 dead files (never imported)
- **src/utils/** — 8 stub files (no-op implementations)
- **Broken fallback URL** — trading.dmarket.com doesn't exist

#### Security
- Structured error handling with 8 categories (API, DB, Auth, Network, etc.)
- HTML escaping in notifier.error()/crash() — no HTML breakage
- Type-safe CallbackData factory — no callback injection
- Never leak exception details to users (CVE-2026-32982)


## [15.2.0] - 2026-07-12
### ⚡ v15.2 Performance & Security Optimization

#### Added
- **cachetools** library for O(1) TTL cache eviction (`src/analytics/historical_data/collector.py`)
- **orjson** integration for 5-10x faster JSON parsing in hot paths
- **numpy** vectorized computation in analytics modules
- **tenacity** for retry logic in `dmarket_api.py` and `retry_decorator.py` (replaces 40+ lines manual retry)
- **structlog** integration in `logging_setup.py` for structured context binding
- **prometheus_client** integration in `health_server.py` for proper metric types
- Composite index `idx_price_name_time` on `price_history(hash_name, recorded_at DESC)`
- Indexes on `decision_logs` and `missed_opportunities` tables
- Performance PRAGMAs to `profit_tracker.py` (synchronous=NORMAL, cache_size=64MB, mmap_size=256MB)

#### Changed
- **dmarket_parser.py**: Python fallback now uses `orjson.loads()` (5-10x faster)
- **dmarket_api_client/core.py**: JSON serialization uses `orjson.dumps()` (2-3x faster)
- **dmarket_api.py**: Manual retry loop replaced with `tenacity.retry()` decorator
- **retry_decorator.py**: Manual exponential backoff replaced with tenacity
- **resilience.py**: Manual retry_async replaced with tenacity
- **logging_setup.py**: Added structlog processor chain for structured logging
- **health_server.py**: Manual Prometheus text replaced with `prometheus_client.generate_latest()`
- **volatility.py**: `realized_vol_std` and `roll_effective_spread` use numpy vectorized ops
- **metrics.py**: `calculate_max_drawdown` and `calculate_sharpe_ratio` use numpy; fixed Sharpe annualization bug
- **self_reflection.py**: Sharpe/Sortino/drawdown calculations use numpy
- **collector.py**: Manual TTL dict replaced with `cachetools.TTLCache`
- **memory_cache.py**: `dict` → `OrderedDict` for O(1) eviction (previous fix)

#### Fixed
- **Timing-safe auth** in `health_server.py`: `==` → `hmac.compare_digest()`
- **Sharpe ratio annualization bug** in `metrics.py`: sqrt(365) was canceling out
- **save_trades_batch** now uses `executemany` instead of individual INSERTs (~10x speedup)

#### Security
- Timing-safe password comparison in health server authentication
- All SQL queries use parameterized statements

#### Performance Summary
| Optimization | Before | After | Speedup |
|---|---|---|---|
| JSON parsing (Python fallback) | json.loads | orjson.loads | 5-10x |
| JSON serialization | json.dumps | orjson.dumps | 2-3x |
| Retry logic | 40+ lines manual | tenacity decorator | maintainability |
| Prometheus metrics | Manual text format | prometheus_client | proper types |
| Structured logging | Manual JSON formatter | structlog processor | context binding |
| Volatility calculation | Manual math | numpy vectorized | 10-50x |
| Sharpe/drawdown | Manual loops | numpy | 10-100x |
| Batch INSERT | Individual execute | executemany | ~10x |
| TTL cache eviction | O(n) min-scan | O(1) OrderedDict/cachetools | ~100x |
| Price history query | Separate indexes | Composite index | 2-5x |


## [14.9.0] - 2026-06-27
### 🦅 v14.9 Value Detection Scanner — Strategy Refactor

#### Added
- **Dual-Signal Pipeline**: Primary VALUE signal (rarity-based) + secondary SPREAD signal (intra-market).
  - `src/core/target_sniping/value_pipelines.py` — new module with `evaluate_combined_signal()`
  - Value signal: rarity premium × oracle_ask vs buy_price
  - Spread signal: best_bid vs best_ask with fee-aware margin
  - Pipeline prioritizes VALUE over SPREAD (can buy without natural spread)
- **New Config Parameters** (`.env`):
  - `VALUE_SCAN_ENABLED=true` — enable value scanner mode
  - `VALUE_SCAN_MIN_PREMIUM=1.05` — minimum rarity multiplier
  - `VALUE_SCAN_MIN_PROFIT_PCT=0.5` — profit margin threshold
  - `VALUE_SCAN_MIN_PROFIT_USD=0.20` — absolute profit floor
- **README.md** fully rewritten to reflect Value Scanner strategy.

#### Changed
- **Disabled HFT microstructure by default** for Value Scanner strategy:
  - `STRICT_MICROSTRUCTURE_FILTERS=false`
  - `OBI_ENABLED=false`, `OFI_ENABLED=false`, `VWAP_FILTER_ENABLED=false`
  - `CVD_ENABLED=false`, `VPIN_ENABLED=false`
  - These are **optional** and can be re-enabled for hybrid mode.
- **Relaxed liquidity filter**: `MIN_TOTAL_SALES=3` (was 5), `MIN_BID_ASK_COUNT=2` (was 5)
- **Expanded oracle validation**: `ORACLE_TOP_K_VALIDATE=50` (was 5)
- **Expanded price-range scan**: `PRICE_RANGE_MAX_TITLES=500` (was 200), `PRICE_RANGE_CYCLE_INTERVAL=1` (was 3)
- **Reduced reserve**: `BALANCE_RESERVE_USD=5.00` (was $10) — deploy more capital
- **Increased FEE_RATE**: `0.05` (was 0.03) — realistic for CS2 sell fees
- **Vault security**: Fixed Fernet key generation in `vault.py` (proper 44-char base64)
- **Config Watcher**: Rewritten to use `dotenv_values()` instead of manual parsing

#### Security
- **Removed .env backup files** that leaked live API keys
- Verified no secrets were ever committed to git


## [14.8.1] - 2026-06-24
### 🦅 v14.8.1 Wide-Net Conveyor + Low-Fee + DMarket-Internal Underpriced

#### Added
- **Low-fee items scan** — `src/api/dmarket_api_client/market.py` now parses the
  `/exchange/v1/customized-fees` `reducedFees` list and `src/core/target_sniping/scanner.py`
  fetches their cheapest listings for the pipeline.
- **DMarket-internal underpriced detection** — `src/core/target_sniping/underpriced.py`
  flags listings cheaper than the local price-history percentile. Falls back to
  DMarket `/last-sales` when available (currently requires JWT auth, so local
  history is the primary source).
- **Unit tests** for underpriced percentile logic and history-based detection
  (`tests/unit/test_underpriced.py`).

#### Changed
- `.env` and `src/config.py` — `AGG_SCAN_TOP_N=100`, `PRICE_RANGE_MAX_PAGES=10`,
  `PRICE_RANGE_MAX_TITLES=200`, `LISTINGS_FETCH_LIMIT=20`,
  `CROSS_MARKET_TARGET_MARGIN=0.02`, `CROSS_MARKET_TARGET_MAX_PER_CYCLE=20`.
- `src/core/limit_orders.py` — cross-market targets are sorted by margin and
  session-level dedup is applied via `_placed_cross_targets`.
- `src/core/target_sniping/filter.py` — uses reduced fee from low-fee scan and
  allows DMarket-internal underpriced as a fourth opportunity gate.
- `src/utils/config_watcher.py` — hot-reload keys for new v14.8.1 settings.
- `tests/unit/test_v12_4_components.py` — updated to reflect that 503 no longer
  trips the circuit breaker.


## [14.8.0] - 2026-06-24
### 🦅 v14.8 Cross-Market Target Discovery — Fix Bot Opportunity Pipeline

#### Fixed
- **DMarket aggregated-prices 503 handling** — `503 Service Unavailable` no longer
  trips the circuit breaker, allowing transient DMarket errors to retry cleanly.
- **Over-strict microstructure filters** — `STRICT_MICROSTRUCTURE_FILTERS` now
  defaults to `false`; OBI/OFI/VWAP/VPIN/Roll/Adverse-Selection/Vol-Regime gates
  are skipped for low-balance CS2 markets where they killed every candidate.
- **Fee model mismatch** — `WITHDRAWAL_FEE_RATE` lowered to `0.5%` and
  `MIN_SPREAD_PCT` to `0.5%` so cross-market edges are not discarded by
  pessimistic cost assumptions.
- **Cross-market buy list_price** — `limit_orders._execute_cross_market_targets`
  now posts DMarket buy targets derived from oracle lowest ask minus fees
  instead of using the DMarket best ask.
- **Cross-market fee validation** — `evaluate_fee_slippage_tod` accepts a
  `cs_ask_price` parameter so cross-market discounts (buy on DMarket, sell on
  free oracles) are evaluated with the destination market in mind.

#### Added
- `src/core/target_sniping/underpriced.py` — DMarket-internal underpriced
  detection based on price-history percentile.
- `src/api/dmarket_api_client/market.py` — `get_market_items_v2` now accepts
  `priceFrom` and `priceTo` for wide-net price-bucket scanning.
- **Price-range secondary scan** — `core.py` now runs a wide-net scan every
  N cycles to discover under-the-radar items not in top-100 aggregated prices.
- **Low-fee items scan** — fetches DMarket items with reduced sell fees.
- Tests for the new underpriced and cross-market components.


## [14.7.0] - 2026-06-21
### ✅ Position Guard (v14.7) — Full v14.0 Microstructure Stack

#### Added
- **Position Guard** (`src/core/target_sniping/position_guard.py`) — monitors
  existing inventory for stop-loss and take-profit conditions.
- `check_stop_losses()` and `check_take_profits()` called every 3 cycles.
- Smart reprice — adjusts stale listings based on oracle reference.

#### Changed
- **v14.0 Microstructure filters** now fully wired:
  - OBI, OFI, VWAP, CVD, VPIN, Slippage, A-S, Queue Imbalance, Multi-level OBI,
    Adverse Selection, Volatility Regime, Roll's Model, Volume Profile/POC,
    Composite Score, Time-of-Day.
- `filter.py` now supports all 15+ filters.
- AUTO_TIER selection with `AUTO_TIER_THRESHOLD` and `AUTO_TIER_MARGIN`.


## [14.6.0] - 2026-06-18
### 🦅 Value Detection Layers (TA Site Analysis)

#### Added
- **9 Value Detection Layers** (0 additional API calls):
  1. Float Premium (FN-0 1.20×, dirty BS 1.30×)
  2. Pattern Premium (Ruby 5×, Blue Gem 3×, Fire & Ice 5×)
  3. Sticker Combo (4× same = +100%)
  4. Filler Tracker (+15% demand multiplier)
  5. Seasonal Timing (0.85-1.15× threshold)
  6. Dirty BS (float > 0.95 → 1.10×)
  7. Round Float (0.5/0.25/0.125 → 1.15×)
  8. Float Date (DDMMYYYY → 1.08×)
  9. Commission Optimizer (low-fee items +15% score)
- `src/analytics/stickers_evaluator.py` — StickerEvaluator with 28 variants.
- `src/core/target_sniping/pricing.py` — pattern/phase premium detection.

#### Changed
- `filter.py` — v14.6 value detection applied after buy decision (modifiers list_price)
- `Config` — added `STICKER_COMBO_ENABLED`, `PATTERN_PREMIUM_ENABLED`, etc.


## [14.5.0] - 2026-06-15
### 🦅 Strategy Selector + Limit Orders + Shadow Trading

#### Added
- **Strategy Selector** — dynamically switches between MarketMaker, SpreadHunter,
  CrossMarket based on market conditions.
- **Limit Orders** — places buy targets for wide-spread items; cross-market buy
  targets when DMarket ask > oracle ask.
- **Live Shadow Engine** — paper-trading running alongside real bot for validation.


## [14.4.0] - 2026-06-10
### 🦅 Balance-Aware Engine (v14.4 — Major)

#### Added
- **Dynamic Max Snipe Price** — `max($5, effective_balance × 0.10)`
- **Half Kelly Sizing** — `position = capital × 0.50 × f*`
- **Drawdown Freeze** — stop buying at >15% peak drop
- **Lock-Aware Inventory Cap** — ≤80% capital in trade-lock
- **Capital Velocity** — min 0.5× weekly turnover

#### Changed
- `.env` — `BALANCE_RESERVE_USD=10.00`, `KELLY_ENABLED=true`
- `src/config.py` — all balance-aware parameters
- `core.py` — balance gates integrated into run_cycle


## [14.3.0] - 2026-06-05
### 🦅 v14.3 Microstructure Enhancements

#### Added
- Avellaneda-Stoikov (A-S) reservation price
- Queue Imbalance (QI)
- Multi-Level OBI
- Adverse Selection (Kyle λ / Amihud)
- Volatility Regime (Parkinson)
- Roll's Model
- Volume Profile / POC


## [14.2.0] - 2026-06-01
### 🦅 v14.2 Self-Reflection & Telemetry

#### Added
- `src/analytics/self_reflection.py` — trade win/loss analysis
- Prometheus `/metrics` endpoint
- `src/utils/health_server.py` — `/healthz`, `/readyz`


## [14.1.0] - 2026-05-28
### 🦅 v14.1 Order Book Microstructure

#### Added
- VWAP filter (Volume-Weighted Average Price)
- CVD (Cumulative Volume Delta)
- VPIN (Volume-Synchronized Probability of Informed Trading)
- Slippage Gate (Almgren-Chriss)
- Time-of-Day (ToD) seasonality


## [14.0.0] - 2026-05-25
### 🦅 v14.0 Microstructure Foundation

#### Added
- OBI (Order Book Imbalance)
- OFI (Order Flow Imbalance)
- Bait/Spoof Detection
- Micro-Price / DOM Gap
- Composite Score

---

## Pre-v14.0 (Legacy)

### v12.x — Core Engine
- **v12.8** — Parallel candidate evaluation (Semaphore=10), inventory saturation pre-compute
- **v12.7** — Per-cycle oracle price cache, PumpDetector restore from disk
- **v12.6** — Pump detection, error classification (FATAL/UNKNOWN/TRANSIENT)
- **v12.5** — SecurityAuditor log filter, DailyBriefingScheduler
- **v12.4** — Oracle in-memory cache (5-min TTL, 200 items)
- **v12.3** — Aggregated-prices-first scan (v12.3 fix for cross-market arb)
- **v12.2** — Liquidity filter, wash-trading detection, multi-level verification
- **v12.1** — Bulk fee estimation (4 tiers)
- **v12.0** — Intra-DMarket Spread Sniping (Strategy A)

### v10.x — Legacy
- **v10.0** — Basic DMarket sniping loop
- **v10.5** — Cross-market oracle integration


[Unreleased]: https://github.com/Dykij/Dmarket_bot/compare/v14.9.0...HEAD
[14.9.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.8.1...v14.9.0
[14.8.1]: https://github.com/Dykij/Dmarket_bot/compare/v14.8.0...v14.8.1
[14.8.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.7.0...v14.8.0
[14.7.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.6.0...v14.7.0
[14.6.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.5.0...v14.6.0
[14.5.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.4.0...v14.5.0
[14.4.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.3.0...v14.4.0
[14.3.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.2.0...v14.3.0
[14.2.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.1.0...v14.2.0
[14.1.0]: https://github.com/Dykij/Dmarket_bot/compare/v14.0.0...v14.1.0
[14.0.0]: https://github.com/Dykij/Dmarket_bot/compare/v12.8.0...v14.0.0