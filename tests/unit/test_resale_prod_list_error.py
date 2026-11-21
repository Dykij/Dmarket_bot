"""Tests for resale_prod.py list_error handling and transient error mitigation (ШАГ 3).

Verifies that unknown outcomes and transient failures (Internal/UNAVAILABLE)
do NOT set list_error, leaving items idle for retry in subsequent cycles.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from tenacity import RetryError

from src.api.dmarket_api_client.backoff import CircuitOpenError
from src.core.target_sniping.resale_prod import (
    _ResaleProdMixin,
    _is_unknown_outcome,
    _transient_failed_ids,
)
from src.db.price_history.core import PriceHistoryDB


def _make_mixin() -> MagicMock:
    mixin = MagicMock(spec=_ResaleProdMixin)
    mixin.client = AsyncMock()
    mixin._background_tasks = set()
    mixin._current_agg_prices = {
        "Item 1": {"best_bid": 15.0, "best_ask": 16.0},
        "Item 2": {"best_bid": 25.0, "best_ask": 26.0},
        "Item 3": {"best_bid": 35.0, "best_ask": 36.0},
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


def _client_response_err(status: int, message: str = "") -> aiohttp.ClientResponseError:
    req_info = MagicMock()
    req_info.real_url = "https://api.dmarket.com/v2/offers/batch"
    return aiohttp.ClientResponseError(req_info, (), status=status, message=message)


def test_unknown_outcome_exceptions():
    """Verify _is_unknown_outcome accurately identifies retryable network/server faults."""
    # Transient / unknown outcome errors
    assert _is_unknown_outcome(asyncio.TimeoutError()) is True
    assert _is_unknown_outcome(TimeoutError()) is True
    assert _is_unknown_outcome(aiohttp.ServerDisconnectedError()) is True
    assert _is_unknown_outcome(aiohttp.ClientConnectionError("conn reset")) is True
    assert _is_unknown_outcome(RetryError(None)) is True
    assert _is_unknown_outcome(_client_response_err(500)) is True
    assert _is_unknown_outcome(_client_response_err(503)) is True
    assert _is_unknown_outcome(_client_response_err(429)) is True
    assert _is_unknown_outcome(CircuitOpenError("dmarket", 12.5)) is True

    # Definite rejections / client errors / non-transient
    assert _is_unknown_outcome(_client_response_err(400)) is False
    assert _is_unknown_outcome(_client_response_err(403)) is False
    assert _is_unknown_outcome(ValueError("Invalid payload")) is False
    assert _is_unknown_outcome(KeyError("missing_key")) is False


@pytest.mark.asyncio
async def test_prod_list_unlocked_unknown_outcome_exceptions_do_not_mark_failed():
    """Network/server failures must NOT mark_list_failed so items can be retried next cycle."""
    unknown_exceptions = [
        asyncio.TimeoutError(),
        aiohttp.ServerDisconnectedError(),
        _client_response_err(500),
        _client_response_err(503),
        _client_response_err(429),
        RetryError(None),
        CircuitOpenError("dmarket", 12.5),
    ]

    for exc in unknown_exceptions:
        mixin = _make_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock(side_effect=exc)
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
            assert len(failed_calls) == 0, (
                f"Expected 0 mark_list_failed for {exc!r}, got {failed_calls}"
            )

            listed_calls = [
                c.args
                for c in mock_db.run_in_thread.call_args_list
                if c.args and c.args[0] == mock_db.mark_listed
            ]
            assert len(listed_calls) == 0


@pytest.mark.asyncio
async def test_prod_list_unlocked_definite_rejections_mark_failed():
    """Client errors (400, 403, ValueError) must still mark_list_failed for all items in chunk."""
    definite_exceptions = [
        _client_response_err(400, "Bad Request"),
        _client_response_err(403, "Forbidden"),
        ValueError("Invalid amount"),
    ]

    for exc in definite_exceptions:
        mixin = _make_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock(side_effect=exc)
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

            failed_calls = [
                c.args
                for c in mock_db.run_in_thread.call_args_list
                if c.args and c.args[0] == mock_db.mark_list_failed
            ]
            assert len(failed_calls) == 2, (
                f"Expected 2 mark_list_failed for {exc!r}, got {failed_calls}"
            )
            row_ids = {c[1] for c in failed_calls}
            assert row_ids == {10, 20}


@pytest.mark.asyncio
async def test_transient_fail_codes_in_failed_map_do_not_mark_failed():
    """Failed items with code:Internal or reasonCode:UNAVAILABLE must not get marked failed."""
    transient_cases = [
        {"assetId": "a1", "code": "Internal", "message": "Internal error"},
        {"assetId": "a1", "reasonCode": "UNAVAILABLE", "message": "Service unavailable"},
        {"assetId": "a1", "code": "internal", "message": "lowercase internal"},
        {"assetId": "a1", "reasonCode": "unavailable", "message": "lowercase unavailable"},
    ]

    for item_fail in transient_cases:
        resp = {"offers": [], "failed": [item_fail]}
        assert _transient_failed_ids(resp) == {"a1"}

        mixin = _make_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
        mock_db = _mock_db_context()

        with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
            candidates = [
                {
                    "id": 1,
                    "hash_name": "Item 1",
                    "buy_price": 10.0,
                    "dm_item_id": "a1",
                    "list_error": None,
                },
            ]
            await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

            failed_calls = [
                c.args
                for c in mock_db.run_in_thread.call_args_list
                if c.args and c.args[0] == mock_db.mark_list_failed
            ]
            assert len(failed_calls) == 0, (
                f"Expected no mark_list_failed for {item_fail!r}, got {failed_calls}"
            )

    # Permanent failure code PriceTooLow MUST call mark_list_failed
    perm_resp = {
        "offers": [],
        "failed": [{"assetId": "a1", "code": "PriceTooLow", "message": "Price too low"}],
    }
    assert _transient_failed_ids(perm_resp) == set()

    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=perm_resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 1,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "a1",
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
        assert "Price" in failed_calls[0][2]


@pytest.mark.asyncio
async def test_mixed_batch_response_handling():
    """Mixed batch with one success, one transient, and one permanent failure."""
    resp = {
        "offers": [{"id": "off_1", "assetId": "a1"}],
        "failed": [
            {"assetId": "a2", "reasonCode": "UNAVAILABLE", "message": "Try again later"},
            {"assetId": "a3", "code": "PriceTooLow", "message": "Price too low"},
        ],
    }

    mixin = _make_mixin()
    mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)
    mock_db = _mock_db_context()

    with patch("src.core.target_sniping.resale_prod.price_db", mock_db):
        candidates = [
            {
                "id": 100,
                "hash_name": "Item 1",
                "buy_price": 10.0,
                "dm_item_id": "a1",
                "list_error": None,
            },
            {
                "id": 200,
                "hash_name": "Item 2",
                "buy_price": 20.0,
                "dm_item_id": "a2",
                "list_error": None,
            },
            {
                "id": 300,
                "hash_name": "Item 3",
                "buy_price": 30.0,
                "dm_item_id": "a3",
                "list_error": None,
            },
        ]
        await _ResaleProdMixin._prod_list_unlocked(mixin, candidates, "a8db")

        # Exactly 1 mark_listed for a1
        listed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_listed
        ]
        assert len(listed_calls) == 1
        assert listed_calls[0][1] == 100
        assert listed_calls[0][2] == "off_1"

        # Exactly 1 mark_list_failed for a3 (permanent)
        failed_calls = [
            c.args
            for c in mock_db.run_in_thread.call_args_list
            if c.args and c.args[0] == mock_db.mark_list_failed
        ]
        assert len(failed_calls) == 1
        assert failed_calls[0][1] == 300
        assert "Price too low" in failed_calls[0][2]


@pytest.mark.asyncio
async def test_sqlite_real_db_transient_vs_permanent(tmp_path):
    """Real SQLite: transient error leaves list_error IS NULL and status idle.

    Permanent error populates list_error, disqualifying item from next cycle.
    """
    db = PriceHistoryDB(
        state_db=str(tmp_path / "state.db"), history_db=str(tmp_path / "history.db")
    )
    try:
        # Add 2 items: buy_price=10.0, unlock_at=0 (unlocked)
        db.add_virtual_item("Item 1", 10.0, 0)
        db.add_virtual_item("Item 2", 20.0, 0)
        db.state_conn.execute("UPDATE virtual_inventory SET dm_item_id = 'dm_1' WHERE id = 1")
        db.state_conn.execute("UPDATE virtual_inventory SET dm_item_id = 'dm_2' WHERE id = 2")
        db.state_conn.commit()

        # Batch response: dm_1 is transient (UNAVAILABLE), dm_2 is permanent (PriceTooLow)
        resp = {
            "offers": [],
            "failed": [
                {"assetId": "dm_1", "reasonCode": "UNAVAILABLE", "message": "Unavailable"},
                {"assetId": "dm_2", "code": "PriceTooLow", "message": "Price too low"},
            ],
        }

        mixin = _make_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock(return_value=resp)

        # Candidates before listing
        candidates_before = db.get_virtual_inventory(status="idle", only_unlocked=True)
        assert len(candidates_before) == 2

        with patch("src.core.target_sniping.resale_prod.price_db", db):
            await _ResaleProdMixin._prod_list_unlocked(mixin, candidates_before, "a8db")

        # Verify database state
        row_1 = db.state_conn.execute(
            "SELECT id, status, list_error FROM virtual_inventory WHERE id = 1"
        ).fetchone()
        row_2 = db.state_conn.execute(
            "SELECT id, status, list_error FROM virtual_inventory WHERE id = 2"
        ).fetchone()

        # Item 1 (transient): list_error is NULL, remains idle
        assert row_1["status"] == "idle"
        assert row_1["list_error"] is None

        # Item 2 (permanent): list_error is set, remains idle
        assert row_2["status"] == "idle"
        assert row_2["list_error"] is not None
        assert "Price" in row_2["list_error"]

        # Second cycle: verify combat filter in _prod_list_unlocked skips item with list_error
        candidates_second = db.get_virtual_inventory(status="idle", only_unlocked=True)
        assert len(candidates_second) == 2

        mixin.client.create_sell_offers_batch = AsyncMock(
            return_value={"offers": [{"id": "off_1", "assetId": "dm_1"}], "failed": []}
        )

        with patch("src.core.target_sniping.resale_prod.price_db", db):
            await _ResaleProdMixin._prod_list_unlocked(mixin, candidates_second, "a8db")

        # (a) Check batch payload: only dm_1 was submitted, Item 2 was skipped by combat filter
        call_args = mixin.client.create_sell_offers_batch.call_args
        assert call_args is not None
        called_batch = call_args[0][1]
        assert len(called_batch) == 1
        assert called_batch[0]["item_id"] == "dm_1"

        # (b) Check row 1: listed successfully, list_error is NULL, dm_offer_id matches mark_listed
        row_1_after = db.state_conn.execute(
            "SELECT id, status, dm_offer_id, list_error FROM virtual_inventory WHERE id = 1"
        ).fetchone()
        assert row_1_after["status"] == "listed"
        assert row_1_after["dm_offer_id"] == "off_1"
        assert row_1_after["list_error"] is None

        # (c) Check row 2: remains idle with list_error still set
        row_2_after = db.state_conn.execute(
            "SELECT id, status, list_error FROM virtual_inventory WHERE id = 2"
        ).fetchone()
        assert row_2_after["status"] == "idle"
        assert row_2_after["list_error"] is not None
        assert "Price" in row_2_after["list_error"]
    finally:
        db.close()
