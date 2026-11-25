"""Tests for buy_offer price amount in _FilterMixin._evaluate_candidate."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.filter import _FilterMixin


def _make_mixin() -> MagicMock:
    mixin = MagicMock(spec=_FilterMixin)
    mixin.client = AsyncMock()
    mixin.buy_budget = 100.0
    mixin._diag_cycle_id = -1
    mixin._extract_and_validate_base_data = _FilterMixin._extract_and_validate_base_data.__get__(mixin)
    mixin._passes_hard_filters = _FilterMixin._passes_hard_filters.__get__(mixin)
    mixin._calculate_position_sizing = _FilterMixin._calculate_position_sizing.__get__(mixin)
    mixin._check_advanced_market_risks = _FilterMixin._check_advanced_market_risks.__get__(mixin)
    mixin._evaluate_edge_strategies = _FilterMixin._evaluate_edge_strategies.__get__(mixin)
    mixin._apply_value_detection_layers = _FilterMixin._apply_value_detection_layers.__get__(mixin)
    mixin._calculate_financial_viability = _FilterMixin._calculate_financial_viability.__get__(mixin)
    mixin._skip_if_locked = AsyncMock(return_value=False)
    mixin.liquidity = MagicMock()
    mixin.liquidity.can_spend = MagicMock(return_value=True)
    mixin.risk = MagicMock()
    mixin.risk.pre_trade_check = MagicMock(return_value=MagicMock(allowed=True, reason="", adjusted_size_usd=None))
    return mixin


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("price_cents", "expected_amount"),
    [
        ("435", "435"),
        ("1550", "1550"),
    ],
)
async def test_evaluate_candidate_buy_offer_amount_in_cents(price_cents: str, expected_amount: str) -> None:
    mixin = _make_mixin()
    item_id = f"offer-{price_cents}"
    item = {"title": "AK-47 | Redline (Field-Tested)", "offerId": item_id, "priceCents": price_cents}
    agg_prices = {
        "AK-47 | Redline (Field-Tested)": {
            "best_bid": 30.0,
            "best_ask": 20.0,
            "ask_count": 5,
            "bid_count": 3,
        }
    }
    ms_result = SimpleNamespace(passed=True, reason="", vwap_signal=0.0, cvd=0.0, vpin=0.0, trade_records=[])
    mock_cfg = MagicMock(
        MIN_PRICE_USD=0.10,
        DRY_RUN=False,
        MAX_SNIPING_PRICE_USD=100.0,
        MAX_POSITION_RISK_PCT=10.0,
        KELLY_ENABLED=False,
        OFI_KELLY_BOOST=0.0,
        STRICT_MICROSTRUCTURE_FILTERS=False,
        SEASONAL_TIMING_ENABLED=False,
        INTRA_MIN_SPREAD_PCT=0.1,
        INTRA_LIST_DISCOUNT=0.01,
        FEE_RATE=0.05,
        MIN_SPREAD_PCT=0.1,
        WITHDRAWAL_FEE_RATE=0.0,
        MIN_BID_ASK_COUNT=1,
    )

    with (
        patch("src.core.target_sniping.filter.Config", mock_cfg),
        patch("src.core.target_sniping.filter.price_db") as mock_db,
        patch("src.core.target_sniping.filter.price_db.run_in_thread", new_callable=AsyncMock, return_value=False),
        patch("src.core.target_sniping.filter.run_microstructure_pipeline", return_value=ms_result),
        patch("src.core.target_sniping.filter.check_bait_detection", return_value={"pass": True}),
        patch.object(mixin, "_apply_value_detection_layers", return_value=(25.0, False)),
        patch.object(mixin, "_calculate_financial_viability", new_callable=AsyncMock, return_value=True),
    ):
        mock_db.is_crashing.return_value = False
        mock_db.get_recent_prices.return_value = [(20.0, 1000)] * 20
        result = await _FilterMixin._evaluate_candidate(
            mixin,
            item=item,
            game_id="a8db",
            agg_prices=agg_prices,
            bulk_fees={},
            current_balance=1000.0,
            current_margin=0.05,
        )

    assert result is not None
    assert result["buy_offer"]["offerId"] == item_id
    assert result["buy_offer"]["price"]["currency"] == "USD"
    assert isinstance(result["buy_offer"]["price"]["amount"], str)
    assert result["buy_offer"]["price"]["amount"] == expected_amount
