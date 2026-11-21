"""Unit tests for offers:batchUpdate response handling in reprice_unsold_offers.

Tests run exclusively via public reprice_unsold_offers with real SQLite price_db
and mocked DMarket API client.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from src.config import Config
from src.core.target_sniping.resale import _ResaleMixin
from src.db.price_history import price_db


class ResaleRunner(_ResaleMixin):
    """Stub runner implementing _ResaleMixin with a mock client."""

    def __init__(self, client: AsyncMock | None = None) -> None:
        self.client = client or AsyncMock()


@pytest.fixture(autouse=True)
def _clean_inventory(monkeypatch: pytest.MonkeyPatch):
    """Ensure clean virtual_inventory table before and after each test."""
    monkeypatch.setattr(Config, "DRY_RUN", False)
    monkeypatch.setattr(Config, "SMART_REPRICE_ENABLED", False)
    monkeypatch.setattr("src.core.target_sniping.resale.REPRICE_DROP_PCT", 5.0)
    with price_db.state_conn:
        price_db.state_conn.execute("DELETE FROM virtual_inventory")
    yield
    with price_db.state_conn:
        price_db.state_conn.execute("DELETE FROM virtual_inventory")


def _insert_stale_item(
    *,
    hash_name: str = "AK-47 | Redline (Field-Tested)",
    buy_price: float = 10.0,
    sell_price: float = 20.0,
    dm_offer_id: str = "off-1",
    dm_item_id: str = "asset-1",
    age_hours: float = 48.0,
) -> int:
    now = time.time()
    listed_at = now - (age_hours * 3600)
    with price_db.state_conn:
        cursor = price_db.state_conn.execute(
            """INSERT INTO virtual_inventory
               (hash_name, buy_price, sell_price, acquired_at, unlock_at,
                status, dm_offer_id, dm_item_id, listed_at)
               VALUES (?, ?, ?, ?, ?, 'listed', ?, ?, ?)""",
            (
                hash_name,
                buy_price,
                sell_price,
                now - 86400 * 3,
                now - 86400 * 2,
                dm_offer_id,
                dm_item_id,
                listed_at,
            ),
        )
        return int(cursor.lastrowid)


def _get_item(row_id: int) -> dict:
    with price_db.state_conn:
        row = price_db.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row) if row else {}


@pytest.mark.asyncio
async def test_reprice_all_confirmed(caplog: pytest.LogCaptureFixture) -> None:
    """CONTROL: all items in offers[] -> all updated in DB."""
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    id2 = _insert_stale_item(dm_offer_id="off-2", sell_price=30.0)

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [{"id": "off-1"}, {"id": "off-2"}],
        "failed": [],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("INFO"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    item2 = _get_item(id2)
    assert item1["sell_price"] == 19.0
    assert item2["sell_price"] == 28.5
    assert item1["dm_offer_id"] == "off-1"
    assert item2["dm_offer_id"] == "off-2"


@pytest.mark.asyncio
async def test_reprice_partial_failure(caplog: pytest.LogCaptureFixture) -> None:
    """RED: 1 in failed[], 1 in offers[] -> failed item not updated, confirmed updated."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    id2 = _insert_stale_item(dm_offer_id="off-2", sell_price=30.0)

    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [{"id": "off-2"}],
        "failed": [
            {
                "offerId": "off-1",
                "code": "OfferNotFound",
                "message": "Offer does not exist",
            }
        ],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    item2 = _get_item(id2)
    # Item 1 was rejected: price and listed_at MUST NOT change
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert item1["dm_offer_id"] == "off-1"

    # Item 2 was confirmed: price updated
    assert item2["sell_price"] == 28.5
    assert item2["dm_offer_id"] == "off-2"

    # WARNING must log offerId, code, and message
    assert "off-1" in caplog.text
    assert "OfferNotFound" in caplog.text
    assert "Offer does not exist" in caplog.text


@pytest.mark.asyncio
async def test_reprice_all_failed(caplog: pytest.LogCaptureFixture) -> None:
    """RED: all in failed[] -> neither updated in DB."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    id2 = _insert_stale_item(dm_offer_id="off-2", sell_price=30.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [],
        "failed": [
            {"offerId": "off-1", "code": "BadPrice", "message": "Price below floor"},
            {"offerId": "off-2", "code": "Locked", "message": "Offer locked"},
        ],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    item2 = _get_item(id2)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert item2["sell_price"] == 30.0
    assert item2["listed_at"] == pytest.approx(t0, abs=1.0)


@pytest.mark.asyncio
async def test_reprice_empty_response_dict(caplog: pytest.LogCaptureFixture) -> None:
    """RED: empty response {} -> unconfirmed, DB not modified."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {}
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert "unconfirmed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_reprice_none_response(caplog: pytest.LogCaptureFixture) -> None:
    """RED: None response -> unconfirmed, DB not modified."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = None
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert "unconfirmed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_reprice_priority_failed_over_offers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RED: offerId appears in both offers[] and failed[] -> failed takes priority."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [{"id": "off-1"}],
        "failed": [{"offerId": "off-1", "code": "Conflict", "message": "Failed priority"}],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert "Conflict" in caplog.text


@pytest.mark.asyncio
async def test_reprice_id_changed_matched_by_asset_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """RED: id in response changed, matched by assetId -> new id written, warning logged."""
    id1 = _insert_stale_item(
        dm_offer_id="old-off-1",
        dm_item_id="asset-123",
        sell_price=20.0,
    )

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [{"id": "new-off-999", "assetId": "asset-123"}],
        "failed": [],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 19.0
    assert item1["dm_offer_id"] == "new-off-999"
    assert "old-off-1" in caplog.text
    assert "new-off-999" in caplog.text


@pytest.mark.asyncio
async def test_reprice_normalization(caplog: pytest.LogCaptureFixture) -> None:
    """RED/CONTROL: numeric id and id with spaces in response -> confirmed, formatted."""
    id1 = _insert_stale_item(dm_offer_id="12345", sell_price=20.0)

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = {
        "offers": [{"id": 12345}],
        "failed": [],
    }
    runner = ResaleRunner(client=client)

    with caplog.at_level("INFO"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 19.0
    assert item1["dm_offer_id"] == "12345"
    assert "confirmed=1 failed=0 unconfirmed=0" in caplog.text


@pytest.mark.asyncio
async def test_reprice_two_chunks(caplog: pytest.LogCaptureFixture) -> None:
    """RED: two chunks (100 in first, 1 in second) -> failure in chunk 1 does not affect chunk 2."""
    t0 = time.time() - 48 * 3600
    row_ids = []
    for i in range(101):
        rid = _insert_stale_item(
            hash_name=f"Item {i}",
            dm_offer_id=f"off-{i}",
            dm_item_id=f"asset-{i}",
            sell_price=20.0,
        )
        row_ids.append(rid)

    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    async def _mock_batch_edit(chunk):
        # Chunk 1: off-0 fails, off-1..off-99 succeed
        if any(e["offer_id"] == "off-0" for e in chunk):
            return {
                "offers": [{"id": e["offer_id"]} for e in chunk if e["offer_id"] != "off-0"],
                "failed": [{"offerId": "off-0", "code": "Fail0", "message": "Failed 0"}],
            }
        # Chunk 2: off-100 succeeds
        return {
            "offers": [{"id": e["offer_id"]} for e in chunk],
            "failed": [],
        }

    client = AsyncMock()
    client.batch_edit_offers_v2.side_effect = _mock_batch_edit
    runner = ResaleRunner(client=client)

    with caplog.at_level("INFO"):
        await runner.reprice_unsold_offers("a9c0")

    # Item 0 in chunk 1 failed: not updated
    item0 = _get_item(row_ids[0])
    assert item0["sell_price"] == 20.0
    assert item0["listed_at"] == pytest.approx(t0, abs=1.0)

    # Item 1 in chunk 1 succeeded: updated
    item1 = _get_item(row_ids[1])
    assert item1["sell_price"] == 19.0

    # Item 100 in chunk 2 succeeded: updated
    item100 = _get_item(row_ids[100])
    assert item100["sell_price"] == 19.0


@pytest.mark.asyncio
async def test_reprice_exception_timeout(caplog: pytest.LogCaptureFixture) -> None:
    """CONTROL: TimeoutError in batch_edit_offers_v2 -> warning, DB not modified."""
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    client.batch_edit_offers_v2.side_effect = TimeoutError("Request timed out")
    runner = ResaleRunner(client=client)

    with caplog.at_level("WARNING"):
        await runner.reprice_unsold_offers("a9c0")

    item1 = _get_item(id1)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert "Batch edit failed" in caplog.text


@pytest.mark.asyncio
async def test_reprice_dry_run(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """CONTROL: DRY mode -> client not called, DB not modified."""
    monkeypatch.setattr(Config, "DRY_RUN", True)
    t0 = time.time() - 48 * 3600
    id1 = _insert_stale_item(dm_offer_id="off-1", sell_price=20.0)
    with price_db.state_conn:
        price_db.state_conn.execute("UPDATE virtual_inventory SET listed_at = ?", (t0,))

    client = AsyncMock()
    runner = ResaleRunner(client=client)

    with caplog.at_level("INFO"):
        await runner.reprice_unsold_offers("a9c0")

    client.batch_edit_offers_v2.assert_not_called()
    item1 = _get_item(id1)
    assert item1["sell_price"] == 20.0
    assert item1["listed_at"] == pytest.approx(t0, abs=1.0)
    assert "would be repriced (DRY simulation)" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "db_offer_id",
        "db_item_id",
        "response",
        "expected_price",
        "expected_offer_id",
        "expect_updated",
    ),
    [
        (
            "off-1",
            "asset-1",
            {"offers": [{"id": "  off-1  "}], "failed": []},
            19.0,
            "off-1",
            True,
        ),
        (
            "off-2",
            "asset-2",
            {
                "offers": [{"id": "off-2"}],
                "failed": [
                    {
                        "offerId": "  off-2  ",
                        "code": "Rejected",
                        "message": "Offer rejected",
                    }
                ],
            },
            20.0,
            "off-2",
            False,
        ),
        (
            "old-off-3",
            "asset-3",
            {
                "offers": [{"id": "  new-off-3  ", "assetId": "  asset-3  "}],
                "failed": [],
            },
            19.0,
            "new-off-3",
            True,
        ),
        (
            "  off-4  ",
            "asset-4",
            {"offers": [{"id": "off-4"}], "failed": []},
            19.0,
            "off-4",
            True,
        ),
    ],
    ids=[
        "offers_id_strip",
        "failed_offer_id_strip_priority",
        "offers_asset_id_strip",
        "request_offer_id_strip",
    ],
)
async def test_reprice_whitespace_normalization(
    db_offer_id: str,
    db_item_id: str,
    response: dict,
    expected_price: float,
    expected_offer_id: str,
    expect_updated: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """F3: verify whitespace normalization (.strip()) on all identifier paths."""
    t0 = time.time() - 48 * 3600
    row_id = _insert_stale_item(
        dm_offer_id=db_offer_id,
        dm_item_id=db_item_id,
        sell_price=20.0,
    )
    with price_db.state_conn:
        price_db.state_conn.execute(
            "UPDATE virtual_inventory SET listed_at = ? WHERE id = ?",
            (t0, row_id),
        )

    client = AsyncMock()
    client.batch_edit_offers_v2.return_value = response
    runner = ResaleRunner(client=client)

    await runner.reprice_unsold_offers("a9c0")

    item = _get_item(row_id)
    assert item["sell_price"] == expected_price
    assert item["dm_offer_id"] == expected_offer_id
    if expect_updated:
        assert item["listed_at"] > t0
    else:
        assert item["listed_at"] == pytest.approx(t0, abs=1.0)
