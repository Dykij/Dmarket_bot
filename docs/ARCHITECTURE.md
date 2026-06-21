# DMarket Quantitative Engine — Technical Architecture (v14.6)

## 1. System Overview
The DMarket Quantitative Engine is a high-performance algorithmic CS2 skin trading bot that combines intra-market spread sniping, cross-market arbitrage through CS2Cap oracle, order book microstructure analysis, and **value detection layers (v14.6)** — all with **balance-aware capital management** (v14.4). It operates as a deterministic state machine with Rust-accelerated critical paths.

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DOCKER CONTAINERS                                                      │
│  ┌─────────────────────┐    ┌──────────────────────┐                    │
│  │ dmarket_bot         │    │ telegram_bot (opt)   │                    │
│  │ trade loop 30s      │    │ aiogram 3.x admin    │                    │
│  │ 512 MB max          │    │ 256 MB max           │                    │
│  └────────┬────────────┘    └──────────┬───────────┘                    │
└───────────┼────────────────────────────┼────────────────────────────────┘
            │                            │
┌───────────┼────────────────────────────┼────────────────────────────────┐
│           ▼                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐                │
│  │  PYTHON 3.13+ — DMarket Quantitative Engine          │                │
│  │                                                       │                │
│  │  ┌───────────────────────────────────────────────────┐│                │
│  │  │ CORE — Trading Pipeline                            ││                │
│  │  │  scanner.py → core.py → filter.py → execution.py  ││                │
│  │  │  scheduler.py → ranking.py → validations.py       ││                │
│  │  │  resale.py + resale_dry.py + resale_prod.py       ││                │
│  │  └───────────────────────────────────────────────────┘│                │
│  │                                                       │                │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐      │                │
│  │  │ API Layer│ │ Analysis │ │ Risk Manager     │      │                │
│  │  │ DMarket  │ │ OBI, OFI │ │ Kelly Sizing     │      │                │
│  │  │ CS2Cap   │ │ CVD,VPIN │ │ Drawdown Freeze  │      │                │
│  │  │ Rust sign│ │ VWAP,ToD │ │ Capital Velocity │      │                │
│  │  └──────────┘ └──────────┘ └──────────────────┘      │                │
│  │                                                       │                │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐      │                │
│  │  │ DB Layer │ │Telemetry │ │ Utils            │      │                │
│  │  │ Dual SQL │ │Prometheus│ │ Vault, ClockSync │      │                │
│  │  │ WAL mode │ │ /metrics │ │ Health /healthz  │      │                │
│  │  └──────────┘ └──────────┘ └──────────────────┘      │                │
│  └─────────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. API Layer (v2 Batch Endpoints)

All DMarket interactions use Ed25519 signing (Rust pynacl with Python fallback).

| Endpoint Category | Method | Batch | Rate Limit |
|---|---|---|---|
| aggregated prices | POST /marketplace-api/v1/aggregated-prices | 100 items | Circuit breaker (3 fails) |
| Market listings | GET /exchange/v1/market/items | 30 per title | Adaptive throttle |
| Buy | POST /exchange/v1/market/buy | Single | 0.22s delay |
| Batch create offers | POST /marketplace-api/v2/offers/batchCreate | 100 items | Exponential backoff |
| Batch edit | PUT /marketplace-api/v2/offers/batchEdit | 100 items | Exponential backoff |
| Batch delete | DELETE /marketplace-api/v2/offers/batchDelete | 100 items | Exponential backoff |
| Balance | GET /account/v1/balance | Single | Cached per cycle |
| Inventory | GET /marketplace-api/v1/user-inventory | Full | Every 20 cycles |

## 4. Core Pipeline (v14.4)

### 4.1 Cycle Flow (~30 seconds)

```
1. Aggregated Prices      → 100 titles, batch 1 request
2. Ranking                → spread × √(volume), top-20
3. Honest Listings        → parallel GET per title, DOM cache
4. Bulk Fees              → 4 tiers (2/5/7/10%), 1 request
5. CS2Cap Cache           → in-memory dict, 5-min TTL
6. BALANCE GATE (v14.4)   → dynamic max price, reserve buffer
7. 15 FILTERS (v14.4)     → OBI, OFI, bait, VWAP, VPIN, slippage,
                            Kelly, drawdown, velocity, lock-cap...
8. Slippage Protection    → parallel re-verify prices
9. Execute                → POST /exchange/v1/market/buy
10. Auto-Resale           → immediate listing after buy
11. Reprice               → every 200 cycles, drop 5% stale
```

### 4.2 v14.4 Balance-Aware Gates

| Gate | Condition | Action |
|---|---|---|
| Dynamic Price | `price > max(floor, balance × fraction)` | SKIP |
| Reserve Buffer | `effective_balance = balance - reserve` | Reduces max_price |
| Drawdown Freeze | `balance < peak × 0.85` | FREEZE (sell-only) |
| Half Kelly | `position = capital × 0.50 × f*` | Caps position size |
| Lock-Aware Cap | `locked_value > balance × 0.80` | SKIP |
| Capital Velocity | `weekly_sales / avg_balance < 0.5` | PAUSE |

### 4.3 v14.6 Value Detection Layer

Nine modules that enrich the `adjusted_value` per item, all using data already returned by DMarket's REST API (zero scraping):

| Module | File | Premium | Data Source |
|---|---|---|---|
| Float Premium | `pricing.py` | 1.08–1.30× | `floatPartValue` |
| Pattern Premium | `pricing.py` | 1.0–5.0× | `phase` + `paintSeed` |
| Sticker Combo | `stickers_evaluator.py` | up to 3.0× | `stickers` array |
| Filler Tracker | `filler_tracker.py` | 1.15× | Static set of 35 filler skins |
| Seasonal Timing | `seasonal.py` | 0.85–1.15× | System clock |
| Round-Float | `pricing.py` | 1.15× | `floatPartValue` |
| Float-Date | `pricing.py` | 1.08× | `floatPartValue` |
| Dirty BS | `pricing.py` | 1.10× | `floatPartValue` > 0.95 |
| Commission Opt. | `ranking.py` | +15% score | `low_fee_items` cache |

## 5. Analysis Instruments (12 tools)

| Tool | Data Source | Purpose | API Calls |
|---|---|---|---|
| OBI | DMarket agg-prices | Buyer/seller pressure | 0 |
| OFI | DMarket agg-prices (delta) | Demand trend | 0 |
| A-S | CS2Cap cache | Inventory-aware listing price | 0 |
| VWAP | DMarket trade_history | Undervaluation detection | 0* |
| Slippage | Agg-prices volume | Impact protection | 0 |
| CVD | trade_history | Volume divergence | 0* |
| VPIN | trade_history | Flow toxicity | 0* |
| Bait | price_db history | Spoof detection | 0 |
| Micro-Price | CS2Cap cache | Fair listing price | 0 |
| DOM Gap | Market listings | Price gap listing | 0 |
| ToD | System clock | Night discount | 0 |
| Kelly | Win/loss history | Position sizing | 0 |

`*` Uses DMarket get_last_sales (5 calls/cycle)

## 6. Database Schema

### OLTP (state.db)
- `virtual_inventory` — Все купленные предметы, статусы, exclusive flags
- `asset_status` — Trade protection tracking (active/trade_protected/reverted)
- `low_fee_cache` — Daily refreshed low-fee item list
- `pump_blacklist` — 24h FOMO protection
- `decision_logs` — Все решения бота (для анализа)

### OLAP (history.db)
- `price_history` — 5-minute snapshots from CS2Cap
- `trade_history` — Last sales for CVD/VPIN/VWAP (90-day retention)
- `snapshots` — Inventory/value snapshots over time

## 7. Deployment

### Docker (recommended)
- Multi-stage build: Rust builder → Python runtime (~250 MB)
- x86_64 + aarch64/ARM64 support
- docker-compose with persistent volumes
- Health check: HTTP /healthz (port 9091)
- Memory: 128-512 MB main, 64-256 MB Telegram

### Bare metal
- Python 3.13+, Rust toolchain (for maturin)
- SQLite (included), no external DB
- systemd service for auto-restart

## 8. Performance Metrics (v14.4)

| Metric | Value |
|---|---|
| Cycle time | ~30 seconds |
| Items scanned/cycle | 100 |
| API calls/cycle | ~8-12 |
| Memory (idle) | ~58 MB RSS |
| Memory (peak) | <150 MB (leak threshold 500 MB) |
| Trades/day | 3-5 (at $44 balance, scalable) |
| Docker build size | ~250 MB final |
| Rust module size | 2.4 MB (.so) |
| SQLite DB size | ~2 MB (growing) |


🦅 *DMarket Quantitative Engine | v14.6 | June 2026*
