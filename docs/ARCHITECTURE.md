# DMarket Bot — Architecture (v16.2)

## Overview

The DMarket Bot v16.2 is a **Value Detection Scanner + Spread Sniper** for CS2 skins on the DMarket marketplace. 239 Python modules across 15+ packages, 30+ quantitative algorithms, 30+ microstructure filters.

Key architectural properties:
- **Dual-signal pipeline**: VALUE (rarity-based) + SPREAD (intra-market)
- **Multi-Source Oracle**: 4 external sources (Market.CSGO, Waxpeer, CSFloat, Steam) + DMarket real-time
- **6-stage cycle pipeline**: Prepare → Scan → Prefetch → Evaluate → Execute → Postprocess
- **Defense-in-depth**: 30+ filter stages, slippage protection, oracle drift re-check, idempotency keys

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    DMarket Bot v16.2                              │
│                                                                  │
│  ┌────────────┐  ┌────────────────┐  ┌─────────────┐            │
│  │ Aggregated │  │ MultiSource    │  │ Price-Range │            │
│  │ Prices API │  │ Oracle (4 src) │  │ Scanner     │            │
│  │ (DMarket)  │  │ + FairPrice    │  │ (500 items) │            │
│  └─────┬──────┘  └─────┬──────────┘  └──────┬──────┘            │
│        │               │                    │                   │
│        └───────────────┼────────────────────┘                   │
│                        ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 6-Stage Cycle Pipeline (CycleOrchestrator)                 │ │
│  │                                                            │ │
│  │  1. Prepare   — balance, oracle init, state reconciliation │ │
│  │  2. Scan      — aggregated prices, cheapest listings       │ │
│  │  3. Prefetch  — bulk fees, oracle batch, pump detection    │ │
│  │  4. Evaluate  — 30+ filters, Kelly, value detection        │ │
│  │  5. Execute   — slippage + oracle re-check + buy           │ │
│  │  6. Postproc  — auto-resale, reprice, telemetry            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Execution: PATCH /exchange/v1/offers-buy                   │ │
│  │ → POST /marketplace-api/v2/offers:batchCreate (resale)     │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/
├── __main__.py                    # Entry point
├── config.py                      # Pydantic BaseSettings (~415 lines)
├── inventory_manager.py           # DMarket inventory sync
│
├── core/                          # Application infrastructure + trading engine
│   ├── target_sniping/            # MAIN TRADING LOOP (20+ mixin files)
│   │   ├── core.py                # SnipingLoop — main class, 10 mixins
│   │   ├── cycle_orchestrator.py  # 6-stage pipeline orchestration
│   │   ├── filter.py              # Candidate filtering (30+ checks)
│   │   ├── filter_evaluator.py    # Per-candidate evaluation logic
│   │   ├── microstructure_pipeline.py  # OBI/OFI/VWAP/VPIN/Hawkes/Bollinger/DEMA/MACD/Hurst
│   │   ├── validations.py         # Standalone validation checks (520 lines)
│   │   ├── ranking.py             # Spread ranking + regime + trend
│   │   ├── pricing.py             # Price calculations (float, pattern, fade)
│   │   ├── execution.py           # Buy execution + slippage + oracle re-check
│   │   ├── position_guard.py      # Fee-aware stop-loss/take-profit
│   │   ├── value_pipelines.py     # Dual-signal VALUE+SPREAD pipeline
│   │   ├── scanner.py             # Market scanner + DOM cache
│   │   ├── resale.py              # Resale mixin (DRY/PROD routing)
│   │   ├── resale_prod.py         # Production resale + A-S pricing
│   │   ├── resale_dry.py          # DRY_RUN resale simulation
│   │   ├── telemetry.py           # Health/equity telemetry
│   │   ├── sticker_cache.py       # Two-tier sticker evaluation
│   │   ├── underpriced.py         # DMarket underpriced detection
│   │   └── scheduler.py           # Cycle scheduling + error recovery
│   ├── application.py             # Application facade
│   ├── autonomous_scanner.py      # Main bot runner with retry/backoff
│   ├── daily_briefing.py          # Daily P&L + risk report
│   ├── event_shield.py            # Event-driven trading shield
│   ├── supply_tracking.py         # Supply monitoring
│   ├── limit_orders.py            # Limit order management
│   ├── live_shadow.py             # Shadow trading engine
│   ├── shadow_engine.py           # Shadow/Paper trading engine
│   ├── config_manager.py          # Runtime config reloader
│   └── ...
│
├── analysis/                      # Market microstructure + quantitative algorithms
│   ├── algo_pack/                 # 16 algorithm modules
│   │   ├── garch.py               # GARCH(1,1) volatility forecasting
│   │   ├── hmm_regime.py          # HMM 4-state regime detection
│   │   ├── ou_process.py          # Ornstein-Uhlenbeck mean-reversion
│   │   ├── event_driven.py        # Event-driven strategy
│   │   ├── pair_trading.py        # Pair trading (cointegration)
│   │   ├── info_theory.py         # Information theory (entropy, MI)
│   │   ├── hawkes.py              # Hawkes process (frenzy detection)
│   │   ├── ewma.py                # EWMA + DEMA/TEMA/MACD
│   │   ├── bayesian_stats.py      # Bayesian Kelly + confidence-weighted
│   │   ├── regime_detector.py     # Markov regime + Hurst
│   │   ├── sell_optimizer.py      # Ternary search optimal sell
│   │   ├── spread_optimizer.py    # Binary search MIN_SPREAD
│   │   ├── trend_strength.py      # LIS trend detection
│   │   ├── sliding_window.py      # O(1) min/max deque
│   │   ├── thompson_sampling.py   # Thompson Sampling A/B testing
│   │   └── vpin.py                # VPIN toxicity detection
│   ├── microstructure/            # OBI, signals, volume, volatility
│   ├── seasonal.py                # Seasonal timing multipliers
│   └── orderbook.py               # Orderbook gap analysis
│
├── analytics/                     # Price analytics, backtester, knowledge base
│   ├── price_analytics/           # Indicators, trends, liquidity
│   ├── backtester/                # Walk-forward engine, strategies, metrics
│   ├── historical_data/           # Collector, sources, models
│   ├── filler_tracker.py          # Trade-up filler demand
│   ├── rare_valuation.py          # Rare skin valuation
│   ├── stickers_evaluator.py      # Sticker combo premium
│   ├── self_reflection.py         # Adaptive parameter tuning
│   └── event_calendar.py          # CS2 Major / Steam Sale calendar
│
├── api/                           # External API clients + oracles
│   ├── dmarket_api_client/        # DMarket Trading API v2 (mixin-based)
│   │   ├── core.py                # Ed25519 signing, rate limiting
│   │   ├── market.py              # GET /exchange/v1/market/items
│   │   ├── account.py             # GET /exchange/v1/user-inventory
│   │   ├── offers.py              # batchCreate/batchUpdate/batchDelete
│   │   ├── targets.py             # PATCH /exchange/v1/offers-buy + targets
│   │   ├── fees.py                # Fee calculation
│   │   ├── rate_limiter.py        # Token bucket
│   │   ├── backoff.py             # Circuit breaker
│   │   └── exceptions.py          # API exceptions
│   ├── multi_source_oracle.py     # 4-source oracle + freshness guard + caching
│   ├── fair_price_calculator.py   # Median-based fair price with outlier removal
│   ├── oracle_factory.py          # Oracle factory (game-specific)
│   ├── steam_oracle.py            # Steam Community Market oracle
│   ├── waxpeer_oracle.py          # Waxpeer oracle
│   ├── market_csgo_oracle.py      # Market.CSGO oracle
│   ├── csfloat_oracle.py          # CSFloat oracle
│   ├── candle_builder.py          # OHLCV candle construction
│   └── dmarket_parser.py          # Response parsing (Rust/Python)
│
├── risk/                          # Risk management (14 modules)
│   ├── risk_manager.py            # Central risk orchestrator
│   ├── price_validator.py         # Arbitrage profit validation
│   ├── pump_detector.py           # FOMO/pump detection
│   ├── liquidity_manager.py       # Liquidity-aware position sizing
│   ├── fatal_errors.py            # Error classification
│   ├── error_reporter.py          # Unified error reporting
│   ├── security_auditor.py        # Secret leak detection
│   ├── circuit_breaker_manager.py # Circuit breaker state
│   ├── concentration_risk.py      # Portfolio concentration
│   ├── lock_tracker.py            # Trade lock tracking
│   └── ...
│
├── db/                            # SQLite persistence (4 databases, 19 tables)
│   ├── price_history/             # State + History DBs (mixin-based, 9 mixins)
│   │   ├── core.py                # Connection management, WAL, migrations
│   │   ├── history.py             # Price history queries
│   │   ├── inventory.py           # Virtual inventory CRUD
│   │   ├── analytics_logs.py      # Analytics logging
│   │   ├── targets.py             # Active targets persistence
│   │   ├── asset_status.py        # Trade protection tracking
│   │   ├── low_fee.py             # Low-fee item tracking
│   │   ├── state.py               # Scanning state persistence
│   │   └── pump_blacklist.py      # Pump blacklist
│   └── profit_tracker.py          # Trading DB (trades + daily P&L)
│
├── strategies/                    # Trading strategies
│   ├── base.py                    # BaseStrategy abstract class
│   ├── almgren_chriss.py          # Optimal execution trajectory
│   ├── twap.py                    # Time-Weighted Average Price
│   ├── market_maker.py            # Market making
│   └── cross_market.py            # Cross-market arbitrage
│
├── telegram/                      # Telegram bot interface
│   ├── notifier.py                # Async notification sender
│   └── control_bot/               # Full Telegram bot (15 files)
│
├── models/                        # Data models (msgspec + dataclasses)
├── types/                         # Protocol types for mixin composition
├── monitoring/                    # Prometheus metrics
├── utils/                         # Vault, health server, charts, etc.
├── reflexion/                     # State/Snapshot with rollback
├── sandbox/                       # Bash sandbox
├── cot_audit/                     # Chain-of-thought audit
└── integration/                   # Agent facade (unified interface)
```

## Data Flow (Verified v16.2)

```
Oracle Sources
  │  Market.CSGO ──┐
  │  Waxpeer ──────┤  [circuit breaker per source]
  │  CSFloat ──────┤  [dynamic TTL cache 5-30min]
  │  Steam ────────┘  [Data Freshness Guard: excludes stale]
  ▼
MultiSourceOracle.get_fair_price()         [multi_source_oracle.py:168]
  │  Sequential queries with circuit breaker protection
  │  Builds PriceReference with sources_count
  ▼
FairPriceCalculator.calculate()            [fair_price_calculator.py:85]
  │  1. Filter zero/invalid prices
  │  2. Outlier removal (min < 0.3× median, max > 2.0× median)
  │  3. fair_price = median(adjusted)
  │  4. Margin tiers: vol≥100→3%, ≥50→5%, ≥20→7%, ≥5→10%, else 15%
  │  5. Confidence: high(3+ sources), medium(2), low(1)
  ▼
CycleOrchestrator._stage_prefetch()        [cycle_orchestrator.py:190]
  │  Batch oracle fetch for top-K titles → cs_snapshots
  ▼
_FilterMixin._evaluate_candidate()         [filter.py:71]
  │  30+ filter stages (see Filter Pipeline below)
  │  NOV-2: blocks oracle-dependent strategies when ALL oracles fail
  ▼
ExecutionMixin._execute_instant_buys()     [execution.py:50]
  │  1. Slippage protection — re-verify listing prices
  │  2. NOV-3: Oracle re-check before buy (10% drift threshold)
  │  3. Pre-trade risk check
  │  4. Inventory cap (cumulative tracking)
  ▼
DMarketAPIClient.buy_items()               [targets.py:73]
  │  PATCH /exchange/v1/offers-buy
  │  Idempotency: SHA256(item_id + price_cents)[:16]
  ▼
Response parsing → virtual inventory recording
  ▼
auto_resale()                              [resale.py:54]
  │  Oracle pricing → Avellaneda-Stoikov reservation
  │  → VWAP bands → DOM gap-aware pricing
  ▼
create_sell_offers_batch()                 [offers.py:123]
  │  POST /marketplace-api/v2/offers:batchCreate
  ▼
Reprice stale listings (every 200 cycles)
  │  POST /marketplace-api/v2/offers:batchUpdate
```

## Filter Pipeline (30+ stages)

```
Pre-validation     — title/itemId/price check, duplicate, locked, min price
Bait detection     — suspicious listing patterns
Budget & balance   — effective_balance check
Dynamic price cap  — max($5 floor, effective_balance × 10%)
Risk gate          — drawdown freeze, daily loss, pump blacklist
Kelly sizing       — Bayesian + EWMA adaptive (Half Kelly 50%)
Microstructure     — OBI, OFI, VWAP, CVD, VPIN, adverse selection,
                     vol regime, roll spread, Hawkes, Bollinger, DEMA,
                     MACD, Hurst, HMM, slippage-at-risk, volume profile
Cross-market arb   — inter-market opportunity evaluation
Liquidity gate     — minimum liquidity threshold
Crash detection    — market crash signals
Wash trading       — wash trade pattern detection
Volatility         — volatility validation
Order book depth   — depth analysis
Oracle resolution  — cs_snapshots (batch) → cache → per-item call
Spread gate        — intra-spread, cross-market, oracle discount,
                     dmarket-underpriced
  └─ NOV-2: When ALL oracles down (cs_price==0),
     blocks oracle-dependent strategies;
     intra-spread (pure DMarket-internal) remains allowed
Oracle overpricing — DMarket > 1.5× oracle → skip
List price calc    — oracle ask, cross-market bid
Value detection    — float premium, dirty BS, filler demand,
                     pattern/phase, sticker value, float-date
Min margin check   — list_price < 1.02 × base → reject
Fee evaluation     — buy + sell + withdrawal fees
Saturation         — max same-item holdings
Lock-aware cap     — ≤80% capital in trade-lock
Composite score    — reject if < 0.2
```

## API Endpoints (Verified)

| Operation | Method | Endpoint | File |
|-----------|--------|----------|------|
| **Buy (instant)** | PATCH | `/exchange/v1/offers-buy` | `targets.py:97` |
| **Sell (batch)** | POST | `/marketplace-api/v2/offers:batchCreate` | `offers.py:62` |
| **Reprice (batch)** | POST | `/marketplace-api/v2/offers:batchUpdate` | `offers.py:83` |
| **Cancel (batch)** | POST | `/marketplace-api/v2/offers:batchDelete` | `offers.py:97` |
| **Market items** | GET | `/exchange/v1/market/items` | `market.py:39` |
| **User offers** | GET | `/exchange/v1/user-offers` | `offers.py:33` |
| **Closed offers** | GET | `/marketplace-api/v1/user-offers/closed` | `offers.py:120` |
| **Create targets** | POST | `/marketplace-api/v1/user-targets/create` | `targets.py:61` |
| **User inventory** | GET | `/exchange/v1/user-inventory` | `account.py:57` |

## Multi-Source Oracle

| Source | Type | Update | Freshness |
|--------|------|--------|-----------|
| Market.CSGO | Batch, free | 5 min | Staleness check |
| Waxpeer | Batch, free | 5 min | Staleness check |
| CSFloat | Per-item, API key | 5 min | Staleness check |
| Steam | Per-item, free | 30 min | Staleness check |
| DMarket | Real-time | Each cycle | Always fresh |

Caching: Dynamic TTL (5/15/30 min based on volatility) in `multi_source_oracle.py`.
Fair price: Median with outlier removal in `fair_price_calculator.py`.

## Risk Management

| Instrument | Description |
|------------|-------------|
| Half Kelly (50%) | `f* = win_rate - (1 - win_rate) / win_loss_ratio` |
| Confidence-Weighted Kelly | Kelly with GARCH vol + HMM regime + entropy |
| Fee-Aware Stop-Loss | Includes sell fees in loss calculation |
| Fee-Aware Take-Profit | Includes sell fees in profit calculation |
| Drawdown Freeze | Stop buys at >15% drawdown from peak |
| Pump Detector | 15% spike/1h → 24h blacklist |
| Lock-Aware Cap | ≤80% capital in trade-lock |
| Capital Velocity | Min 0.5× turnover/week |
| HMM CRISIS Gate | Hard block all buys at CRISIS regime |
| Capital Ledger | Atomic balance reservation |
| State Reconciliation | Virtual vs real inventory sync |
| Portfolio Concentration | Collection + category + item limits |

## Execution Safety

| Control | Description |
|---------|-------------|
| Slippage Protection | Re-verify listing prices before buy; abort if >5% increase |
| Oracle Re-check (NOV-3) | Fresh oracle price before buy; abort if >10% drift or below profitability |
| Oracle-Down Guard (NOV-2) | Block oracle-dependent strategies when ALL oracles fail |
| Idempotency Keys | SHA256(item_id + price_cents)[:16] — prevents duplicate orders |
| Inventory Cap | Cumulative tracking prevents intra-batch overspending |
| Circuit Breaker | Blocks requests when circuit is open (5 consecutive failures) |

## Execution Strategy

**Current (v12.3+):** Bot operates exclusively via **instant-buy** (`PATCH /exchange/v1/offers-buy`). This is the only active purchase path in the trading loop.

**Archived:** Target-based buying (limit orders via `batch_create_targets`/`batch_delete_targets`) was implemented in the DMarket API client but never integrated into the main trading loop. Related code (`limit_orders.py`, `check_stale_targets()`, legacy `DMarketAPI` client) archived to `trash/dead_code_2026_07_22/` for potential future use.

The API client (`src/api/dmarket_api_client/targets.py`) retains `batch_create_targets()`, `batch_delete_targets()`, and `get_user_targets()` — the last is actively used by Telegram control bot for displaying active orders.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/core/target_sniping/core.py` | Main SnipingLoop (10 mixins) |
| `src/core/target_sniping/cycle_orchestrator.py` | 6-stage pipeline |
| `src/core/target_sniping/filter.py` | 30+ filter evaluation |
| `src/core/target_sniping/execution.py` | Buy execution + slippage + oracle re-check |
| `src/core/target_sniping/position_guard.py` | Fee-aware stop-loss/take-profit |
| `src/core/target_sniping/value_pipelines.py` | Dual-signal VALUE+SPREAD |
| `src/api/multi_source_oracle.py` | 4-source oracle + caching + freshness guard |
| `src/api/fair_price_calculator.py` | Median-based fair price with outlier removal |
| `src/api/dmarket_api_client/targets.py` | PATCH /exchange/v1/offers-buy |
| `src/api/dmarket_api_client/offers.py` | Sell/reprice/cancel batch endpoints |
| `src/db/price_history/core.py` | SQLite connection, WAL, migrations |
| `src/risk/risk_manager.py` | Central risk orchestrator |
| `src/config.py` | All parameters (Pydantic BaseSettings) |

---

🦅 *DMarket Quantitative Engine | v16.2 Architecture | 2026-07-22*
