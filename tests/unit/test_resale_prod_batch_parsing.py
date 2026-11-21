"""Tests for resale_prod.py batch listing response parsing (П.7).

Verifies that offers:batchCreate answers are matched by assetId (not array index)
and that failed[] takes priority over index-based lookups.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.core.target_sniping.resale_prod import (
    _ResaleProdMixin,
    _parse_sell_offer_result,
)


def _make_mixin() -> MagicMock:
    mixin = MagicMock(spec=_ResaleProdMixin)
    mixin.client = AsyncMock()
    mixin._background_tasks = set()
    mixin._current_agg_prices = {
        "Item 1": {"best_bid": 15.0, "best_ask": 16.0},
        "Item 2": {"best_bid": 25.0, "best_ask": 26.0},
    }
    return mixin


def test_parse_sell_offer_result_failed_priority_over_index():
    """Item A is in failed[], while offers[0] belongs to Item B.

    Must NOT assign Item B's offerId to Item A!
    """
    resp = {
        "offers": [{"id": "off_B", "assetId": "asset_B"}],
        "failed": [{"assetId": "asset_A", "code": "AlreadyExists", "message": "Already listed"}],
    }

    # Item A is index 0 in the request
    off_a, err_a = _parse_sell_offer_result(resp, 0, "asset_A")
    assert off_a is None
    assert err_a is not None
    assert "Already" in err_a or "AlreadyExists" in err_a

    # Item B is index 1 in the request
    off_b, err_b = _parse_sell_offer_result(resp, 1, "asset_B")
    assert off_b == "off_B"
    assert err_b is None


@pytest.mark.asyncio
async def test_prod_list_unlocked_partial_failure_matches_by_asset_id():
    """When the first item in the batch fails, the second item must be marked listed,

    and the first item must be marked failed (not vice versa).
    """
    mixin = _make_mixin()
    resp = {
        "offers": [{"id": "off_2", "assetId": "asset_2"}],
        "failed": [{"assetId": "asset_1", "code": "PriceTooLow", "message": "Price too low"}],
    }
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)

    mock_get_inv = MagicMock(name="get_virtual_inventory", return_value=[])

    async def _mock_run(fn, *args):
        if fn is mock_get_inv:
            return []
        return MagicMock(fetchone=MagicMock(return_value=None))

    with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
        mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
        mock_db.get_virtual_inventory = mock_get_inv
        mock_db.mark_listed = MagicMock()
        mock_db.mark_list_failed = MagicMock()

        candidates = [
            {"id": 1, "hash_name": "Item 1", "buy_price": 10.0, "dm_item_id": "asset_1", "list_error": None},
            {"id": 2, "hash_name": "Item 2", "buy_price": 20.0, "dm_item_id": "asset_2", "list_error": None},
        ]

        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        # Verify DB updates
        # Row 1 (asset_1) must be mark_list_failed
        failed_calls = [c.args for c in mock_db.run_in_thread.call_args_list if c.args and c.args[0] == mock_db.mark_list_failed]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 1  # row_id 1
        assert "Price" in failed_calls[0][2]

        # Row 2 (asset_2) must be mark_listed with off_2
        listed_calls = [c.args for c in mock_db.run_in_thread.call_args_list if c.args and c.args[0] == mock_db.mark_listed]
        assert len(listed_calls) == 1
        assert listed_calls[0][1] == 2  # row_id 2
        assert listed_calls[0][2] == "off_2"



def test_numeric_asset_id_and_offer_id_handled():
    """Numeric assetId/offerId from JSON are normalized to str."""
    resp = {
        "offers": [{"id": 999888, "assetId": 123456}],
        "failed": [{"assetId": 654321, "code": "AlreadyExists"}],
    }
    off_ok, err_ok = _parse_sell_offer_result(resp, 0, "123456")
    assert off_ok == "999888"
    assert err_ok is None

    off_fail, err_fail = _parse_sell_offer_result(resp, 1, "654321")
    assert off_fail is None
    assert err_fail == "AlreadyExists"


def test_malformed_failed_and_offers_does_not_crash():
    """Non-list or non-dict items in failed/offers are safely skipped without crash."""
    resp = {
        "offers": "not-a-list",
        "failed": 500,
    }
    off, err = _parse_sell_offer_result(resp, 0, "asset_1")
    assert off is None
    assert err == "no offerId in response"


@pytest.mark.asyncio
async def test_status_error_without_message_does_not_crash():
    """API response {"status": "error"} without message field does not raise TypeError."""
    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value={"status": "error"})

    mock_get_inv = MagicMock(name="get_virtual_inventory", return_value=[])

    async def _mock_run(fn, *args):
        if fn is mock_get_inv:
            return []
        return MagicMock(fetchone=MagicMock(return_value=None))

    with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
        mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
        mock_db.get_virtual_inventory = mock_get_inv
        mock_db.mark_list_failed = MagicMock()

        candidates = [
            {"id": 1, "hash_name": "Item 1", "buy_price": 10.0, "dm_item_id": "asset_1", "list_error": None},
        ]

        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        failed_calls = [c.args for c in mock_db.run_in_thread.call_args_list if c.args and c.args[0] == mock_db.mark_list_failed]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 1
        assert "error" in failed_calls[0][2]


def test_parse_sell_offer_result_status_error_none_message():
    """When message is explicitly None, returns a valid error string, not (None, None)."""
    resp = {"status": "error", "message": None}
    off, err = _parse_sell_offer_result(resp, 0, "asset_1")
    assert off is None
    assert err is not None
    assert "unknown error" in err
