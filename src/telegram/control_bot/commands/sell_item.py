"""
sell_item.py — Manual single-item sell command (/sell_item).

Allows the admin to pick any unlocked idle item (including exclusive ⭐ items),
inspect the current DMarket best_bid, fee, net proceeds, and P&L, and confirm sale.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import src.db.price_history as _price_history_mod
from src.config import Config
from src.core.target_sniping.position_guard import _PositionGuardMixin, _run_db
from src.utils.fee_utils import get_total_fee_rate

from ..callback_data import SellItemCallback
from ..resilience import safe_call
from ..state import state

logger = logging.getLogger("TelegramControl.commands.sell_item")
router = Router(name="telegram-control-sell-item")


def _safe_md_code(text: str) -> str:
    """Prevent backtick breakout inside Telegram Markdown v1 code spans."""
    return text.replace("`", "'")


def _find_unlocked_idle_row(row_id: int) -> dict[str, Any] | None:
    """Find a virtual_inventory row by id among unlocked idle items."""
    items = _price_history_mod.price_db.get_virtual_inventory(
        status="idle", only_unlocked=True
    )
    for it in items:
        if int(it["id"]) == int(row_id):
            return dict(it) if not isinstance(it, dict) else it
    return None


async def prepare_sell_item(
    client: Any, row_id: int
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Fetch fresh best_bid for row_id and build confirmation text + keyboard."""
    db = _price_history_mod.price_db
    row = await _run_db(db, _find_unlocked_idle_row, row_id)
    if row is None:
        return (
            "❌ Item is not available (locked, already listed, or sold).",
            None,
        )

    hash_name = str(row["hash_name"])
    safe_name = _safe_md_code(hash_name)
    buy_price = float(row.get("buy_price") or 0)
    excl_mark = "⭐ " if row.get("exclusive") else ""

    agg: dict[str, Any] = {}
    try:
        agg = await client.get_aggregated_prices(Config.GAME_ID, titles=[hash_name])
    except Exception as e:
        logger.warning(f"[SELL-ITEM] Price fetch failed for {hash_name}: {e}")

    bid = float((agg.get(hash_name) or {}).get("best_bid") or 0)
    if bid <= 0:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data=SellItemCallback(
                            action="no", row_id=row_id
                        ).pack(),
                    )
                ]
            ]
        )
        text = (
            f"🎯 {excl_mark}`{safe_name}`\n\n"
            f"Buy price: ${buy_price:.2f}\n"
            f"No current bid — not selling."
        )
        return text, kb

    fee_rate = get_total_fee_rate()
    net_proceeds = bid * (1.0 - fee_rate)
    pnl = net_proceeds - buy_price
    dry_note = "\n🧪 `DRY_RUN: simulated`" if Config.DRY_RUN else ""

    text = (
        f"🎯 {excl_mark}`{safe_name}`\n\n"
        f"Buy price: ${buy_price:.2f}\n"
        f"Best bid: ${bid:.2f}\n"
        f"Fee ({fee_rate * 100:.1f}%): ${bid * fee_rate:.2f}\n"
        f"Net proceeds: ${net_proceeds:.2f}\n"
        f"P&L: ${pnl:+.2f}"
        f"{dry_note}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Sell",
                    callback_data=SellItemCallback(
                        action="yes", row_id=row_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=SellItemCallback(
                        action="no", row_id=row_id
                    ).pack(),
                ),
            ]
        ]
    )
    return text, kb


async def _execute_sell_item_once(client: Any, row_id: int) -> dict[str, Any]:
    """Re-verify row availability and fresh best_bid, then execute sale."""
    db = _price_history_mod.price_db
    row = await _run_db(db, _find_unlocked_idle_row, row_id)
    if row is None:
        return {"sold": 0, "reason": "not_available", "price": None, "exclusive": False}  # sel3:si-recheck

    hash_name = str(row["hash_name"])
    is_exclusive = bool(row.get("exclusive"))

    agg: dict[str, Any] = {}
    try:
        agg = await client.get_aggregated_prices(Config.GAME_ID, titles=[hash_name])
    except Exception as e:
        logger.warning(f"[SELL-ITEM] Price fetch failed for {hash_name}: {e}")

    bid = float((agg.get(hash_name) or {}).get("best_bid") or 0)
    if bid <= 0:
        return {"sold": 0, "reason": "no_bid", "price": None, "exclusive": is_exclusive}  # sel3:si-no-bid

    # Re-verify row state right after the async price call to avoid double-sell races
    row = await _run_db(db, _find_unlocked_idle_row, row_id)
    if row is None:
        return {"sold": 0, "reason": "not_available", "price": None, "exclusive": is_exclusive}

    guard = _PositionGuardMixin()
    guard.client = client
    sold = await guard._execute_liquidation(
        [(row, bid, "manual-sell-item")], Config.GAME_ID, "SELL-ITEM"
    )
    if sold <= 0:
        return {"sold": 0, "reason": "failed", "price": bid, "exclusive": is_exclusive}
    return {"sold": sold, "reason": "ok", "price": bid, "exclusive": is_exclusive}


# sel4: single-flight per row_id. Check and add run with no await in between,
# so a second confirm callback for the same row cannot pass while the first runs.
_IN_FLIGHT: set[int] = set()


async def execute_sell_item(client: Any, row_id: int) -> dict[str, Any]:
    """Sell one row; a concurrent second call for the same row returns reason='in_progress'."""
    row_id = int(row_id)
    if row_id in _IN_FLIGHT:
        return {"sold": 0, "reason": "in_progress", "price": None, "exclusive": False}  # sel4:inflight-check
    _IN_FLIGHT.add(row_id)  # sel4:inflight-add
    try:
        return await _execute_sell_item_once(client, row_id)
    finally:
        _IN_FLIGHT.discard(row_id)  # sel4:inflight-release


@router.message(Command("sell_item"))
@safe_call
async def cmd_sell_item(message: types.Message) -> None:
    """List up to 20 unlocked idle items sorted by buy_price descending."""
    if state.client is None:
        await message.answer("❌ Bot is not running. Start the bot first with /start_bot")
        return

    db = _price_history_mod.price_db
    idle = await _run_db(db, db.get_virtual_inventory, status="idle", only_unlocked=True)
    if not idle:
        await message.answer("🎯 *Sell Item* — No unlocked items in inventory.")
        return

    items = sorted(idle, key=lambda it: -float(it.get("buy_price") or 0))[:20]
    rows: list[list[InlineKeyboardButton]] = []
    for it in items:
        prefix = "⭐ " if it.get("exclusive") else ""
        buy_price = float(it.get("buy_price") or 0)
        label = f"{prefix}{str(it['hash_name'])[:28]} ${buy_price:.2f}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=SellItemCallback(
                        action="pick", row_id=int(it["id"])
                    ).pack(),
                )
            ]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("🎯 *Select an item to sell:*", reply_markup=kb)


@router.callback_query(SellItemCallback.filter(F.action == "pick"))
@safe_call
async def cb_sell_item_pick(
    callback: types.CallbackQuery, callback_data: SellItemCallback
) -> None:
    """Show bid & P&L preview for the picked item."""
    if callback.message is None or not isinstance(callback.message, types.Message):
        await callback.answer()
        return

    if state.client is None:
        await callback.message.edit_text("❌ Bot is not running. Start the bot first with /start_bot")
        await callback.answer()
        return

    text, kb = await prepare_sell_item(state.client, callback_data.row_id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(SellItemCallback.filter(F.action == "yes"))
@safe_call
async def cb_sell_item_confirm(
    callback: types.CallbackQuery, callback_data: SellItemCallback
) -> None:
    """Execute manual sale of the selected item."""
    if callback.message is None or not isinstance(callback.message, types.Message):
        await callback.answer()
        return

    if state.client is None:
        await callback.message.edit_text("❌ Bot is not running. Start the bot first with /start_bot")
        await callback.answer()
        return

    await callback.message.edit_text("⏳ *Selling item...*")
    await callback.answer()

    result = await execute_sell_item(state.client, callback_data.row_id)
    reason = result["reason"]
    if reason == "ok":
        excl_tag = " ⭐" if result["exclusive"] else ""
        if Config.DRY_RUN:
            heading = f"✅ *Item Sold{excl_tag}* (DRY\\_RUN)"
        else:
            heading = f"✅ *Item Listed for Sale{excl_tag}*"
        await callback.message.edit_text(
            f"{heading}\n"
            f"Price: ${result['price']:.2f}"
        )
    elif reason == "not_available":
        await callback.message.edit_text("❌ Item is not available (locked, already listed, or sold).")
    elif reason == "in_progress":
        logger.info("[SELL-ITEM] duplicate confirm for row %s ignored", callback_data.row_id)
    elif reason == "no_bid":
        await callback.message.edit_text("❌ No current bid — not selling.")
    else:
        await callback.message.edit_text("❌ Sale failed. Check logs for details.")


@router.callback_query(SellItemCallback.filter(F.action == "no"))
@safe_call
async def cb_sell_item_cancel(
    callback: types.CallbackQuery, callback_data: SellItemCallback
) -> None:
    """Cancel single-item sell dialog."""
    if callback.message is not None and isinstance(callback.message, types.Message):
        await callback.message.edit_text("❌ Sell cancelled.")
    await callback.answer()
