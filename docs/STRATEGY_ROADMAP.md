# DMarket Bot — Strategy Roadmap (v14.4)

> **Last updated:** 2026-06-18
> **Status:** v14.4 Balance-Aware — in sandbox validation
> **Balance:** $43.91 (real DMarket account, v14.4 dynamic limits active)
> **Tests:** 289/289 passing

---

## Vision

The DMarket bot is a **Balance-Aware Intra-DMarket Arbitrage Engine** that:
1. **Adapts** dynamically to account balance (Half Kelly sizing, dynamic max price)
2. **Buys** underpriced items on DMarket (using aggregated prices, CS2Cap oracle, last sales)
3. **Resells** on DMarket at a profit (A-S reservation price, DOM Gap, Micro-Price)
4. **Uses CS2Cap** as external price oracle (BUFF163 + 41 markets)
5. **Compounds** capital through high-frequency, low-margin volume trading
6. **Defends** with 15+ filters: OBI, OFI, bait, VWAP, VPIN, slippage, drawdown freeze, velocity, lock-cap
7. **Protects capital**: drawdown freeze >15%, reserve buffer $10, Kelly sizing

The bot operates **only inside DMarket**, exploiting inefficiencies in the order book.

---

## v14.4 — Current State (June 2026)

### ✅ Strategy A — Intra-Spread Balance-Aware (LIVE)

**Production status:** 🟢 **Active** with v14.4 enhancements

**Pipeline:**
```
1. Aggregated prices batch 100 titles
2. Rank by spread × √(volume), top-20
3. Honest listings + DOM cache
4. Bulk fee (4 tiers: 2/5/7/10%)
5. CS2Cap cache (in-memory, 5-min TTL)
6. BALANCE GATE (v14.4):
   - Dynamic max price = max($5, effective_balance × 0.10)
   - Reserve buffer = $10 unspendable
7. DRAWDOWN CHECK (v14.4):
   - balance < peak × 0.85 → sell-only freeze
8. 15 FILTERS pipeline:
   - Bait detection, OBI, OFI, VWAP, VPIN, slippage
   - Cross-market arb, volatility, crash guard
   - Half Kelly sizing, lock-aware cap, capital velocity
9. Execute buy → POST /exchange/v1/market/buy
10. Auto-resale (A-S + Micro-Price + DOM Gap)
11. Reprice stale every 200 cycles
```

### ✅ v14.4 New Features (8 items, all live)

| Feature | Logic | Impact |
|---|---|---|
| Dynamic Max Price | `max(floor, balance × fraction)` | $5 at $43, $50 at $500 |
| Reserve Buffer | `effective = balance - $10` | $33.91 effective at $43.91 |
| Half Kelly | `position = capital × 0.50 × f*` | 50% less drawdown, 85% growth |
| Lock-Aware Cap | `max 80% capital in trade-lock` | Prevents freeze |
| Capital Velocity | `min 0.5× weekly turnover` | Prevents capital stagnation |
| Drawdown Freeze | `>15% peak drop → sell-only` | Automatic risk control |
| Balance Pre-Filter | `rank by dynamic_max_price` | CPU efficiency |
| Sandbox Report | Affordable vs Missed items | Transparency |

---

## The 6 Strategies (A → F)

### ✅ Strategy A — Intra-DMarket Spread (PRIORITY: 🥇) — **LIVE v14.4**

**Status:** Production with balance-aware gates

**v14.4 Enhancements:**
- Dynamic max price instead of hardcoded $5 limit
- Half Kelly position sizing (risk-mitigated compounding)
- Drawdown freeze (automatic stop-loss at portfolio level)
- Lock-aware inventory cap (prevents capital freeze)
- Capital velocity constraint (minimum turnover)

**Pros:**
- Instant execution (no trade lock for marketplace buys)
- Self-contained within DMarket
- Predictable profit (3-15% per item)
- Defended by 15+ quantitative filters

**Complexity:** Medium-High (balance gates add safety)
**Estimated margin:** 3-10% per trade
**Frequency:** High (scales with balance)

---

### ✅ Strategy B — Cross-Market Oracle (PRIORITY: 🥈) — **EMBEDDED in A**

**Data flow:**
```
CS2Cap /prices/batch + /bids/batch
  → returns: lowest ask, highest bid across 41 marketplaces
  → filter: provider_bid > DMarket_ask × 1.025
  → if cross-edge > 3%: buy signal
```

**Status:** ✅ **Already integrated into Strategy A filter pipeline**
- CS2Cap cache with 5-min TTL
- Selective top-K validation (5 items/cycle)
- Cross-market arb as secondary signal

---

### ✅ Strategy C — Low-Fee Items — **EMBEDDED in A**

DMarket daily list of items with 2-3% fee (vs 5%+).
Low-fee cache auto-refreshes every 24h. Applied in fee validation.

---

### 📋 Strategy D — Sticker Items **DEFERRED**

Evaluating expensive stickers (Katowice 2014, Crown Foil) requires dedicated DB.
**Deferred until balance >$200 or sticker DB is built.**
(100-1000% margin potential, but only 1-3 finds/week.)

---

### ✅ Strategy E — Float Sniping — **EMBEDDED in A**

FN-0 (1.20x premium), FN (1.10x), FT-0 (1.15x). Already live.
`FLOAT_PREMIUM_ENABLED=false` by default — DMarket prices already incorporate float.

---

### ❌ Strategy F — Volume Sniping **NOT RECOMMENDED**

Low absolute profit ($0.05-0.20/item) with current $44 balance.
Also redundant with balance-aware dynamic filters (Kelly + lock-cap already prevent over-trading).

---

## Risk Management (v14.4)

### Balance Gates
```
1. Dynamic max price: max($5.00, (balance - $10) × 0.10)
2. Reserve buffer: $10 always unspendable
3. Drawdown freeze: stop buying at >15% peak drop
4. Capital velocity: min 0.5× weekly turnover
5. Lock-aware cap: max 80% in trade-lock
6. Half Kelly: position = capital × 0.50 × f*
```

### Per-Trade Filters (15+ total)
1. Spread gate: `≥ fee × 2 + 3%`
2. Bait detection: `≤3 price changes in 5 min`
3. OBI: bid/ask ratio `≥0.7` (skip seller-dominated)
4. OFI: delta `≥-10` (skip falling demand)
5. VWAP: best_ask `< VWAP × 0.90` (undervalued)
6. VPIN: toxicity `<0.8` (skip toxic flow)
7. Slippage: `<50% of edge` (Almgren-Chriss)
8. Cross-market: provider bid `> DMarket_ask × 1.025`
9. Volatility: annualized `<60%` (Garman-Klass)
10. Crash guard: no crash in price_db
11. Liquidity: min sales, wash-trade detection
12. Half Kelly: position `≤ Kelly × capital`
13. Saturation: `≤3 same item`, dynamic cap
14. Rare flag: stickers, Ruby/Sapphire, FN-0
15. Inventory cap: lock-aware 80% limit

### Safety
- `DRY_RUN=true` by default (simulates all trades)
- Circuit breaker: stops after 3 consecutive API errors
- Lock file: prevents duplicate instances
- Leak detection: auto-restart at >500 MB RSS
- Encrypted keys: Fernet vault in memory

---

## Configuration (src/config.py) — v14.4 additions

```python
# v14.4 — Balance-Aware
BALANCE_RESERVE_USD = 10.00
MAX_SNIPING_PRICE_FLOOR = 5.00
MAX_SNIPING_PRICE_BALANCE_FRACTION = 0.10
KELLY_ENABLED = True
KELLY_FRACTION = 0.50
KELLY_FLOOR_PCT = 3.0
LOCK_AWARE_CAP_ENABLED = True
LOCK_AWARE_LIQUID_FRACTION = 0.80
CAPITAL_VELOCITY_ENABLED = True
CAPITAL_VELOCITY_MIN = 0.50
DRAWDOWN_FREEZE_ENABLED = True
DRAWDOWN_FREEZE_THRESHOLD = 0.15
```

---

## Success Metrics (v14.4)

| Metric | v12.2 Target | v14.4 Projection |
|---|---|---|
| Profitable trades/day | 5-15 | 3-10 (balance-aware) |
| Average margin | 5-10% | 5-15% (Kelly improves) |
| Daily profit | $1-5 | $0.5-3 (safe: drawdown protection) |
| Win rate | 60-80% | 75-85% (better filters) |
| Max drawdown | unlimited | capped at 15% (freeze) |
| Capital lock duration | 7-14 days | <7 days (velocity) |
| API calls/cycle | ~15 | ~8-12 (cache) |
| Yearly projection | $411 on $44 | $300-600 (conservative) |

---

## Future Work

### Short-term (1-3 months)
1. **Production launch** with $43.91 — enable DRY_RUN=false after sandbox validation
2. **Sticker Value DB** — CSFloat integration for sticker evaluation
3. **Multi-venue sell-side** — Skinport/CSFloat as secondary sell platforms

### Medium-term (3-6 months)
1. **RL execution** — PPO agent training in ABIDES simulator
2. **TWAP/MPC** — Split large positions over time
3. **Cross-skin OFI** — Lead-lag correlation signals between skins

### Long-term (6-12 months)
1. **Production canary** — $100, 2 weeks live validation
2. **HashiCorp Vault** — Production-grade key storage
3. **Web UI** — Dashboard for monitoring/control


## Risk Disclosure

- **Trading CS2 skins involves real financial risk**
- **All code is for educational/simulation purposes**
- **Bot may lose money due to:** market volatility, trade locks, fees, liquidity, API errors, DMarket policy changes
- **v14.4 mitigations:** Drawdown freeze (15%), Half Kelly, reserve buffer, lock-aware cap, capital velocity
- **Always start with DRY_RUN=true, test ≥48h, then enable live trading**


🦅 *DMarket Intra-Spread Engine | v14.4 | June 2026*
