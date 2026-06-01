"""
commands.py — All /command and reply-keyboard button handlers.

Handles:
- /start, /help, /start_bot, /stop_bot, /panic
- /balance, /status, /inventory, /profits, /settings
- /test (with FSM), /cancel, /clock, /refresh
"""

import logging
import os
from typing import Optional

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.api.cs2cap_oracle import CS2CapOracle
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
from src.db.price_history import price_db
from src.utils.clock_sync import clock_sync

from .formatters import (
    format_balance,
    format_inventory_summary,
    format_profits_summary,
    format_status,
)
from .keyboards import (
    BTN_PANIC,
    BTN_START,
    BTN_STOP,
    BTN_TEST,
    get_inline_balance_kb,
    get_inline_inventory_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
    get_main_keyboard,
)
from .resilience import dmarket_client, retry_async, safe_call
from .state import state

logger = logging.getLogger("TelegramControl.commands")
router = Router(name="telegram-control-commands")


# ============================================================
# FSM for /test flow
# ============================================================
class TestItemFSM(StatesGroup):
    """FSM for /test flow when user pressed button (not typed /test <item>)."""
    waiting_for_item = State()


# ============================================================
# Welcome
# ============================================================
@router.message(Command("start"))
@safe_call
async def cmd_start(message: types.Message):
    mode = "🧪 SIMULATION (DRY_RUN)" if Config.DRY_RUN else "💸 LIVE TRADING"
    text = (
        f"🤖 *DMarket Sniper v{Config.BOT_VERSION} — Control Center*\n\n"
        f"📌 *Mode:* {mode}\n"
        f"🎯 *Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"💵 *Min Spread:* {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"💼 *Max Position:* {Config.MAX_POSITION_RISK_PCT}% of balance\n\n"
        f"Use the buttons below or type /help for all commands."
    )
    await message.answer(text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
@safe_call
async def cmd_help(message: types.Message):
    text = (
        "🆘 *Available Commands*\n\n"
        "*Control:*\n"
        "🚀 /start\\_bot — Start the sniping loop\n"
        "🛑 /stop\\_bot — Stop the sniping loop\n"
        "🔥 /panic — Emergency stop (kill switch)\n\n"
        "*Info:*\n"
        "💰 /balance — Real DMarket balance\n"
        "📊 /status — Bot state + equity\n"
        "📦 /inventory — Virtual inventory\n"
        "📈 /profits — Realized + unrealized P&L\n"
        "⚙️ /settings — View configuration\n\n"
        "*Actions:*\n"
        "🧪 /test `<item>` — Test arbitrage for an item\n"
        "🔄 /refresh — Refresh clocksync + caches\n"
        "⏰ /clock — View clock sync status\n"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


# ============================================================
# Control: start/stop/panic
# ============================================================
@router.message(Command("start_bot"))
@router.message(F.text == BTN_START)
@safe_call
async def cmd_start_bot(message: types.Message):
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
async def cmd_stop_bot(message: types.Message):
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
async def cmd_panic(message: types.Message):
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
        await message.answer(
            f"⚠️ Could not cancel offers: `{err}`\n"
            "Cancel manually if needed."
        )
    await message.answer("🔥 *Panic complete. You are safe.*")
    logger.warning(f"PANIC executed by admin {message.from_user.id}")


async def _cancel_all_offers() -> tuple[int, Optional[Exception]]:
    """Cancel all active offers on DMarket. Returns (count, error)."""
    client_to_close = None
    if state.client is None:
        # Bot was not running — create a temp client just for cancellation
        from src.utils.vault import vault

        secret = (
            vault.get_dmarket_secret()
            if hasattr(vault, "get_dmarket_secret")
            else Config.SECRET_KEY
        )
        state.client = DMarketAPIClient(Config.PUBLIC_KEY, secret)
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
            try:
                await client_to_close.close()
            except Exception:
                pass
            state.client = None


# ============================================================
# Info: balance / status / inventory / profits / settings
# ============================================================
@router.message(Command("balance"))
@router.message(F.text == "💰 BALANCE")
@safe_call
async def cmd_balance(message: types.Message):
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
async def cmd_status(message: types.Message):
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
async def cmd_inventory(message: types.Message):
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    selling = price_db.get_virtual_inventory(status='selling')
    sold = price_db.get_virtual_inventory(status='sold')
    await message.answer(
        format_inventory_summary(idle, selling, sold),
        reply_markup=get_inline_inventory_kb(),
    )


@router.message(Command("profits"))
@router.message(F.text == "📈 PROFITS")
@safe_call
async def cmd_profits(message: types.Message):
    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    selling = price_db.get_virtual_inventory(status='selling')
    await message.answer(
        format_profits_summary(sold, idle, selling, detailed=True),
        reply_markup=get_inline_profits_kb(),
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ SETTINGS")
@safe_call
async def cmd_settings(message: types.Message):
    text = (
        f"⚙️ *Configuration (v{Config.BOT_VERSION})*\n\n"
        f"*Risk:*\n"
        f"   Min spread: {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"   Min price: ${Config.MIN_PRICE_USD}\n"
        f"   Max price: ${Config.MAX_PRICE_USD}\n"
        f"   Max position: {Config.MAX_POSITION_RISK_PCT}%\n"
        f"   Max inventory: {Config.MAX_OPEN_INVENTORY} items\n\n"
        f"*Strategy:*\n"
        f"   Active: {Config.ACTIVE_STRATEGY}\n"
        f"   Game: {Config.GAME_ID}\n"
        f"   Fee rate: {Config.FEE_RATE*100:.1f}%\n\n"
        f"*v12.2 Defenses:*\n"
        f"   Wash trading: {Config.WASH_TRADING_DETECTION}\n"
        f"   Liquidity filter: {Config.USE_LIQUIDITY_FILTER}\n"
        f"   Min sales (liquidity): {Config.MIN_TOTAL_SALES}\n\n"
        f"*Mode:*\n"
        f"   DRY\\_RUN: `{Config.DRY_RUN}` {'🧪' if Config.DRY_RUN else '💸'}\n\n"
        f"💡 *Edit src/config.py to change settings, then restart bot.*"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


# ============================================================
# Test item (with FSM)
# ============================================================
@router.message(Command("test"))
@router.message(F.text == BTN_TEST)
@safe_call
async def cmd_test(message: types.Message, state_fsm: FSMContext):
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
        await state_fsm.set_state(TestItemFSM.waiting_for_item)
        return

    await _do_test(message, item_name)


@router.message(TestItemFSM.waiting_for_item)
@safe_call
async def cmd_test_receive(message: types.Message, state_fsm: FSMContext):
    """Receive item name after the user pressed the button or /test without args."""
    item_name = (message.text or "").strip()
    if not item_name:
        await message.answer("❌ Empty item name. Send me the name or /cancel.")
        return
    await state_fsm.clear()
    await _do_test(message, item_name)


@router.message(Command("cancel"))
@safe_call
async def cmd_cancel(message: types.Message, state_fsm: FSMContext):
    await state_fsm.clear()
    await message.answer("✅ Cancelled.", reply_markup=get_main_keyboard())


async def _do_test(message: types.Message, item_name: str) -> None:
    """Run the actual arbitrage test (DMarket + CS2Cap oracle)."""
    await message.answer(f"⏳ Testing `{item_name}`...")

    client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    oracle = CS2CapOracle(
        os.getenv("CS2C_API_KEY", ""),
        tier=os.getenv("CS2C_TIER", "free"),
    )
    try:
        market = await retry_async(
            lambda: client.get_market_items_v2(Config.GAME_ID, limit=100),
            operation="test.market",
        )
        found = next(
            (
                it for it in market.get("objects", [])
                if it.get("title", "").lower() == item_name.lower()
            ),
            None,
        )

        if not found:
            await message.answer(f"❌ `{item_name}` not found on DMarket.")
            return

        dm_price = float(found.get("price", {}).get("USD", 0)) / 100.0
        agg = await retry_async(
            lambda: client.get_aggregated_prices(Config.GAME_ID, [item_name]),
            operation="test.agg",
        )
        ag = agg.get(item_name, {})

        try:
            cs_price = await retry_async(
                lambda: oracle.get_item_price(item_name),
                operation="test.oracle",
            )
        except Exception:
            cs_price = 0.0

        best_ask = ag.get("best_ask", 0.0)
        best_bid = ag.get("best_bid", 0.0)
        spread = ((best_bid - best_ask) / best_ask * 100) if best_ask > 0 else 0

        text = (
            f"🧪 *Arbitrage Test:* `{item_name}`\n\n"
            f"📉 *DMarket:*\n"
            f"   Cheapest listing: `${dm_price:.2f}`\n"
            f"   Best ask: `${best_ask:.2f}`\n"
            f"   Best bid: `${best_bid:.2f}`\n"
            f"   Spread: `{spread:+.1f}%`\n\n"
            f"📈 *CS2Cap Oracle (BUFF163):*\n"
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
        try:
            await client.close()
        except Exception:
            pass
        try:
            await oracle.close()
        except Exception:
            pass


# ============================================================
# Misc: clock, refresh
# ============================================================
@router.message(Command("clock"))
@safe_call
async def cmd_clock(message: types.Message):
    cs = clock_sync.get_status()
    text = (
        f"🕐 *Clock Sync Status*\n\n"
        f"   Offset: `{cs['offset_seconds']}s`\n"
        f"   Last sync: `{cs['last_sync_ago_seconds']}s ago`\n"
        f"   Sync count: `{cs['sync_count']}`\n"
        f"   Drift warnings: `{cs['drift_warnings']}`\n"
        f"   Needs refresh: `{cs['needs_refresh']}`\n"
        f"   *Healthy:* `{cs['is_healthy']}`\n\n"
        f"   ⚠️ DMarket rejects X-Sign-Date if drift > 120s"
    )
    await message.answer(text)


@router.message(Command("refresh"))
@safe_call
async def cmd_refresh(message: types.Message):
    await message.answer("🔄 Refreshing clocksync + caches...")
    try:
        await clock_sync.sync_with_dmarket()
        cs = clock_sync.get_status()
        await message.answer(
            f"✅ *Refreshed!*\n\n"
            f"   New offset: `{cs['offset_seconds']}s`\n"
            f"   Healthy: `{cs['is_healthy']}`\n"
            f"   Last sync: `{cs['last_sync_ago_seconds']}s ago`"
        )
    except Exception as e:
        await message.answer(f"❌ Refresh failed: `{e}`")
