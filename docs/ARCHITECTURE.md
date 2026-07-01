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

### NIM Orchestrator (v14.9)

**Location:** `src/nim_orchestrator/`

NVIDIA NIM free endpoint pool with transparent model failover:
- 121+ free NVIDIA NIM models with circuit breaker
- API key pool rotation and stream-through failover
- Task groups: heavy-reasoning | fast-coding | code-specialized
- RoundRobin routing strategy with configurable cooldown

### Reflexion Layer (v14.9)

**Location:** `src/reflexion/`

State/Snapshot pattern with rollback capabilities:
- Git-based snapshot integration
- Content-based backup fallback for non-git environments
- Automatic pruning of old snapshots

### Workflow Chains (v14.9)

**Location:** `src/workflow/`

Async pipeline with Conductor pattern (Parser→Coder→Tester):
- `Conductor` orchestration with asyncio.Queue + TaskGroup
- Support for multiple workers per role
- DAG-based dependency resolution
- Graceful shutdown with sentinel pattern

### Bash Sandbox (v14.9)

**Location:** `src/sandbox/`

Lightweight sandbox with timeout/security checks:
- Timeout enforcement (asyncio.wait_for)
- Allowed/disallowed command lists with regex patterns
- Max output size limiting
- Docker isolation helper

### CoT Audit (v14.9)

**Location:** `src/cot_audit/`

Chain-of-thought formatting and incremental metadata cache:
- Markdown/Numbered/Bullet output styles
- Incremental scan with mtime+md5 invalidation
- Automatic .file exclusion

### Integration Facade (v14.9)

**Location:** `src/integration/`

Unified interface for all subsystems:
- `safe_bash()`, `get_cot_markdown()`, `create_snapshot()`, `execute_with_snapshot()`
- E2E full cycle testing
- Load testing (1000 concurrent tasks)

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
| `src/nim_orchestrator/orchestrator.py` | NIM model failover pool |
| `src/reflexion/core.py` | State snapshots and rollback |
| `src/workflow/chains.py` | Async pipeline orchestration |
| `src/sandbox/core.py` | Safe shell execution |
| `src/cot_audit/core.py` | Chain-of-thought formatting |
| `src/integration/agent_facade.py` | Unified subsystem interface |


🦅 *DMarket Quantitative Engine | v14.9 Architecture*