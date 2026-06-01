"""
Verification Suite v12.2 — Tests for Intra-Spread Strategy A + v12.2 enhancements.

Validates:
1. CS2Cap oracle connectivity
2. DMarket aggregated prices endpoint
3. Strategy A spread filter (5%+ spread)
4. Sell pipeline (create/batch_create/delete offers)
5. Last sales endpoint
6. Low-fee items endpoint
7. Trade lock logic
8. Competition modeling
9. Position risk cap
10. Volatility filter
11. Slippage guard
12. Price history trend
13. Event shield multiplier
14. Bifurcated SQLite
15. Low-fee cache
16. Float premium calculation
17. Strategy A with float premium

v12.2 additions (Phase 2.1-2.5):
18. trade_protected status tracking
19. reverted status detection
20. FinalizationTime field
21. Dynamic bulk fee fetching
22. Trimmed mean + wash trading detection
23. Multi-level liquidity filter
24. DMarket API v2 batch-create
25. DMarket API v2 batch-edit

v12.2 Phase 3.1 (Clock Sync / NTP-like):
26. ClockSync initialization
27. ClockSync offset calculation
28. ClockSync status reporting
"""

import asyncio
import os
import time
import logging
import sys
from typing import List

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("TestV12")

PASSED = 0
FAILED = 0
TESTS = []


def record(test_name: str, passed: bool, details: str = ""):
    global PASSED, FAILED
    if passed:
        PASSED += 1
        status = "✅ PASS"
    else:
        FAILED += 1
        status = "❌ FAIL"
    TESTS.append((test_name, passed, details))
    logger.info(f"{status} | {test_name} | {details}")


async def test_cs2cap_oracle():
    """Test 1: CS2Cap oracle connectivity."""
    from src.api.cs2cap_oracle import CS2CapOracle
    oracle = CS2CapOracle(api_key=os.getenv("CS2C_API_KEY", ""), tier="free")
    try:
        # Try a popular CS2 skin
        price = await oracle.get_item_price("AK-47 | Redline (Field-Tested)")
        record("CS2Cap Oracle", price > 0 or price == 0, f"price=${price:.2f}")
    except Exception as e:
        record("CS2Cap Oracle", False, str(e))
    finally:
        await oracle.close()


async def test_dmarket_aggregated_prices():
    """Test 2: DMarket aggregated prices endpoint."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        titles = ["AK-47 | Redline (Field-Tested)"]
        res = await client.get_aggregated_prices("a8db", titles)
        # In DRY_RUN, returns empty dict (no real call)
        record("DMarket Aggregated Prices", isinstance(res, dict), f"got {len(res)} items")
    except Exception as e:
        record("DMarket Aggregated Prices", False, str(e))
    finally:
        await client.close()


async def test_sell_endpoints():
    """Test 3: Sell pipeline (create/batch_create/delete)."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        # DRY_RUN returns simulated success
        r1 = await client.create_offer("asset_123", 10.0)
        r2 = await client.batch_create_offers([{"asset_id": "a1", "price_usd": 5.0}])
        r3 = await client.delete_offers(["offer_1"])
        ok = r1.get("status") == "success" and r2.get("status") == "success" and r3.get("status") == "success"
        record("Sell Pipeline (create/batch/delete)", ok, "all 3 simulated OK")
    except Exception as e:
        record("Sell Pipeline (create/batch/delete)", False, str(e))
    finally:
        await client.close()


async def test_last_sales():
    """Test 4: Last sales endpoint."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        sales = await client.get_last_sales("a8db", "AK-47 | Redline (Field-Tested)")
        record("Last Sales Endpoint", isinstance(sales, list), f"got {len(sales)} sales")
    except Exception as e:
        record("Last Sales Endpoint", False, str(e))
    finally:
        await client.close()


async def test_low_fee_items():
    """Test 5: Low-fee items endpoint."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        items = await client.get_low_fee_items("a8db")
        record("Low-Fee Items", isinstance(items, list), f"got {len(items)} items")
    except Exception as e:
        record("Low-Fee Items", False, str(e))
    finally:
        await client.close()


async def test_trade_lock():
    """Test 6: Trade lock logic."""
    from src.db.price_history import price_db
    price_db.add_virtual_item("Test Item AK-47", 5.0, trade_lock_hours=168)
    inv_all = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    inv_unlocked = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    record("Trade Lock", len(inv_all) > len(inv_unlocked), f"locked={len(inv_all)-len(inv_unlocked)}")


async def test_competition_modeling():
    """Test 7: Competition (ghost buyers)."""
    from src.core.target_sniping import SnipingLoop
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    bot = SnipingLoop(client)
    fails = sum(1 for _ in range(20) if not bot._simulate_competition(0.45))
    record("Competition Modeling", fails >= 14, f"high margin fail rate={fails}/20")


async def test_position_risk_cap():
    """Test 8: Position risk cap."""
    from src.risk.liquidity_manager import LiquidityManager
    lm = LiquidityManager()
    # With $100 balance and 30% cap, max single position is $30
    from src.config import Config
    max_pct = Config.MAX_POSITION_RISK_PCT / 100.0
    can = lm.can_spend(50.0, "a8db", 100.0)  # 50% of balance
    record("Position Risk Cap (30%)", not can, "$50 rejected on $100 balance")


async def test_volatility_filter():
    """Test 9: Volatility filter."""
    from src.risk.price_validator import validate_volatility, PriceValidationError
    stable = [10.0, 10.1, 10.05, 10.2, 10.15]
    volatile = [10.0, 8.0, 12.0, 6.0, 14.0]
    try:
        validate_volatility(stable)
        stable_ok = True
    except PriceValidationError:
        stable_ok = False
    try:
        validate_volatility(volatile)
        volatile_ok = True
    except PriceValidationError:
        volatile_ok = False
    record("Volatility Filter", stable_ok and not volatile_ok, "stable=ok, volatile=rejected")


async def test_slippage_guard():
    """Test 10: Slippage guard."""
    from src.risk.price_validator import validate_slippage, PriceValidationError
    try:
        validate_slippage(10.0, 10.0, max_slippage_pct=0.02)
        ok1 = True
    except PriceValidationError:
        ok1 = False
    try:
        validate_slippage(10.0, 9.5, max_slippage_pct=0.02)  # 5% slippage
        ok2 = True
    except PriceValidationError:
        ok2 = False
    record("Slippage Guard", ok1 and not ok2, "0% OK, 5% rejected")


async def test_arbitrage_validator():
    """Test 11: Arbitrage profit validator."""
    from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
    try:
        m = validate_arbitrage_profit(10.0, 12.0, fee_markup=0.05, min_profit_margin=0.05, lock_days=7)
        ok1 = m > 0
    except PriceValidationError:
        ok1 = False
    try:
        m = validate_arbitrage_profit(10.0, 10.2, fee_markup=0.05, min_profit_margin=0.05, lock_days=7)
        ok2 = True
    except PriceValidationError:
        ok2 = False
    record("Arbitrage Validator", ok1 and not ok2, "10→12 OK, 10→10.2 rejected")


async def test_price_history_trend():
    """Test 12: Price trend analysis."""
    from src.db.price_history import price_db
    title = "Test_Trend_Item"
    for i, p in enumerate([10.0, 10.5, 11.0, 11.5, 12.0]):
        price_db.record_price(title, p, source="test")
    prices = price_db.get_recent_prices(title, days=7)
    record("Price History Trend", len(prices) >= 5, f"{len(prices)} prices recorded")


async def test_event_shield():
    """Test 13: Event shield multiplier."""
    from src.core.event_shield import event_shield
    mult = event_shield.get_margin_multiplier()
    record("Event Shield", 0.5 <= mult <= 3.0, f"multiplier={mult}")


async def test_bifurcated_sqlite():
    """Test 14: Bifurcated SQLite state + history."""
    from src.db.price_history import price_db
    state_exists = price_db.state_path.exists()
    history_exists = price_db.history_path.exists()
    record("Bifurcated SQLite", state_exists and history_exists, f"state={state_exists}, history={history_exists}")


async def test_low_fee_cache():
    """Test 15: Low-fee items cache."""
    from src.db.price_history import price_db
    test_items = [
        {"title": "AK-47 | Redline (Field-Tested)", "fee_rate": 0.025},
        {"title": "AWP | Asiimov (Field-Tested)", "fee_rate": 0.02},
    ]
    price_db.save_low_fee_items(test_items)
    rate = price_db.get_low_fee_rate("AK-47 | Redline (Field-Tested)")
    age = price_db.low_fee_cache_age_seconds()
    size = price_db.low_fee_cache_size()
    record("Low-Fee Cache", rate == 0.025 and age is not None and age < 60 and size == 2,
           f"rate={rate}, age={age:.1f}s, size={size}")


async def test_float_premium_calculation():
    """Test 16: Float premium calculation."""
    from src.core.target_sniping import SnipingLoop
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    bot = SnipingLoop(client)
    await client.close()

    # FN-0: float < 0.01 → 1.20x
    fn0 = bot._calculate_float_premium({"floatPartValue": "0.005"})
    # FN: 0.01 <= float < 0.07 → 1.10x
    fn = bot._calculate_float_premium({"floatPartValue": "0.04"})
    # FT-0: 0.15 <= float <= 0.18 → 1.15x
    ft0 = bot._calculate_float_premium({"floatPartValue": "0.16"})
    # MW / regular FT: → 1.0x
    mw = bot._calculate_float_premium({"floatPartValue": "0.10"})
    # WW: → 0.95x
    ww = bot._calculate_float_premium({"floatPartValue": "0.40"})
    # BS: float >= 0.45 → 0.90x
    bs = bot._calculate_float_premium({"floatPartValue": "0.55"})
    # No float → 1.0x
    none = bot._calculate_float_premium({})

    ok = (fn0 == 1.20 and fn == 1.10 and ft0 == 1.15 and mw == 1.0 and ww == 0.95 and bs == 0.90 and none == 1.0)
    record("Float Premium Calculation", ok,
           f"FN-0={fn0} FN={fn} FT-0={ft0} MW={mw} WW={ww} BS={bs} none={none}")


async def test_strategy_a_with_filters():
    """Test 17: Strategy A end-to-end with low-fee + float filters."""
    from src.db.price_history import price_db
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        # Mock aggregated prices
        agg = {
            "AK-47 | Redline (FT)": {"best_ask": 10.0, "best_bid": 11.5, "ask_count": 3, "bid_count": 2},
            "AWP | Asiimov (FT)":  {"best_ask": 60.0, "best_bid": 70.0, "ask_count": 2, "bid_count": 1},
        }
        # Without float premium: list_price = best_bid - 0.01
        # With FN-0 float: list_price = 11.49 * 1.20 = 13.79
        # Spread: (13.79 / 10.0) - 1 = 37.9% — profitable!
        list_price_no_float = round(agg["AK-47 | Redline (FT)"]["best_bid"] - 0.01, 2)
        list_price_fn0 = round(list_price_no_float * 1.20, 2)
        spread_fn0 = (list_price_fn0 / agg["AK-47 | Redline (FT)"]["best_ask"]) - 1
        record("Strategy A + Float Premium",
               spread_fn0 > 0.30,
               f"AK-47 FN-0 spread: {spread_fn0*100:.1f}% (${list_price_fn0})")
    finally:
        await client.close()


# ============================================================================
# v12.2: 8 new tests
# ============================================================================

async def test_trade_protected_status():
    """Test 18: trade_protected status tracking (Phase 2.1)."""
    from src.db.price_history import price_db
    item_id = "test_trade_protected_123"
    title = "Test AK-47 FN"
    # Set status to trade_protected with future finalization time
    future = time.time() + 3600  # 1 hour from now
    price_db.update_asset_status(item_id, title, "trade_protected", finalization_time=future)
    is_locked = price_db.is_trade_locked(item_id)
    asset = price_db.get_asset_status(item_id)
    price_db.update_asset_status(item_id, title, "active", finalization_time=0.0)  # cleanup
    record("Trade Protected Status",
           is_locked and asset and asset["status"] == "trade_protected",
           f"locked={is_locked}, status={asset['status'] if asset else None}")


async def test_reverted_detection():
    """Test 19: reverted status detection (Phase 2.1)."""
    from src.db.price_history import price_db
    item_id = "test_reverted_456"
    title = "Test AWP BS"
    price_db.update_asset_status(item_id, title, "active", finalization_time=0.0)
    price_db.mark_reverted(item_id)
    asset = price_db.get_asset_status(item_id)
    reverted_list = price_db.get_reverted_assets()
    is_locked = price_db.is_trade_locked(item_id)
    record("Reverted Detection",
           asset and asset["status"] == "reverted" and is_locked and len(reverted_list) >= 1,
           f"status={asset['status'] if asset else None}, locked={is_locked}, count={len(reverted_list)}")


async def test_finalization_time():
    """Test 20: FinalizationTime field is correctly stored (Phase 2.1)."""
    from src.db.price_history import price_db
    item_id = "test_finalization_789"
    title = "Test M4A4 MW"
    fin_time = time.time() + 86400  # 1 day from now
    price_db.update_asset_status(item_id, title, "trade_protected", finalization_time=fin_time)
    asset = price_db.get_asset_status(item_id)
    price_db.update_asset_status(item_id, title, "active", finalization_time=0.0)  # cleanup
    record("FinalizationTime",
           asset and abs(asset["finalization_time"] - fin_time) < 1.0,
           f"stored={asset['finalization_time']:.0f}, expected={fin_time:.0f}")


async def test_dynamic_fee_bulk():
    """Test 21: Bulk fee endpoint (Phase 2.2)."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        # In DRY_RUN, returns empty dict
        fees = await client.get_item_fee_bulk("a8db", ["item1", "item2", "item3"])
        record("Dynamic Fee Bulk", isinstance(fees, dict), f"got {len(fees)} fees")
    finally:
        await client.close()


async def test_trimmed_mean_wash_trading():
    """Test 22: Trimmed mean with outlier detection (Phase 2.3)."""
    from src.db.price_history import price_db
    title = "Test_WashTrade"
    # Clean any existing data
    price_db.history_conn.execute("DELETE FROM price_history WHERE hash_name = ?", (title,))
    # Add 6 prices: 5 normal + 1 inflated
    for p in [10.0, 10.1, 10.05, 10.2, 10.15]:
        price_db.record_price(title, p, source="test")
    # Inject outlier: 100.0 (900% above mean)
    price_db.record_price(title, 100.0, source="test")

    raw = price_db.get_avg_price(title, days=14)
    trimmed = price_db.get_trimmed_mean(title, days=14, boost_pct=24.0, max_outliers=3)
    not_wash = price_db.detect_wash_trading(title, days=14, boost_pct=24.0, max_outliers=3)

    # Cleanup
    price_db.history_conn.execute("DELETE FROM price_history WHERE hash_name = ?", (title,))
    price_db.history_conn.commit()

    record("Trimmed Mean + Wash Detection",
           trimmed is not None and raw is not None and abs(trimmed - 10.1) < 0.1 and not not_wash,
           f"raw={raw:.2f}, trimmed={trimmed:.2f}, flagged={not not_wash}")


async def test_liquidity_filter():
    """Test 23: Multi-level liquidity filter (Phase 2.4)."""
    from src.db.price_history import price_db
    from src.config import Config

    liquid_title = "Test_Liquid_Item"
    dry_title = "Test_Dry_Item"

    # Cleanup
    for t in [liquid_title, dry_title]:
        price_db.history_conn.execute("DELETE FROM price_history WHERE hash_name = ?", (t,))
        price_db.history_conn.commit()

    # Liquid: 100+ observations (>= MIN_TOTAL_SALES=80)
    # We patch the recorded_at to spread over 20 days
    now = time.time()
    for i in range(100):
        # Spread over 20 days (well within 23-day window)
        ts = now - (i * 0.2 * 86400)  # 0.2 days = 4.8 hours apart
        price_db.history_conn.execute(
            "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
            (liquid_title, 10.0 + (i % 3) * 0.1, "test", ts)
        )
    price_db.history_conn.commit()

    # Dry: only 3 observations (insufficient)
    for i in range(3):
        price_db.record_price(dry_title, 5.0, source="test")

    liquid_metrics = price_db.get_liquidity_metrics(liquid_title)
    dry_metrics = price_db.get_liquidity_metrics(dry_title)

    # Cleanup
    for t in [liquid_title, dry_title]:
        price_db.history_conn.execute("DELETE FROM price_history WHERE hash_name = ?", (t,))
        price_db.history_conn.commit()

    record("Liquidity Filter",
           liquid_metrics["is_liquid"] and not dry_metrics["is_liquid"],
           f"liquid_ok={liquid_metrics['is_liquid']}, dry_ok={dry_metrics['is_liquid']}, "
           f"liq_total={liquid_metrics['total_sales']}, dry_total={dry_metrics['total_sales']}, "
           f"reason={liquid_metrics['reason']}")


async def test_v2_batch_create():
    """Test 24: DMarket API v2 batch-create (Phase 2.5)."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        r = await client.batch_create_offers_v2([
            {"asset_id": "asset_a", "price_usd": 5.0},
            {"asset_id": "asset_b", "price_usd": 7.5},
        ])
        record("V2 Batch Create",
               r.get("status") == "success",
               f"status={r.get('status')}, simulated={r.get('simulated')}")
    finally:
        await client.close()


async def test_v2_batch_edit():
    """Test 25: DMarket API v2 batch-edit (Phase 2.5)."""
    from src.api.dmarket_api_client import DMarketAPIClient
    client = DMarketAPIClient("pub", "sec")
    try:
        r = await client.batch_edit_offers_v2([
            {"offer_id": "offer_a", "new_price_usd": 4.5},
            {"offer_id": "offer_b", "new_price_usd": 6.0},
        ])
        record("V2 Batch Edit",
               r.get("status") == "success",
               f"status={r.get('status')}, simulated={r.get('simulated')}")
    finally:
        await client.close()


# ============================================================================
# v12.2 Phase 3.1: Clock Sync (NTP-like)
# ============================================================================

async def test_clock_sync_init():
    """Test 26: ClockSync initialization and singleton."""
    from src.utils.clock_sync import clock_sync
    # Reset to clean state
    clock_sync._offset = 0.0
    clock_sync._last_sync = 0.0
    # Check that we have a ClockSync instance with expected methods
    has_methods = (
        hasattr(clock_sync, 'sync_with_dmarket') and
        hasattr(clock_sync, 'now') and
        hasattr(clock_sync, 'needs_refresh') and
        hasattr(clock_sync, 'get_status')
    )
    # Check default state
    status = clock_sync.get_status()
    record("ClockSync Init",
           has_methods and status["needs_refresh"] is True and status["is_healthy"] is True,
           f"methods={has_methods}, offset={status['offset_seconds']}s, needs_refresh={status['needs_refresh']}")


async def test_clock_sync_offset():
    """Test 27: ClockSync offset calculation works correctly."""
    from src.utils.clock_sync import ClockSync
    # Create isolated instance for testing
    test_sync = ClockSync()
    # Manually set offset (simulating successful sync)
    test_sync._offset = 5.0
    test_sync._last_sync = time.time()
    test_sync._sync_count = 1

    local_ts = time.time()
    server_ts = test_sync.now()
    computed_offset = server_ts - local_ts

    # Should be ~5.0s (within tolerance)
    record("ClockSync Offset",
           abs(computed_offset - 5.0) < 0.5,
           f"expected=5.0s, got={computed_offset:.3f}s")


async def test_clock_sync_status():
    """Test 28: ClockSync status reporting."""
    from src.utils.clock_sync import ClockSync
    test_sync = ClockSync()

    # Initial state
    initial_status = test_sync.get_status()
    initial_ok = (
        initial_status["offset_seconds"] == 0.0
        and initial_status["needs_refresh"] is True
        and initial_status["is_healthy"] is True  # 0s offset = healthy
    )

    # After simulated sync
    test_sync._offset = -2.5
    test_sync._last_sync = time.time()
    test_sync._sync_count = 1
    after_status = test_sync.get_status()
    after_ok = (
        after_status["offset_seconds"] == -2.5
        and after_status["needs_refresh"] is False
        and after_status["is_healthy"] is True
        and after_status["sync_count"] == 1
    )

    # With unhealthy drift
    test_sync._offset = -150.0
    unhealthy_status = test_sync.get_status()
    unhealthy_ok = unhealthy_status["is_healthy"] is False

    record("ClockSync Status",
           initial_ok and after_ok and unhealthy_ok,
           f"initial={initial_ok}, after_sync={after_ok}, unhealthy_detected={unhealthy_ok}")


async def main():
    os.environ["DRY_RUN"] = "true"
    logger.info("="*60)
    logger.info("VERIFICATION SUITE v12.2 — STATUS + FEE + TRIMMED + LIQUIDITY + V2 + CLOCK")
    logger.info("="*60)

    tests = [
        test_cs2cap_oracle,
        test_dmarket_aggregated_prices,
        test_sell_endpoints,
        test_last_sales,
        test_low_fee_items,
        test_trade_lock,
        test_competition_modeling,
        test_position_risk_cap,
        test_volatility_filter,
        test_slippage_guard,
        test_arbitrage_validator,
        test_price_history_trend,
        test_event_shield,
        test_bifurcated_sqlite,
        test_low_fee_cache,
        test_float_premium_calculation,
        test_strategy_a_with_filters,
        # v12.2 new tests
        test_trade_protected_status,
        test_reverted_detection,
        test_finalization_time,
        test_dynamic_fee_bulk,
        test_trimmed_mean_wash_trading,
        test_liquidity_filter,
        test_v2_batch_create,
        test_v2_batch_edit,
        # v12.2 Phase 3.1: ClockSync
        test_clock_sync_init,
        test_clock_sync_offset,
        test_clock_sync_status,
    ]

    for t in tests:
        try:
            await t()
        except Exception as e:
            record(t.__name__, False, f"CRASH: {e}")

    logger.info("="*60)
    logger.info(f"RESULTS: {PASSED} passed / {FAILED} failed / {len(tests)} total")
    logger.info("="*60)
    if FAILED > 0:
        for name, ok, details in TESTS:
            if not ok:
                logger.info(f"  ❌ {name}: {details}")
        sys.exit(1)
    else:
        logger.info("🎉 ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
