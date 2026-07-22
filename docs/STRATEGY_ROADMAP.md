# DMarket Bot — Strategy Roadmap (v14.9)

> **Last updated:** 2026-06-27
> **Status:** v14.9 Value Detection Scanner — dual-signal pipeline deployed
> **Balance:** $43.91 (real DMarket account, dynamic limits active)
> **Tests:**ack 289 tests (unit + bottleneck + sandbox)

---

## Vision (v14.9)

The DMarket bot is a **Value Detection Scanner + Spread Sniper** that:

1. **Finds** undervalued items by rarity (float, pattern, stickers) — **even without natural spread**
2. **Buys** at DMarket ask, sells at rarity-adjusted price (oracle ask × premium)
3. **Falls back** to intra-market spread sniping for liquid items
4. **Uses MultiSourceOracle** as external price oracle (BUFF163 + free marketplaces)
5. **Compounds** capital through high-frequency, low-margin volume trading
6. **Defends** with risk gates: drawdown freeze, Kelly sizing, lock-aware cap

The bot operates **only inside DMarket**, using a **dual-signal pipeline**:
- **VALUE signal** (primary): rarity premium × oracle ask vs buy price
- **SPREAD signal** (secondary): best_bid > best_ask × margin

---

## v14.9 — Current State (June 2026)

### ✅ Strategy — Value Detection Scanner (LIVE)

**Production status:** 🟢 Active with dual-signal pipeline

**Pipeline:**
```
 1. Aggregated prices batch 100 titles
 2. Oracle cache (in-memory, 5-min TTL)
 3. Fetch cheapest listings per title (parallel)
 4. VALUE SIGNAL EVALUATION (v14.9, NEW):
    - Float premium → 1.08-1.30×
    - Pattern/phase → 1.0-5.0× (Ruby, Blue Gem, Fire & Ice)
    - Sticker combo → +50-100%
    - Filler demand → 1.15×
     - est_sell = oracle_ask × rarity_mult
    - BUY if est_sell > ask × (1 + fee + margin)
 5. SPREAD FALLBACK (if value fails):
    - best_bid > best_ask × (1 + fee + margin)
 6. Execute buy → PATCH /exchange/v1/offers-buy
 7. Auto-resale at est_sell price
 8. Reprice stale every 200 cycles
```

### Dual-Signal Architecture

| Signal | Trigger | Typical Items | Frequency |
|---|---|---|---|
| **VALUE** | rarity_mult × oracle_ask > ask × cost | Ruby, FN-0, Blue Gem, stickered | Rare but high margin (8-20%) |
| **SPREAD** | best_bid > ask × margin | Liquid skins, volatile periods | Common but lower margin (3-7%) |

---

## v14.9 New Features

### 1. Value Detection Scanner (v14.9)

| Feature | Logic | Impact |
|---|---|---|
| Float Premium | FN-0 1.20×, dirty BS 1.30×, round 1.15× | Higher sell prices |
| Pattern Premium | Ruby 5×, Blue Gem 3×, Fire & Ice 5× | Rare item capture |
| Sticker Combo | 4× same = +100%, team match = +10% | Stickered item edge |
| Filler Tracker | 35 fillers +15% demand multiplier | Faster turnover |
| dirty BS | float > 0.95 → 1.10× | Undervalued BS skins |

### 2. Relaxed Microstructure (v14.9)

Strict HFT filters are **off by default** for Value Scanner:
- `STRICT_MICROSTRUCTURE_FILTERS=false`
- `OBI_ENABLED=false`, `OFI_ENABLED=false`, `VWAP_FILTER_ENABLED=false`
- These can be re-enabled for hybrid trading mode

### 3. Expanded Scan Coverage

| Parameter | v14.6 | v14.9 | Change |
|---|---|---|---|
| PRICE_RANGE_MAX_TITLES | 200 | 500 | +150% coverage |
| ORACLE_TOP_K_VALIDATE | 5 | 50 | +900% validation |
| MIN_TOTAL_SALES | 5 | 3 | More illiquid items |
| MIN_BID_ASK_COUNT | 5 | 2 | Thinner items |
| BALANCE_RESERVE_USD | $10 | $5 | Deploy more capital |
| FEE_RATE | 3% | 5% | Realistic for CS2 |

---

## The 2 Strategies (v14.9)

### ✅ Primary — Value Scanner (NEW in v14.9)

**Status:** Production with dual-signal pipeline

**Concept:** Buy undervalued rare items, resell at rarity-adjusted price.

**Buy criteria (VALUE signal):**
```
oracle_ask × rarity_mult > ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
```

**Examples:**
- FN-0 Doppler Ruby: oracle $120 × 5.0 = $600 fair → buy at $100 → sell at $480
- 4× Katowice Sticker: base $20 + $10 sticker value → sell at $35
- Dirty BS AK-47: oracle $15 × 1.30 = $19.50 → buy at $12 → sell at $17

**Pros:**
- Captures rare mispriced items (high margin)
- Works in flat markets (no spread needed)
- Self-reinforcing (value detection localizes premium)

**Cons:**
- Rare items are, well, rare (lower frequency)
- Requires accurate rarity premium database
- May hold inventory longer for right buyer

**Estimated margin:** 8-20% per trade
**Frequency:** Medium (depends on DMarket listings)

---

### ✅ Secondary — Spread Sniper (LEGACY, fallback)

**Status:** Fallback when Value signal fails

**Concept:** Classic intra-market spread arbitrage.

```
best_bid > best_ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
```

**Pros:**
- Instant execution
- No rarity assessment needed
- High frequency when market is volatile

**Cons:**
- Requires natural spread (rare in efficient markets)
- Lower margins (3-7%)
- Competitive (others also looking for spreads)

**Estimated margin:** 3-7% per trade
**Frequency:** Low-Medium

---

## Risk Management (v14.9)

### Balance Gates
```
1. Dynamic max price: max($5.00, (balance - $5) × 0.10)
2. Reserve buffer: $5 unspendable (reduced from $10)
3. Drawdown freeze: stop buying at >15% peak drop
4. Capital velocity: min 0.5× weekly turnover
5. Lock-aware cap: max 80% in trade-lock
6. Half Kelly: position = capital × 0.50 × f*
```

### Per-Trade Filters
1. **Value gate:** rarity_mult × oracle_ask > ask × cost (primary)
2. **Spread gate:** best_bid > best_ask × margin (secondary/fallback)
3. **Bait detection:** rapid price changes
4. **Liquidity:** min 3 sales (relaxed)
5. **Fee validation:** profit after all fees
6. **Pump guard:** blacklist spiking items
7. **Kelly sizing:** max position size
8. **Saturation:** ≤3 same item, dynamic cap
9. **Inventory cap:** lock-aware 80% limit
10. **Drawdown freeze:** portfolio-level stop

---

## Configuration (src/config.py) — v14.9 additions

```python
# v14.9 — Value Detection Scanner
VALUE_SCAN_ENABLED = True
VALUE_SCAN_MIN_PREMIUM = 1.05
VALUE_SCAN_MIN_PROFIT_PCT = 0.5
VALUE_SCAN_MIN_PROFIT_USD = 0.20

# v14.9 — Relaxed Microstructure (disabled by default)
STRICT_MICROSTRUCTURE_FILTERS = False
OBI_ENABLED = False
OFI_ENABLED = False
VWAP_FILTER_ENABLED = False
CVD_ENABLED = False
VPIN_ENABLED = False

# v14.9 — Expanded Scan Coverage
ORACLE_TOP_K_VALIDATE = 50
PRICE_RANGE_MAX_TITLES = 500
MIN_TOTAL_SALES = 3
MIN_BID_ASK_COUNT = 2
BALANCE_RESERVE_USD = 5.00
FEE_RATE = 0.05
```

---

## Success Metrics (v14.9)

| Metric | v14.6 Target | v14.9 Projection |
|---|---|---|
| Profitable trades/day | 3-10 | 5-15 (value + spread) |
| Average margin | 5-15% | 8-20% (rarity premiums) |
| Daily profit | $0.5-3 | $1-5 (value detection adds) |
| Win rate | 78-88% | 80-90% (better filtering) |
| Max drawdown | 15% | 15% (freeze) |
| Value signal hit rate | — | 20-30% of scans |
| API calls/cycle | 8-12 | 8-12 (same) |
| Yearly projection | $300-800 | $500-1000 |

---

## Future Work

### Short-term (1-3 months)
1. **Production testing** — DRY_RUN=false with $43.91
2. **Premium calibration** — cross-reference with CSFloat sold prices
3. **Sticker DB expansion** — Katowice 2014, Crown, Howl special handling

### Medium-term (3-6 months)
1. **Multi-venue sell-side** — Skinport/CSFloat as secondary sell platform
2. **RL execution** — PPO agent in ABIDES simulator
3. **Cross-skin correlation** — lead-lag signals between skins

### Long-term (6-12 months)
1. **Production canary** — $100, 2 weeks live validation
2. **HashiCorp Vault** — production-grade key storage
3. **Web UI** — dashboard for monitoring/control

---

## Risk Disclosure

- **Trading CS2 skins involves real financial risk**
- **Value Detection is experimental** — rarity premiums may not materialize
- **Bot may lose money due to:** market volatility, trade locks, fees, liquidity, API errors, DMarket policy changes
- **v14.9 mitigations:** Dual-signal pipeline, drawdown freeze (15%), Half Kelly, reserve buffer, lock-aware cap, plus value detection that only trades items with measurable intrinsic premium
- **Always start with DRY_RUN=true, test ≥48h, then enable live trading**


🦅 *DMarket Value Scanner | v14.9 | June 2026*