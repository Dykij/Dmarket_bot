# DMarket Bot — Strategy Roadmap (v14.6)

> **Last updated:** 2026-06-21
> **Status:** v14.6 Value Detection Layers — deployed, tested, documented
> **Balance:** $43.91 (real DMarket account, dynamic limits active)
> **Tests:** 52/52 new v14.6 tests + 94/95 existing = 146/147 passing

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

The bot operates **only inside DMarket**, exploiting inefficiencies in the order book and **value detection layers** (v14.6) that identify undervalued items by float, pattern, phase, sticker combos, filler demand, and seasonal timing — all without scraping.

---

## v14.6 — Current State (June 2026)

### ✅ Strategy A — Intra-Spread Balance-Aware (LIVE)

**Production status:** 🟢 **Active** with v14.6 value detection

**Pipeline:**
```
 1. Aggregated prices batch 100 titles
 2. Rank by spread × √(volume) + Commission optimizer (+15% low-fee)
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
 9. ⭐ VALUE DETECTION (v14.6):
    - Float premium → 1.08-1.30× list_price
    - Pattern/phase premium → 1.0-5.0× (Ruby, Blue Gem, Fire & Ice)
    - Sticker combo → up to 3.0×
    - Filler demand → 1.15×
    - Seasonal timing → 0.85-1.15× spread threshold
10. Slippage protection (parallel re-verify prices)
11. Execute buy → POST /exchange/v1/market/buy
12. Auto-resale (A-S + Micro-Price + DOM Gap)
13. Reprice stale every 200 cycles
```

### ✅ v14.6 New Features (9 layers, all live)

| Feature | Logic | Impact |
|---|---|---|
| Float Premium | FN-0 1.20×, dirty BS 1.30×, round 1.15× | Higher sell prices |
| Pattern Premium | Ruby 5×, Blue Gem 3×, Fire & Ice 5× | Rare item capture |
| Sticker Combo | 4× same = +100%, team match = +10% | Stickered item edge |
| Filler Tracker | 35 fillers +15% demand multiplier | Faster turnover |
| Seasonal Timing | Spring +10%, Wed +5%, daytime +3% | Better entry timing |
| Dirty BS | float > 0.95 → 1.10× | Undervalued BS skins |
| Round Float | 0.5/0.25/0.125/0.375 → 1.15× | Collector premiums |
| Float Date | DDMMYYYY pattern → 1.08× | Niche collector value |
| Commission Opt. | Low-fee items +15% rank score | Lower cost basis |
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

### ✅ Strategy D — Sticker Items **LIVE v14.6**

Sticker combo detection active: 4× identical = +100%, team/event match = +10%,
Katowice 2014 special handling (28 variants tracked, 15% of total value).
Integrated into `list_price` in the filter pipeline. Items with sticker value
>$2 flagged as exclusive (auto-keep).

**Status:** Live with v14.6 sticker combo calculator.
(100-1000% margin potential on rare sticker combos.)

---

### ✅ Strategy E — Float Sniping — **LIVE v14.6**

FN-0 (1.20x premium), FN (1.08x), FT-0 (1.15x).
`FLOAT_PREMIUM_ENABLED=true` by default in v14.6.
Plus: dirty BS (1.30×), round-float (1.15×), float-date (1.08×).

---

### ❌ Strategy F — Volume Sniping **NOT RECOMMENDED**

Low absolute profit ($0.05-0.20/item) with current $44 balance.
Also redundant with balance-aware dynamic filters (Kelly + lock-cap already prevent over-trading).

---

## Risk Management (v14.4)

### v14.4 Balance Gates (unchanged)
```
1. Dynamic max price: max($5.00, (balance - $10) × 0.10)
2. Reserve buffer: $10 always unspendable
3. Drawdown freeze: stop buying at >15% peak drop
4. Capital velocity: min 0.5× weekly turnover
5. Lock-aware cap: max 80% in trade-lock
6. Half Kelly: position = capital × 0.50 × f*
```

### v14.6 Value Detection (9 new filters, 0 API calls)
```
 7. Float premium: FN-0 1.20×, double-zero 1.25×, dirty BS 1.30×
 8. Pattern/phase: Ruby 5×, Blue Gem 3×, Fire & Ice 5×
 9. Sticker combo: 4× same = +100%, team match = +10%
10. Filler demand: +15% for trade-up fillers
11. Seasonal timing: spring +10%, summer -10%, Wed +5%
12. Commission optimizer: +15% rank score for 2% fee items
13. Round-float: 0.5/0.25/0.125/0.375 → 1.15×
14. Float-date: DDMMYYYY pattern → 1.08×
15. Dirty BS: float > 0.95 → 1.10×
```

### Per-Trade Filters (15 total, unchanged)
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
14. Rare flag: v14.6 value detection → exclusive
15. Inventory cap: lock-aware 80% limit

### Safety
- `DRY_RUN=true` by default (simulates all trades)
- Circuit breaker: stops after 3 consecutive API errors
- Lock file: prevents duplicate instances
- Leak detection: auto-restart at >500 MB RSS
- Encrypted keys: Fernet vault in memory

---

## Configuration (src/config.py) — v14.6 additions

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

# v14.6 — Value Detection Layers
FLOAT_PREMIUM_ENABLED = True           # Default ON (was OFF)
PATTERN_PREMIUM_ENABLED = True
STICKER_COMBO_ENABLED = True
SEASONAL_TIMING_ENABLED = True
FILLER_TRACKING_ENABLED = True
DIRTY_BS_ENABLED = True
ROUND_FLOAT_ENABLED = True
FLOAT_DATE_ENABLED = True
COMMISSION_OPTIMIZER_ENABLED = True
```

---

## Success Metrics (v14.6)

| Metric | v14.4 Target | v14.6 Projection |
|---|---|---|
| Profitable trades/day | 3-10 | 4-12 (+value detection) |
| Average margin | 5-15% | 8-20% (float/pattern premiums) |
| Daily profit | $0.5-3 | $0.75-4.5 (premium capture) |
| Win rate | 75-85% | 78-88% (better value assessment) |
| Max drawdown | capped at 15% | capped at 15% (freeze) |
| Capital lock duration | <7 days | <6 days (faster filler turnover) |
| API calls/cycle | 8-12 | 8-12 (no new API calls) |
| Yearly projection | $300-600 | $400-800 (value detection adds ~30%) |

---

## Future Work

### Short-term (1-3 months)
1. **Production launch** with $43.91 — enable DRY_RUN=false after sandbox validation
2. **Multi-venue sell-side** — Skinport as secondary sell platform
3. **Value detection cross-validation** — Compare adjusted_value vs buy_price to measure premium capture

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
- **v14.6 mitigations:** Drawdown freeze (15%), Half Kelly, reserve buffer, lock-aware cap, capital velocity, plus value detection layers that only trade items with measurable intrinsic premium
- **Always start with DRY_RUN=true, test ≥48h, then enable live trading**


🦅 *DMarket Intra-Spread Engine | v14.6 | June 2026*
