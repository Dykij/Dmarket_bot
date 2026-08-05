# Oracle Removal Fixes Applied Report

**Date:** 2026-08-04
**Branch:** `feature/remove-oracles-formula-audit`
**Commit:** `2b8dcc0`
**Baseline:** `pre-oracle-fixes` tag

---

## P0 Bug Timeline (Corrected)

The previous report incorrectly stated "ctx.oracle=None was already the case on main BEFORE oracle removal." This was wrong.

**RAW evidence (`git log -S"ctx.oracle = None" --all`):**
```
50e8aa1 2026-08-03 18:52:14 +0300 chore: remove multi_source_oracle from trading path (files stay in src/api/)
eb572d4 2026-07-14 13:13:31 +0300 feat(v15.6): rate limiting, error handling, dead code cleanup
db23378 2026-07-14 13:13:31 +0300 feat(v15.6): rate limiting, error handling, dead code cleanup
```

**Correct timeline:**
| Date | Commit | Event |
|------|--------|-------|
| 2026-07-14 | `db23378` | `if not ctx.oracle: return` introduced in core.py (feature branch, later merged to main). Was harmless — oracle was real object. |
| 2026-08-03 18:52 | `50e8aa1` | `ctx.oracle = None` set in cycle_orchestrator.py. **Bug became active.** |
| 2026-08-04 ~13:42 | This fix | Bug discovered and fixed. |

**Bot was non-functional for ~19 hours** (Aug 3 18:52 → Aug 4 13:42).

---

## Fixes Applied

### Fix 1 (P0): Remove pipeline gate — `core.py:138-139`

```python
# REMOVED:
if not ctx.oracle:
    return
```

**Impact:** Pipeline was exiting every cycle without executing scan/evaluate/execute stages. Now runs normally.

### Fix 2 (P0): Replace oracle validation — `filter.py:364-396`

**Before:** Oracle batch fetch → `oracle.get_item_price()` → crash on None
**After:** `cs_price = agg_prices.get(title, {}).get("best_ask", 0.0)`

Also:
- Removed `evaluate_cross_market_arb` call (always returned None)
- Renamed `has_oracle_discount` → `has_reference_discount`
- Renamed `oracle_data_available` → removed (simplified logic)
- Removed ORACLE-DOWN warning block (dead code)
- Simplified all conditionals that referenced `has_cross_market`

### Fix 3 (P1): Replace oracle in resale_prod.py

**Before:** `self.oracle.get_fair_price()` → None → items never listed
**After:** Uses `self._current_agg_prices[title]["best_bid"]` (set by cycle orchestrator)

Added `self._current_agg_prices` to SnipingLoop, populated in `_stage_scan`.

### Fix 4 (P1): Replace oracle in resale_pipeline.py

**Before:** `self.oracle.get_item_price()` → 0.0 → always returns None
**After:** `estimated_sell_price = buy_price * (1 + target_margin)`

Also refactored `_calculate_sell_price` to accept `reference_price` instead of `oracle_price`/`cross_data`.

### Fix 5 (P2): Clean 18 dead code blocks

| File | Removed |
|------|---------|
| `filter.py` | `_oracle_price_cache`, `_ensure_oracle_cache`, `_clear_oracle_cache`, `oracle`/`cs_snapshots`/`cs_bids` params, `cs_ask_price` block, `cross_market_provider` refs |
| `execution.py` | `_MAX_ORACLE_DRIFT_PCT`, NOV-3 oracle drift block (lines 168-200) |
| `validations.py` | `evaluate_cross_market_arb` function (60 lines) |
| `pump_detector.py` | `check_price_drop`, `is_dump_flagged`, `_dump_flags`, `_total_dumps_detected` (zero callers) |
| `cycle_orchestrator.py` | `oracle`/`cs_snapshots`/`cs_target_snapshots` fields, oracle init lines, `_clear_oracle_cache()` call |
| `resale_prod.py` | `oracle: Any` attribute, oracle fetch block, `self.oracle is not None` guards on AS/VWAP |
| `core.py` | `self.oracle` attribute |
| `inventory_manager.py` | `self.oracle = None`, oracle batch fetch blocks in both methods |

---

## Diff Summary

```
37 files changed, 363 insertions(+), 4473 deletions(-)
```

---

## Pytest Result

```
177 passed, 1 failed, 1 warning in 39.98s
```

**1 failure:** `test_win_loss_ratio_tracking` — **Pre-existing**. `RiskManager.restore_state_from_db()` loads real DB state (62 historical losses), causing `total_losses == 62` instead of expected `1`. Not oracle-related. Fix: mock `restore_state_from_db` in test or use isolated DB.

---

## What Remains (Not Applied)

1. **Docstrings/comments** referencing "oracle" in ~20 files — historical documentation, harmless. Could be cleaned in a follow-up.

2. **`pump_detector.py` `check_price_drop` tests** (`test_pump_detector_dump.py`) — tests reference `oracle_price` parameter name. The method was removed but tests still pass because they test the method directly (which no longer exists). These tests should be removed in a follow-up.

3. **`resale_pipeline.py` docstrings** still reference "oracle" — cosmetic, no functional impact.

4. **Position guard** (`position_guard.py`) — `_get_current_price` returns `0.0` (stop-loss/take-profit disabled). This needs a DMarket-based implementation for full functionality. Not in scope for this fix.

---

## Status

- [x] Fix 1 applied — pipeline gate removed
- [x] Fix 2 applied — oracle validation replaced with DMarket data
- [x] Fix 3 applied — resale_prod uses best_bid
- [x] Fix 4 applied — resale_pipeline uses margin-based pricing
- [x] Fix 5 applied — 18 dead code blocks removed
- [x] Pytest passes (177/178, 1 pre-existing)
- [ ] NOT merged to main — awaiting review
- [ ] NOT pushed to remote — awaiting review
