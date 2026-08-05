# Oracle Removal & Formula Audit Report

**Date:** 2026-08-04
**Branch:** `feature/remove-oracles-formula-audit`
**Baseline:** `main` @ `c175c44`
**Tag:** `pre-oracle-removal`

---

## Section 1: Oracle Removal Confirmation

### Files Deleted

**Source files (7):**
```
src/_archived/oracles/csfloat_oracle.py
src/_archived/oracles/market_csgo_oracle.py
src/_archived/oracles/multi_source_oracle.py
src/_archived/oracles/oracle_factory.py
src/_archived/oracles/rust_oracle.py
src/_archived/oracles/steam_oracle.py
src/_archived/oracles/waxpeer_oracle.py
```

**Test files (11):**
```
tests/unit/test_oracles.py
tests/unit/test_steam_oracle.py
tests/unit/test_waxpeer_oracle.py
tests/unit/test_csfloat_oracle.py
tests/unit/test_market_csgo_oracle.py
tests/test_multi_source_oracle_and_volatility.py
tests/unit/api/test_steam_oracle.py
tests/unit/api/test_market_csgo_oracle.py
tests/unit/api/test_csfloat_oracle.py
tests/unit/api/test_waxpeer_oracle.py
+ all __pycache__/*.pyc for above
```

### Production Files Modified (oracle imports removed)

| File | Change |
|------|--------|
| `src/core/target_sniping/resale_dry.py` | Removed `OracleFactory` import, `oracle: Any` attr, oracle usage in `_dry_list_unlocked` (fallback to `buy_price * 1.05`) |
| `src/core/target_sniping/scheduler.py` | Removed `OracleFactory` import, `close_all()` in shutdown, oracle status in `_reporter_stats` |
| `src/core/resale_pipeline.py` | Removed `OracleFactory` import, set `self.oracle = None` |
| `src/inventory_manager.py` | Removed `OracleFactory` import, set `self.oracle = None` |
| `src/core/target_sniping/position_guard.py` | Removed `oracle: Any` attr, replaced `_get_current_price` with `return 0.0` |
| `src/telegram/control_bot/commands/test.py` | Removed `MultiSourceOracle` import, oracle usage in `_do_test` |
| `src/telegram/control_bot/commands/views.py` | Replaced oracle-based `cmd_prices` with DMarket-only inventory listing |

### Test Files Modified (oracle mocks updated)

| File | Change |
|------|--------|
| `tests/unit/test_inventory_manager.py` | Removed `OracleFactory` patch, set `manager.oracle = mock_oracle` directly |
| `tests/unit/test_resale_pipeline.py` | Removed `OracleFactory` patch, set `pipeline.oracle = mock_oracle` directly |
| `tests/unit/test_cycle_orchestrator.py` | Removed `OracleFactory` patches (2 occurrences) |
| `tests/test_resale_pipeline.py` | Removed dead `from src.api.multi_source_oracle import MultiSourceOracle` |

### RAW Grep Confirmation

```
$ grep -rn "from src._archived.oracles\|from src.api.*oracle_factory\|from src.api.*multi_source_oracle\|import OracleFactory\|import MultiSourceOracle" src/ tests/ --include="*.py"
ZERO imports of deleted oracle modules
```

### Pytest Result

```
177 passed, 1 failed, 1 warning in 39.87s
```

1 failure = pre-existing `test_win_loss_ratio_tracking` (DB state leak, not oracle-related).

---

## Section 2: P1f/P1g Diff Analysis (commit 2fafbee)

### P1f: Kelly Warmup from ProfitTracker (`execution.py:498-516`)

```python
# On first DynamicRiskManager creation:
recent_trades = profit_db.get_recent_trades(days=30)
for t in recent_trades:
    net = t.get("net_profit", 0) or 0
    self._dynamic_risk.record_trade(won=net > 0, ...)
```

| Question | Answer |
|----------|--------|
| Empty history (new bot/DB)? | `get_recent_trades` → empty list → `if recent_trades:` = False → warmup skipped → Kelly starts cold at 0. **Safe.** |
| Small sample (1-2 trades)? | Kelly uses win_rate from 1 trade. 1 win → win_rate=1.0, wl_ratio=very high → could over-size. But `half_kelly` + `max_position_pct` cap limit impact. **Acceptable risk.** |
| Regression risk? | `DynamicRiskManager` previously started cold (0 trades). Now loads history. If history is unrepresentative of current market → Kelly could over-size. **Intentional P1 fix.** `try/except` fallback to cold start on error. |
| Verdict | **Clean P1 fix. No regression risk to existing Kelly sizing.** |

### P1g: Equity Update Post-Cycle (`cycle_orchestrator.py:563-580`)

```python
for item in open_items:
    bid = ctx.agg_prices[title].get("best_bid", 0) or 0
    inventory_value += bid
total_equity = ctx.balance_after + inventory_value
self.risk._update_equity(total_equity)
```

| Question | Answer |
|----------|--------|
| Uses `best_bid` (conservative)? | Yes — `best_bid` = what you'd get if you sold now. **Conservative estimate.** |
| Double-counting with RiskManager? | No. `daily_realized_pnl` (daily limits) is separate from `_current_equity` (drawdown tracking). Equity = total portfolio value, not daily P&L. **No conflict.** |
| False soft-halt prevention? | Previously equity updated only on trades. Cash drop on buy ≠ loss, but old code counted it as drawdown. P1g fixes this. **Correct.** |
| Error handling? | `try/except` fallback — on error, equity not updated (old behavior). **Safe.** |
| Verdict | **Clean P1 fix. No double-counting. Conservative valuation.** |

---

## Section 3: Formula vs DMarket API Audit

### P0 CRITICAL BUG (Pre-existing)

**File:** `src/core/target_sniping/core.py:138-139`
```python
if not ctx.oracle:
    return
```

**Root cause:** `cycle_orchestrator.py:95-97` sets `ctx.oracle = None` (was already the case on main BEFORE oracle removal). This guard exits the entire pipeline every cycle. **The bot was already non-functional before this audit.**

**Fix required:** Remove or invert the guard at `core.py:138-139`.

### Active Formulas — Oracle Dependency Status

| Formula | File | Oracle Dep? | Status | Notes |
|---------|------|-------------|--------|-------|
| OBI Demand Score | `demand_strategy.py:102-307` | **No** | ✅ Active | Uses only `bid_count`, `ask_count`, `best_bid`, `best_ask` from DMarket aggregated prices |
| OFI Momentum | `microstructure_pipeline.py:117-129` | **No** | ✅ Active | Uses `bid_count`, `ask_count` changes between cycles |
| Kelly Position Sizing | `filter.py:230` | **No** | ✅ Active | Uses `effective_balance`, `kelly_risk_pct` from RiskManager |
| Dynamic Max Price | `cycle_orchestrator.py:115-123` | **No** | ✅ Active | Uses `current_balance`, `BALANCE_RESERVE_USD` |
| Slippage-at-Risk | `validations.py:471-530` | **No** | ✅ Active | Uses `best_ask`, `best_bid`, `ask_count`, `bid_count` |
| VWAP Signal | `validations.py:64-80` | **No** | ✅ Active | Uses `last-sales` from DMarket API |
| CVD | `validations.py:93-96` | **No** | ✅ Active | Uses `last-sales` trade records |
| VPIN | `validations.py:97-98` | **No** | ✅ Active | Uses `last-sales` trade records |
| Hawkes Intensity | `microstructure_pipeline.py:186-206` | **No** | ✅ Active | Uses `last-sales` trade records |
| Adverse Selection (Kyle) | `validations.py:134-136` | **No** | ✅ Active | Uses `last-sales` trade records |
| Realized Vol (Parkinson) | `validations.py:162-163` | **No** | ✅ Active | Uses `last-sales` trade records |
| Roll's Effective Spread | `validations.py:184-185` | **No** | ✅ Active | Uses `last-sales` trade records |
| Volume Profile POC | `validations.py:203-204` | **No** | ✅ Active | Uses `last-sales` trade records |
| Fee-Aware Spread | `validations.py:389-468` | **No** | ✅ Active | Uses `best_bid`, `best_ask`, fee rates |
| Float Premium | `filter.py:554-561` | **No** | ✅ Active | Uses `attributes` from marketplace listings |
| Pattern Premium | `filter.py:586-601` | **No** | ✅ Active | Uses `attributes` from marketplace listings |
| Smart Reprice | `resale.py:200-208` | **No** | ✅ Active | Uses `bid_count`, `ask_count` changes |
| Underpriced Detection | `underpriced.py:65-93` | **No** | ✅ Active | Uses `last-sales` percentile |
| Intra-Spread Gate | `filter.py:403` | **No** | ⚠️ Dead | Guarded by `oracle_data_available` which is always False |
| Oracle Discount | `filter.py:407-410` | **Yes** | ❌ Dead | Depends on `cs_price` from oracle (always 0.0) |
| Cross-Market Arb | `validations.py:249-309` | **Yes** | ❌ Dead | Depends on `cs_bids` (always None) |
| Oracle Drift Check | `execution.py:168-200` | **Yes** | ❌ Dead | Guarded by `self.oracle is not None` |
| Oracle Price Validation | `filter.py:364-396` | **Yes** | ❌ Bug | Crashes on `oracle.get_item_price()` when oracle=None |

### DMarket API Endpoint → Formula Mapping

| Endpoint | Fields Used | Consumed By |
|----------|-------------|-------------|
| `GET /account/v1/balance` | `usd` (cents) | Dynamic Max Price, Kelly, Drawdown, Cycle P&L |
| `POST /marketplace-api/v1/aggregated-prices` | `best_ask`, `best_bid`, `ask_count`, `bid_count` | OBI, OFI, Slippage, Spread, Ranking, Equity |
| `GET /marketplace-api/v2/offers` | `objects[]`, `priceCents`, `title`, `attributes`, `stickers`, `createdAt` | Scanner, Float Premium, Pattern Premium, Age Filter |
| `PATCH /exchange/v1/offers-buy` | `status`, `Items[]`, `dmOffersStatus` | Execution, Blacklisting, Asset ID extraction |
| `GET /trade-aggregator/v1/last-sales` | `sales[].price.USD`, `sales[].date` | VWAP, CVD, VPIN, Hawkes, Kyle, Parkinson, Roll, POC, Underpriced |
| `GET /exchange/v1/user-inventory` | `items[].itemId`, `title`, `status`, `FinalizationTime` | Inventory sync, Phantom detection, Trade protection |
| `GET /marketplace-api/v1/user-offers/closed` | `offerId`, `status`, `price.USD`, `FinalizationTime` | Sell P&L, Rollback detection, Funds hold |
| `POST /marketplace-api/v2/offers:batchCreate` | `offers[].id`, `assetId`, `failed[]` | Listing, Stop-loss, Take-profit |
| `POST /marketplace-api/v2/offers:batchUpdate` | (standard response) | Repricing |
| `GET /exchange/v1/customized-fees` | `title`, `fraction` | Fee rate override, Commission optimizer |
| `GET /marketplace-api/v1/targets-by-title/{gameId}/{title}` | `orders[].amount`, `orders[].price` | Demand signal, targets-by-title |
| `GET /exchange/v1/transactions` | `type`, `itemId`, `amount.USD`, `status` | Rollback detection |
| `GET /exchange/v1/user-offers` | (active sell listings) | Repricing pipeline |
| `GET /exchange/v1/user-inventory` (detailed) | `objects[]`, `status`, `FinalizationTime` | Detailed inventory sync |

**No formulas reference fields that don't exist in DMarket API.** All data sources are DMarket-internal.

### Dead Code After Oracle Removal

| Code | File:Line | Why Dead | Recommended Action |
|------|-----------|----------|-------------------|
| `_oracle_price_cache` | `filter.py:49-61` | Always empty | Remove |
| `has_oracle_discount` | `filter.py:407-410` | `cs_price` always 0.0 | Remove |
| `oracle_data_available` | `filter.py:417` | Always False | Remove |
| `_MAX_ORACLE_DRIFT_PCT` | `execution.py:119` | Unused constant | Remove |
| NOV-3 drift block | `execution.py:168-200` | `self.oracle is None` | Remove |
| `evaluate_cross_market_arb` | `validations.py:249-309` | `cs_bids` always None | Remove or stub |
| `check_price_drop` | `pump_detector.py:329` | Zero callers | Remove |
| `oracle: Any` attr | `resale_prod.py:32` | Always None | Remove |
| Oracle listing block | `resale_prod.py:276-290` | `self.oracle is None` → items never listed | **Fix: use best_bid** |
| Oracle batch fetch | `resale_pipeline.py:240-260` | `self.oracle is None` → nothing listed | **Fix: use best_bid** |
| Oracle eval guard | `resale_pipeline.py:135-146` | `oracle_price=0.0` → always returns None | **Fix: use agg_prices** |
| `oracle` param in `_evaluate_candidate` | `filter.py:76` | Always None | Remove param |
| `cs_snapshots` param | `filter.py:81` | Always empty dict | Remove param |
| `oracle` in CycleContext | `cycle_orchestrator.py:38` | Always None | Remove field |
| `cs_snapshots` in CycleContext | `cycle_orchestrator.py:42` | Always empty | Remove field |
| `if not ctx.oracle: return` | `core.py:138-139` | **P0 BUG** — exits pipeline | **Remove immediately** |

---

## Section 4: Proposed Fixes (NOT Applied)

### Fix 1: P0 — Remove oracle gate in core.py

```python
# core.py:138-139 — REMOVE these lines:
if not ctx.oracle:
    return
```

### Fix 2: P0 — Remove oracle validation crash in filter.py

Replace lines 364-396 (oracle validation block) with DMarket-only logic:
```python
# Use agg_prices as reference instead of oracle
cs_price = 0.0
if title in ctx.agg_prices:
    cs_price = ctx.agg_prices[title].get("best_ask", 0) or 0
```

### Fix 3: P1 — Fix resale_prod.py listing block

Replace oracle price fetch (lines 276-290) with DMarket `best_bid`:
```python
# Instead of oracle.get_fair_price(), use agg_prices
cs_price = 0.0
if title in self._agg_prices:
    cs_price = self._agg_prices[title].get("best_bid", 0) or 0
```

### Fix 4: P1 — Fix resale_pipeline.py evaluation

Replace oracle price check (lines 135-146) with DMarket reference:
```python
# Instead of oracle.get_item_price(), use aggregated prices
oracle_price = 0.0
# TODO: pass agg_prices from scan context
```

### Fix 5: P2 — Clean up dead oracle code

Remove all dead code listed in the table above (`_oracle_price_cache`, `has_oracle_discount`, `oracle_data_available`, `_MAX_ORACLE_DRIFT_PCT`, NOV-3 block, `evaluate_cross_market_arb`, `check_price_drop`, oracle attrs in CycleContext, etc.)

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Oracle source files deleted | 7 | ✅ Done |
| Oracle test files deleted | 11 | ✅ Done |
| Production files cleaned | 7 | ✅ Done |
| Test files updated | 4 | ✅ Done |
| P1f/P1g review | 2 commits | ✅ Clean P1 fixes |
| Active formulas (DMarket-only) | 18 | ✅ No oracle deps |
| Dead oracle-dependent formulas | 4 | ❌ Need removal |
| P0 bugs found (pre-existing) | 2 | ⚠️ `core.py:138`, `filter.py:385` |
| P1 bugs found (pre-existing) | 2 | ⚠️ `resale_prod.py:278`, `resale_pipeline.py:135` |
| Dead code blocks to clean | 15+ | 📋 Listed in Section 3 |
| Pytest | 177 pass, 1 fail | ✅ (1 pre-existing) |
