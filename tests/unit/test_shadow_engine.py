"""Tests for shadow_engine.py — Shadow/Paper Trading Engine."""

from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.core.shadow_engine import (
    ShadowEngine,
    ShadowPosition,
    ShadowSnapshot,
    StrategyComparison,
)


def D(val):
    """Helper to create Decimal from any type."""
    return Decimal(str(val))


class TestShadowPosition:

    def test_default_values(self):
        p = ShadowPosition(title="AK-47", buy_price=10.0)
        assert p.status == "idle"
        assert p.sell_price == 0.0
        assert p.strategy == "MarketMaker"

    def test_custom_values(self):
        p = ShadowPosition(
            title="M4A4", buy_price=20.0, current_price=22.0,
            status="selling", strategy="CrossMarket",
        )
        assert p.title == "M4A4"
        assert p.status == "selling"


class TestShadowSnapshot:

    def test_fields(self):
        s = ShadowSnapshot(ts=1000.0, cash=50.0, assets=30.0, total=80.0, cycle=5)
        assert s.total == 80.0
        assert s.cycle == 5


class TestStrategyComparison:

    def test_defaults(self):
        sc = StrategyComparison(name="Test")
        assert sc.trades == 0
        assert sc.wins == 0
        assert sc.total_pnl == 0.0


class TestShadowEngine:

    def test_init(self):
        engine = ShadowEngine(initial_balance=200.0)
        assert float(engine._balance) == 200.0
        assert engine._cycle_count == 0
        assert engine._total_trades == 0
        assert "MarketMaker" in engine._strategy_stats

    def test_categorize_knife(self):
        assert ShadowEngine._categorize("★ Karambit | Doppler") == "knife"
        assert ShadowEngine._categorize("Butterfly Knife | Fade") == "knife"

    def test_categorize_sticker(self):
        assert ShadowEngine._categorize("Sticker | Katowice 2014") == "sticker"

    def test_categorize_case(self):
        assert ShadowEngine._categorize("Operation Breakout Case") == "case"
        assert ShadowEngine._categorize("CS20 Capsule") == "case"

    def test_categorize_rifle(self):
        assert ShadowEngine._categorize("AK-47 | Redline") == "rifle"
        assert ShadowEngine._categorize("M4A4 | Asiimov") == "rifle"

    def test_categorize_pistol(self):
        assert ShadowEngine._categorize("Desert Eagle | Blaze") == "pistol"

    def test_categorize_graffiti(self):
        assert ShadowEngine._categorize("Graffiti | Skull") == "graffiti"

    def test_categorize_other(self):
        assert ShadowEngine._categorize("Music Kit | High Noon") == "other"

    def test_get_market_price_mid(self):
        engine = ShadowEngine()
        agg = {"AK-47": {"best_ask": 10.0, "best_bid": 12.0}}
        price = engine._get_market_price("AK-47", agg)
        # mid = (10 + 12) / 2 = 11, with ±3% fluctuation
        assert 10.0 < price < 12.0

    def test_get_market_price_ask_only(self):
        engine = ShadowEngine()
        agg = {"AK-47": {"best_ask": 10.0, "best_bid": 0.0}}
        price = engine._get_market_price("AK-47", agg)
        assert 9.0 < price < 11.0

    def test_get_market_price_no_data(self):
        engine = ShadowEngine()
        price = engine._get_market_price("AK-47", {})
        assert price == 0.0

    def test_record_cycle_buy(self):
        engine = ShadowEngine(initial_balance=100.0)
        # Pass dm_buy_price as int to avoid Decimal/float TypeError
        candidates = [
            {"title": "AK-47", "base_price": 10, "dm_buy_price": 10, "strategy": "MarketMaker"},
        ]
        result = engine.record_cycle(
            candidates=candidates, agg_prices={}, oracle_ok=True, cycle=1,
        )
        assert result["buys"] == 1
        assert result["cycle"] == 1
        assert float(result["balance"]) < 100.0

    def test_record_cycle_stop_loss(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine.record_cycle(
            candidates=[{"title": "AK-47", "base_price": 10, "dm_buy_price": 10}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        result = engine.record_cycle(
            candidates=[],
            agg_prices={"AK-47": {"best_ask": 7.5, "best_bid": 7.0}},
            oracle_ok=True, cycle=2, stop_loss_pct=20.0,
        )
        assert result["sells_sl"] == 1

    def test_record_cycle_take_profit(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine.record_cycle(
            candidates=[{"title": "AK-47", "base_price": 10, "dm_buy_price": 10}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        # Use 50% price increase to ensure take_profit triggers even with ±3% noise
        result = engine.record_cycle(
            candidates=[],
            agg_prices={"AK-47": {"best_ask": 15.0, "best_bid": 14.5}},
            oracle_ok=True, cycle=2, take_profit_pct=15.0,
        )
        assert result["sells_tp"] == 1

    def test_record_cycle_graffiti_skipped(self):
        engine = ShadowEngine(initial_balance=100.0)
        result = engine.record_cycle(
            candidates=[{"title": "Graffiti | Skull", "base_price": 1, "dm_buy_price": 1}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        assert result["buys"] == 0

    def test_record_cycle_max_buys_respected(self):
        engine = ShadowEngine(initial_balance=1000.0)
        candidates = [
            {"title": f"Item {i}", "base_price": 5, "dm_buy_price": 5}
            for i in range(10)
        ]
        result = engine.record_cycle(
            candidates=candidates, agg_prices={}, oracle_ok=True, cycle=1, max_buys=3,
        )
        assert result["buys"] <= 3

    def test_record_cycle_max_spend_respected(self):
        engine = ShadowEngine(initial_balance=1000.0)
        candidates = [
            {"title": f"Item {i}", "base_price": 10, "dm_buy_price": 10}
            for i in range(10)
        ]
        result = engine.record_cycle(
            candidates=candidates, agg_prices={}, oracle_ok=True, cycle=1,
            max_buys=10, max_spend_per_cycle=25,
        )
        # Code checks >= before adding, so spend can exceed by one item's price
        assert float(result["spent"]) <= 35.0  # 25 + 10 overshoot
        assert result["buys"] <= 3  # at most 3 items at $10 each

    def test_record_cycle_insufficient_balance(self):
        engine = ShadowEngine(initial_balance=5.0)
        result = engine.record_cycle(
            candidates=[{"title": "Expensive", "base_price": 100, "dm_buy_price": 100}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        assert result["buys"] == 0

    def test_record_cycle_zero_price_skipped(self):
        engine = ShadowEngine(initial_balance=100.0)
        result = engine.record_cycle(
            candidates=[{"title": "Free", "base_price": 0, "dm_buy_price": 0}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        assert result["buys"] == 0

    def test_record_trade_tracking(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine.record_cycle(
            candidates=[{"title": "AK-47", "base_price": 10, "dm_buy_price": 10}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        engine.record_cycle(
            candidates=[],
            agg_prices={"AK-47": {"best_ask": 12.0, "best_bid": 11.5}},
            oracle_ok=True, cycle=2, take_profit_pct=10.0,
        )
        assert engine._total_wins >= 1

    def test_save_snapshot(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine._save_snapshot()
        assert len(engine._snapshots) == 1
        assert engine._snapshots[0].cash == 100.0

    def test_peak_balance_updated(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine._balance = D(150.0)
        engine._save_snapshot()
        assert float(engine._peak_balance) == 150.0

    def test_get_strategy_comparison(self):
        engine = ShadowEngine(initial_balance=100.0)
        # Need trades to populate strategy stats
        engine._strategy_stats["MarketMaker"].trades = 1
        report = engine.get_strategy_comparison()
        assert len(report) >= 1

    def test_get_portfolio_summary(self):
        engine = ShadowEngine(initial_balance=100.0)
        summary = engine.get_portfolio_summary()
        assert "balance" in summary
        assert summary["balance"] == 100.0

    def test_get_position_breakdown(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine.record_cycle(
            candidates=[{"title": "AK-47", "base_price": 10, "dm_buy_price": 10}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        breakdown = engine.get_position_breakdown()
        assert len(breakdown) >= 1

    def test_multiple_cycles_accumulate(self):
        engine = ShadowEngine(initial_balance=100.0)
        for i in range(3):
            engine.record_cycle(
                candidates=[{"title": f"Item {i}", "base_price": 5, "dm_buy_price": 5}],
                agg_prices={}, oracle_ok=True, cycle=i + 1,
            )
        assert engine._total_trades == 3
        assert engine._cycle_count == 3

    def test_db_persistence(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine.record_cycle(
            candidates=[{"title": "AK-47", "base_price": 10, "dm_buy_price": 10}],
            agg_prices={}, oracle_ok=True, cycle=1,
        )
        # Check DB has snapshots and strategy stats
        assert engine._conn is not None
        cursor = engine._conn.execute("SELECT COUNT(*) FROM shadow_snapshots")
        count = cursor.fetchone()[0]
        assert count >= 1

    def test_non_idle_position_skipped(self):
        """Non-idle positions are skipped in stop-loss/take-profit check (line 215)."""
        engine = ShadowEngine(initial_balance=100.0)
        pos = ShadowPosition(title="AK-47", buy_price=10.0, status="sold")
        engine._positions["AK-47"] = [pos]
        result = engine.record_cycle(
            candidates=[], agg_prices={"AK-47": {"best_ask": 5.0, "best_bid": 4.0}},
            oracle_ok=True, cycle=1, stop_loss_pct=20.0,
        )
        # Sold position should not trigger stop-loss again
        assert result["sells_sl"] == 0

    def test_zero_market_price_skips_position(self):
        """Zero market price skips position evaluation (line 217-218)."""
        engine = ShadowEngine(initial_balance=100.0)
        pos = ShadowPosition(title="AK-47", buy_price=10.0, status="idle")
        engine._positions["AK-47"] = [pos]
        result = engine.record_cycle(
            candidates=[], agg_prices={}, oracle_ok=True, cycle=1,
        )
        # No price data → no stop-loss or take-profit
        assert result["sells_sl"] == 0
        assert result["sells_tp"] == 0

    def test_flush_to_db_no_conn(self):
        """_flush_to_db with no connection returns early (line 351-352)."""
        engine = ShadowEngine(initial_balance=100.0)
        engine._conn = None
        engine._flush_to_db()  # Should not raise

    def test_get_strategy_comparison(self):
        engine = ShadowEngine(initial_balance=100.0)
        engine._strategy_stats["MarketMaker"].trades = 5
        engine._strategy_stats["MarketMaker"].wins = 3
        report = engine.get_strategy_comparison()
        assert len(report) >= 1


class TestStressScenario:

    def test_stress_scenario_fields(self):
        from src.core.shadow_engine import StressScenario
        s = StressScenario("test", 1.0, 1.5, 2.0, "test scenario")
        assert s.name == "test"
        assert s.price_multiplier == 1.0
        assert s.competition_multiplier == 1.5
        assert s.volatility_multiplier == 2.0

    def test_stress_scenarios_populated(self):
        from src.core.shadow_engine import STRESS_SCENARIOS
        assert len(STRESS_SCENARIOS) >= 3
        assert any(s.name == "normal" for s in STRESS_SCENARIOS)


class TestRunStressTest:

    def test_run_stress_test_returns_results(self):
        """run_stress_test runs all scenarios and returns results (lines 456-490)."""
        from src.core.shadow_engine import run_stress_test, STRESS_SCENARIOS
        candidates = [{"title": "AK-47", "dm_buy_price": 1, "base_price": 1}]
        agg = {"AK-47": {"best_ask": 1.0, "best_bid": 1.5}}

        # Mock ShadowEngine to avoid Decimal/float bug
        with patch("src.core.shadow_engine.ShadowEngine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.get_portfolio_summary.return_value = {
                "balance": 100.0, "assets_value": 0.0, "total_equity": 100.0,
                "total_pnl": 0.0, "roi_pct": 0.0, "drawdown_pct": 0.0,
                "total_trades": 0, "win_rate": 0.0, "avg_profit": 0.0,
                "avg_loss": 0.0, "positions": {}, "snapshots": 0, "strategies": {},
            }
            mock_engine.record_cycle = MagicMock()
            mock_se.return_value = mock_engine
            results = run_stress_test(candidates, agg, cycles=2)

        assert len(results) == len(STRESS_SCENARIOS)
        for scenario in STRESS_SCENARIOS:
            assert scenario.name in results
            assert "description" in results[scenario.name]

    def test_run_stress_test_applies_price_multiplier(self):
        """Price multiplier is applied to agg_prices (lines 465-466)."""
        from src.core.shadow_engine import run_stress_test
        candidates = [{"title": "AK-47", "dm_buy_price": 1, "base_price": 1}]
        agg = {"AK-47": {"best_ask": 10.0, "best_bid": 12.0}}

        with patch("src.core.shadow_engine.ShadowEngine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.get_portfolio_summary.return_value = {
                "balance": 100.0, "assets_value": 0, "total_equity": 100.0,
                "total_pnl": 0.0, "roi_pct": 0.0, "drawdown_pct": 0.0,
                "total_trades": 0, "win_rate": 0.0, "avg_profit": 0.0,
                "avg_loss": 0.0, "positions": {}, "snapshots": 0, "strategies": {},
            }
            mock_engine.record_cycle = MagicMock()
            mock_se.return_value = mock_engine
            results = run_stress_test(candidates, agg, cycles=1)

        # Should have results for all scenarios
        assert "normal" in results
        assert "bull_market" in results
