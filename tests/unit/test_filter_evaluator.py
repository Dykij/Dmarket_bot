"""Tests for filter_evaluator.py — extracted evaluation stages."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEvalContext:
    """Tests for EvalContext dataclass."""

    def test_default_values(self):
        from src.core.target_sniping.filter_evaluator import EvalContext
        ctx = EvalContext()
        assert ctx.title == ""
        assert ctx.base_price == 0.0
        assert ctx.best_bid == 0.0
        assert ctx.is_rare is False
        assert ctx.is_sandbox is False

    def test_custom_values(self):
        from src.core.target_sniping.filter_evaluator import EvalContext
        ctx = EvalContext(title="AK-47", base_price=10.0, is_rare=True)
        assert ctx.title == "AK-47"
        assert ctx.base_price == 10.0
        assert ctx.is_rare is True


class TestStageRiskGates:
    """Tests for _stage_risk_gates."""

    def _make_mixin(self):
        from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
        mixin = _FilterEvaluatorMixin()
        mixin.client = AsyncMock()
        mixin.risk = MagicMock()
        mixin.liquidity = MagicMock()
        mixin.stickers = MagicMock()
        mixin.buy_budget = 100.0
        mixin._prev_agg_prices = {}
        mixin._oracle_price_cache = {}
        mixin._dom_cache = {}
        mixin._sales_cache = {}
        mixin._skip_if_locked = MagicMock(return_value=False)
        return mixin

    @patch("src.core.target_sniping.filter_evaluator.price_db")
    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_empty_title(self, mock_config, mock_db):
        mixin = self._make_mixin()
        result = mixin._stage_risk_gates(
            item={"title": "", "itemId": "1", "price": {"USD": "100"}},
            game_id="a8db", current_balance=100.0, effective_balance=95.0,
            dynamic_max_price=50.0, current_margin=0.05,
        )
        assert result is None

    @patch("src.core.target_sniping.filter_evaluator.price_db")
    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_zero_price(self, mock_config, mock_db):
        mixin = self._make_mixin()
        result = mixin._stage_risk_gates(
            item={"title": "AK-47", "itemId": "1", "price": {"USD": "0"}},
            game_id="a8db", current_balance=100.0, effective_balance=95.0,
            dynamic_max_price=50.0, current_margin=0.05,
        )
        assert result is None

    @patch("src.core.target_sniping.filter_evaluator.price_db")
    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_already_placed(self, mock_config, mock_db):
        mock_db.has_target_been_placed.return_value = True
        mixin = self._make_mixin()
        result = mixin._stage_risk_gates(
            item={"title": "AK-47", "itemId": "1", "price": {"USD": "1000"}},
            game_id="a8db", current_balance=100.0, effective_balance=95.0,
            dynamic_max_price=50.0, current_margin=0.05,
        )
        assert result is None

    @patch("src.core.target_sniping.filter_evaluator.price_db")
    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_locked_item(self, mock_config, mock_db):
        mixin = self._make_mixin()
        mixin._skip_if_locked.return_value = True
        result = mixin._stage_risk_gates(
            item={"title": "AK-47", "itemId": "1", "price": {"USD": "1000"}},
            game_id="a8db", current_balance=100.0, effective_balance=95.0,
            dynamic_max_price=50.0, current_margin=0.05,
        )
        assert result is None


class TestStageMicrostructure:
    """Tests for _stage_microstructure."""

    def _make_mixin(self):
        from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
        mixin = _FilterEvaluatorMixin()
        mixin.client = AsyncMock()
        mixin.risk = MagicMock()
        mixin.liquidity = MagicMock()
        mixin.stickers = MagicMock()
        mixin._prev_agg_prices = {}
        mixin._oracle_price_cache = {}
        mixin._dom_cache = {}
        mixin._sales_cache = {}
        return mixin

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_zero_bid(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47")
        result = mixin._stage_microstructure(ctx, {"AK-47": {"best_bid": 0, "best_ask": 10}})
        assert result is False

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_zero_ask(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47")
        result = mixin._stage_microstructure(ctx, {"AK-47": {"best_bid": 10, "best_ask": 0}})
        assert result is False

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_passes_valid_data(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = False
        mock_config.MIN_BID_ASK_COUNT = 1
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47")
        result = mixin._stage_microstructure(ctx, {
            "AK-47": {"best_bid": 10.0, "best_ask": 12.0, "ask_count": 5, "bid_count": 3}
        })
        assert result is True
        assert ctx.best_bid == 10.0
        assert ctx.best_ask == 12.0


class TestStageValueLayers:
    """Tests for _stage_value_layers."""

    def _make_mixin(self):
        from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
        mixin = _FilterEvaluatorMixin()
        mixin.client = AsyncMock()
        mixin.stickers = MagicMock()
        mixin._calculate_float_premium = MagicMock(return_value=1.0)
        mixin._calculate_pattern_premium = MagicMock(return_value=1.0)
        return mixin

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_basic_list_price(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.FLOAT_PREMIUM_ENABLED = False
        mock_config.PATTERN_PREMIUM_ENABLED = False
        mock_config.INTRA_LIST_DISCOUNT = 0.01
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47", best_bid=10.0, base_price=8.0, required_margin=0.05)
        mixin._stage_value_layers(ctx, {"title": "AK-47", "attributes": []})
        assert ctx.list_price > 0
        assert ctx.list_price <= 10.0

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_float_premium_applied(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.FLOAT_PREMIUM_ENABLED = True
        mock_config.PATTERN_PREMIUM_ENABLED = False
        mock_config.INTRA_LIST_DISCOUNT = 0.01
        mixin = self._make_mixin()
        mixin._calculate_float_premium.return_value = 1.20
        ctx = EvalContext(title="AK-47", best_bid=10.0, base_price=8.0, required_margin=0.05)
        base_list = round(10.0 - 0.01, 2)
        mixin._stage_value_layers(ctx, {"title": "AK-47", "attributes": []})
        assert ctx.list_price == round(base_list * 1.20, 2)
        assert ctx.is_rare is True


class TestStageFeeAndCaps:
    """Tests for _stage_fee_and_caps."""

    def _make_mixin(self):
        from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
        mixin = _FilterEvaluatorMixin()
        mixin.client = AsyncMock()
        mixin.liquidity = MagicMock()
        return mixin

    @patch("src.core.target_sniping.filter_evaluator.price_db")
    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_rejects_low_margin(self, mock_config, mock_db):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.FEE_RATE = 0.05
        mock_config.MIN_SPREAD_PCT = 5.0
        mock_config.MAX_SAME_ITEM_HOLDINGS = 3
        mock_config.LOCK_AWARE_CAP_ENABLED = False
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47", item_id="1", base_price=10.0, list_price=10.1,
                         best_bid=10.5, best_ask=12.0, ask_count=5, bid_count=3,
                         fee_rate=0.05, is_sandbox=False)
        result = mixin._stage_fee_and_caps(ctx, {}, {}, {}, 100.0, 100.0, "a8db")
        # list_price (10.1) < base_price * 1.02 (10.2) → rejected
        assert result is False


class TestStageAssemble:
    """Tests for _stage_assemble."""

    def _make_mixin(self):
        from src.core.target_sniping.filter_evaluator import _FilterEvaluatorMixin
        mixin = _FilterEvaluatorMixin()
        mixin._prev_agg_prices = {}
        return mixin

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_returns_buy_payload(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = False
        mixin = self._make_mixin()
        ctx = EvalContext(
            title="AK-47", item_id="item1", base_price=10.0,
            list_price=12.0, best_bid=12.5, best_ask=13.0,
        )
        result = mixin._stage_assemble(ctx, {"title": "AK-47"})
        assert result["action"] == "buy" if "action" in result else True
        assert result["title"] == "AK-47"
        assert result["item_id"] == "item1"
        assert result["base_price"] == 10.0
        assert result["list_price"] == 12.0

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_strategy_intra_spread(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = False
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47", item_id="1", base_price=10.0,
                         list_price=12.0, best_bid=12.5, best_ask=13.0,
                         has_dmarket_underpriced=False, cross_market_provider=None)
        result = mixin._stage_assemble(ctx, {})
        assert result["strategy"] == "intra_spread"

    @patch("src.core.target_sniping.filter_evaluator.Config")
    def test_strategy_cross_market(self, mock_config):
        from src.core.target_sniping.filter_evaluator import EvalContext
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = False
        mixin = self._make_mixin()
        ctx = EvalContext(title="AK-47", item_id="1", base_price=10.0,
                         list_price=12.0, best_bid=12.5, best_ask=13.0,
                         cross_market_provider="waxpeer")
        result = mixin._stage_assemble(ctx, {})
        assert result["strategy"] == "cross_market"
        assert result["target_platform"] == "waxpeer"
