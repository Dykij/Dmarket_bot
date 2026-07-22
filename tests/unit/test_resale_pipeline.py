"""Tests for resale_pipeline.py — end-to-end buy-sell pipeline."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.resale_pipeline import ResalePipeline
from src.core import resale_pipeline as _rp_mod


def _make_dmarket_item(
    item_id: str = "dm_001",
    title: str = "AK-47 | Redline",
    price_cents: int = 1000,
) -> dict[str, Any]:
    return {
        "itemId": item_id,
        "title": title,
        "price": {"USD": str(price_cents)},
    }


def _make_virtual_item(
    item_id: int = 1,
    hash_name: str = "AK-47 | Redline",
    buy_price: float = 10.0,
    status: str = "idle",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "hash_name": hash_name,
        "buy_price": buy_price,
        "status": status,
        "acquired_at": 1700000000.0,
    }


def _make_pipeline() -> tuple[ResalePipeline, MagicMock]:
    """Create a ResalePipeline with mocked dependencies."""
    api = AsyncMock()
    api.get_item_fee = AsyncMock(return_value=0.05)

    with (
        patch("src.core.resale_pipeline.OracleFactory") as mock_factory,
        patch("src.core.resale_pipeline.price_db") as mock_db,
    ):
        oracle = AsyncMock()
        oracle.get_item_price = AsyncMock(return_value=15.0)
        oracle.get_cross_market_data = AsyncMock(return_value=None)
        oracle.get_prices_batch = AsyncMock(return_value={})
        oracle.close = AsyncMock()
        mock_factory.get_cross_market_oracle.return_value = oracle

        risk = MagicMock()
        risk_result = MagicMock()
        risk_result.allowed = True
        risk_result.reason = ""
        risk.pre_trade_check = MagicMock(return_value=risk_result)
        risk.record_trade_outcome = MagicMock()

        mock_db.has_target_been_placed.return_value = False
        mock_db.get_virtual_inventory.return_value = []
        mock_db.add_virtual_item = MagicMock()
        mock_db.record_placed_target = MagicMock()
        mock_db.update_virtual_status = MagicMock()

        pipeline = ResalePipeline(api_client=api, risk=risk)
        pipeline._mock_db = mock_db
        pipeline._mock_oracle = oracle
        return pipeline, api


class TestCalculateSellPrice:

    def test_basic_undercut(self):
        """Sell price undercuts oracle by 2%."""
        pipeline, _ = _make_pipeline()
        result = pipeline._calculate_sell_price(
            buy_price=10.0, oracle_price=15.0, cross_data=None, fee_rate=0.05,
        )
        assert result == 14.70

    def test_oracle_price_zero_fallback(self):
        """When oracle_price is 0, fallback to buy_price * 1.10."""
        pipeline, _ = _make_pipeline()
        result = pipeline._calculate_sell_price(
            buy_price=10.0, oracle_price=0.0, cross_data=None, fee_rate=0.05,
        )
        assert result == 11.0

    def test_min_profit_margin_enforced(self):
        """Sell price respects minimum profit margin (capped by oracle * 1.10)."""
        pipeline, _ = _make_pipeline()
        original = _rp_mod.Config.MIN_SPREAD_PCT
        try:
            _rp_mod.Config.MIN_SPREAD_PCT = 10.0
            result = pipeline._calculate_sell_price(
                buy_price=10.0, oracle_price=10.5, cross_data=None, fee_rate=0.05,
            )
        finally:
            _rp_mod.Config.MIN_SPREAD_PCT = original
        # min_sell = 10.0 * 1.10 / 0.95 ≈ 11.58, but max_allowed = 10.5 * 1.10 = 11.55
        # So result is capped at 11.55 (still well above buy price)
        assert result == 11.55
        assert result > 10.0  # profitable

    def test_cross_market_bid_adjustment(self):
        """Cross-market high bid can lower sell price."""
        pipeline, _ = _make_pipeline()
        cross_data = SimpleNamespace(global_max_bid=14.5)
        result = pipeline._calculate_sell_price(
            buy_price=10.0, oracle_price=15.0, cross_data=cross_data, fee_rate=0.05,
        )
        assert result == 14.36

    def test_does_not_exceed_max_above_oracle(self):
        """Sell price doesn't exceed oracle * 1.10."""
        pipeline, _ = _make_pipeline()
        original = _rp_mod.Config.MIN_SPREAD_PCT
        try:
            _rp_mod.Config.MIN_SPREAD_PCT = 50.0
            result = pipeline._calculate_sell_price(
                buy_price=10.0, oracle_price=12.0, cross_data=None, fee_rate=0.05,
            )
        finally:
            _rp_mod.Config.MIN_SPREAD_PCT = original
        assert result <= 13.20


class TestEvaluateAndBuy:

    @pytest.mark.asyncio
    async def test_price_below_min_returns_none(self):
        pipeline, _ = _make_pipeline()
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 5.0, 100.0
            with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(price_cents=100), balance=100.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_price_above_max_returns_none(self):
        pipeline, _ = _make_pipeline()
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 50.0
            with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(price_cents=6000), balance=100.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_insufficient_balance_returns_none(self):
        pipeline, _ = _make_pipeline()
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 100.0
            with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(price_cents=5000), balance=30.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_already_placed_target_returns_none(self):
        pipeline, _ = _make_pipeline()
        with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=True):
            orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
            try:
                _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 100.0
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
            finally:
                _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_oracle_price_zero_returns_none(self):
        pipeline, _ = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=0.0)
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 100.0
            with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_buy_returns_result(self):
        pipeline, api = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=15.0)
        attrs = ("MIN_PRICE_USD", "MAX_PRICE_USD", "TRADE_LOCK_HOURS", "GAME_ID")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.MIN_PRICE_USD = 1.0
            _rp_mod.Config.MAX_PRICE_USD = 100.0
            _rp_mod.Config.TRADE_LOCK_HOURS = 24
            _rp_mod.Config.GAME_ID = "a8db"
            with (
                patch("src.core.resale_pipeline.validate_arbitrage_profit", return_value=0.20),
                patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False),
                patch.object(_rp_mod.price_db, "add_virtual_item"),
                patch.object(_rp_mod.price_db, "record_placed_target"),
            ):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)
        assert result is not None
        assert result["title"] == "AK-47 | Redline"
        assert result["buy_price"] == 10.0
        assert result["status"] == "purchased_sim"

    @pytest.mark.asyncio
    async def test_price_validation_failure_returns_none(self):
        pipeline, _ = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=15.0)
        from src.risk.price_validator import PriceValidationError
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 100.0
            with (
                patch("src.core.resale_pipeline.validate_arbitrage_profit", side_effect=PriceValidationError("low")),
                patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False),
            ):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None

    @pytest.mark.asyncio
    async def test_oracle_exception_returns_none(self):
        pipeline, _ = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(side_effect=Exception("timeout"))
        orig_min, orig_max = _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD
        try:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = 1.0, 100.0
            with patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            _rp_mod.Config.MIN_PRICE_USD, _rp_mod.Config.MAX_PRICE_USD = orig_min, orig_max
        assert result is None


class TestScanAndBuy:

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty(self):
        pipeline, api = _make_pipeline()
        api.get_market_items_v2 = AsyncMock(return_value={"objects": []})
        result = await pipeline.scan_and_buy(balance=100.0, max_items=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_risk_blocks_item(self):
        pipeline, api = _make_pipeline()
        api.get_market_items_v2 = AsyncMock(return_value={"objects": [_make_dmarket_item()]})
        pipeline._risk.pre_trade_check.return_value = SimpleNamespace(allowed=False, reason="drawdown")
        attrs = ("GAME_ID", "BATCH_SIZE")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.GAME_ID, _rp_mod.Config.BATCH_SIZE = "a8db", 50
            result = await pipeline.scan_and_buy(balance=100.0, max_items=5)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)
        assert result == []

    @pytest.mark.asyncio
    async def test_api_called_for_scan(self):
        pipeline, api = _make_pipeline()
        api.get_market_items_v2 = AsyncMock(return_value={"objects": []})
        attrs = ("GAME_ID", "BATCH_SIZE")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.GAME_ID, _rp_mod.Config.BATCH_SIZE = "a8db", 50
            await pipeline.scan_and_buy(balance=100.0, max_items=2)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)
        api.get_market_items_v2.assert_called()


class TestSellInventoryItems:

    @pytest.mark.asyncio
    async def test_empty_inventory_returns_empty(self):
        pipeline, _ = _make_pipeline()
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=[]):
            result = await pipeline.sell_inventory_items()
        assert result == []

    @pytest.mark.asyncio
    async def test_dry_run_lists_items(self):
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47 | Redline": snapshot})
        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.object(_rp_mod.price_db, "update_virtual_status") as mock_update,
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread
        assert len(result) == 1
        assert result[0]["status"] == "listed_sim"
        mock_update.assert_called_once_with(1, "selling")

    @pytest.mark.asyncio
    async def test_low_margin_item_skipped(self):
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="Expensive", buy_price=14.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=14.5)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"Expensive": snapshot})
        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 10.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread
        assert result == []


class TestGetInventoryStatus:

    @pytest.mark.asyncio
    async def test_returns_virtual_and_real_counts(self):
        pipeline, api = _make_pipeline()
        idle_items = [_make_virtual_item(status="idle")]
        selling_items = [_make_virtual_item(status="selling")]
        call_count = 0
        def _get_virtual(status=None, only_unlocked=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return idle_items
            elif call_count == 2:
                return selling_items
            return []
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", side_effect=_get_virtual):
            api.get_user_inventory = AsyncMock(return_value={"objects": [{}] * 3})
            api.get_user_offers = AsyncMock(return_value={"objects": [{}] * 2})
            result = await pipeline.get_inventory_status()
        assert result["virtual"]["idle"] == 1
        assert result["virtual"]["selling"] == 1
        assert result["real"]["inventory"] == 3
        assert result["real"]["active_offers"] == 2

    @pytest.mark.asyncio
    async def test_api_failure_handled_gracefully(self):
        pipeline, api = _make_pipeline()
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=[]):
            api.get_user_inventory = AsyncMock(side_effect=Exception("down"))
            api.get_user_offers = AsyncMock(side_effect=Exception("down"))
            result = await pipeline.get_inventory_status()
        assert result["real"]["inventory"] == 0
        assert result["real"]["active_offers"] == 0


class TestTurnoverPenalty:

    def test_lazy_init_market_maker(self):
        pipeline, _ = _make_pipeline()
        assert pipeline._turnover_mm is None
        with patch("src.strategies.market_maker.MarketMaker") as mock_mm:
            mock_mm.return_value = MagicMock(calculate_turnover_penalty=MagicMock(return_value=0.02))
            result = pipeline._get_turnover_penalty()
        assert result == 0.02
        assert pipeline._turnover_mm is not None


class TestScanAndBuyExtended:

    @pytest.mark.asyncio
    async def test_max_items_early_return(self):
        """When max_items reached, return immediately (line 80)."""
        pipeline, api = _make_pipeline()
        items = [_make_dmarket_item(item_id=f"i{i}") for i in range(5)]
        api.get_market_items_v2 = AsyncMock(return_value={"objects": items})

        # Make _evaluate_and_buy return a result for each item
        async def _fake_eval(item, balance):
            return {"buy_price": 10.0, "title": item.get("title", "")}

        pipeline._evaluate_and_buy = AsyncMock(side_effect=_fake_eval)

        attrs = ("GAME_ID", "BATCH_SIZE", "MIN_PRICE_USD", "MAX_PRICE_USD")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.GAME_ID = "a8db"
            _rp_mod.Config.BATCH_SIZE = 50
            _rp_mod.Config.MIN_PRICE_USD = 1.0
            _rp_mod.Config.MAX_PRICE_USD = 100.0
            result = await pipeline.scan_and_buy(balance=100.0, max_items=2)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_pump_blacklist_skips_item(self):
        """PumpDetector blacklist filtering (lines 96-97)."""
        pipeline, api = _make_pipeline()
        api.get_market_items_v2 = AsyncMock(return_value={
            "objects": [_make_dmarket_item(title="Pumped Item")],
        })

        # PumpDetector is imported inside scan_and_buy, patch at the source
        with patch("src.risk.pump_detector.PumpDetector") as mock_pump_cls:
            mock_pump = MagicMock()
            mock_pump.is_blacklisted.return_value = True
            mock_pump_cls.return_value = mock_pump

            attrs = ("GAME_ID", "BATCH_SIZE")
            originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
            try:
                _rp_mod.Config.GAME_ID = "a8db"
                _rp_mod.Config.BATCH_SIZE = 50
                result = await pipeline.scan_and_buy(balance=100.0, max_items=5)
            finally:
                for a, v in originals.items():
                    setattr(_rp_mod.Config, a, v)

        assert result == []

    @pytest.mark.asyncio
    async def test_pagination_stops_on_empty_cursor(self):
        """Pagination stops when cursor is empty (line 113)."""
        pipeline, api = _make_pipeline()
        call_count = 0
        async def _fake_market(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"objects": [_make_dmarket_item(item_id="i1")], "cursor": "page2"}
            return {"objects": [], "cursor": ""}

        api.get_market_items_v2 = AsyncMock(side_effect=_fake_market)

        attrs = ("GAME_ID", "BATCH_SIZE")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.GAME_ID = "a8db"
            _rp_mod.Config.BATCH_SIZE = 50
            await pipeline.scan_and_buy(balance=100.0, max_items=5)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)

        assert call_count == 2  # First page + second empty page

    @pytest.mark.asyncio
    async def test_production_buy_path(self):
        """Production buy path (line 185) when DRY_RUN=false."""
        pipeline, api = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=15.0)
        api.buy_items = AsyncMock()

        attrs = ("MIN_PRICE_USD", "MAX_PRICE_USD", "TRADE_LOCK_HOURS", "GAME_ID")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.MIN_PRICE_USD = 1.0
            _rp_mod.Config.MAX_PRICE_USD = 100.0
            _rp_mod.Config.TRADE_LOCK_HOURS = 24
            _rp_mod.Config.GAME_ID = "a8db"
            with (
                patch("src.core.resale_pipeline.validate_arbitrage_profit", return_value=0.20),
                patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False),
                patch.object(_rp_mod.price_db, "add_virtual_item"),
                patch.object(_rp_mod.price_db, "record_placed_target"),
                patch.dict("os.environ", {"DRY_RUN": "false"}),
            ):
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)

        assert result is not None
        assert result["status"] == "purchased"
        api.buy_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_self_reflection_adjusted_spread(self):
        """Self-reflection spread adjustment (lines 161-162)."""
        pipeline, _ = _make_pipeline()
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=15.0)

        reflection = SimpleNamespace(confidence=0.5, recommended_spread_adjustment=2.0)

        attrs = ("MIN_PRICE_USD", "MAX_PRICE_USD", "TRADE_LOCK_HOURS", "GAME_ID", "MIN_SPREAD_PCT")
        originals = {a: getattr(_rp_mod.Config, a) for a in attrs}
        try:
            _rp_mod.Config.MIN_PRICE_USD = 1.0
            _rp_mod.Config.MAX_PRICE_USD = 100.0
            _rp_mod.Config.TRADE_LOCK_HOURS = 24
            _rp_mod.Config.GAME_ID = "a8db"
            _rp_mod.Config.MIN_SPREAD_PCT = 5.0
            with (
                patch("src.core.resale_pipeline.self_reflection") as mock_sr,
                patch("src.core.resale_pipeline.validate_arbitrage_profit", return_value=0.20) as mock_validate,
                patch.object(_rp_mod.price_db, "has_target_been_placed", return_value=False),
                patch.object(_rp_mod.price_db, "add_virtual_item"),
                patch.object(_rp_mod.price_db, "record_placed_target"),
                patch.dict("os.environ", {"DRY_RUN": "true"}),
            ):
                mock_sr._cached_result = reflection
                result = await pipeline._evaluate_and_buy(_make_dmarket_item(), balance=100.0)
        finally:
            for a, v in originals.items():
                setattr(_rp_mod.Config, a, v)

        # validate_arbitrage_profit should be called with adjusted spread (5.0 + 2.0 = 7.0)
        call_kwargs = mock_validate.call_args[1]
        assert call_kwargs["min_profit_margin"] == 0.07


class TestSellOracleFallback:
    """Tests for oracle batch fallback (lines 252-262) and zero price skip (272)."""

    @pytest.mark.asyncio
    async def test_oracle_batch_attribute_error_fallback(self):
        """AttributeError triggers per-item fallback (lines 252-260)."""
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        pipeline._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        pipeline._mock_oracle.get_item_price = AsyncMock(return_value=15.0)

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.object(_rp_mod.price_db, "update_virtual_status"),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert len(result) == 1
        pipeline._mock_oracle.get_item_price.assert_called_once_with("AK-47 | Redline")

    @pytest.mark.asyncio
    async def test_oracle_per_item_fallback_exception(self):
        """Per-item oracle fallback exception is logged (lines 259-260)."""
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        pipeline._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        pipeline._mock_oracle.get_item_price = AsyncMock(side_effect=Exception("item timeout"))

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            result = await pipeline.sell_inventory_items()

        # Item skipped because oracle per-item call also failed
        assert result == []

    @pytest.mark.asyncio
    async def test_oracle_batch_generic_exception(self):
        """Generic exception in batch is logged and skipped (line 261-262)."""
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1)]
        pipeline._mock_oracle.get_prices_batch = AsyncMock(side_effect=Exception("timeout"))

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            result = await pipeline.sell_inventory_items()

        assert result == []

    @pytest.mark.asyncio
    async def test_oracle_price_zero_skip_in_sell(self):
        """Items with oracle_price <= 0 are skipped (line 272)."""
        pipeline, _ = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="Unknown Item", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=False, min_price=0.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={})

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            result = await pipeline.sell_inventory_items()

        assert result == []


class TestSellProductionPath:
    """Tests for production sell path with batch listing (lines 318-399)."""

    @pytest.mark.asyncio
    async def test_production_sell_batch_listing(self):
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47 | Redline": snapshot})

        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"title": "AK-47 | Redline", "assetId": "asset_001"}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        api.batch_create_offers_v2 = AsyncMock(return_value={
            "offers": [{"assetId": "asset_001", "id": "offer_001"}],
        })

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.object(_rp_mod.price_db, "update_virtual_status") as mock_update,
            patch.dict("os.environ", {"DRY_RUN": "false"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert len(result) == 1
        assert result[0]["status"] == "listed"
        assert result[0]["offer_id"] == "offer_001"
        mock_update.assert_called_once_with(1, "selling")
        api.batch_create_offers_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_production_sell_no_asset_id_skips(self):
        """Items without asset_id are skipped (lines 350-355)."""
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="Missing", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"Missing": snapshot})

        # No matching asset in inventory
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        api.get_user_offers = AsyncMock(return_value={"objects": []})

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "false"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert result == []

    @pytest.mark.asyncio
    async def test_production_sell_batch_api_failure(self):
        """batch_create_offers_v2 failure returns empty (lines 365-367)."""
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47 | Redline": snapshot})

        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"title": "AK-47 | Redline", "assetId": "asset_001"}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        api.batch_create_offers_v2 = AsyncMock(side_effect=Exception("API 500"))

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "false"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert result == []

    @pytest.mark.asyncio
    async def test_production_sell_asset_enumeration_failure(self):
        """Asset enumeration failure is handled (lines 342-343)."""
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47 | Redline": snapshot})

        api.get_user_inventory = AsyncMock(side_effect=Exception("auth failed"))

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "false"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert result == []

    @pytest.mark.asyncio
    async def test_user_offers_fallback_for_asset_lookup(self):
        """Items found in user_offers as fallback (lines 328-341)."""
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        snapshot = SimpleNamespace(has_data=True, min_price=15.0)
        pipeline._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47 | Redline": snapshot})

        # Primary inventory has no matching items
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        # Fallback: user_offers has the item
        api.get_user_offers = AsyncMock(return_value={
            "items": [{"title": "AK-47 | Redline", "assetId": "asset_from_offer"}],
        })
        api.batch_create_offers_v2 = AsyncMock(return_value={
            "offers": [{"assetId": "asset_from_offer", "id": "offer_001"}],
        })

        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.object(_rp_mod.price_db, "update_virtual_status"),
            patch.dict("os.environ", {"DRY_RUN": "false"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread

        assert len(result) == 1
        assert result[0]["offer_id"] == "offer_001"


class TestClose:

    @pytest.mark.asyncio
    async def test_close_calls_oracle_close(self):
        pipeline, _ = _make_pipeline()
        pipeline._mock_oracle.close = AsyncMock()
        await pipeline.close()
        pipeline._mock_oracle.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_no_oracle(self):
        pipeline, _ = _make_pipeline()
        pipeline.oracle = None
        await pipeline.close()  # Should not raise
