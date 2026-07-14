"""
test.py — /test flow with FSM (StatesGroup + receive + cancel + do_test).

Runs an arbitrage test for a given item by querying DMarket + the
free multi-source oracle. Uses aiogram FSM to ask the user for the item
name if they pressed the button instead of using `/test <name>` directly.
"""

from __future__ import annotations

import contextlib
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.api.multi_source_oracle import MultiSourceOracle
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

from ..formatters import escape_md
from ..keyboards import BTN_TEST, get_main_keyboard
from ..resilience import retry_async, safe_call

logger = logging.getLogger("TelegramControl.commands.test")
router = Router(name="telegram-control-test")


# ============================================================
# FSM for /test flow
# ============================================================
class TestItemFSM(StatesGroup):
    """FSM for /test flow when user pressed button (not typed /test <item>)."""

    waiting_for_item = State()


# ============================================================
# Test item (with FSM)
# ============================================================
@router.message(Command("test"))
@safe_call
async def cmd_test(message, state_fsm: FSMContext | None = None):
    """If called with /test <item>, run it; otherwise enter FSM to ask for name."""
    if message.text and message.text.startswith("/test"):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "🧪 *Test Arbitrage*\n\n"
                "Usage: `/test <Item Name>`\n"
                "Example: `/test AK-47 | Redline (Field-Tested)`\n\n"
                "Or just send me the item name:"
            )
            if state_fsm:
                await state_fsm.set_state(TestItemFSM.waiting_for_item)
            return
        item_name = args[1].strip()
    else:
        # User pressed the button — ask for the name
        await message.answer(
            "🧪 *Test Arbitrage*\n\n"
            "Send me the item name to test, e.g.:\n"
            "`AK-47 | Redline (Field-Tested)`"
        )
        if state_fsm:
            await state_fsm.set_state(TestItemFSM.waiting_for_item)
        return

    await _do_test(message, item_name)

@router.message(F.text == BTN_TEST)
@safe_call
async def cmd_test_btn(message, state_fsm: FSMContext):
    """Button handler — enter FSM immediately."""
    await message.answer(
        "🧪 *Test Arbitrage*\n\n"
        "Send me the item name to test, e.g.:\n"
        "`AK-47 | Redline (Field-Tested)`"
    )
    await state_fsm.set_state(TestItemFSM.waiting_for_item)


@router.message(TestItemFSM.waiting_for_item)
@safe_call
async def cmd_test_receive(message, state_fsm: FSMContext):
    """Receive item name after the user pressed the button or /test without args."""
    item_name = (message.text or "").strip()
    if not item_name:
        await message.answer("❌ Empty item name. Send me the name or /cancel.")
        return
    await state_fsm.clear()
    await _do_test(message, item_name)


@router.message(Command("cancel"))
@safe_call
async def cmd_cancel(message, state_fsm: FSMContext):
    await state_fsm.clear()
    await message.answer("✅ Cancelled.", reply_markup=get_main_keyboard())


async def _do_test(message, item_name: str) -> None:
    """Run the actual arbitrage test (DMarket + free multi-source oracle)."""
    safe_name = escape_md(item_name)
    await message.answer(f"⏳ Testing `{safe_name}`...")

    from src.utils.vault import vault
    secret = (
        vault.get_dmarket_secret()
        if hasattr(vault, "get_dmarket_secret")
        else Config.SECRET_KEY
    )
    client = DMarketAPIClient(Config.PUBLIC_KEY, secret)  # type: ignore[arg-type]
    oracle = MultiSourceOracle()
    try:
        market = await retry_async(
            lambda: client.get_market_items_v2(Config.GAME_ID, limit=100),
            operation="test.market",
        )
        found = next(
            (
                it
                for it in market.get("objects", [])
                if it.get("title", "").lower() == item_name.lower()
            ),
            None,
        )

        if not found:
            await message.answer(f"❌ `{safe_name}` not found on DMarket.")
            return

        dm_price = float(found.get("price", {}).get("USD", 0)) / 100.0
        agg = await retry_async(
            lambda: client.get_aggregated_prices(Config.GAME_ID, [item_name]),
            operation="test.agg",
        )
        ag = agg.get(item_name, {})

        try:
            fair_result = await retry_async(
                lambda: oracle.get_fair_price(item_name),
                operation="test.oracle",
            )
            cs_price = fair_result.fair_price if fair_result.has_enough_sources else 0.0
        except Exception:
            cs_price = 0.0

        best_ask = ag.get("best_ask", 0.0)
        best_bid = ag.get("best_bid", 0.0)
        spread = ((best_bid - best_ask) / best_ask * 100) if best_ask > 0 else 0

        text = (
            f"🧪 *Arbitrage Test:* `{safe_name}`\n\n"
            f"📉 *DMarket:*\n"
            f"   Cheapest listing: `${dm_price:.2f}`\n"
            f"   Best ask: `${best_ask:.2f}`\n"
            f"   Best bid: `${best_bid:.2f}`\n"
            f"   Spread: `{spread:+.1f}%`\n\n"
            f"📈 *Free Oracle (multi-source):*\n"
            f"   Reference: `${cs_price:.2f}`\n\n"
        )

        if best_bid > best_ask * 1.05:
            est_profit = (best_bid - 0.01) * 0.95 - best_ask
            text += "✅ *VIABLE:* Spread >5%, profit potential!\n"
            text += f"   Est. net profit: `${est_profit:+.2f}` per item"
        elif best_bid > best_ask:
            text += "⚠️ *MARGINAL:* Spread exists but <5%"
        else:
            text += "❌ *NOT VIABLE:* No positive spread"

        await message.answer(text)
    finally:
        with contextlib.suppress(Exception):
            await client.close()
        with contextlib.suppress(Exception):
            await oracle.close()
