"""
views.py — Read-only info commands: balance, status, inventory, profits.

All read from the local DB and (for status/balance) a single DMarket call.
"""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command

from src.db.price_history import price_db

from ..formatters import (
    format_balance,
    format_inventory_summary,
    format_profits_summary,
    format_status,
)
from ..keyboards import (
    get_inline_balance_kb,
    get_inline_inventory_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
)
from ..resilience import dmarket_client, retry_async, safe_call
from ..state import state

logger = logging.getLogger("TelegramControl.commands.views")
router = Router(name="telegram-control-views")


# ============================================================
# Info: balance / status / inventory / profits
# ============================================================
@router.message(Command("balance"))
@router.message(F.text == "💰 BALANCE")
@safe_call
async def cmd_balance(message):
    async with dmarket_client() as client:
        balance = await retry_async(
            lambda: client.get_real_balance(),
            operation="balance",
        )
        equity = price_db.get_total_equity(balance)
        await message.answer(
            format_balance(balance, equity),
            reply_markup=get_inline_balance_kb(),
        )


@router.message(Command("status"))
@router.message(F.text == "📊 STATUS")
@safe_call
async def cmd_status(message):
    st = await state.status()
    is_running = st["is_running"]
    balance_data = await _fetch_balance_data()
    await message.answer(
        format_status(is_running, balance_data),
        reply_markup=get_inline_status_kb(is_running),
    )


async def _fetch_balance_data() -> Optional[dict]:
    """Fetch balance + equity. Returns dict with cash_str/locked_str/total_str or None on error."""
    try:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="status.balance",
            )
            equity = price_db.get_total_equity(balance)
            return {
                "cash_str": f"${equity['cash']:.2f}",
                "locked_str": f"${equity['assets']:.2f} ({equity['count']} items)",
                "total_str": f"${equity['total']:.2f}",
            }
    except Exception:
        return None


@router.message(Command("inventory"))
@router.message(F.text == "📦 INVENTORY")
@safe_call
async def cmd_inventory(message):
    idle = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
    selling = price_db.get_virtual_inventory(status="selling")
    sold = price_db.get_virtual_inventory(status="sold")
    await message.answer(
        format_inventory_summary(idle, selling, sold),
        reply_markup=get_inline_inventory_kb(),
    )


@router.message(Command("profits"))
@router.message(F.text == "📈 PROFITS")
@safe_call
async def cmd_profits(message):
    sold = price_db.get_virtual_inventory(status="sold")
    idle = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
    selling = price_db.get_virtual_inventory(status="selling")
    await message.answer(
        format_profits_summary(sold, idle, selling, detailed=True),
        reply_markup=get_inline_profits_kb(),
    )
