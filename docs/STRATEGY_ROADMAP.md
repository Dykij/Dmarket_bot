# DMarket Bot — Strategy Roadmap v12.0

> **Last updated:** 2026-06-01
> **Status:** Active — Strategy A in implementation
> **Balance:** $43.91 (real DMarket account)

---

## Vision

The DMarket bot is an **Intra-DMarket Arbitrage Engine** that:
1. **Buys** underpriced items on DMarket (using DMarket bids, last sales, low-fee lists as price references)
2. **Resells** on DMarket at a profit (above the bid price, below the ask spread)
3. **Uses CS2Cap** as an external price oracle (BUFF163 + 41 markets) for sanity checks
4. **Compounds** capital through high-frequency, low-margin volume trading

The bot does **NOT** cross-list on BUFF163 — it only operates inside DMarket, exploiting inefficiencies in the order book.

---

## Problem Statement (v11.0 audit)

The previous logic tried to find items where:
```
DMarket ask < BUFF163 ask * 0.85
```
**This never worked** because DMarket prices are typically 30-90% **above** BUFF163 (the Chinese market is consistently cheaper). The bot scanned 50 items, found 0 profitable trades.

### Root Cause
- BUFF163 ≠ DMarket pricing universe
- Cross-market arbitrage requires Steam trade locks (7d + 7d = 14d frozen capital)
- Within DMarket, the spread between `best_bid` and `best_ask` is the real opportunity

---

## The 6 Strategies (A → F)

### ✅ Strategy A — Intra-DMarket Spread (PRIORITY: 🥇)

**Idea:** Buy at `best_ask`, sell at `best_bid - $0.01`. The spread is the profit.

**Data flow:**
```
DMarket /marketplace-api/v1/aggregated-prices
   → returns: {best_ask, best_bid, count} for up to 100 items in 1 request
   → filter: best_bid > best_ask * 1.05 (5%+ spread)
   → buy at best_ask via /exchange/v1/market/buy
   → list at best_bid - 0.01 via /marketplace-api/v1/user-offers/create
```

**Pros:**
- Instant execution (no 14d trade lock for the bid side)
- Self-contained within DMarket
- Predictable profit (5-15% per item)
- Single API call covers 100 items

**Cons:**
- Competition with other bots is fierce
- Spread can evaporate in seconds
- Requires constant scanning

**Complexity:** Medium
**Estimated margin:** 3-10% per trade
**Frequency:** High (10-50 trades/day)
**Status:** 🟡 **In implementation**

---

### ⏳ Strategy B — Last Sales Arbitrage (PRIORITY: 🥈)

**Idea:** Use real DMarket sale prices as the "fair value" reference.

**Data flow:**
```
DMarket /trade-aggregator/v1/last-sales?title=...
   → returns: list of {price, date, seller} for the last 30 days
   → filter: ask_price < last_sale_avg * 0.90 (10%+ discount to recent sales)
```

**Pros:**
- Real transaction data (not intentions)
- Better at spotting undervalued items
- 5-20% margin potential

**Cons:**
- Sale data may be stale (item trends change)
- Low volume per item
- 7d trade lock required (Steam deposit → DMarket → Steam withdraw)

**Complexity:** Low
**Estimated margin:** 5-20% per trade
**Frequency:** Medium (5-15 trades/day)
**Status:** 📋 Planned

---

### ⏳ Strategy C — Low-Fee Items (PRIORITY: 🥉)

**Idea:** DMarket publishes a daily list of items with reduced fees (2-3% vs 5%).

**Data flow:**
```
DMarket /marketplace-api/v1/low-fee-items
   → returns: list of {title, fee_rate} with 2-3% fees
   → apply Strategy A logic but with lower fee overhead
```

**Pros:**
- 50-100% more margin than regular items
- Updated daily
- Simple filter

**Cons:**
- Limited selection (only specific items)
- High competition (everyone targets them)
- List changes daily → may miss window

**Complexity:** Low (just a filter)
**Estimated margin boost:** +2-3% on top of Strategy A
**Frequency:** Low (5-10 items/day)
**Status:** 📋 Planned

---

### ⭐ Strategy D — Sticker Items (PRIORITY: HIGH ROI)

**Idea:** DMarket listings often miss the value of expensive stickers (Howl, Katowice 2014, Crown Foil).

**Data flow:**
```
DMarket /exchange/v1/market/items
   → check attributes.stickers[]
   → query CS2Cap or internal DB for sticker value
   → if ask_price < (item_value + sticker_value * 0.7): buy
```

**Pros:**
- 100-1000%+ margin on rare stickers
- Low competition (most bots don't evaluate stickers)
- Permanent value (rare stickers don't depreciate)

**Cons:**
- Requires sticker value database
- High risk if sticker is fake
- Very rare listings
- Need authenticator/manual verification

**Complexity:** High (sticker DB + validation)
**Estimated margin:** 100-1000%
**Frequency:** Very low (1-3/week)
**Status:** 📋 Planned (after strategies A-C are proven)

---

### ⭐ Strategy E — Float Sniping (PRIORITY: MEDIUM)

**Idea:** Items with extreme floats (FN-0 0.00-0.01, FT-0 0.15-0.18) sell for 20-50% more.

**Data flow:**
```
DMarket /exchange/v1/market/items
   → check attributes.floatPartValue
   → if float < 0.005 (FN-0) or float in [0.15, 0.18] (FT-0):
        buy and resell with float premium pricing
```

**Pros:**
- Stable margin (15-30%)
- Easy to detect (float is in API response)
- Many items qualify

**Cons:**
- Float verification required (DMarket data may be unreliable)
- Some items already priced correctly
- Need to compete with float-specific bots

**Complexity:** Medium (float validation + pricing)
**Estimated margin:** 15-30%
**Frequency:** Medium (5-10/day)
**Status:** 📋 Planned (parallel to A-C)

---

### ⭐ Strategy F — Volume Sniping (PRIORITY: LOW ROI, HIGH TURNOVER)

**Idea:** With $43.91 balance, buy many cheap items ($0.50-2) and resell at small markup.

**Data flow:**
```
DMarket /exchange/v1/market/items?priceFrom=50&priceTo=200 (50¢-$2 in cents)
   → buy 10-20 items per cycle
   → resell at +10-20% markup
```

**Pros:**
- Low risk per item
- Many small wins
- High turnover

**Cons:**
- 5% fee + 7d trade lock = low ROI
- Capital tied up for 7+ days
- Spreads are usually already optimized

**Complexity:** Low
**Estimated margin:** 5-10% but small absolute profit ($0.05-0.20/item)
**Frequency:** Very high (20-50/day)
**Status:** 📋 Not recommended for $43.91 (lock overhead too high)

---

## Recommended Implementation Order

| Phase | Strategy | Effort | Expected Daily Profit | Status |
|-------|----------|--------|----------------------|--------|
| 1 | A — Intra-Spread | 4h | $1-3 | 🟡 Implementing |
| 2 | B — Last Sales | 3h | $2-5 | 📋 Next |
| 3 | C — Low-Fee | 2h | +$0.5-1 | 📋 Parallel |
| 4 | E — Float | 4h | $1-3 | 📋 After A-C |
| 5 | D — Stickers | 8h | $5-50 (irregular) | 📋 Premium |
| 6 | F — Volume | 2h | $0.1-0.5 | ❌ Not recommended |

**Cumulative expected profit (Phase 1-3):** $3-9/day on $44 balance = **7-20% daily ROI**

---

## Architecture Changes for v12.0

### 1. CS2Cap Oracle (replaces CSFloat)
- `src/api/cs2cap_oracle.py` — BUFF163 price fetcher
  - `get_item_price(hash_name)` → lowest ask (CS2Cap `a8db` endpoint)
  - `get_buy_order(hash_name)` → highest bid (Starter tier, $19/mo)
  - `get_item_value(hash_name)` → fallback: ask * 0.95 if bids unavailable
  - `get_batch_prices(hash_names[])` → batch queries (with throttling)
  - Caching: 3h SQLite, 15m in-memory
  - Throttling: 1 RPS default, 0.5 RPS on 429

### 2. DMarket Aggregated Prices
- `src/api/dmarket_api_client.py`
  - `get_aggregated_prices(game_id, titles[])` → batch bid+ask
  - Endpoint: `GET /marketplace-api/v1/aggregated-prices`

### 3. Strategy A Engine
- `src/core/target_sniping.py`
  - Replace CSFloat ref_price with DMarket bid-based pricing
  - Filter: `best_bid > best_ask * 1.05`
  - Buy at `best_ask`, list at `best_bid - 0.01`

### 4. Sell Pipeline (already exists in v11.0)
- `create_offer(offerId, price)` → list single item
- `batch_create_offers(offers[])` → batch list
- `delete_offers(offerIds[])` → cancel listings

### 5. Last Sales Integration (Phase 2)
- `src/api/dmarket_api_client.py`
  - `get_last_sales(game_id, title, days=30)` → list of sales
  - `get_batch_last_sales(game_id, titles[])` → batch
  - Endpoint: `GET /trade-aggregator/v1/last-sales`

### 6. Low-Fee Filter (Phase 3)
- `src/api/dmarket_api_client.py`
  - `get_low_fee_items(game_id)` → daily list
  - Endpoint: `GET /marketplace-api/v1/low-fee-items`

### 7. Repricing (Phase 4)
- `src/api/dmarket_api_client.py`
  - `edit_offers(offerId, newPrice)` → reprice
  - Endpoint: `PATCH /user-offers/edit`
  - Trigger: every 6h for items not sold in 24h

---

## Risk Management

### Position Sizing
- MAX_POSITION_RISK_PCT = 30% of balance ($13.17 max per item)
- MAX_OPEN_TARGETS = 50
- MAX_OPEN_INVENTORY = 30 items (to avoid 7d lock overflow)

### Per-Trade Filters
1. `spread > 5%` — minimum profit
2. `price > $0.50` — avoid dust
3. `price < $50` — avoid whale risk
4. `volume > 3` — at least 3 active sellers
5. `bid_exists` — someone is willing to buy
6. `fee_rate < 5%` — prefer low-fee items
7. `volatility < 20%` — stable price
8. `slippage < 2%` — tight order book

### Trade Protection Logic
- After buy, item is locked for 7d (Trade Protection)
- Cannot resell on DMarket during protection
- After 7d, can resell (but may be subject to 7d Trade Lock from original Steam deposit)
- Total: 14d maximum capital lock — bot must account for this in position sizing

### Safety
- DRY_RUN = true (no real money)
- All write operations simulated
- Real APIs only for read operations
- 5% simulated error rate in sandbox

---

## Configuration (src/config.py)

```python
# Strategy Selection
ACTIVE_STRATEGY = "IntraSpread"  # A | B | C | D | E | F

# Risk
MIN_SPREAD_PCT = 5.0      # 5% minimum spread
MIN_PRICE_USD = 0.50
MAX_PRICE_USD = 50.00
MAX_POSITION_RISK_PCT = 30.0
MAX_OPEN_TARGETS = 50
MAX_OPEN_INVENTORY = 30

# Performance
BATCH_SIZE = 50
SCAN_INTERVAL = 1  # seconds

# Fees
FEE_RATE = 0.05  # default
LOW_FEE_THRESHOLD = 0.03

# CS2Cap
CS2C_API_KEY = "sk_live_..."
CS2C_TIER = "free"  # free | starter | pro
CS2C_RPS_LIMIT = 1.0

# Repricing
REPRICE_INTERVAL_HOURS = 6
REPRICE_AFTER_HOURS = 24
REPRICE_DISCOUNT_PCT = 2.0
```

---

## OpenCode Prompt (v12.0)

```markdown
# DMarket Bot — Intra-Spread Arbitrage Engine

## Goal
Buy cheap on DMarket, sell higher on DMarket. Use CS2Cap (BUFF163) as oracle.

## Context
- Balance: $43.91 real
- DRY_RUN: true (simulate, don't trade)
- Working dir: /tmp/opencode/Dmarket_bot/

## Stack
- Python 3.11+, AsyncIO
- DMarket v2 (Ed25519 NaCL)
- CS2Cap API (BUFF163 + 41 markets)
- SQLite (bifurcated: state + history)

## Architecture
- src/api/cs2cap_oracle.py — BUFF163 oracle
- src/api/dmarket_api_client.py — DMarket API
- src/api/market_data_fetcher.py — DMarket order book
- src/core/target_sniping.py — main loop
- src/db/price_history.py — Bifurcated SQLite

## Rules
1. Always read existing code first
2. Always test via scratch/test_sandbox_v9.py
3. Never delete API methods — only add
4. DRY_RUN must be true
5. Log that bot is SIMULATING

## Commands
- PYTHONPATH=. python3 scratch/test_sandbox_v9.py
- PYTHONPATH=. python3 scratch/sandbox_audit.py
- git push with token URL
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `docs/STRATEGY_ROADMAP.md` | CREATE | This file |
| `src/api/cs2cap_oracle.py` | CREATE | CS2Cap oracle (replaces csfloat) |
| `src/api/csfloat_oracle.py` | DELETE | Remove CSFloat |
| `src/api/oracle_factory.py` | MODIFY | Use CS2Cap instead of CSFloat |
| `src/api/dmarket_api_client.py` | MODIFY | Add `get_aggregated_prices`, `get_last_sales`, `get_low_fee_items` |
| `src/core/target_sniping.py` | MODIFY | Strategy A: bid-based spread |
| `src/config.py` | MODIFY | New tunables |
| `scratch/test_sandbox_v9.py` | MODIFY | Test Strategy A |
| `scratch/sandbox_audit.py` | MODIFY | Test full pipeline |
| `.env` | CREATE | Real credentials |
| `README.md` | MODIFY | v12.0 docs |
| `CHANGELOG.md` | MODIFY | v12.0 entry |
| `MEMORY.md` | MODIFY | v12.0 summary |

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Profitable trades per day | 5-15 | 0 |
| Average margin per trade | 5-10% | -50% (losing) |
| Daily profit | $1-5 | $0 |
| Win rate | 60-80% | N/A |
| Capital lock duration | 7-14 days | N/A |
| ROI (daily) | 2-10% | 0% |

---

## Risk Disclosure

- **Trading CS2 skins involves real financial risk**
- **All code is for educational/simulation purposes**
- **Bot may lose money due to:**
  - Market volatility
  - Trade locks (7-14d)
  - Fee structure (5% standard)
  - Liquidity risk (unable to sell)
  - API errors / rate limits
- **Use DRY_RUN first, test thoroughly, then enable live trading**

---

🦅 *DMarket Intra-Spread Engine | v12.0 | 2026*
