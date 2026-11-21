"""Tests for resale_prod.py batch listing response parsing (П.7).

Verifies that offers:batchCreate answers are parsed by assetId (not array index)
via _parse_batch_create_results and applied accurately in _prod_list_unlocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.core.target_sniping.resale_prod import (
    _ResaleProdMixin,
    _parse_batch_create_results,
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


@pytest.fixture(autouse=True)
def _mock_notifier():
    mock_notif = MagicMock()
    mock_notif.buy = AsyncMock()
    with patch("src.core.target_sniping.resale_prod._get_notifier", return_value=mock_notif):
        yield mock_notif


def _mock_db_context() -> MagicMock:
    mock_get_inv = MagicMock(name="get_virtual_inventory", return_value=[])

    async def _mock_run(fn, *args):
        if fn is mock_get_inv:
            return []
        return MagicMock(fetchone=MagicMock(return_value=None))

    mock_db = MagicMock()
    mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
    mock_db.get_virtual_inventory = mock_get_inv
    mock_db.mark_listed = MagicMock()
    mock_db.mark_list_failed = MagicMock()
    return mock_db


def test_parse_batch_create_results_failed_priority_over_index():
    """Item A is in failed[], while offers[0] belongs to Item B.

    Must NOT assign Item B's offerId to Item A!
    """
    resp = {
        "offers": [{"id": "off_B", "assetId": "asset_B"}],
        "failed": [{"assetId": "asset_A", "code": "AlreadyExists", "message": "Already listed"}],
    }
    success_map, failed_map = _parse_batch_create_results(resp)
    assert "asset_A" in failed_map
    assert "Already listed" in failed_map["asset_A"]
    assert "asset_A" not in success_map
    assert success_map == {"asset_B": "off_B"}


@pytest.mark.asyncio
async def test_numeric_ids_on_parser_and_prod_list_unlocked():
    """Numeric assetId/offerId from JSON are normalized to str in parser and call site."""
    resp = {
        "offers": [{"id": 999888, "assetId": 123456}],
        "failed": [{"assetId": 654321, "code": "AlreadyExists"}],
    }
    success_map, failed_map = _parse_batch_create_results(resp)
    assert success_map == {"123456": "999888"}
    assert failed_map == {"654321": "AlreadyExists"}

    # Test via _prod_list_unlocked
    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 1,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": 123456,
                "list_error": None,
            },
            {
                "id": 2,
                "hash_name": "Item 2",
                "buy_price": 20.0,
                "dm_item_id": 654321,
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        listed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_listed
        ]
        assert len(listed_calls) == 1
        assert listed_calls[0][1] == 1
        assert listed_calls[0][2] == "999888"

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 2
        assert "AlreadyExists" in failed_calls[0][2]


@pytest.mark.asyncio
async def test_malformed_response_parser_and_prod_list_unlocked():
    """Non-list offers/failed returns ({}, {}); call site marks 'no offerId in response'."""
    resp = {
        "offers": "not-a-list",
        "failed": 500,
    }
    success_map, failed_map = _parse_batch_create_results(resp)
    assert success_map == {}
    assert failed_map == {}

    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 1,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "asset_1",
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 1
        assert failed_calls[0][2] == "no offerId in response"


@pytest.mark.asyncio
async def test_non_dict_response_parser_and_prod_list_unlocked():
    """Non-dict response returns ({}, {}); call site marks 'no offerId in response'."""
    success_map, failed_map = _parse_batch_create_results("string-response")
    assert success_map == {}
    assert failed_map == {}

    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value="string-response")
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 1,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "asset_1",
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 1
        assert failed_calls[0][2] == "no offerId in response"


@pytest.mark.asyncio
async def test_status_error_variants_prod_list_unlocked():
    """status:'error' with no message or message=None preserves 'error' in error message."""
    for resp in [{"status": "error"}, {"status": "error", "message": None}]:
        mixin = _make_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
        mock_db = _mock_db_context()

        with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
            candidates = [
                {
                    "id": 1,
                    "hash_name": "Item 1",
                    "buy_price": 10.0,
                    "dm_item_id": "asset_1",
                    "list_error": None,
                },
            ]
            await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

            failed_calls = [
                c.args
                for c in mock_db.run_in_thread.call_args_list
                if c.args and c.args[0] == mock_db.mark_list_failed
            ]
            assert len(failed_calls) == 1
            assert failed_calls[0][1] == 1
            assert "error" in failed_calls[0][2]


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
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 1,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "asset_1",
                "list_error": None,
            },
            {
                "id": 2,
                "hash_name": "Item 2",
                "buy_price": 20.0,
                "dm_item_id": "asset_2",
                "list_error": None,
            },
        ]

        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 1  # row_id 1
        assert "Price" in failed_calls[0][2]

        listed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_listed
        ]
        assert len(listed_calls) == 1
        assert listed_calls[0][1] == 2  # row_id 2
        assert listed_calls[0][2] == "off_2"


@pytest.mark.asyncio
async def test_prod_list_unlocked_happy_path_all_listed():
    """All items in batch successfully listed -> mark_listed with correct offerIds."""
    mixin = _make_mixin()
    resp = {
        "offers": [
            {"id": "off_1", "assetId": "asset_1"},
            {"id": "off_2", "assetId": "asset_2"},
        ],
        "failed": [],
    }
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 10,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "asset_1",
                "list_error": None,
            },
            {
                "id": 20,
                "hash_name": "Item 2",
                "buy_price": 20.0,
                "dm_item_id": "asset_2",
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        listed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_listed
        ]
        assert len(listed_calls) == 2
        call_map = {c[1]: c[2] for c in listed_calls}
        assert call_map == {10: "off_1", 20: "off_2"}

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 0


@pytest.mark.asyncio
async def test_parse_batch_create_conflict_asset_in_both_offers_and_failed():
    """If asset is present in both offers[] and failed[], failed[] MUST win."""
    resp = {
        "offers": [{"id": "off_conflict", "assetId": "asset_X"}],
        "failed": [{"assetId": "asset_X", "code": "ItemConflict", "message": "Conflict rejection"}],
    }
    success_map, failed_map = _parse_batch_create_results(resp)
    assert "asset_X" in failed_map
    assert "asset_X" not in success_map

    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 99,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "asset_X",
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 99
        assert "Conflict" in failed_calls[0][2]

        listed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_listed
        ]
        assert len(listed_calls) == 0
