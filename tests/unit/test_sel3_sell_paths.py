"""Unit tests for sel3: sell paths, exclusive handling, and /sell_item."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config
from src.core.resale_pipeline import ResalePipeline
from src.core.target_sniping.position_guard import _PositionGuardMixin
from src.db.price_history.core import PriceHistoryDB
from src.telegram.control_bot.commands import control as control_mod


@pytest.fixture()
def real_db(tmp_path, monkeypatch):
    """Create a real PriceHistoryDB backed by a temporary directory."""
    monkeypatch.setenv("DMARKET_DATA_DIR", str(tmp_path))
    db = PriceHistoryDB(
        state_db=str(tmp_path / "state.db"),
        history_db=str(tmp_path / "history.db"),
    )
    yield db
    db.close()


def _make_notifier_mock() -> MagicMock:
    notifier = MagicMock()
    notifier.sell = AsyncMock()
    return notifier


@pytest.mark.asyncio
async def test_t1_sell_inventory_items_skips_exclusive(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T1: sell_inventory_items skips exclusive items before slicing max_items."""
    real_db.add_virtual_item("Item Exclusive", 10.0, 0, True)
    real_db.add_virtual_item("Item Normal", 10.0, 0, False)

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(
        return_value={
            "Item Exclusive": {"best_bid": 20.0, "best_ask": 22.0},
            "Item Normal": {"best_bid": 20.0, "best_ask": 22.0},
        }
    )

    monkeypatch.setattr("src.core.resale_pipeline.price_db", real_db)
    monkeypatch.setattr(Config, "DRY_RUN", True)
    monkeypatch.setattr(Config, "FEE_RATE", 0.05)
    monkeypatch.setattr(Config, "MIN_SPREAD_PCT", 5.0)

    pipeline = ResalePipeline(client)
    await pipeline.sell_inventory_items(max_items=10)

    idle_names = [r["hash_name"] for r in real_db.get_virtual_inventory(status="idle")]
    selling_names = [r["hash_name"] for r in real_db.get_virtual_inventory(status="selling")]

    assert idle_names == ["Item Exclusive"]
    assert selling_names == ["Item Normal"]


@pytest.mark.asyncio
async def test_t2_emergency_liquidate_all_bids_and_exclusive(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T2: emergency_liquidate_all fetches bids once, skips no-bid, reports exclusive."""
    real_db.add_virtual_item("Item X", 10.0, 0, False)
    real_db.add_virtual_item("Item Y", 10.0, 0, False)
    real_db.add_virtual_item("Item Z", 10.0, 0, True)

    rows_by_name = {
        r["hash_name"]: r for r in real_db.get_virtual_inventory(status="idle")
    }
    real_db.attach_dm_item_id(int(rows_by_name["Item X"]["id"]), "dm-x")
    real_db.attach_dm_item_id(int(rows_by_name["Item Y"]["id"]), "dm-y")
    real_db.attach_dm_item_id(int(rows_by_name["Item Z"]["id"]), "dm-z")

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(
        return_value={
            "Item X": {"best_bid": 9.0, "best_ask": 10.0},
            "Item Z": {"best_bid": 30.0, "best_ask": 32.0},
        }
    )

    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)
    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr(Config, "DRY_RUN", True)
    monkeypatch.setattr(
        "src.core.target_sniping.position_guard._get_notifier",
        _make_notifier_mock,
    )

    guard = _PositionGuardMixin()
    guard.client = client

    result = await guard.emergency_liquidate_all("a8db")

    assert result["liquidated"] == 2
    assert result["skipped_no_price"] == 1
    assert result["exclusive"] == 1
    client.get_aggregated_prices.assert_awaited_once()

    idle_names = [r["hash_name"] for r in real_db.get_virtual_inventory(status="idle")]
    sold_by_name = {
        r["hash_name"]: r for r in real_db.get_virtual_inventory(status="sold")
    }
    assert idle_names == ["Item Y"]
    assert set(sold_by_name.keys()) == {"Item X", "Item Z"}
    assert sold_by_name["Item X"]["sell_price"] == 9.0


@pytest.mark.asyncio
async def test_t3_cmd_liquidate_includes_all_candidates_and_exclusive(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3: cmd_liquidate counts idle+unlocked, selling, listed and reports exclusive."""
    real_db.add_virtual_item("Idle Normal", 10.0, 0, False)
    real_db.add_virtual_item("Idle Excl", 15.0, 0, True)
    real_db.add_virtual_item("Selling Item", 20.0, 0, False)
    real_db.add_virtual_item("Listed Item", 25.0, 0, False)

    idle_map = {r["hash_name"]: int(r["id"]) for r in real_db.get_virtual_inventory(status="idle")}
    real_db.update_virtual_status(idle_map["Selling Item"], "selling")
    real_db.update_virtual_status(idle_map["Listed Item"], "listed")

    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)
    monkeypatch.setattr(control_mod.state, "client", object())

    message = MagicMock()
    message.from_user = MagicMock(id=12345)
    message.answer = AsyncMock()

    await control_mod.cmd_liquidate.__wrapped__(message)

    message.answer.assert_awaited_once()
    reply_text = message.answer.call_args.args[0]
    assert "Items to sell: **4**" in reply_text
    assert "Exclusive (keep-forever) included: 1" in reply_text


@pytest.mark.asyncio
async def test_t4_sell_item_list_buttons_and_callback_unpack(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T4: /sell_item lists unlocked idle buttons with star for exclusive, unpacks SellItemCallback."""
    from src.telegram.control_bot.callback_data import SellItemCallback
    from src.telegram.control_bot.commands import sell_item as sell_item_mod

    real_db.add_virtual_item("Excl Unlocked", 15.0, 0, True)
    real_db.add_virtual_item("Norm Unlocked", 10.0, 0, False)
    real_db.add_virtual_item("Locked Item", 20.0, 24, False)
    real_db.add_virtual_item("Selling Item", 25.0, 0, False)

    all_idle = {r["hash_name"]: int(r["id"]) for r in real_db.get_virtual_inventory(status="idle")}
    real_db.update_virtual_status(all_idle["Selling Item"], "selling")

    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr(sell_item_mod.state, "client", MagicMock())

    message = MagicMock()
    message.from_user = MagicMock(id=12345)
    message.answer = AsyncMock()

    await sell_item_mod.cmd_sell_item.__wrapped__(message)

    message.answer.assert_awaited_once()
    markup = message.answer.call_args.kwargs.get("reply_markup")
    assert markup is not None
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    texts = [b.text for b in buttons]

    assert len(buttons) == 2
    assert any(t.startswith("⭐ ") and "Excl Unlocked" in t for t in texts)
    assert any((not t.startswith("⭐ ")) and "Norm Unlocked" in t for t in texts)
    assert not any("Locked Item" in t for t in texts)
    assert not any("Selling Item" in t for t in texts)

    unpacked = [SellItemCallback.unpack(b.callback_data) for b in buttons]
    assert all(cb.action == "pick" for cb in unpacked)
    assert {cb.row_id for cb in unpacked} == {
        all_idle["Excl Unlocked"],
        all_idle["Norm Unlocked"],
    }


@pytest.mark.asyncio
async def test_t5_prepare_sell_item_no_bid(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T5: prepare_sell_item without bid shows 'No current bid' and no action='yes' button."""
    from src.telegram.control_bot.callback_data import SellItemCallback
    from src.telegram.control_bot.commands.sell_item import prepare_sell_item

    real_db.add_virtual_item("No Bid Item", 12.0, 0, False)
    row_id = int(real_db.get_virtual_inventory(status="idle")[0]["id"])

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(return_value={})

    monkeypatch.setattr("src.db.price_history.price_db", real_db)

    text, markup = await prepare_sell_item(client, row_id)

    assert "No current bid" in text
    if markup is not None:
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        actions = [SellItemCallback.unpack(b.callback_data).action for b in buttons if b.callback_data]
        assert "yes" not in actions


@pytest.mark.asyncio
async def test_t6_execute_sell_item_exclusive_ok(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T6: execute_sell_item sells exclusive row at best_bid and leaves neighbor idle."""
    from src.telegram.control_bot.commands.sell_item import execute_sell_item

    real_db.add_virtual_item("Excl Target", 15.0, 0, True)
    real_db.add_virtual_item("Neighbor Item", 10.0, 0, False)
    rows = {r["hash_name"]: r for r in real_db.get_virtual_inventory(status="idle")}
    excl_id = int(rows["Excl Target"]["id"])
    real_db.attach_dm_item_id(excl_id, "dm-excl-1")

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(
        return_value={"Excl Target": {"best_bid": 25.0, "best_ask": 27.0}}
    )

    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)
    monkeypatch.setattr(Config, "DRY_RUN", True)
    monkeypatch.setattr(
        "src.core.target_sniping.position_guard._get_notifier",
        _make_notifier_mock,
    )

    res = await execute_sell_item(client, excl_id)

    assert res["sold"] == 1
    assert res["reason"] == "ok"
    assert res["exclusive"] is True

    sold_rows = real_db.get_virtual_inventory(status="sold")
    idle_rows = real_db.get_virtual_inventory(status="idle")
    assert len(sold_rows) == 1
    assert int(sold_rows[0]["id"]) == excl_id
    assert sold_rows[0]["sell_price"] == 25.0
    assert [r["hash_name"] for r in idle_rows] == ["Neighbor Item"]


@pytest.mark.asyncio
async def test_t7_execute_sell_item_selling_not_available(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T7: execute_sell_item on 'selling' row returns not_available and skips _execute_liquidation."""
    from src.telegram.control_bot.commands.sell_item import execute_sell_item

    real_db.add_virtual_item("Already Selling", 10.0, 0, False)
    row_id = int(real_db.get_virtual_inventory(status="idle")[0]["id"])
    real_db.update_virtual_status(row_id, "selling")

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(
        return_value={"Already Selling": {"best_bid": 15.0}}
    )

    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    with patch.object(_PositionGuardMixin, "_execute_liquidation", new_callable=AsyncMock) as mock_exec:
        res = await execute_sell_item(client, row_id)

    assert res["sold"] == 0
    assert res["reason"] == "not_available"
    mock_exec.assert_not_called()
    assert len(real_db.get_virtual_inventory(status="selling")) == 1


@pytest.mark.asyncio
async def test_t8_execute_sell_item_no_bid_and_help_commands(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T8: execute_sell_item without bid returns no_bid; /help and set_commands updated."""
    from src.telegram.control_bot.commands.lifecycle import cmd_help
    from src.telegram.control_bot.commands.sell_item import execute_sell_item
    from src.telegram.control_bot.lifecycle import set_commands

    real_db.add_virtual_item("No Bid Item", 10.0, 0, False)
    row_id = int(real_db.get_virtual_inventory(status="idle")[0]["id"])

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(return_value={})
    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    res = await execute_sell_item(client, row_id)
    assert res["reason"] == "no_bid"
    assert len(real_db.get_virtual_inventory(status="idle")) == 1

    msg = MagicMock()
    msg.answer = AsyncMock()
    await cmd_help.__wrapped__(msg)
    help_text = msg.answer.call_args.args[0]
    assert "/sell\\_item" in help_text
    assert "/set " not in help_text

    bot = MagicMock()
    bot.set_my_commands = AsyncMock()
    await set_commands(bot)
    commands = bot.set_my_commands.call_args.args[0]
    assert any(c.command == "sell_item" for c in commands)
    assert all("Oracle" not in c.description for c in commands)


@pytest.mark.asyncio
async def test_t9_check_stop_losses_one_reason_per_item(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9: check_stop_losses emits at most one liquidation reason per item."""
    real_db.add_virtual_item(
        hash_name="Demand Item",
        buy_price=10.0,
        trade_lock_hours=0,
        strategy="demand",
    )
    old_ts = time.time() - (48.0 * 3600.0)
    with real_db.state_conn:
        real_db.state_conn.execute(
            "UPDATE virtual_inventory SET acquired_at = ?", (old_ts,)
        )

    monkeypatch.setattr(Config, "DEMAND_STRATEGY_ENABLED", True)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_ENABLED", True)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_MIN_AGE_HOURS", 24.0)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_PCT", 10.0)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    guard = _PositionGuardMixin()
    guard.client = MagicMock()
    guard._current_agg_prices = {"Demand Item": {"best_bid": 7.0, "best_ask": 7.5}}
    guard._execute_liquidation = AsyncMock(return_value=1)  # type: ignore[method-assign]

    await guard.check_stop_losses("a8db")

    guard._execute_liquidation.assert_awaited_once()
    liquidate_arg = guard._execute_liquidation.call_args.args[0]
    assert len(liquidate_arg) == 1


# --- sel4: single-flight in execute_sell_item ---


@pytest.mark.asyncio
async def test_t10_execute_sell_item_single_flight(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T10: two concurrent confirms for one row call _execute_liquidation once (sell_item.py single-flight)."""
    import asyncio

    from src.telegram.control_bot.commands import sell_item as sell_item_mod

    real_db.add_virtual_item("Twice", 10.0, 0, False)
    row_id = int(real_db.get_virtual_inventory(status="idle")[0]["id"])

    async def slow_prices(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return {"Twice": {"best_bid": 12.0, "best_ask": 13.0}}

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(side_effect=slow_prices)
    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    with patch.object(_PositionGuardMixin, "_execute_liquidation", new_callable=AsyncMock, return_value=1) as mock_exec:
        r1, r2 = await asyncio.gather(
            sell_item_mod.execute_sell_item(client, row_id),
            sell_item_mod.execute_sell_item(client, row_id),
        )

    assert mock_exec.await_count == 1
    assert sorted(r["reason"] for r in (r1, r2)) == ["in_progress", "ok"]
    assert sell_item_mod._IN_FLIGHT == set()


@pytest.mark.asyncio
async def test_t11_execute_sell_item_releases_after_error(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T11: an exception inside the sale releases the single-flight slot for the row."""
    from src.telegram.control_bot.commands import sell_item as sell_item_mod

    real_db.add_virtual_item("Retry", 10.0, 0, False)
    row_id = int(real_db.get_virtual_inventory(status="idle")[0]["id"])

    client = MagicMock()
    client.get_aggregated_prices = AsyncMock(return_value={"Retry": {"best_bid": 12.0, "best_ask": 13.0}})
    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    with patch.object(
        _PositionGuardMixin, "_execute_liquidation", new_callable=AsyncMock, side_effect=[RuntimeError("boom"), 1]
    ) as mock_exec:
        with pytest.raises(RuntimeError):
            await sell_item_mod.execute_sell_item(client, row_id)
        res = await sell_item_mod.execute_sell_item(client, row_id)

    assert res["reason"] == "ok"
    assert mock_exec.await_count == 2
    assert sell_item_mod._IN_FLIGHT == set()
