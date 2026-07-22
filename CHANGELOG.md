# Changelog

All notable changes to this project will be documented in this file.

## [16.2] - 2026-07-22

### Fixed — Security & Financial Safety Audit (3 rounds, 13 files)

**Financial Safety Fixes (P1):**
- `steam_oracle.py`: `resp.json()` moved inside `async with` context manager (was reading from closed connection)
- `fair_price_calculator.py`: Outlier removal now handles both min AND max outliers independently (was only removing one)
- `fair_price_calculator.py`: `outlier_removed` now tracks both removed sources via comma-separated string
- `filter.py`, `filter_evaluator.py`, `almgren_chriss.py`, `twap.py`, `dmarket/targets.py`: `int(round(price * 100))` instead of `int(price * 100)` (prevents systematic truncation loss up to 0.99¢ per trade)
- `filter.py`: Added guard blocking oracle-dependent strategies when ALL oracles are unavailable (NOV-2)
- `execution.py`: Added oracle price re-check before buy execution — cancels trade if oracle drift >10% or fair price dropped below profitability threshold (NOV-3)

**Idempotency Fix (P2):**
- `targets.py`, `offers.py`: Deterministic idempotency key `{item_id}_{sha256(item_id+price_cents)}` instead of timestamp-based key (prevents duplicate orders on retry)

**Code Quality (P2):**
- `position_guard.py`: Added `import time` — replaced `__import__("time").time()` with `time.time()`

**Infrastructure:**
- Updated semgrep MCP config from deprecated `uvx semgrep-mcp` to `semgrep mcp`
- Removed youtube-transcript MCP server (unused)
- Added AGENTS.md sections: trading architecture, MCP server status, MimoCode limitations, audit status

### Architecture — Dead Code Cleanup (v16.2)

**Archived to `trash/dead_code_2026_07_22/`:**
- `src/dmarket/dmarket_api.py` — Legacy DMarketAPI client (httpx-based). Replaced by `src/api/dmarket_api_client/` (aiohttp-based). Zero imports in production code; only used by 3 now-archived integration tests.
- `src/dmarket/targets.py` — Legacy target management. Zero imports.
- `src/core/limit_orders.py` — Limit order mixin. Never called from main loop (0 imports in `src/`). Target-based buying was never integrated into the trading pipeline.
- `src/strategies/canary_mode.py` — Legacy A/B testing. Zero imports. Replaced by Thompson Sampling.
- `src/strategies/almgren_chriss.py` — Almgren-Chriss executor. Zero imports in production (unused standalone; `TWAPExecutor` in `twap.py` is used instead).
- `src/analytics/knowledge_base.py` — Zero imports.
- `src/utils/retry_decorator.py` — Zero imports.
- `tests/integration/test_targets_edge_cases.py` — Tested legacy target workflow.
- `tests/integration/test_dmarket_api_integration.py` — Tested legacy DMarketAPI client.
- `tests/integration/test_integration_edge_cases.py` — Tested legacy DMarketAPI edge cases.
- `tests/unit/test_limit_orders.py` — Tested limit_orders.py.

**Removed from production code:**
- `position_guard.py`: Removed `check_stale_targets()` method (0 callers) and `TIME_STOP_ENABLED`/`TIME_STOP_MINUTES` constants.
- `tests/sandbox_comprehensive/test_pipeline.py`: Removed `_LimitOrderMixin` import and cross-market target simulation block.

**Removed directories:**
- `src/dmarket/` — Entirely removed (was legacy API client + 5 empty zombie subdirectories).

**NOT touched (still active):**
- `src/api/dmarket_api_client/targets.py` — `get_user_targets()` used by Telegram control bot.
- `src/db/profit_tracker.py` — Used by `tests/unit/test_db_risk_extended.py`.
- `src/utils/database.py` — Used by `tests/integration/conftest.py`.

**Key finding:** Target-based buying (limit orders via `create_targets`/`delete_targets`) was never integrated into the main trading loop. The bot operates exclusively via instant-buy (`buy_items()` / `PATCH /exchange/v1/offers-buy`) since v12.3.

See `ANALYSIS_STAGE4.md` for full details and revalidation results.

## [16.1] - 2026-07-19

### Fixed — Ultra Code Review (48 agent runs, ~180 bugs)

**Pipeline-Breaking Fixes:**
- `cycle_orchestrator.py`: Fixed method name `_fetch_float_phase_listings` → `_fetch_float_filtered_listings`
- `cycle_orchestrator.py`: Fixed `action=="buy"` check → `buy_offer` key check (items now reach execution)
- `cycle_orchestrator.py`: Ranking return value now captured and applied for evaluation ordering
- `cycle_orchestrator.py`: Added missing `oracle` + `current_balance` params to `_eval` call

**Financial Safety Fixes:**
- `position_guard.py`: Stop-loss/take-profit now include sell-side fees in calculation
- `limit_orders.py`: Fixed `int()` → `round()` for price cents (prevents off-by-one cent loss)
- `limit_orders.py`: Fixed `os.getenv("DRY_RUN")` → `Config.DRY_RUN` (prevents bypass)
- `resale_prod.py`: Margin check now includes `FEE_RATE + WITHDRAWAL_FEE_RATE`
- `execution.py`: Equity failure log level raised from debug to warning

**Async/DB Safety Fixes:**
- `daily_briefing.py`: Wrapped 3 sync DB calls in `await price_db.run_in_thread()`
- `scheduler.py`: Added try/except around `run_cycle` (prevents single error from killing bot)
- `app_notifications.py`: Implemented `handle_critical_shutdown` (was a no-op)

**Algorithm Fixes:**
- `info_theory.py`: Fixed population std → sample std (Bessel correction) for ApEn
- `info_theory.py`: Fixed division by zero guard `n < m + 2` → `n < m + 3`
- `info_theory.py`: Fixed asymmetric c_m==0 handling in ApEn

### Architecture Findings (documented, not fixed)
- 59 `Any` type annotations in `core/` mixins
- `filter.py` god module (694 lines)
- 100+ bare `except Exception` blocks
- `composite_buy_score` has 18 positional parameters
- `resale.py` and `limit_orders.py` have 0% test coverage

## [16.0] - 2026-07-17

### Added
- **GARCH(1,1) Volatility Forecasting** (`src/analysis/algo_pack/garch.py`)
  - Replaces EWMA for items with >30 observations
  - Better volatility clustering detection
  - Data-driven persistence estimation (not hardcoded 0.85)
  - Annualization uses sqrt(365) for 24/7 CS2 market

- **Ornstein-Uhlenbeck Mean-Reversion** (`src/analysis/algo_pack/ou_process.py`)
  - Z-score based entry/exit for mean-reverting items
  - Entry at Z < -1.5σ, stop-loss at Z < -3σ
  - Half-life estimation for optimal hold period
  - Proper stop-loss check order (stop checked before entry)

- **HMM Regime Detection (4-state)** (`src/analysis/algo_pack/hmm_regime.py`)
  - CRISIS/BEAR/RECOVERY/BULL states
  - Baum-Welch calibration + online Viterbi decoding
  - CRISIS hard gate blocks all buys (composite_score=0.0)
  - Regime-specific Kelly and position size multipliers
  - math.sqrt guard for negative variance (float precision)

- **Event-Driven Strategy** (`src/analysis/algo_pack/event_driven.py`)
  - CS2 Major tournament calendar
  - Steam Sale awareness
  - Seasonal monthly/weekday patterns
  - Pre-event accumulation signals
  - Proper past-event filtering

- **Pair Trading** (`src/analysis/algo_pack/pair_trading.py`)
  - Cointegration test (Engle-Granger)
  - Z-score spread trading
  - Stop-loss for long_spread positions
  - No short selling (DMarket limitation)

- **Information Theory** (`src/analysis/algo_pack/info_theory.py`)
  - Shannon Entropy for regime detection
  - Approximate Entropy for predictability
  - Mutual Information for signal quality

- **12-Agent Ultra Code Review** (`.opencode/skills/deep-code-review/`)
  - Expanded from 6 to 12 parallel reviewer agents
  - Added: Async Safety, Database Safety, API Safety, Config Safety, Error Recovery, DRY Violations
  - Goal file for easy triggering (`.opencode/goals/code-review-ultra.md`)

- **New Config Parameters** (`src/config.py`)
  - `VOLATILITY_METHOD=garch` (default)
  - `OU_ENABLED`, `OU_ENTRY_Z_SCORE`, `OU_STOP_Z_SCORE`
  - `EVENT_DRIVEN_ENABLED`, `EVENT_PROXIMITY_WEIGHT`, `SEASONAL_WEIGHT`
  - `HMM_ENABLED`, `HMM_MIN_OBSERVATIONS`
  - `PAIR_TRADING_ENABLED`, `PAIR_MIN_CORRELATION`
  - `INFO_THEORY_ENABLED`, `INFO_THEORY_BINS`
  - `EVENT_ACCUMULATE_MULTIPLIER`

### Changed
- **Composite Score** expanded from 15 to 20 components
  - Added: `event` (seasonal/event proximity), `hmm` (regime detection)
  - CRISIS hard gate returns score=0.0 immediately
- **Volatility estimation** now uses GARCH as primary, EWMA as fallback
- **Annualization** consistently uses sqrt(365) instead of sqrt(252) for 24/7 market
- **Price-to-cents** uses `round()` instead of `int()` to prevent systematic underpayment
- **Position sizing** returns 0 when balance <= 0 or item_price <= 0

### Fixed
- HMM update now uses log_return instead of raw percentage
- get_upcoming_events properly excludes past events
- OU stop-loss check order (stop checked before entry)
- Pair trading stop_loss for long_spread positions
- _stage_assemble now captures and returns composite_score
- Filter.py legacy path uses round() instead of int()
- GARCH persistence estimated from data instead of hardcoded 0.85
- Fire-and-forget create_task now stores reference in _pending_tasks
- **Ultra Code Review (19.07.2026):** 9 bugs fixed across 6 files
  - `execution.py`: equity_now["available"] outside isinstance check (TypeError crash)
  - `execution.py`: item_data['best_bid'] without .get() (KeyError)
  - `resale_prod.py`: 2x unheld asyncio.create_task (GC risk, silent exception loss)
  - `autonomous_scanner.py`: unheld asyncio.create_task (Telegram alert GC'd)
  - `position_guard.py`: redundant dict(item) conversion
  - `resale_dry.py`: unheld asyncio.create_task (sell notification GC'd)
  - `workflow/chains.py`: unheld asyncio.create_task (enqueue task GC'd)
  - `core.py`: ctx.current_balance accessed before ctx populated in except block

## [15.9] - 2026-07-16

### Added
- Hawkes Process for frenzy detection
- Bollinger Bands (squeeze + %B)
- DEMA/TEMA/MACD crossovers
- Hurst Exponent regime detection
- Composite score with 15 components

## [15.8] - 2026-07-15

### Added
- Ternary Search sell optimizer
- LIS trend strength
- EWMA + Dual Volatility
- Sliding Window Min/Max
- Markov Regime Detector
- Bayesian Stats + Kelly
- Binary Search spread optimizer
