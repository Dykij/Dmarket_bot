"""
callbacks.py — Inline-button callback handlers (btn:start, btn:stop, etc.)

Each handler responds to a specific callback_data and re-renders the message.
"""

import logging
from typing import Optional

from aiogram import F, Router, types

from src.db.price_history import price_db

from .formatters import (
    format_balance,
    format_inventory_summary,
    format_profits_summary,
    format_status,
)
from .keyboards import (
    CB_BALANCE,
    CB_INVENTORY,
    CB_NOOP,
    CB_PROFITS,
    CB_REFRESH_STATUS,
    CB_START,
    CB_STOP,
    get_inline_balance_kb,
    get_inline_inventory_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
)
from .resilience import dmarket_client, retry_async, safe_call
from .state import state

logger = logging.getLogger("TelegramControl.callbacks")
router = Router(name="telegram-control-callbacks")


@router.callback_query(F.data == CB_START)
@safe_call
async def cb_start(callback: types.CallbackQuery):
    if callback.message is None:
        return
    await callback.message.answer("Use 🚀 START BOT button or /start_bot command.")
    await callback.answer()


@router.callback_query(F.data == CB_STOP)
@safe_call
async def cb_stop(callback: types.CallbackQuery):
    if callback.message is None:
        return
    await callback.message.answer("Use 🛑 STOP BOT button or /stop_bot command.")
    await callback.answer()


@router.callback_query(F.data == CB_BALANCE)
@safe_call
async def cb_balance(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    await callback.message.edit_text("💰 Fetching balance...")
    try:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="cb.balance",
            )
            equity = price_db.get_total_equity(balance)
            text = format_balance(balance, equity)
            await callback.message.edit_text(
                text, reply_markup=get_inline_balance_kb()
            )
    except Exception as e:
        logger.exception(f"cb_balance error: {e}")
        await callback.message.edit_text("❌ Error fetching balance. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_INVENTORY)
@safe_call
async def cb_inventory(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    selling = price_db.get_virtual_inventory(status='selling')
    sold = price_db.get_virtual_inventory(status='sold')
    text = format_inventory_summary(idle, selling, sold, top_n=5)
    await callback.message.edit_text(
        text, reply_markup=get_inline_inventory_kb()
    )
    await callback.answer()


@router.callback_query(F.data == CB_PROFITS)
@safe_call
async def cb_profits(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    text = format_profits_summary(sold, idle, [], detailed=False)
    await callback.message.edit_text(
        text, reply_markup=get_inline_profits_kb()
    )
    await callback.answer()


@router.callback_query(F.data == CB_REFRESH_STATUS)
@safe_call
async def cb_refresh_status(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    st = await state.status()
    is_running = st["is_running"]
    balance_data = await _fetch_balance_data()
    text = format_status(is_running, balance_data)
    await callback.message.edit_text(
        text, reply_markup=get_inline_status_kb(is_running)
    )
    await callback.answer()


async def _fetch_balance_data() -> Optional[dict]:
    """Fetch balance + equity. Returns dict with cash_str/locked_str/total_str or None on error."""
    try:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="cb.balance_data",
            )
            equity = price_db.get_total_equity(balance)
            return {
                "cash_str": f"${equity['cash']:.2f}",
                "locked_str": f"${equity['assets']:.2f} ({equity['count']} items)",
                "total_str": f"${equity['total']:.2f}",
            }
    except Exception:
        return None


@router.callback_query(F.data == CB_NOOP)
@safe_call
async def cb_noop(callback: types.CallbackQuery):
    """No-op for buttons that reflect state (e.g., '🟡 RUNNING' shows but does nothing)."""
    await callback.answer()
