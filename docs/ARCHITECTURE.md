# DMarket Bot — Architecture (v14.9)

## Overview

The DMarket Bot v14.9 is a **Value Detection Scanner + Spread Sniper** for CS2 skins on the DMarket marketplace.

Key architectural changes in v14.9:
- **Dual-signal pipeline**: VALUE (rarity-based) + SPREAD (intra-market)
- **Relaxed microstructure**: HFT filters disabled by default
- **Expanded scan coverage**: 500 titles/cycle, 50 CS2Cap validations

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│               DMarket Bot v14.9                      │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐   │
│  │ Aggregated │  │ CS2Cap     │  │ Price-Range │   │
│  │ Prices API │  │ Oracle     │  │ Scanner     │   │
│  │ (100 items)│  │ (41 mkts)  │  │ (500 items) │   │
│  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘   │
│        │               │                │          │
│        └───────────────┼────────────────┘          │
│                        ↓                           │
│          ┌──────────────────────┐                 │
│          │ Dual-Signal Pipeline │                 │
│          │  ┌────────────────┐  │                 │
│          │  │ VALUE Signal   │  │     Primary    │
│          │  │ (float/pattern │  │     (rarity)   │
│          │  │ /sticker)      │  │                 │
│          │  └──┬─────────────┘  │                 │
│          │     ↓ Falls through │                 │
│          │  ┌────────────────┐  │                 │
│          │  │ SPREAD Signal  │  │     Secondary  │
│          │  │ (best_bid vs   │  │     (spread)   │
│          │  │ best_ask)      │  │                 │
│          │  └────────────────┘  │                 │
│          └──────────────────────┘                 │
│                        ↓                           │
│          ┌──────────────────────┐                 │
│          │ Risk Management      │                 │
│          │ (Kelly, Drawdown,    │                 │
│          │ Lock-Aware Cap)      │                 │
│          └──────────────────────┘                 │
│                        ↓                           │
│  ┌─────────────────────────────────────────────┐ │
│  │ Execution: Buy → Auto-Resale → Reprice       │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Components

### Value Scanner (v14.9)

**Location:** `src/core/target_sniping/value_pipelines.py`

Evaluates each item for rarity value:
- Float premium: FN-0, dirty BS, round floats
- Pattern premium: Ruby, Sapphire, Blue Gem, Fire & Ice
- Sticker combo: 4× same, team match
- Filler demand: trade-up skins

Returns: `est_sell_price = cs2cap_ask × rarity_mult`

### Spread Sniper (Legacy)

**Location:** `src/core/target_sniping/filter.py`

Classic intra-market arbitrage:
- `has_intra_spread = best_bid > best_ask × margin`
- Only triggers if Value signal fails

### CS2Cap Cache

**Location:** `src/api/cs2cap_cache.py`

- In-memory cache (5-min TTL)
- 200-item coverage
- Sub-ms dict lookup for price validation

### Risk Manager

**Location:** `src/risk/risk_manager.py`

- Drawdown freeze (>15%)
- Half Kelly sizing
- Lock-aware cap (≤80%)
- Capital velocity (min 0.5×/week)

## Data Flow

```
Cycle Start
    │
    ├── Fetch aggregated prices (100 titles)
    ├── Fetch CS2Cap cache (200 titles)
    ├── Fetch cheapest listings (parallel)
    │
    ├── For each item:
    │   ├── Evaluate VALUE signal
    │   │   ├── Calculate rarity premium
    │   │   └── est_sell = cs2cap × premium
    │   │       └── If est_sell > ask × cost: BUY
    │   └── Else evaluate SPREAD signal
    │       └── If best_bid > ask × margin: BUY
    │
    ├── Apply risk filters
    ├── Execute buys
    └── Auto-resale at est_sell price
```

## Key Files

| File | Purpose |
|---|---|
| `src/core/target_sniping/value_pipelines.py` | Dual-signal evaluation (v14.9) |
| `src/core/target_sniping/filter.py` | Legacy spread filters |
| `src/core/target_sniping/pricing.py` | Rarity premium calculators |
| `src/api/cs2cap_cache.py` | In-memory price cache |
| `src/config.py` | All parameters (v14.9 defaults) |
| `src/risk/risk_manager.py` | Drawdown, Kelly, etc. |


🦅 *DMarket Quantitative Engine | v14.9 Architecture*