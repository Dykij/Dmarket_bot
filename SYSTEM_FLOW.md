# SYSTEM_FLOW — DMarket Quantitative Engine (v16.2)

Логическая цепочка работы бота в режиме **v16.2 (30+ algorithms, 30+ filters, 4-source oracle)**.

---

## Основной торговый цикл (~30s pipeline)

```
START CYCLE (run_cycle)
  │
  ├── 1. _stage_prepare
  │      ├── Balance check (effective = total - reserved)
  │      ├── Dynamic max price = max($5 floor, effective × 10%)
  │      ├── Oracle initialization (MultiSourceOracle refresh)
  │      ├── State Reconciliation (every 10 cycles)
  │      └── Cycle counters reset
  │
  ├── 2. _stage_scan
  │      ├── DMarket aggregated-prices (100 titles)
  │      ├── Cheapest listings fetch
  │      └── Secondary scans: float/phase, price-range, low-fee
  │
  ├── 3. _stage_prefetch
  │      ├── Bulk fee lookup (4 tiers)
  │      ├── Oracle batch fetch: MultiSourceOracle.get_fair_prices_batch()
  │      │   └── FairPriceCalculator: outlier removal → median → margin tiers
  │      ├── Pump detection scan per title
  │      ├── Sales cache (for CVD/VPIN)
  │      └── Dynamic margin calculation
  │
  ├── 4. _stage_evaluate (parallel, semaphore=10)
  │      ├── Rank candidates by spread
  │      └── For each candidate: _evaluate_candidate() — 30+ filter stages
  │           ├── Pre-validation (title, itemId, price, duplicate, locked)
  │           ├── Bait detection
  │           ├── Budget & balance check
  │           ├── Dynamic price cap (balance-aware)
  │           ├── Risk gate (drawdown freeze, daily loss, pump blacklist)
  │           ├── Kelly sizing (Bayesian + EWMA, Half Kelly 50%)
  │           ├── Microstructure pipeline (15+ signals):
  │           │   OBI, OFI, VWAP, CVD, VPIN, adverse selection,
  │           │   vol regime, roll spread, Hawkes, Bollinger, DEMA,
  │           │   MACD, Hurst, HMM regime, slippage-at-risk, volume profile
  │           ├── Cross-market arbitrage evaluation
  │           ├── Liquidity gate + crash detection
  │           ├── Wash trading detection
  │           ├── Volatility validation + order book depth
  │           ├── Oracle price resolution (batch → cache → per-item)
  │           ├── Spread/opportunity gate
  │           │   └─ NOV-2: ALL oracles down → block oracle-dependent;
  │           │      intra-spread (DMarket-internal) remains allowed
  │           ├── Oracle overpricing check (DMarket > 1.5× oracle → skip)
  │           ├── Value detection layers:
  │           │   float premium, dirty BS, filler demand,
  │           │   pattern/phase, sticker value, float-date
  │           ├── Minimum margin check
  │           ├── Fee evaluation (buy + sell + withdrawal)
  │           ├── Saturation check (max same-item holdings)
  │           ├── Lock-aware inventory cap (≤80%)
  │           └── Composite microstructure score (reject if < 0.2)
  │
  ├── 5. _stage_execute
  │      ├── Slippage protection (re-verify listing prices, abort if >5%)
  │      ├── NOV-3: Oracle re-check before buy
  │      │   └── Fresh fair price < profitability → cancel
  │      │   └── Price drifted >10% from evaluation → cancel
  │      ├── Pre-trade risk check (fee-aware)
  │      ├── Inventory cap (cumulative tracking, atomic gate)
  │      ├── PATCH /exchange/v1/offers-buy
  │      │   └── Idempotency: SHA256(item_id + price_cents)[:16]
  │      └── Response parsing → virtual inventory recording
  │
  └── 6. _stage_postprocess
         ├── Auto-resale
         │   ├── Oracle fair price via get_fair_price()
         │   ├── Avellaneda-Stoikov reservation price (if enabled)
         │   ├── VWAP bands + DOM gap-aware pricing
         │   └── POST /marketplace-api/v2/offers:batchCreate
         ├── Repricing unsold offers (every 200 cycles)
         │   └── POST /marketplace-api/v2/offers:batchUpdate
         ├── Telegram notifications
         ├── Telemetry + cycle metrics
         └── State Reconciliation (periodic)
```

---

## Dual-Signal Pipeline

```
VALUE SIGNAL (primary):
  rarity_mult × oracle_ask > ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
  → Float premium (1.08-1.30×)
  → Pattern/phase premium (1.0-5.0×)
  → Sticker combo (+50-100%)
  → Filler demand (1.15×)
  → est_sell = oracle_ask × rarity_mult
  → BUY if est_sell > ask × cost

SPREAD SIGNAL (fallback):
  best_bid > best_ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
  → Classic intra-market spread arbitrage
  → Does NOT require oracle data (pure DMarket-internal)
```

---

## Oracle Data Flow

```
Market.CSGO ──┐
Waxpeer ──────┤  Sequential queries with circuit breaker
CSFloat ──────┤  Dynamic TTL cache (5/15/30 min by volatility)
Steam ────────┘  Data Freshness Guard (excludes stale sources)
       │
       ▼
MultiSourceOracle.get_fair_price()     [multi_source_oracle.py:168]
  │  Builds PriceReference with sources_count
  │  Confidence: high(3+), medium(2), low(1)
  ▼
FairPriceCalculator.calculate()        [fair_price_calculator.py:85]
  │  1. Filter zero/invalid prices
  │  2. Outlier removal: min < 0.3× median, max > 2.0× median
  │  3. fair_price = median(adjusted)
  │  4. Margin tiers: vol≥100→3%, ≥50→5%, ≥20→7%, ≥5→10%, else 15%
  │  5. sell_price = fair_price × (1 + margin/100)
  │  6. Min 3% profit over buy price
  ▼
FairPriceResult { fair_price, sell_price, confidence, sources_count }
```

---

## Risk Gates

```
BALANCE GATE:
  effective = max(0, balance - BALANCE_RESERVE_USD)
  max_price = max($5 floor, effective * 0.10)
  if item.price > max_price → SKIP

DRAWDOWN GATE:
  if balance < peak_balance * 0.85 → FREEZE (sell-only mode)

KELLY GATE:
  f* = win_rate - (1 - win_rate) / win_loss_ratio
  position_size = capital * 0.50 * f*  (Half Kelly)
  Adjusted by: GARCH volatility + HMM regime + entropy regime

VELOCITY GATE:
  weekly_sales / avg_balance < 0.5 → PAUSE BUYING

LOCK-AWARE CAP:
  if trade-locked items > 80% of max → SKIP new buys

HMM CRISIS GATE:
  if regime == CRISIS → HARD BLOCK ALL BUYS

PUMP DETECTOR:
  if price spike > 15% in 1h → 24h blacklist
```

---

## Execution Safety

| Control | File | Description |
|---------|------|-------------|
| Slippage Protection | `execution.py:93-168` | Re-verify listing prices; abort if >5% increase |
| Oracle Re-check (NOV-3) | `execution.py:136-163` | Fresh oracle price before buy; abort if >10% drift |
| Oracle-Down Guard (NOV-2) | `filter.py:391-414` | Block oracle-dependent strategies when ALL oracles fail |
| Idempotency Keys | `targets.py:15-27` | SHA256(item_id + price_cents)[:16] |
| Inventory Cap | `execution.py:213-256` | Cumulative tracking prevents intra-batch overspending |
| Circuit Breaker | `backoff.py` | 5 consecutive failures → circuit OPEN |

---

## API Endpoints

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Buy (instant) | PATCH | `/exchange/v1/offers-buy` |
| Sell (batch) | POST | `/marketplace-api/v2/offers:batchCreate` |
| Reprice (batch) | POST | `/marketplace-api/v2/offers:batchUpdate` |
| Cancel (batch) | POST | `/marketplace-api/v2/offers:batchDelete` |
| Market items | GET | `/exchange/v1/market/items` |
| User offers | GET | `/exchange/v1/user-offers` |
| User inventory | GET | `/exchange/v1/user-inventory` |

---

## Docker Deployment

- **Multi-stage build**: Builder (Rust + Python) → Runtime (~250 MB)
- **Architectures**: x86_64 + aarch64/ARM64
- **Health check**: `/healthz` on port 9091
- **Persistence**: Docker volumes for `data/` (SQLite) and `logs/`
- **Memory limits**: 512 MB (main), 256 MB (Telegram)

---

🦅 *DMarket Quantitative Engine | v16.2 | 2026-07-22*
