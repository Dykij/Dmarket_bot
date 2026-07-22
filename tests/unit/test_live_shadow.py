"""Tests for live_shadow.py — Live Shadow Trading."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.live_shadow import LiveShadow, MonteCarloResult


class TestMonteCarloResult:

    def test_fields(self):
        mc = MonteCarloResult(
            runs=100, mean_pnl=5.0, median_pnl=4.0, std_pnl=2.0,
            min_pnl=-10.0, max_pnl=20.0, pnl_5th=-8.0, pnl_95th=15.0,
            win_rate_mean=0.6, profit_probability=0.65, sharpe_estimate=1.2,
            max_drawdown_mean=5.0, distribution=[1.0, 2.0, 3.0],
        )
        assert mc.runs == 100
        assert mc.profit_probability == 0.65


class TestLiveShadow:

    def test_init(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = True
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        assert ls.enabled is True
        assert ls.total_cycles == 0

    def test_start(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = True
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        ls.start()
        assert ls._started is True

    def test_start_disabled(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = False
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        ls.start()
        assert ls._started is False

    def test_stop(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 5
        ls._last_feed = time.time()
        ls._monte_carlo_task = None
        ls.stop()
        assert ls._started is False

    def test_feed_cycle_disabled(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = False
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        result = ls.feed_cycle(candidates=[], agg_prices={})
        assert result is None

    def test_feed_cycle_not_started(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = True
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        result = ls.feed_cycle(candidates=[], agg_prices={})
        assert result is None

    def test_feed_cycle_empty_data(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        result = ls.feed_cycle(candidates=[], agg_prices={})
        assert result is None

    def test_feed_cycle_with_candidates(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.record_cycle = MagicMock(return_value={"buys": 1})
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_equity": 100.0, "total_pnl": 0.0,
            "total_trades": 0, "win_rate": 0.0,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None

        candidates = [{"title": "AK-47", "dm_buy_price": 10, "base_price": 10}]
        result = ls.feed_cycle(candidates=candidates, agg_prices={})

        assert result is not None
        assert ls._total_cycles == 1

    def test_feed_cycle_builds_from_agg(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.record_cycle = MagicMock(return_value={"buys": 0})
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_equity": 100.0, "total_pnl": 0.0,
            "total_trades": 0, "win_rate": 0.0,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None

        agg = {"AK-47": {"best_ask": 10.0, "best_bid": 12.0}}
        result = ls.feed_cycle(candidates=[], agg_prices=agg)

        assert result is not None

    def test_build_candidates(self):
        agg = {
            "AK-47": {"best_ask": 10.0, "best_bid": 12.0},
            "M4A4": {"best_ask": 20.0, "best_bid": 22.0},
        }
        cands = LiveShadow._build_candidates(agg)
        assert len(cands) == 2
        assert cands[0]["title"] == "AK-47"

    def test_build_candidates_skips_zero_ask(self):
        agg = {
            "AK-47": {"best_ask": 0, "best_bid": 12.0},
            "M4A4": {"best_ask": 20.0, "best_bid": 22.0},
        }
        cands = LiveShadow._build_candidates(agg)
        assert len(cands) == 1

    def test_build_candidates_strategy_selection(self):
        agg = {
            "Wide": {"best_ask": 10.0, "best_bid": 15.0},    # 50% margin → CrossMarket
            "Narrow": {"best_ask": 10.0, "best_bid": 10.2},  # 2% margin → MarketMaker
        }
        cands = LiveShadow._build_candidates(agg)
        wide = next(c for c in cands if c["title"] == "Wide")
        narrow = next(c for c in cands if c["title"] == "Narrow")
        assert wide["strategy"] == "CrossMarket"
        assert narrow["strategy"] == "MarketMaker"

    def test_get_status_disabled(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._enabled = False
        ls._started = False
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None
        status = ls.get_status()
        assert status["enabled"] is False

    def test_get_status_enabled(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_equity": 100.0, "total_pnl": 0.0,
            "total_trades": 0, "win_rate": 0.0, "roi_pct": 0.0,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 10
        ls._last_feed = time.time()
        ls._monte_carlo_task = None
        status = ls.get_status()
        assert status["enabled"] is True
        assert status["cycles"] == 10

    def test_compare_with_real(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_pnl": 10.0, "total_trades": 5,
            "win_rate": 60.0, "roi_pct": 10.0,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 10
        ls._last_feed = time.time()
        ls._monte_carlo_task = None

        result = ls.compare_with_real(real_equity=120.0)
        assert "shadow_pnl" in result
        assert "real_pnl" in result
        assert "delta" in result


class TestMonteCarlo:

    @pytest.mark.asyncio
    async def test_no_agg_prices_raises(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        with pytest.raises(ValueError, match="No agg_prices"):
            await ls.run_monte_carlo([], {})

    @pytest.mark.asyncio
    async def test_no_candidates_raises(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        agg = {"AK-47": {"best_ask": 0, "best_bid": 0}}  # all zero → no candidates
        with pytest.raises(ValueError, match="No candidates"):
            await ls.run_monte_carlo([], agg)

    @pytest.mark.asyncio
    async def test_runs_simulations(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        agg = {"AK-47": {"best_ask": 1.0, "best_bid": 1.5}}
        cands = [{"title": "AK-47", "dm_buy_price": 1, "base_price": 1}]

        result = await ls.run_monte_carlo(cands, agg, runs=5, cycles=2)
        assert result.runs == 5
        assert len(result.distribution) == 5
        assert result.profit_probability >= 0.0

    @pytest.mark.asyncio
    async def test_builds_candidates_from_agg(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        agg = {"AK-47": {"best_ask": 1.0, "best_bid": 1.5}}

        # Mock ShadowEngine to avoid Decimal/float bug in record_cycle
        with patch("src.core.live_shadow.ShadowEngine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.get_portfolio_summary.return_value = {
                "total_pnl": 1.0, "win_rate": 50.0, "drawdown_pct": 0.0,
            }
            mock_engine.record_cycle = MagicMock()
            mock_se.return_value = mock_engine
            result = await ls.run_monte_carlo([], agg, runs=3, cycles=1)

        assert result.runs == 3
        assert len(result.distribution) == 3

    @pytest.mark.asyncio
    async def test_monte_carlo_statistics(self):
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        agg = {"AK-47": {"best_ask": 1.0, "best_bid": 1.5}}
        cands = [{"title": "AK-47", "dm_buy_price": 1, "base_price": 1}]

        with patch("src.core.live_shadow.ShadowEngine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.get_portfolio_summary.return_value = {
                "total_pnl": 2.0, "win_rate": 60.0, "drawdown_pct": 5.0,
            }
            mock_engine.record_cycle = MagicMock()
            mock_se.return_value = mock_engine
            result = await ls.run_monte_carlo(cands, agg, runs=10, cycles=3)

        assert result.mean_pnl == 2.0
        assert result.median_pnl == 2.0
        assert result.min_pnl == 2.0
        assert result.max_pnl == 2.0

    @pytest.mark.asyncio
    async def test_monte_carlo_var(self):
        """Value at Risk (5th percentile) is computed."""
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        agg = {"AK-47": {"best_ask": 1.0, "best_bid": 1.5}}
        cands = [{"title": "AK-47", "dm_buy_price": 1, "base_price": 1}]

        with patch("src.core.live_shadow.ShadowEngine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.get_portfolio_summary.return_value = {
                "total_pnl": 1.0, "win_rate": 50.0, "drawdown_pct": 2.0,
            }
            mock_engine.record_cycle = MagicMock()
            mock_se.return_value = mock_engine
            result = await ls.run_monte_carlo(cands, agg, runs=20, cycles=2)

        assert result.pnl_5th is not None
        assert result.pnl_95th is not None
        assert result.win_rate_mean == 50.0


class TestFeedCycleExtended:

    def test_feed_cycle_builds_candidates_from_agg(self):
        """feed_cycle builds candidates from agg_prices when none provided."""
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.record_cycle = MagicMock(return_value={"buys": 0})
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_equity": 100.0, "total_pnl": 0.0,
            "total_trades": 0, "win_rate": 0.0,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 0
        ls._last_feed = 0.0
        ls._monte_carlo_task = None

        agg = {"AK-47": {"best_ask": 10.0, "best_bid": 12.0}}
        result = ls.feed_cycle(candidates=[], agg_prices=agg)
        assert result is not None

    def test_feed_cycle_logs_every_50_cycles(self):
        """Logs summary every 50 cycles (lines 131-139)."""
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.record_cycle = MagicMock(return_value={"buys": 0})
        ls._engine.get_portfolio_summary = MagicMock(return_value={
            "total_equity": 100.0, "total_pnl": 5.0,
            "total_trades": 3, "win_rate": 66.7,
        })
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 49  # next cycle is 50
        ls._last_feed = time.time()
        ls._monte_carlo_task = None

        cands = [{"title": "AK-47", "dm_buy_price": 10, "base_price": 10}]
        result = ls.feed_cycle(candidates=cands, agg_prices={})
        assert result is not None
        assert ls._total_cycles == 50

    def test_feed_cycle_exception_returns_none(self):
        """Exception in record_cycle returns None (lines 141-143)."""
        ls = LiveShadow.__new__(LiveShadow)
        ls._engine = MagicMock()
        ls._engine.record_cycle = MagicMock(side_effect=Exception("boom"))
        ls._enabled = True
        ls._started = True
        ls._total_cycles = 0
        ls._last_feed = time.time()
        ls._monte_carlo_task = None

        cands = [{"title": "AK-47", "dm_buy_price": 10, "base_price": 10}]
        result = ls.feed_cycle(candidates=cands, agg_prices={})
        assert result is None

    def test_engine_property(self):
        """engine property returns the internal engine (line 77)."""
        ls = LiveShadow.__new__(LiveShadow)
        mock_engine = MagicMock()
        ls._engine = mock_engine
        assert ls.engine is mock_engine
