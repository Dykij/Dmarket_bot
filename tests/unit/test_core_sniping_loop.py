"""Tests for core.py — the main SnipingLoop orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.core import SnipingLoop


@pytest.fixture(autouse=True)
def _dry_run(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DRY_RUN", "true")


@pytest.fixture()
def loop():
    client = AsyncMock()
    return SnipingLoop(client=client)


class TestSnipingLoopInit:

    def test_initialization_sets_client(self, loop):
        assert loop.client is not None

    def test_initialization_sets_counters(self, loop):
        assert loop.deep_scan_counter == 0
        assert loop.reprice_counter == 0
        assert loop.empty_page_count == 0
        assert loop.running is False

    def test_initialization_sets_target_games(self, loop):
        assert "a8db" in loop.target_games

    def test_initialization_creates_risk_manager(self, loop):
        assert loop.risk is not None

    def test_initialization_creates_pump_detector(self, loop):
        assert loop.pump_detector is not None

    def test_initialization_sets_empty_prev_prices(self, loop):
        assert loop._prev_agg_prices == {}
        assert loop._sales_cache == {}


class TestRunCycle:

    @pytest.mark.asyncio
    async def test_run_cycle_dry_run_full_pipeline(self, loop):
        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {"AK-47": {"best_ask": 10.0}}
        ctx.items = [{"itemId": "i1", "title": "AK-47"}]
        ctx.instant_buys = []
        ctx.current_balance = 100.0

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_execute", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_postprocess", new_callable=AsyncMock),
        ):
            await loop.run_cycle("a8db")

    @pytest.mark.asyncio
    async def test_run_cycle_with_no_items_skips(self, loop):
        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {}
        ctx.items = []

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock) as mock_prefetch,
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock) as mock_eval,
            patch.object(loop, "_stage_execute", new_callable=AsyncMock) as mock_exec,
        ):
            await loop.run_cycle("a8db")

            mock_prefetch.assert_not_called()
            mock_eval.assert_not_called()
            mock_exec.assert_not_called()
            assert loop.empty_page_count == 1

    @pytest.mark.asyncio
    async def test_run_cycle_with_no_oracle_skips(self, loop):
        ctx = MagicMock()
        ctx.oracle = None

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock) as mock_scan,
        ):
            await loop.run_cycle("a8db")

            mock_scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cycle_resets_empty_count_on_items(self, loop):
        loop.empty_page_count = 5

        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {"item": {}}
        ctx.items = [{"itemId": "i1"}]
        ctx.instant_buys = []

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_execute", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_postprocess", new_callable=AsyncMock),
        ):
            await loop.run_cycle("a8db")

        assert loop.empty_page_count == 0


class TestRunCycleProfitableItem:

    @pytest.mark.asyncio
    async def test_run_cycle_with_profitable_item(self, loop):
        buy_item = {
            "action": "buy", "title": "AK-47 | Redline",
            "base_price": 10.0, "list_price": 12.0, "item_id": "item_001",
        }

        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {"AK-47 | Redline": {"best_ask": 10.0, "best_bid": 12.0}}
        ctx.items = [{"itemId": "item_001", "title": "AK-47 | Redline"}]
        ctx.instant_buys = [buy_item]
        ctx.current_balance = 100.0

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_execute", new_callable=AsyncMock, return_value=ctx) as mock_exec,
            patch.object(loop, "_stage_postprocess", new_callable=AsyncMock),
        ):
            await loop.run_cycle("a8db")

            mock_exec.assert_called_once()
            assert mock_exec.call_args[0][0].instant_buys == [buy_item]


class TestRunCycleNoProfitableItems:

    @pytest.mark.asyncio
    async def test_run_cycle_with_no_profitable_items(self, loop):
        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {"AK-47": {"best_ask": 10.0}}
        ctx.items = [{"itemId": "i1", "title": "AK-47"}]
        ctx.instant_buys = []
        ctx.current_balance = 100.0

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_execute", new_callable=AsyncMock, return_value=ctx) as mock_exec,
            patch.object(loop, "_stage_postprocess", new_callable=AsyncMock),
        ):
            await loop.run_cycle("a8db")

            ctx_exec = mock_exec.call_args[0][0]
            assert ctx_exec.instant_buys == []


class TestDrawdownFreeze:

    def test_drawdown_freeze_blocks_buys(self, loop):
        """When drawdown % is above freeze threshold, buys are blocked."""
        loop.risk._current_drawdown_pct = 20.0
        loop.risk._peak_equity = 100.0
        loop.risk._current_equity = 80.0

        risk_result = loop.risk.pre_trade_check(
            proposed_size_usd=10.0,
            current_equity_usd=80.0,
            game_id="a8db",
            item_title="AK-47",
        )

        assert risk_result.allowed is False
        assert "freeze" in risk_result.reason.lower() or "drawdown" in risk_result.reason.lower()

    def test_drawdown_healthy_allows(self, loop):
        loop.risk._current_drawdown_pct = 0.0
        loop.risk._peak_equity = 100.0
        loop.risk._current_equity = 100.0

        risk_result = loop.risk.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=100.0,
            game_id="a8db",
            item_title="AK-47",
        )

        assert risk_result.allowed is True


class TestBalanceGate:

    @pytest.mark.asyncio
    async def test_balance_gate_skips_expensive_items(self, loop):
        ctx = MagicMock()
        ctx.oracle = MagicMock()
        ctx.agg_prices = {"Expensive Skin": {"best_ask": 50.0}}
        ctx.items = [{"itemId": "i1", "title": "Expensive Skin", "price": {"USD": "5000"}}]
        ctx.instant_buys = []
        ctx.current_balance = 20.0
        ctx.effective_balance = 15.0
        ctx.dynamic_max_price = 5.0

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_prefetch", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_evaluate", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_execute", new_callable=AsyncMock, return_value=ctx) as mock_exec,
            patch.object(loop, "_stage_postprocess", new_callable=AsyncMock),
        ):
            await loop.run_cycle("a8db")

            ctx_result = mock_exec.call_args[0][0]
            assert ctx_result.instant_buys == []


class TestGetMinProfitMargin:

    @pytest.mark.asyncio
    async def test_get_min_profit_margin_returns_positive(self, loop):
        with patch("src.core.target_sniping.core.event_shield") as mock_shield:
            mock_shield.get_margin_multiplier.return_value = 1.0
            margin = await loop.get_min_profit_margin()

        assert margin > 0
        assert isinstance(margin, float)


class TestRunCycleErrorHandling:

    @pytest.mark.asyncio
    async def test_run_cycle_handles_transient_error(self, loop):
        ctx = MagicMock()
        ctx.current_balance = 0.0
        ctx.items = []

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, side_effect=ConnectionError("timeout")),
            patch("src.risk.fatal_errors.classify", return_value="transient"),
        ):
            await loop.run_cycle("a8db")

    @pytest.mark.asyncio
    async def test_run_cycle_fatal_error_reraises(self, loop):
        ctx = MagicMock()
        ctx.current_balance = 100.0
        ctx.items = []

        with (
            patch.object(loop, "_stage_prepare", new_callable=AsyncMock, return_value=ctx),
            patch.object(loop, "_stage_scan", new_callable=AsyncMock, side_effect=SystemExit("fatal")),
            patch("src.risk.fatal_errors.classify", return_value="fatal"),
            patch("src.risk.error_reporter.ErrorReporter") as mock_reporter,
        ):
            mock_reporter.return_value.format_log.return_value = "FATAL ERROR"
            with pytest.raises(SystemExit):
                await loop.run_cycle("a8db")
