"""Tests for filter.py — per-item candidate evaluation with deep mixin mocking."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.filter import _FilterMixin


def _make_item(
    title: str = "AK-47 | Redline",
    item_id: str = "item_001",
    price_cents: int = 1000,
):
    return {"title": title, "itemId": item_id, "price": {"USD": str(price_cents)}}


def _make_ms_result(passed=True, reason=""):
    return SimpleNamespace(
        passed=passed, reason=reason, vwap_signal=0.0, cvd=0.0, vpin=0.0,
        trade_records=[], vol_regime="medium", hawkes_activity="normal",
        bollinger_squeeze="normal", bollinger_pctb=0.5, dema_crossover="neutral",
        macd_signal="neutral", hurst_exponent=None, hmm_regime="",
    )


def _make_mixin() -> MagicMock:
    mixin = MagicMock(spec=_FilterMixin)
    mixin.client = AsyncMock()
    mixin.client.get_item_fee = AsyncMock(return_value=0.05)
    mixin.buy_budget = 100.0
    mixin.liquidity = MagicMock()
    mixin.liquidity.can_spend = MagicMock(return_value=True)
    mixin._diag_cycle_id = -1
    mixin._oracle_price_cache = {}
    mixin._skip_if_locked = MagicMock(return_value=False)
    mixin._calculate_float_premium = MagicMock(return_value=1.0)
    mixin._calculate_pattern_premium = MagicMock(return_value=1.0)
    mixin.is_dirty_bs = MagicMock(return_value=False)
    mixin.risk = MagicMock()
    risk_result = MagicMock()
    risk_result.allowed = True
    risk_result.reason = ""
    risk_result.adjusted_size_usd = None
    mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)
    mixin.risk.get_state = MagicMock(return_value=MagicMock(
        win_rate=0.55, win_loss_ratio=1.5, total_wins=10, total_losses=5,
    ))
    return mixin


_DEFAULT_CFG = {
    "MIN_PRICE_USD": 0.10, "DRY_RUN": True, "MAX_SNIPING_PRICE_USD": 100.0,
    "MAX_POSITION_RISK_PCT": 10.0, "KELLY_ENABLED": False,
    "FLOAT_PREMIUM_ENABLED": False, "DIRTY_BS_ENABLED": False,
    "FILLER_TRACKING_ENABLED": False, "PATTERN_PREMIUM_ENABLED": False,
    "FLOAT_DATE_ENABLED": False, "STRICT_MICROSTRUCTURE_FILTERS": False,
    "USE_LIQUIDITY_FILTER": False, "WASH_TRADING_DETECTION": False,
    "SEASONAL_TIMING_ENABLED": False, "INTRA_MIN_SPREAD_PCT": 0.1,
    "INTRA_LIST_DISCOUNT": 0.01, "FEE_RATE": 0.05, "MIN_SPREAD_PCT": 0.1,
    "WITHDRAWAL_FEE_RATE": 0.005, "MIN_BID_ASK_COUNT": 1,
    "MAX_SAME_ITEM_HOLDINGS": 3, "LOCK_AWARE_CAP_ENABLED": False,
    "TRADE_LOCK_HOURS": 24, "COMMISSION_OPTIMIZER_ENABLED": False,
    "BAIT_DETECTION_ENABLED": False,
}


@contextmanager
def _patch_filter(ms_result=None, cross_market=None, fee_result=None, cfg=None):
    """Context manager that applies all common filter patches."""
    ms_result = ms_result or _make_ms_result()
    cross_market = cross_market or {"provider": None, "bid": 0.0, "is_viable": False}
    fee_result = fee_result or {"pass": True, "reason": None}
    mock_config = MagicMock(**{**_DEFAULT_CFG, **(cfg or {})})

    with (
        patch("src.core.target_sniping.filter.Config", mock_config),
        patch("src.core.target_sniping.filter.price_db") as mock_db,
        patch("src.core.target_sniping.filter.run_microstructure_pipeline", return_value=ms_result),
        patch("src.core.target_sniping.filter.evaluate_cross_market_arb", return_value=cross_market),
        patch("src.core.target_sniping.filter.evaluate_fee_slippage_tod", return_value=fee_result),
        patch("src.core.target_sniping.filter.check_bait_detection", return_value={"pass": True}),
        patch("src.core.target_sniping.filter.validate_volatility"),
    ):
        mock_db.has_target_been_placed.return_value = False
        mock_db.is_crashing.return_value = False
        mock_db.get_recent_prices.return_value = [(10.0, 1000)] * 20
        mock_db.get_low_fee_rate.return_value = None
        mock_db.get_liquidity_metrics.return_value = {"is_liquid": True, "reason": "", "total_sales": 10}
        mock_db.detect_wash_trading.return_value = True
        mock_db.get_virtual_inventory_locked_value.return_value = 0.0
        mock_db.record_missed_opportunity = MagicMock()
        mock_db.log_decision = MagicMock()
        yield mock_db


class TestEvaluateCandidateFullFlow:

    @pytest.mark.asyncio
    async def test_successful_intra_spread(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter() as mock_db:
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None
        assert result["strategy"] == "intra_spread"

    @pytest.mark.asyncio
    async def test_successful_cross_market(self):
        mixin = _make_mixin()
        cross = {"provider": "steam", "bid": 20.0, "is_viable": True}
        agg = {"AK-47 | Redline": {"best_bid": 8.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cross_market=cross):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None
        assert result["strategy"] == "cross_market"

    @pytest.mark.asyncio
    async def test_successful_oracle_discount(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 8.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=20.0)}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_microstructure_fail_returns_none(self):
        mixin = _make_mixin()
        ms = _make_ms_result(passed=False, reason="OBI fail")
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter(ms_result=ms):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_liquidity_filter_blocks(self):
        mixin = _make_mixin()
        mixin.liquidity.can_spend = MagicMock(return_value=False)
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_crashing_item_returns_none(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter() as mock_db:
            mock_db.is_crashing.return_value = True
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_no_spread_no_edge_returns_none(self):
        """No intra-spread, no cross-market, no oracle discount → None."""
        mixin = _make_mixin()
        # bid == ask → no spread, oracle price close to buy → no discount
        agg = {"AK-47 | Redline": {"best_bid": 10.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=10.0)}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_overpriced_vs_oracle_returns_none(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 8.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=5.0)}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_bid_ask_returns_none(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 0, "best_ask": 0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_thin_order_book_returns_none(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 0, "bid_count": 0}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_saturation_blocks(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}
        sat = {"AK-47 | Redline": 3}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, saturation_counts=sat, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_fee_slippage_fail_returns_none(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(fee_result={"pass": False, "reason": "Spread too thin"}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_oracle_cache_hit(self):
        mixin = _make_mixin()
        mixin._oracle_price_cache = {"AK-47 | Redline": 15.0}
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_oracle_fallback_per_item(self):
        mixin = _make_mixin()
        oracle = AsyncMock()
        oracle.get_item_price = AsyncMock(return_value=15.0)
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=oracle,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
                cs_snapshots={},
            )
        assert result is not None
        oracle.get_item_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_price_too_thin_returns_none(self):
        """list_price < base_price * 1.02 → None."""
        mixin = _make_mixin()
        # Oracle price = buy price → list_price barely above base → too thin
        agg = {"AK-47 | Redline": {"best_bid": 10.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=10.0)}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_bulk_fee_used(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter() as mock_db:
            mock_fee = AsyncMock(return_value=0.05)
            mixin.client.get_item_fee = mock_fee
            await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={"item_001": 0.02}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )

    @pytest.mark.asyncio
    async def test_liquidity_filter_enabled(self):
        """USE_LIQUIDITY_FILTER blocks non-liquid items."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"USE_LIQUIDITY_FILTER": True}) as mock_db:
            mock_db.get_liquidity_metrics.return_value = {"is_liquid": False, "reason": "too few sales", "total_sales": 1}
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_wash_trading_blocks(self):
        """WASH_TRADING_DETECTION blocks wash-traded items."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"WASH_TRADING_DETECTION": True}) as mock_db:
            mock_db.detect_wash_trading.return_value = False
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_lock_aware_cap_blocks(self):
        """LOCK_AWARE_CAP_ENABLED blocks when locked value exceeds liquid fraction."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"LOCK_AWARE_CAP_ENABLED": True, "LOCK_AWARE_LIQUID_FRACTION": 0.5}) as mock_db:
            mock_db.get_virtual_inventory_locked_value.return_value = 90.0
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
                effective_balance=100.0,
            )
        assert result is None


class TestEarlyReturns:

    @pytest.mark.asyncio
    async def test_empty_title_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item={"title": "", "itemId": "i1", "price": {"USD": "1000"}},
                game_id="a8db", oracle=None, agg_prices={}, bulk_fees={},
                current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_no_item_id_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item={"title": "AK-47", "price": {"USD": "1000"}},
                game_id="a8db", oracle=None, agg_prices={}, bulk_fees={},
                current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_price_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item={"title": "AK-47", "itemId": "i1", "price": {"USD": "0"}},
                game_id="a8db", oracle=None, agg_prices={}, bulk_fees={},
                current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_already_placed_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter() as mock_db:
            mock_db.has_target_been_placed.return_value = True
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_locked_item_returns_none(self):
        mixin = _make_mixin()
        mixin._skip_if_locked = MagicMock(return_value=True)
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_below_min_price_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(price_cents=1), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_bait_detection_blocks(self):
        mixin = _make_mixin()
        with _patch_filter() as mock_db:
            # Override bait detection to block
            with patch("src.core.target_sniping.filter.check_bait_detection", return_value={"pass": False}):
                result = await _FilterMixin._evaluate_candidate(
                    mixin, item=_make_item(), game_id="a8db", oracle=None,
                    agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
                )
        assert result is None

    @pytest.mark.asyncio
    async def test_above_buy_budget_returns_none(self):
        mixin = _make_mixin()
        mixin.buy_budget = 5.0
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(price_cents=1000), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_above_dynamic_max_price_returns_none(self):
        mixin = _make_mixin()
        with _patch_filter(cfg={"MAX_SNIPING_PRICE_USD": 5.0}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(price_cents=1000), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
                dynamic_max_price=5.0,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_risk_blocks(self):
        mixin = _make_mixin()
        risk_result = MagicMock()
        risk_result.allowed = False
        risk_result.reason = "drawdown"
        risk_result.adjusted_size_usd = None
        mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)
        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices={}, bulk_fees={}, current_balance=100.0, current_margin=0.05,
                dynamic_max_price=100.0,
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_oracle_rate_limit_returns_none(self):
        """Oracle rate limit → None."""
        mixin = _make_mixin()
        oracle = AsyncMock()
        oracle.get_item_price = AsyncMock(side_effect=Exception("429 rate limit"))
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}

        with _patch_filter():
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=oracle,
                agg_prices=agg, bulk_fees={}, current_balance=100.0, current_margin=0.05,
                cs_snapshots={},
            )
        assert result is None


class TestValueDetectionLayers:

    @pytest.mark.asyncio
    async def test_float_premium_applied(self):
        mixin = _make_mixin()
        mixin._calculate_float_premium = MagicMock(return_value=1.25)
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"FLOAT_PREMIUM_ENABLED": True}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_pattern_premium_applied(self):
        mixin = _make_mixin()
        mixin._calculate_pattern_premium = MagicMock(return_value=2.0)
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"PATTERN_PREMIUM_ENABLED": True}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None
        assert result["is_rare"] is True

    @pytest.mark.asyncio
    async def test_seasonal_timing_adjustment(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with (
            _patch_filter(cfg={"SEASONAL_TIMING_ENABLED": True}),
            patch("src.analysis.seasonal.get_timing_multiplier", return_value=2.0),
        ):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_composite_score_calculated(self):
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with (
            _patch_filter(cfg={"STRICT_MICROSTRUCTURE_FILTERS": True}),
            patch("src.core.target_sniping.filter.compute_microstructure_scores", return_value={"composite_score": 0.8, "components": {}}),
        ):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_low_fee_override(self):
        """Low-fee override from _low_fee_rate attribute."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}
        item = _make_item()
        item["_low_fee_rate"] = 0.02

        with _patch_filter() as mock_db:
            mock_db.get_low_fee_rate.return_value = None
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=item, game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_cached_low_fee_used(self):
        """Cached low fee rate from price_db."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter() as mock_db:
            mock_db.get_low_fee_rate.return_value = 0.01
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None


class TestKellySizing:

    @pytest.mark.asyncio
    async def test_kelly_enabled_reduces_max_price(self):
        """Kelly sizing with high risk reduces effective max price."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"KELLY_ENABLED": True, "KELLY_FLOOR_PCT": 1.0, "KELLY_FRACTION": 0.5}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap, effective_balance=100.0,
                dynamic_max_price=100.0,
            )
        # Kelly with 55% win rate and 1.5 WLR should allow the trade
        assert result is not None

    @pytest.mark.asyncio
    async def test_kelly_risk_state_unavailable_fallback(self):
        """When risk state raises, use conservative half-cap fallback."""
        mixin = _make_mixin()
        mixin.risk.get_state = MagicMock(side_effect=Exception("no state"))
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"KELLY_ENABLED": True, "MAX_POSITION_RISK_PCT": 10.0}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap, effective_balance=100.0,
                dynamic_max_price=100.0,
            )
        # Half-cap fallback = 5% of 100 = $5 max. Item is $10 → blocked.
        assert result is None


class TestDMarketUnderpriced:

    @pytest.mark.asyncio
    async def test_dmarket_underpriced_detected(self):
        """DMarket underpriced detection when no other edge exists."""
        mixin = _make_mixin()
        # No spread, no cross-market, no oracle discount
        agg = {"AK-47 | Redline": {"best_bid": 10.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=10.0)}

        with (
            _patch_filter(),
            patch("src.core.target_sniping.underpriced.is_dmarket_underpriced", new_callable=AsyncMock) as mock_up,
        ):
            mock_up.return_value = {"underpriced": True, "reference_price": 15.0, "margin_pct": 30.0}
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None
        assert result["strategy"] == "dmarket_underpriced"

    @pytest.mark.asyncio
    async def test_dmarket_underpriced_exception_handled(self):
        """Underpriced check exception is caught."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 10.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=10.0)}

        with (
            _patch_filter(),
            patch("src.core.target_sniping.underpriced.is_dmarket_underpriced", new_callable=AsyncMock) as mock_up,
        ):
            mock_up.side_effect = Exception("API error")
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        # Falls through to "no edge" → None
        assert result is None


class TestDirtyBsLayer:

    @pytest.mark.asyncio
    async def test_dirty_bs_applied(self):
        """Dirty BS detection applies 1.10x multiplier (lines 488-494)."""
        mixin = _make_mixin()
        mixin.is_dirty_bs = MagicMock(return_value=True)
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"DIRTY_BS_ENABLED": True}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_dirty_bs_exception_handled(self):
        """Dirty BS exception is caught (line 493-494)."""
        mixin = _make_mixin()
        mixin.is_dirty_bs = MagicMock(side_effect=ValueError("bad float"))
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with _patch_filter(cfg={"DIRTY_BS_ENABLED": True}):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None


class TestFillerLayer:

    @pytest.mark.asyncio
    async def test_filler_multiplier_applied(self):
        """Filler demand multiplier applied (lines 498-506)."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with (
            _patch_filter(cfg={"FILLER_TRACKING_ENABLED": True}),
            patch("src.analytics.filler_tracker.get_filler_multiplier", return_value=1.15),
        ):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_filler_exception_handled(self):
        """Filler exception is caught (line 505-506)."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}

        with (
            _patch_filter(cfg={"FILLER_TRACKING_ENABLED": True}),
            patch("src.analytics.filler_tracker.get_filler_multiplier", side_effect=ImportError("no module")),
        ):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=_make_item(), game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None


class TestFloatDateLayer:

    @pytest.mark.asyncio
    async def test_float_date_applied(self):
        """Float-date detection applies 1.08x multiplier (lines 549-558)."""
        mixin = _make_mixin()
        agg = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        snap = {"AK-47 | Redline": SimpleNamespace(has_data=True, min_price=15.0)}
        item = _make_item()
        item["attributes"] = [{"name": "floatPartValue", "value": "0.21021992"}]

        with (
            _patch_filter(cfg={"FLOAT_DATE_ENABLED": True}),
            patch("src.core.target_sniping.pricing._is_float_date", return_value=True),
        ):
            result = await _FilterMixin._evaluate_candidate(
                mixin, item=item, game_id="a8db", oracle=None,
                agg_prices=agg, bulk_fees={}, current_balance=100.0,
                current_margin=0.05, cs_snapshots=snap,
            )
        assert result is not None


class TestEnsureOracleCache:

    def test_creates_cache_if_missing(self):
        mixin = MagicMock()
        del mixin._oracle_price_cache
        _FilterMixin._ensure_oracle_cache(mixin)
        assert mixin._oracle_price_cache == {}

    def test_creates_cache_if_not_dict(self):
        mixin = MagicMock()
        mixin._oracle_price_cache = "not_a_dict"
        _FilterMixin._ensure_oracle_cache(mixin)
        assert mixin._oracle_price_cache == {}

    def test_preserves_existing_cache(self):
        mixin = MagicMock()
        mixin._oracle_price_cache = {"AK-47": 15.0}
        _FilterMixin._ensure_oracle_cache(mixin)
        assert mixin._oracle_price_cache == {"AK-47": 15.0}


class TestClearOracleCache:

    def test_clears_cache(self):
        mixin = MagicMock()
        mixin._oracle_price_cache = {"AK-47": 15.0, "M4A4": 20.0}
        _FilterMixin._clear_oracle_cache(mixin)
        assert mixin._oracle_price_cache == {}


class TestRankCandidatesBySpread:

    def test_delegates_to_ranking_module(self):
        items = [{"title": "A"}]
        agg = {"A": {"best_bid": 12.0, "best_ask": 10.0}}
        with patch("src.core.target_sniping.filter.rank_candidates_by_spread") as mock_rank:
            mock_rank.return_value = [("A", 1.5)]
            result = _FilterMixin._rank_candidates_by_spread(items, agg)
        assert result == [("A", 1.5)]
        mock_rank.assert_called_once_with(items, agg, None)
