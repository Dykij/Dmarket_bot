"""
control.py — Start/stop/panic (bot lifecycle control).

Handles the commands that change the bot's running state, including
the kill-switch that cancels all DMarket offers.
"""

from __future__ import annotations

import contextlib
import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

from ..keyboards import BTN_PANIC, BTN_START, BTN_STOP
from ..callback_data import ConfirmCallback
from ..resilience import retry_async, safe_call
from ..state import state

logger = logging.getLogger("TelegramControl.commands.control")
router = Router(name="telegram-control-control")


# ============================================================
# Control: start/stop/panic
# ============================================================
@router.message(Command("start_bot"))
@router.message(F.text == BTN_START)
@safe_call
async def cmd_start_bot(message):
    started = await state.start()
    if not started:
        await message.answer("⚠️ *Bot is already running!*\nUse /stop\\_bot to stop.")
        return
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"
    await message.answer(
        f"✅ *Bot STARTED* in {mode} mode!\n\n"
        f"Strategy: {Config.ACTIVE_STRATEGY}\n"
        f"Game: {Config.GAME_ID}\n"
        f"Scan interval: {Config.SCAN_INTERVAL}s\n\n"
        f"Use 📊 STATUS to monitor progress."
    )
    logger.info(f"Bot started by admin {message.from_user.id}")


@router.message(Command("stop_bot"))
@router.message(F.text == BTN_STOP)
@safe_call
async def cmd_stop_bot(message):
    stopped = await state.stop()
    if not stopped:
        await message.answer("⚠️ *Bot is not running.*")
        return
    await message.answer(
        "🛑 *Bot STOPPED.*\n\n"
        "Active orders remain on DMarket (cancel manually if needed)."
    )
    logger.info(f"Bot stopped by admin {message.from_user.id}")


@router.message(Command("panic"))
@router.message(F.text == BTN_PANIC)
@safe_call
async def cmd_panic(message):
    await message.answer(
        "🔥 *PANIC PROTOCOL INITIATED*\n"
        "Stopping bot and cancelling all offers..."
    )

    # 1. Stop loop (reuses the SAME client)
    await state.stop()

    # 2. Cancel all offers
    cancelled, err = await _cancel_all_offers()

    if err is None:
        if cancelled:
            await message.answer(f"🗑 Cancelled {cancelled} offers.")
        else:
            await message.answer("✅ No active offers found.")
    else:
        logger.warning(f"PANIC: cancel offers failed: {err}")
        await message.answer(
            "⚠️ Could not cancel offers. Check logs for details.\n"
            "Cancel manually if needed."
        )
    await message.answer("🔥 *Panic complete. You are safe.*")
    logger.warning(f"PANIC executed by admin {message.from_user.id}")


async def _cancel_all_offers() -> tuple[int, Exception | None]:
    """Cancel all active offers on DMarket. Returns (count, error)."""
    async with state.lock:
        client_to_close = None
        if state.client is None:
            # Bot was not running — create a temp client just for cancellation
            from ..resilience import get_dmarket_secret
            state.client = DMarketAPIClient(Config.PUBLIC_KEY, get_dmarket_secret())  # type: ignore[arg-type]
            client_to_close = state.client

        try:
            offers_resp = await retry_async(
                lambda: state.client.get_user_offers_v2(Config.GAME_ID, limit=100),  # type: ignore[union-attr]
                operation="PANIC: list offers",
            )
            offer_ids = [
                o.get("offerId", "")
                for o in offers_resp.get("items", [])
                if o.get("offerId")
            ]
            if offer_ids:
                await retry_async(
                    lambda: state.client.batch_delete_offers_v2(offer_ids),  # type: ignore[union-attr]
                    operation="PANIC: cancel offers",
                )
                return len(offer_ids), None
            return 0, None
        except Exception as e:
            logger.exception("PANIC cancellation failed")
            return 0, e
        finally:
            if client_to_close is not None:
                with contextlib.suppress(Exception):
                    await client_to_close.close()
                state.client = None


# ============================================================
# Liquidate: sell all unlocked inventory at market bid
# ============================================================
@router.message(Command("liquidate"))
@safe_call
async def cmd_liquidate(message):
    """Show confirmation dialog before force-selling ALL unlocked inventory."""
    if state.client is None:
        await message.answer("❌ Bot is not running. Start the bot first with /start_bot")
        return

    # P1 FIX: Show inventory summary and require confirmation
    from src.db.price_history import price_db

    idle_items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
    if not idle_items:
        await message.answer("💧 *Liquidate* — No unlocked items in inventory.")
        return

    total_value = sum(float(item.get("buy_price", 0)) for item in idle_items)
    item_count = len(idle_items)
    sample_names = [item.get("hash_name", "?") for item in idle_items[:5]]
    names_text = "\n".join(f"  • {n}" for n in sample_names)
    if item_count > 5:
        names_text += f"\n  ... and {item_count - 5} more"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Yes, sell ALL",
                callback_data=ConfirmCallback(action="yes", context="liquidate").pack(),
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=ConfirmCallback(action="no", context="liquidate").pack(),
            ),
        ]
    ])
    await message.answer(
        f"⚠️ *LIQUIDATION CONFIRMATION*\n\n"
        f"Items to sell: **{item_count}**\n"
        f"Total cost basis: **${total_value:.2f}**\n\n"
        f"Items:\n{names_text}\n\n"
        f"This will list ALL items at best bid. This action is **irreversible**.\n"
        f"Confirm?",
        reply_markup=kb,
    )


@router.callback_query(ConfirmCallback.filter((F.action == "yes") & (F.context == "liquidate")))
@safe_call
async def cb_liquidate_confirm(callback: types.CallbackQuery):
    """Execute liquidation after confirmation."""
    if callback.message is None or not isinstance(callback.message, types.Message):
        return

    if state.client is None:
        await callback.message.edit_text("❌ Bot client unavailable. Start the bot first.")
        await callback.answer()
        return

    await callback.message.edit_text("💧 *LIQUIDATION IN PROGRESS*\nSelling all unlocked inventory at best bid...")

    from src.core.target_sniping.position_guard import _PositionGuardMixin
    guard = _PositionGuardMixin()
    guard.client = state.client

    try:
        result = await guard.emergency_liquidate_all(Config.GAME_ID)
    except Exception:
        logger.exception("Liquidation failed")
        await callback.message.edit_text("❌ Liquidation failed. Check logs for details.")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"💧 *Liquidation Complete*\n\n"
        f"Items listed: {result['liquidated']}\n"
        f"Total value: ${result['total_value']:.2f}\n"
        f"Errors: {result['errors']}"
    )
    logger.warning(f"LIQUIDATION executed by admin {callback.from_user.id}: {result}")
    await callback.answer()


@router.callback_query(ConfirmCallback.filter((F.action == "no") & (F.context == "liquidate")))
@safe_call
async def cb_liquidate_cancel(callback: types.CallbackQuery):
    """Cancel liquidation."""
    if callback.message is not None and isinstance(callback.message, types.Message):
        await callback.message.edit_text("❌ Liquidation cancelled.")
    await callback.answer()
