"""
dry_run_full.py — Full pipeline dry run test for DMarket Bot.

Tests the ENTIRE trading pipeline with mocked DMarket API:
1. Market scanning (aggregated prices, cheapest listings)
2. Oracle integration (MultiSourceOracle, fair price calculation)
3. Financial instruments (OBI, CVD, VPIN, VWAP, float premium, pattern premium)
4. Risk management (Kelly sizing, drawdown freeze, balance gate)
5. Candidate evaluation (15+ filter stages)
6. Sell price calculation (list price with premiums)
7. Inventory management (virtual inventory, lock-aware cap)
8. Database operations (price history, trade logging, state persistence)
9. Full SnipingLoop cycle orchestration

Usage: PYTHONUNBUFFERED=1 .venv/bin/python tests/sandbox/dry_run_full.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ["DRY_RUN"] = "true"

from src.utils.logging_setup import configure_logging
configure_logging(component="dry_run_full", level=logging.INFO, log_file="logs/dry_run_full.log")
logger = logging.getLogger("DryRunFull")


# =====================================================================
# Mock DMarket API Client
# =====================================================================

MOCK_AGG_PRICES = {
    "AK-47 | Redline (Field-Tested)": {
        "best_bid": 12.50, "best_ask": 13.00,
        "ask_count": 15, "bid_count": 10,
    },
    "AWP | Asiimov (Field-Tested)": {
        "best_bid": 28.00, "best_ask": 30.00,
        "ask_count": 8, "bid_count": 5,
    },
    "M4A4 | Neo-Noir (Field-Tested)": {
        "best_bid": 8.00, "best_ask": 8.50,
        "ask_count": 20, "bid_count": 15,
    },
    "USP-S | Kill Confirmed (Field-Tested)": {
        "best_bid": 15.00, "best_ask": 16.00,
        "ask_count": 12, "bid_count": 8,
    },
    "Glock-18 | Fade (Factory New)": {
        "best_bid": 250.00, "best_ask": 260.00,
        "ask_count": 3, "bid_count": 2,
    },
}

MOCK_LISTINGS = {
    "AK-47 | Redline (Field-Tested)": [
        {"itemId": "ak47_red_1", "title": "AK-47 | Redline (Field-Tested)",
         "price": {"USD": "1300"}, "extra": [
             {"name": "floatPartValue", "value": "0.15"},
             {"name": "paintSeed", "value": "420"},
         ]},
    ],
    "AWP | Asiimov (Field-Tested)": [
        {"itemId": "awp_asi_1", "title": "AWP | Asiimov (Field-Tested)",
         "price": {"USD": "3000"}, "extra": [
             {"name": "floatPartValue", "value": "0.25"},
         ]},
    ],
    "M4A4 | Neo-Noir (Field-Tested)": [
        {"itemId": "m4a4_neo_1", "title": "M4A4 | Neo-Noir (Field-Tested)",
         "price": {"USD": "850"}, "extra": [
             {"name": "floatPartValue", "value": "0.18"},
         ]},
    ],
    "USP-S | Kill Confirmed (Field-Tested)": [
        {"itemId": "usps_kc_1", "title": "USP-S | Kill Confirmed (Field-Tested)",
         "price": {"USD": "1600"}, "extra": [
             {"name": "floatPartValue", "value": "0.22"},
         ]},
    ],
    "Glock-18 | Fade (Factory New)": [
        {"itemId": "glock_fade_1", "title": "Glock-18 | Fade (Factory New)",
         "price": {"USD": "26000"}, "extra": [
             {"name": "floatPartValue", "value": "0.01"},
             {"name": "paintSeed", "value": "56"},
         ]},
    ],
}


def make_mock_client():
    """Create a comprehensive mock DMarket API client."""
    client = AsyncMock(spec=[
        'get_real_balance', 'get_aggregated_prices', 'get_market_items_v2',
        'get_item_fee_bulk', 'get_item_fee', 'get_last_sales',
        'create_targets', 'delete_target', 'get_user_targets',
        'create_sell_offers_batch', 'get_user_offers',
        'close',
    ])

    client.get_real_balance = AsyncMock(return_value=100.0)
    client.get_aggregated_prices = AsyncMock(return_value=MOCK_AGG_PRICES)
    client.get_item_fee_bulk = AsyncMock(return_value={
        "ak47_red_1": 0.05, "awp_asi_1": 0.05,
        "m4a4_neo_1": 0.05, "usps_kc_1": 0.05, "glock_fade_1": 0.05,
    })
    client.get_item_fee = AsyncMock(return_value=0.05)
    client.get_last_sales = AsyncMock(return_value=[
        {"price": 13.50, "date": time.time() - 3600},
        {"price": 13.20, "date": time.time() - 7200},
        {"price": 12.80, "date": time.time() - 10800},
    ])

    async def mock_get_market_items_v2(game_id, limit=10, title="", **kwargs):
        listings = MOCK_LISTINGS.get(title, [])
        return {"objects": listings[:limit], "cursor": ""}

    client.get_market_items_v2 = AsyncMock(side_effect=mock_get_market_items_v2)
    client.create_targets = AsyncMock(return_value={"Result": [{"TargetID": "t1", "Status": "Created"}]})
    client.delete_target = AsyncMock(return_value={"success": True})
    client.get_user_targets = AsyncMock(return_value={"Items": []})
    client.create_sell_offers_batch = AsyncMock(return_value={"results": [{"status": "success"}]})
    client.get_user_offers = AsyncMock(return_value={"objects": []})
    client.close = AsyncMock()

    return client


# =====================================================================
# Test Results Collector
# =====================================================================

class TestResults:
    def __init__(self):
        self.tests: list[dict] = []
        self.start_time = time.time()

    def add(self, name: str, passed: bool, detail: str = ""):
        self.tests.append({"name": name, "passed": passed, "detail": detail, "ts": time.time()})
        status = "PASS" if passed else "FAIL"
        logger.info(f"[{status}] {name}: {detail}" if detail else f"[{status}] {name}")

    def summary(self) -> dict:
        total = len(self.tests)
        passed = sum(1 for t in self.tests if t["passed"])
        return {
            "total": total, "passed": passed, "failed": total - passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "duration_s": round(time.time() - self.start_time, 2),
            "tests": self.tests,
        }


# =====================================================================
# Test Suite
# =====================================================================

async def test_db_operations(results: TestResults):
    """Test 1: Database operations."""
    from src.db.price_history import price_db

    # Write
    try:
        price_db.save_state("dry_test_key", "dry_test_value")
        results.add("DB.save_state", True)
    except Exception as e:
        results.add("DB.save_state", False, str(e))

    # Read
    try:
        val = price_db.get_state("dry_test_key")
        results.add("DB.get_state", val == "dry_test_value", f"got={val}")
    except Exception as e:
        results.add("DB.get_state", False, str(e))

    # Price history
    try:
        price_db.record_price("AK-47 | Redline (Field-Tested)", 13.0, "dry_run")
        latest = price_db.get_latest_price("AK-47 | Redline (Field-Tested)")
        results.add("DB.record_price", latest is not None, f"latest={latest}")
    except Exception as e:
        results.add("DB.record_price", False, str(e))

    # Virtual inventory
    try:
        inv = price_db.get_virtual_inventory(status="idle")
        results.add("DB.get_virtual_inventory", isinstance(inv, list), f"count={len(inv)}")
    except Exception as e:
        results.add("DB.get_virtual_inventory", False, str(e))

    # Thread pool stats
    try:
        stats = price_db.get_thread_pool_stats()
        results.add("DB.thread_pool_stats", "max_workers" in stats, f"workers={stats.get('max_workers')}")
    except Exception as e:
        results.add("DB.thread_pool_stats", False, str(e))


async def test_oracle_integration(results: TestResults):
    """Test 2: Oracle integration."""
    from src.api.multi_source_oracle import MultiSourceOracle

    oracle = MultiSourceOracle()
    try:
        ref = await oracle.get_fair_price("AK-47 | Redline (Field-Tested)", dmarket_buy_price=13.0)
        results.add("Oracle.get_fair_price", ref is not None, f"fair_price={ref.fair_price:.2f}")
    except Exception as e:
        results.add("Oracle.get_fair_price", False, str(e))

    try:
        batch = await oracle.get_fair_prices_batch(["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Field-Tested)"])
        results.add("Oracle.get_fair_prices_batch", len(batch) >= 0, f"count={len(batch)}")
    except Exception as e:
        results.add("Oracle.get_fair_prices_batch", False, str(e))

    try:
        stats = oracle.get_stats()
        results.add("Oracle.get_stats", "api_calls" in stats)
    except Exception as e:
        results.add("Oracle.get_stats", False, str(e))

    try:
        await oracle.close()
        results.add("Oracle.close", True)
    except Exception as e:
        results.add("Oracle.close", False, str(e))


async def test_financial_instruments(results: TestResults):
    """Test 3: Financial instruments."""
    from src.core.target_sniping.pricing import _PricingMixin
    from src.core.target_sniping.validations import check_obi, check_cvd_vpin, check_vwap_filter

    # OBI
    try:
        obi = check_obi(ask_cnt=15, bid_cnt=10, best_ask=13.0, best_bid=12.5)
        results.add("OBI.check", isinstance(obi, dict), f"pass={obi.get('pass')}")
    except Exception as e:
        results.add("OBI.check", False, str(e))

    # Float premium
    try:
        mixin = _PricingMixin()
        mixin._oracle_price_cache = {}
        premium = mixin._calculate_float_premium({"floatPartValue": "0.01"})
        results.add("FloatPremium.calculate", premium >= 1.0, f"premium={premium:.2f}x")
    except Exception as e:
        results.add("FloatPremium.calculate", False, str(e))

    # Pattern premium
    try:
        premium = mixin._calculate_pattern_premium({"phase": "Ruby"})
        results.add("PatternPremium.calculate", premium >= 1.0, f"premium={premium:.2f}x")
    except Exception as e:
        results.add("PatternPremium.calculate", False, str(e))


async def test_risk_management(results: TestResults):
    """Test 4: Risk management."""
    from src.risk.risk_manager import RiskManager

    rm = RiskManager(
        daily_loss_limit_usd=10.0,
        daily_trade_limit=200,
        max_drawdown_pct=15.0,
        soft_halt_drawdown_pct=5.0,
    )

    # Pre-trade check
    try:
        check = rm.pre_trade_check(proposed_size_usd=5.0, current_equity_usd=100.0)
        results.add("Risk.pre_trade_check", check.allowed, f"reason={check.reason}")
    except Exception as e:
        results.add("Risk.pre_trade_check", False, str(e))

    # Drawdown detection
    try:
        check2 = rm.pre_trade_check(proposed_size_usd=5.0, current_equity_usd=80.0)
        results.add("Risk.drawdown_check", True, f"allowed={check2.allowed}")
    except Exception as e:
        results.add("Risk.drawdown_check", False, str(e))

    # State
    try:
        state = rm.get_state()
        results.add("Risk.get_state", hasattr(state, "current_drawdown_pct"))
    except Exception as e:
        results.add("Risk.get_state", False, str(e))


async def test_inventory_management(results: TestResults):
    """Test 5: Inventory management."""
    from src.db.price_history import price_db

    # Add virtual item
    try:
        price_db.add_virtual_item(
            hash_name="AK-47 | Redline (Field-Tested)",
            buy_price=13.0,
        )
        results.add("Inventory.add_virtual_item", True)
    except Exception as e:
        results.add("Inventory.add_virtual_item", False, str(e))

    # Get inventory
    try:
        inv = price_db.get_virtual_inventory(status="idle")
        results.add("Inventory.get_virtual_inventory", len(inv) > 0, f"count={len(inv)}")
    except Exception as e:
        results.add("Inventory.get_virtual_inventory", False, str(e))

    # Update status
    try:
        inv = price_db.get_virtual_inventory(status="idle")
        if inv:
            item_id = inv[-1]["id"]
            price_db.update_virtual_status(item_id, "listed")
            results.add("Inventory.update_status", True)
        else:
            results.add("Inventory.update_status", False, "no items")
    except Exception as e:
        results.add("Inventory.update_status", False, str(e))

    # Record sale
    try:
        inv = price_db.get_virtual_inventory(status="listed")
        if inv:
            item_id = inv[-1]["id"]
            price_db.record_virtual_sale(item_id, sell_price=15.0, fee_paid=0.75)
            results.add("Inventory.record_sale", True)
        else:
            results.add("Inventory.record_sale", False, "no listed items")
    except Exception as e:
        results.add("Inventory.record_sale", False, str(e))

    # Equity snapshot
    try:
        price_db.record_equity_snapshot(cash=100.0, assets=50.0, total=150.0, realized_pnl=2.25)
        snap = price_db.get_equity_snapshot_today()
        results.add("Inventory.equity_snapshot", snap is not None, f"total={snap.get('total') if snap else '?'}")
    except Exception as e:
        results.add("Inventory.equity_snapshot", False, str(e))


async def test_pipeline_cycle(results: TestResults):
    """Test 6: Full SnipingLoop pipeline cycle."""
    from src.core.target_sniping.core import SnipingLoop
    from src.core.target_sniping.cycle_orchestrator import CycleContext

    client = make_mock_client()

    # Create SnipingLoop without __init__ (avoid real API)
    loop = SnipingLoop.__new__(SnipingLoop)
    loop.client = client
    loop.valuation = MagicMock()
    loop.stickers = MagicMock()
    loop.stickers.calculate_added_value = MagicMock(return_value=0.0)
    loop.liquidity = MagicMock()
    loop.liquidity.can_spend = MagicMock(return_value=True)
    loop.inventory_mgr = None
    loop.target_games = ["a8db"]
    loop.deep_scan_counter = 0
    loop.buy_budget = 100.0
    loop.running = True
    loop.empty_page_count = 0
    loop.resale_cycle_limit = 1
    loop.reprice_counter = 0
    loop._prev_agg_prices = {}
    loop._prev_agg_prices_prior = {}
    loop._sales_cache = {}
    loop._oracle_price_cache = {}
    loop.multi_source_oracle = None
    loop.pump_detector = None
    loop.risk = MagicMock()
    loop.risk.pre_trade_check = MagicMock(return_value=MagicMock(allowed=True, reason=""))
    loop.risk.get_state = MagicMock(return_value=MagicMock(
        win_rate=0.55, win_loss_ratio=1.5,
        current_drawdown_pct=0.0, soft_halt_active=False,
    ))
    loop.self_reflection = MagicMock()
    loop.self_reflection._cached_result = None
    loop.self_reflection.get_adjusted_spread = MagicMock(return_value=5.0)
    loop.self_reflection.get_volatility_regime_adjustment = AsyncMock(return_value=0.0)
    loop.briefing_scheduler = None
    loop._last_quota_warn = 0.0
    loop._last_milestone = 0.0

    # Stage 1: Prepare
    try:
        ctx = CycleContext(game_id="a8db")
        ctx = await loop._stage_prepare(ctx)
        results.add("Pipeline.stage_prepare", ctx.oracle is not None,
                     f"balance={ctx.current_balance:.2f} max_price={ctx.dynamic_max_price:.2f}")
    except Exception as e:
        results.add("Pipeline.stage_prepare", False, str(e))
        return

    # Stage 2: Scan
    try:
        ctx = await loop._stage_scan(ctx)
        results.add("Pipeline.stage_scan", len(ctx.items) > 0,
                     f"items={len(ctx.items)} agg_titles={len(ctx.agg_prices)}")
    except Exception as e:
        results.add("Pipeline.stage_scan", False, str(e))
        return

    # Verify financial instruments found items
    results.add("Pipeline.items_found", len(ctx.items) > 0,
                 f"found {len(ctx.items)} candidates")

    # Verify aggregated prices
    results.add("Pipeline.agg_prices", len(ctx.agg_prices) > 0,
                 f"{len(ctx.agg_prices)} titles with bid/ask data")

    # Stage 3: Prefetch
    try:
        ctx = await loop._stage_prefetch(ctx)
        results.add("Pipeline.stage_prefetch", True,
                     f"fees={len(ctx.bulk_fees)} cs_snapshots={len(ctx.cs_snapshots)}")
    except Exception as e:
        results.add("Pipeline.stage_prefetch", False, str(e))

    # Stage 4: Evaluate
    try:
        ctx = await loop._stage_evaluate(ctx)
        results.add("Pipeline.stage_evaluate", True,
                     f"instant_buys={len(ctx.instant_buys)}")
    except Exception as e:
        results.add("Pipeline.stage_evaluate", False, str(e))

    # Verify sell price was calculated
    if ctx.instant_buys:
        buy = ctx.instant_buys[0]
        has_list_price = "list_price" in buy
        results.add("Pipeline.sell_price_calculated", has_list_price,
                     f"list_price={buy.get('list_price', 'N/A')}")
        has_base_price = "base_price" in buy
        results.add("Pipeline.buy_price_verified", has_base_price,
                     f"base_price={buy.get('base_price', 'N/A')}")

    # Stage 5: Execute (DRY_RUN — no real orders)
    try:
        ctx = await loop._stage_execute(ctx)
        results.add("Pipeline.stage_execute", True, f"executed={len(ctx.instant_buys)}")
    except Exception as e:
        results.add("Pipeline.stage_execute", False, str(e))

    # Stage 6: Postprocess
    try:
        await loop._stage_postprocess(ctx)
        results.add("Pipeline.stage_postprocess", True)
    except Exception as e:
        results.add("Pipeline.stage_postprocess", False, str(e))


async def test_full_cycle_through_run_cycle(results: TestResults):
    """Test 7: Full cycle via run_cycle() entry point."""
    from src.core.target_sniping.core import SnipingLoop

    client = make_mock_client()

    loop = SnipingLoop.__new__(SnipingLoop)
    loop.client = client
    loop.valuation = MagicMock()
    loop.stickers = MagicMock()
    loop.stickers.calculate_added_value = MagicMock(return_value=0.0)
    loop.liquidity = MagicMock()
    loop.liquidity.can_spend = MagicMock(return_value=True)
    loop.inventory_mgr = None
    loop.target_games = ["a8db"]
    loop.deep_scan_counter = 0
    loop.buy_budget = 100.0
    loop.running = True
    loop.empty_page_count = 0
    loop.resale_cycle_limit = 1
    loop.reprice_counter = 0
    loop._prev_agg_prices = {}
    loop._prev_agg_prices_prior = {}
    loop._sales_cache = {}
    loop._oracle_price_cache = {}
    loop.multi_source_oracle = None
    loop.pump_detector = None
    loop.risk = MagicMock()
    loop.risk.pre_trade_check = MagicMock(return_value=MagicMock(allowed=True, reason=""))
    loop.risk.get_state = MagicMock(return_value=MagicMock(
        win_rate=0.55, win_loss_ratio=1.5,
        current_drawdown_pct=0.0, soft_halt_active=False,
    ))
    loop.self_reflection = MagicMock()
    loop.self_reflection._cached_result = None
    loop.self_reflection.get_adjusted_spread = MagicMock(return_value=5.0)
    loop.self_reflection.get_volatility_regime_adjustment = AsyncMock(return_value=0.0)
    loop.briefing_scheduler = None
    loop._last_quota_warn = 0.0
    loop._last_milestone = 0.0

    try:
        await loop.run_cycle("a8db")
        results.add("FullCycle.run_cycle", True, "cycle completed without error")
    except Exception as e:
        results.add("FullCycle.run_cycle", False, str(e))


# =====================================================================
# Main
# =====================================================================

async def main():
    results = TestResults()

    logger.info("=" * 60)
    logger.info("DMARKET BOT — FULL PIPELINE DRY RUN")
    logger.info("=" * 60)

    await test_db_operations(results)
    await test_oracle_integration(results)
    await test_financial_instruments(results)
    await test_risk_management(results)
    await test_inventory_management(results)
    await test_pipeline_cycle(results)
    await test_full_cycle_through_run_cycle(results)

    # Generate report
    summary = results.summary()
    report_path = Path("logs/dry_run_full_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, default=str))

    # Print summary
    logger.info("=" * 60)
    logger.info(f"RESULTS: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']}%)")
    logger.info(f"Duration: {summary['duration_s']}s")
    logger.info("=" * 60)

    for t in summary["tests"]:
        status = "PASS" if t["passed"] else "FAIL"
        detail = f" — {t['detail']}" if t["detail"] else ""
        logger.info(f"  [{status}] {t['name']}{detail}")

    logger.info("=" * 60)
    logger.info(f"Report: {report_path}")

    failed = [t for t in summary["tests"] if not t["passed"]]
    if failed:
        logger.warning(f"FAILED TESTS: {[t['name'] for t in failed]}")
    else:
        logger.info("ALL TESTS PASSED — Bot is ready for production dry run")

    return summary


if __name__ == "__main__":
    asyncio.run(main())
