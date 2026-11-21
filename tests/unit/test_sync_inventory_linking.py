"""_sync_real_inventory must LINK bought rows, not duplicate them.

Bought items are recorded by execution.py without dm_item_id (the offers-buy
response carries no item ids). Once get_user_inventory works (v2), the sync
sees those items; before the fix it inserted a second `idle` row for each.
Real SQLite (PriceHistoryDB in tmp_path); only the client is stubbed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.resale_prod import _ResaleProdMixin
from src.db.price_history.core import PriceHistoryDB

UUID1 = "3d9c9c6a-4f2e-4b83-a1c7-90ab12cd34e1"
UUID2 = "3d9c9c6a-4f2e-4b83-a1c7-90ab12cd34e2"
TITLE = "AK-47 | Redline (Field-Tested)"


@pytest.fixture()
def db(tmp_path):
    inst = PriceHistoryDB(
        state_db=str(tmp_path / "state.db"), history_db=str(tmp_path / "history.db")
    )
    yield inst
    inst.close()


def _client(*items) -> MagicMock:
    client = MagicMock()
    client.get_user_inventory = AsyncMock(
        return_value={"objects": list(items), "cursor": None}
    )
    return client


def _obj(dm_id: str, title: str = TITLE, in_market=True) -> dict:
    return {"itemId": dm_id, "assetId": dm_id, "title": title, "inMarket": in_market}


async def _sync(db, client) -> int:
    mixin = MagicMock()
    mixin.client = client
    with patch("src.core.target_sniping.resale_prod.price_db", db):
        return await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")


def _rows(db):
    return db.state_conn.execute(
        "SELECT id, hash_name, buy_price, status, dm_item_id FROM virtual_inventory ORDER BY id"
    ).fetchall()


@pytest.mark.asyncio
async def test_bought_row_is_linked_not_duplicated(db) -> None:
    db.add_virtual_item(TITLE, 12.5, 0)  # what execution.py records after a buy
    n = await _sync(db, _client(_obj(UUID1)))
    rows = _rows(db)
    assert len(rows) == 1
    assert rows[0]["dm_item_id"] == UUID1
    assert rows[0]["buy_price"] == 12.5  # real buy price kept
    assert n == 1


@pytest.mark.asyncio
async def test_two_buys_two_items_link_one_to_one(db) -> None:
    db.add_virtual_item(TITLE, 12.5, 0)
    db.add_virtual_item(TITLE, 13.0, 0)
    n = await _sync(db, _client(_obj(UUID1), _obj(UUID2)))
    rows = _rows(db)
    assert len(rows) == 2
    assert {r["dm_item_id"] for r in rows} == {UUID1, UUID2}
    assert n == 2


@pytest.mark.asyncio
async def test_second_sync_is_idempotent(db) -> None:
    db.add_virtual_item(TITLE, 12.5, 0)
    client = _client(_obj(UUID1))
    await _sync(db, client)
    n = await _sync(db, client)
    assert n == 0
    assert len(_rows(db)) == 1


@pytest.mark.asyncio
async def test_unknown_item_is_still_inserted(db) -> None:
    """An item the bot never bought is added as before (idle, dm_item_id set)."""
    n = await _sync(db, _client(_obj(UUID1)))
    rows = _rows(db)
    assert n == 1 and len(rows) == 1
    assert rows[0]["dm_item_id"] == UUID1 and rows[0]["status"] == "idle"


@pytest.mark.asyncio
async def test_other_title_and_non_idle_rows_are_not_touched(db) -> None:
    db.add_virtual_item("Other | Item (Factory New)", 5.0, 0)
    db.add_virtual_item(TITLE, 12.5, 0)
    db.state_conn.execute(
        "UPDATE virtual_inventory SET status='listed' WHERE hash_name=?", (TITLE,)
    )
    db.state_conn.commit()
    await _sync(db, _client(_obj(UUID1)))
    rows = _rows(db)
    other = [r for r in rows if r["hash_name"].startswith("Other")][0]
    listed = [r for r in rows if r["status"] == "listed"][0]
    assert not other["dm_item_id"] and not listed["dm_item_id"]
    assert len(rows) == 3  # the new idle row was inserted for the unmatched item
