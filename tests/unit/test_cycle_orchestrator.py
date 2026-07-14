"""Tests for cycle_orchestrator.py — pipeline stage decomposition."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.cycle_orchestrator import CycleContext, CycleOrchestrator


def _make_ctx(game_id: str = "a8db", balance: float = 100.0) -> CycleContext:
    return CycleContext(game_id=game_id, current_balance=balance)


def _make_orchestrator() -> MagicMock:
    orch = MagicMock()
    orch.client = AsyncMock()
    orch.deep_scan_counter = 0
    orch.reprice_counter = 0
    orch.empty_page_count = 0
    orch.multi_source_oracle = None
    orch.pump_detector = None
    orch.risk = MagicMock()
    orch.self_reflection = MagicMock()
    orch._prev_agg_prices = {}
    orch._sales_cache = {}
    orch.resale_cycle_limit = 1
    orch._clear_oracle_cache = MagicMock()
    orch._sync_inventory_statuses = AsyncMock()
    orch._fetch_cheapest_listings = AsyncMock(return_value=[])
    orch._fetch_float_phase_listings = AsyncMock(return_value=[])
    orch._fetch_price_range_listings = AsyncMock(return_value=[])
    orch._fetch_low_fee_listings = AsyncMock(return_value=[])
    orch.get_min_profit_margin = AsyncMock(return_value=0.05)
    orch._evaluate_candidate = AsyncMock()
    orch._execute_buy = AsyncMock()
    orch.auto_resale = AsyncMock()
    orch.reprice_unsold_offers = AsyncMock()
    return orch


class TestCycleContext:

    def test_default_values(self):
        ctx = CycleContext()
        assert ctx.game_id == ""
        assert ctx.current_balance == 0.0
        assert ctx.effective_balance == 0.0
        assert ctx.dynamic_max_price == 0.0
        assert ctx.oracle is None
        assert ctx.agg_prices == {}
        assert ctx.items == []
        assert ctx.instant_buys == []
        assert ctx.is_fresh_cycle is False
        assert ctx.total_spent == 0.0
        assert ctx.total_earned == 0.0

    def test_custom_values(self):
        ctx = CycleContext(game_id="a8db", current_balance=50.0, effective_balance=45.0)
        assert ctx.game_id == "a8db"
        assert ctx.current_balance == 50.0
        assert ctx.effective_balance == 45.0

    def test_field_defaults_are_independent(self):
        ctx1 = CycleContext()
        ctx2 = CycleContext()
        ctx1.items.append({"title": "test"})
        assert len(ctx2.items) == 0


class TestStagePrepare:

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_prepare_sets_balance(self, mock_db):
        orch = _make_orchestrator()
        orch.client.get_real_balance = AsyncMock(return_value=150.0)

        ctx = _make_ctx(balance=0.0)
        result = await CycleOrchestrator._stage_prepare(orch, ctx)

        assert result.current_balance == 150.0
        assert result.balance_before == 150.0

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_prepare_increments_counter(self, mock_db):
        orch = _make_orchestrator()
        orch.deep_scan_counter = 4
        orch.client.get_real_balance = AsyncMock(return_value=100.0)

        ctx = _make_ctx()
        result = await CycleOrchestrator._stage_prepare(orch, ctx)

        assert orch.deep_scan_counter == 5
        assert result.is_fresh_cycle is True

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_prepare_dynamic_max_price(self, mock_db):
        orch = _make_orchestrator()
        orch.client.get_real_balance = AsyncMock(return_value=200.0)

        ctx = _make_ctx()
        result = await CycleOrchestrator._stage_prepare(orch, ctx)

        assert result.effective_balance > 0
        assert result.dynamic_max_price > 0


class TestStageScan:

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_scan_with_empty_prices_returns_empty(self, mock_db):
        orch = _make_orchestrator()
        orch.client.get_aggregated_prices = AsyncMock(return_value={})

        ctx = _make_ctx()
        ctx.oracle = MagicMock()
        result = await CycleOrchestrator._stage_scan(orch, ctx)

        assert result.agg_prices == {}

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_scan_collects_items(self, mock_db):
        orch = _make_orchestrator()
        orch.client.get_aggregated_prices = AsyncMock(return_value={
            "AK-47 | Redline": {"best_ask": 10.0, "best_bid": 12.0},
        })
        orch._fetch_cheapest_listings = AsyncMock(return_value=[
            {"itemId": "i1", "title": "AK-47 | Redline", "price": {"USD": "1000"}}
        ])

        async def _fake_secondary(ctx, cursor):
            return ctx.items

        orch._run_secondary_scans = AsyncMock(side_effect=_fake_secondary)

        ctx = _make_ctx()
        ctx.oracle = MagicMock()
        result = await CycleOrchestrator._stage_scan(orch, ctx)

        assert len(result.agg_prices) == 1

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_scan_handles_api_error(self, mock_db):
        orch = _make_orchestrator()
        orch.client.get_aggregated_prices = AsyncMock(side_effect=Exception("API down"))

        ctx = _make_ctx()
        ctx.oracle = MagicMock()
        result = await CycleOrchestrator._stage_scan(orch, ctx)

        assert result.agg_prices == {}


class TestStageEvaluate:

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_evaluate_empty_candidates(self, mock_db):
        orch = _make_orchestrator()

        ctx = _make_ctx()
        ctx.items = []
        ctx.agg_prices = {}
        ctx.bulk_fees = {}
        ctx.cs_snapshots = {}
        ctx.current_margin = 0.05
        result = await CycleOrchestrator._stage_evaluate(orch, ctx)

        assert result.instant_buys == []

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_evaluate_filters_buy_actions(self, mock_db):
        orch = _make_orchestrator()
        mock_db.get_virtual_inventory.return_value = []

        buy_result = {"action": "buy", "title": "AK-47", "base_price": 10.0}
        orch._evaluate_candidate = AsyncMock(return_value=buy_result)

        ctx = _make_ctx()
        ctx.items = [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}]
        ctx.agg_prices = {"AK-47": {"best_ask": 10.0}}
        ctx.bulk_fees = {}
        ctx.cs_snapshots = {}
        ctx.current_margin = 0.05

        with patch("src.core.target_sniping.ranking.rank_candidates_by_spread", return_value=ctx.items):
            result = await CycleOrchestrator._stage_evaluate(orch, ctx)

        assert len(result.instant_buys) == 1
        assert result.instant_buys[0]["action"] == "buy"

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_evaluate_handles_exception_in_candidate(self, mock_db):
        orch = _make_orchestrator()
        mock_db.get_virtual_inventory.return_value = []
        orch._evaluate_candidate = AsyncMock(side_effect=Exception("eval boom"))

        ctx = _make_ctx()
        ctx.items = [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}]
        ctx.agg_prices = {"AK-47": {"best_ask": 10.0}}
        ctx.bulk_fees = {}
        ctx.cs_snapshots = {}
        ctx.current_margin = 0.05

        with patch("src.core.target_sniping.ranking.rank_candidates_by_spread", return_value=ctx.items):
            result = await CycleOrchestrator._stage_evaluate(orch, ctx)

        assert result.instant_buys == []


class TestStageExecute:

    @pytest.mark.asyncio
    async def test_execute_empty_buys_is_noop(self):
        orch = _make_orchestrator()
        ctx = _make_ctx()
        ctx.instant_buys = []

        result = await CycleOrchestrator._stage_execute(orch, ctx)

        orch._execute_buy.assert_not_called()
        assert result.total_spent == 0.0

    @pytest.mark.asyncio
    async def test_execute_calls_buy_for_each_item(self):
        orch = _make_orchestrator()
        orch.client.get_real_balance = AsyncMock(return_value=100.0)

        ctx = _make_ctx()
        ctx.instant_buys = [
            {"title": "Item A", "base_price": 5.0},
            {"title": "Item B", "base_price": 8.0},
        ]

        result = await CycleOrchestrator._stage_execute(orch, ctx)

        assert orch._execute_buy.call_count == 2
        assert result.total_spent == 13.0

    @pytest.mark.asyncio
    async def test_execute_skips_when_insufficient_balance(self):
        orch = _make_orchestrator()
        orch.client.get_real_balance = AsyncMock(return_value=3.0)

        ctx = _make_ctx()
        ctx.instant_buys = [{"title": "Expensive", "base_price": 50.0}]

        result = await CycleOrchestrator._stage_execute(orch, ctx)

        orch._execute_buy.assert_not_called()
        assert result.total_spent == 0.0

    @pytest.mark.asyncio
    async def test_execute_continues_on_buy_error(self):
        orch = _make_orchestrator()
        orch.client.get_real_balance = AsyncMock(return_value=100.0)
        orch._execute_buy = AsyncMock(side_effect=Exception("API 500"))

        ctx = _make_ctx()
        ctx.instant_buys = [{"title": "Item", "base_price": 5.0}]

        result = await CycleOrchestrator._stage_execute(orch, ctx)

        assert result.total_spent == 0.0


class TestStagePostprocess:

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_postprocess_calls_resale(self, mock_db):
        orch = _make_orchestrator()
        orch.deep_scan_counter = 1
        orch.reprice_counter = 60
        orch.client.get_real_balance = AsyncMock(return_value=100.0)
        orch.risk.get_state.return_value = MagicMock(current_drawdown_pct=0.0)

        ctx = _make_ctx(balance=100.0)
        ctx.balance_before = 100.0
        ctx.total_spent = 5.0

        await CycleOrchestrator._stage_postprocess(orch, ctx)

        orch.auto_resale.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_postprocess_calls_reprice(self, mock_db):
        orch = _make_orchestrator()
        orch.deep_scan_counter = 1
        orch.reprice_counter = 60
        orch.client.get_real_balance = AsyncMock(return_value=100.0)
        orch.risk.get_state.return_value = MagicMock(current_drawdown_pct=0.0)

        ctx = _make_ctx(balance=100.0)
        ctx.balance_before = 100.0

        await CycleOrchestrator._stage_postprocess(orch, ctx)

        orch.reprice_unsold_offers.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_postprocess_tracks_balance_after(self, mock_db):
        orch = _make_orchestrator()
        orch.deep_scan_counter = 1
        orch.reprice_counter = 1
        orch.client.get_real_balance = AsyncMock(return_value=120.0)
        orch.risk.get_state.return_value = MagicMock(current_drawdown_pct=0.0)

        ctx = _make_ctx(balance=100.0)
        ctx.balance_before = 100.0
        ctx.total_spent = 10.0

        await CycleOrchestrator._stage_postprocess(orch, ctx)

        assert ctx.balance_after == 120.0
        assert ctx.total_earned == 30.0

    @pytest.mark.asyncio
    @patch("src.core.target_sniping.cycle_orchestrator.price_db")
    async def test_postprocess_handles_resale_error(self, mock_db):
        orch = _make_orchestrator()
        orch.deep_scan_counter = 1
        orch.reprice_counter = 1
        orch.auto_resale = AsyncMock(side_effect=Exception("resale boom"))
        orch.client.get_real_balance = AsyncMock(return_value=100.0)
        orch.risk.get_state.return_value = MagicMock(current_drawdown_pct=0.0)

        ctx = _make_ctx(balance=100.0)
        ctx.balance_before = 100.0

        await CycleOrchestrator._stage_postprocess(orch, ctx)


class TestStageOrder:

    @pytest.mark.asyncio
    async def test_stages_execute_in_order(self):
        call_order = []

        class OrderedOrchestrator(CycleOrchestrator):
            async def _stage_prepare(self, ctx):
                call_order.append("prepare")
                ctx.oracle = MagicMock()
                return ctx

            async def _stage_scan(self, ctx):
                call_order.append("scan")
                ctx.agg_prices = {"test": {}}
                ctx.items = [{"itemId": "1"}]
                return ctx

            async def _stage_prefetch(self, ctx):
                call_order.append("prefetch")
                return ctx

            async def _stage_evaluate(self, ctx):
                call_order.append("evaluate")
                return ctx

            async def _stage_execute(self, ctx):
                call_order.append("execute")
                return ctx

            async def _stage_postprocess(self, ctx):
                call_order.append("postprocess")

        orch = OrderedOrchestrator()
        orch.client = AsyncMock()

        ctx = CycleContext(game_id="a8db")
        ctx = await orch._stage_prepare(ctx)
        ctx = await orch._stage_scan(ctx)
        ctx = await orch._stage_prefetch(ctx)
        ctx = await orch._stage_evaluate(ctx)
        ctx = await orch._stage_execute(ctx)
        await orch._stage_postprocess(ctx)

        assert call_order == ["prepare", "scan", "prefetch", "evaluate", "execute", "postprocess"]
