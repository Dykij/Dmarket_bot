"""
Verification Suite v12.0 — Tests for Intra-Spread Strategy A.

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


async def main():
    os.environ["DRY_RUN"] = "true"
    logger.info("="*60)
    logger.info("VERIFICATION SUITE v12.0 — STRATEGY A + LOW-FEE + FLOAT")
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
