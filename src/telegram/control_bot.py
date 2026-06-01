"""
Telegram Control Bot v12.2 — Full Integration with DMarket Sniper.

Features:
- Start/Stop the sniping loop remotely
- View real DMarket balance
- View virtual inventory (from price_db)
- View realized + unrealized profit
- Test arbitrage for specific items
- Panic button (emergency stop)
- Working inline + reply keyboards

Run:
    PYTHONPATH=. python -m src.telegram.control_bot
"""

import asyncio
import logging
import os
import sys
import time
from typing import Optional

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.cs2cap_oracle import CS2CapOracle
from src.db.price_history import price_db
from src.core.target_sniping import SnipingLoop
from src.utils.clock_sync import clock_sync

load_dotenv()

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TelegramControl")

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set in .env!")
    sys.exit(1)
if not ADMIN_ID:
    logger.error("TELEGRAM_ADMIN_ID not set in .env!")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except (TypeError, ValueError):
    logger.error(f"TELEGRAM_ADMIN_ID must be numeric, got: {ADMIN_ID}")
    sys.exit(1)


# --- Access control ---
def is_admin(user_id: int) -> bool:
    """Only the configured admin can control the bot."""
    return user_id == ADMIN_ID


# --- Bot Setup ---
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- Global State ---
sniping_loop: Optional[SnipingLoop] = None
sniping_task: Optional[asyncio.Task] = None
is_running: bool = False
last_status_msg: Optional[types.Message] = None  # For inline updates


# ============================================================
# Keyboards
# ============================================================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard — always visible."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 START BOT"),
                KeyboardButton(text="🛑 STOP BOT"),
            ],
            [
                KeyboardButton(text="💰 BALANCE"),
                KeyboardButton(text="📊 STATUS"),
            ],
            [
                KeyboardButton(text="📦 INVENTORY"),
                KeyboardButton(text="📈 PROFITS"),
            ],
            [
                KeyboardButton(text="🧪 TEST ITEM"),
                KeyboardButton(text="⚙️ SETTINGS"),
            ],
            [
                KeyboardButton(text="🔥 PANIC"),
                KeyboardButton(text="🆘 HELP"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose action or /help",
    )


def get_inline_status_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for status message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟢 START" if not is_running else "🟡 RUNNING",
                callback_data="btn:start" if not is_running else "noop",
            ),
            InlineKeyboardButton(
                text="🔴 STOP" if is_running else "⚪ STOPPED",
                callback_data="btn:stop" if is_running else "noop",
            ),
        ],
        [
            InlineKeyboardButton(text="💰 Balance", callback_data="btn:balance"),
            InlineKeyboardButton(text="📦 Inventory", callback_data="btn:inventory"),
        ],
        [
            InlineKeyboardButton(text="📈 Profits", callback_data="btn:profits"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:refresh_status"),
        ],
    ])


def get_inline_inventory_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for inventory."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:inventory"),
            InlineKeyboardButton(text="📈 Profits", callback_data="btn:profits"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back to Status", callback_data="btn:refresh_status"),
        ],
    ])


# ============================================================
# Access filter
# ============================================================

@router.message(lambda m: not is_admin(m.from_user.id))
async def reject_non_admin(message: types.Message):
    """Silently ignore messages from non-admin users."""
    logger.warning(f"Unauthorized access attempt from user_id={message.from_user.id}")


@router.callback_query(lambda c: not is_admin(c.from_user.id))
async def reject_non_admin_callback(callback: types.CallbackQuery):
    """Silently ignore callbacks from non-admin users."""
    logger.warning(f"Unauthorized callback from user_id={callback.from_user.id}")


# ============================================================
# Commands
# ============================================================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Show welcome + main keyboard."""
    if not is_admin(message.from_user.id):
        return
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
async def cmd_help(message: types.Message):
    """Show all commands."""
    if not is_admin(message.from_user.id):
        return
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


@router.message(Command("start_bot"))
@router.message(F.text == "🚀 START BOT")
async def cmd_start_bot(message: types.Message):
    """Start the sniping loop in background."""
    global sniping_loop, sniping_task, is_running
    if not is_admin(message.from_user.id):
        return

    if is_running:
        await message.answer("⚠️ *Bot is already running!*\nUse /stop\\_bot to stop.")
        return

    try:
        sniping_loop = SnipingLoop(client=None)  # Will be created in run
        # Initialize client
        from src.utils.vault import vault
        sniping_loop.client = DMarketAPIClient(
            Config.PUBLIC_KEY,
            vault.get_dmarket_secret() if hasattr(vault, 'get_dmarket_secret') else Config.SECRET_KEY
        )

        is_running = True
        sniping_task = asyncio.create_task(sniping_loop.start())

        mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"
        await message.answer(
            f"✅ *Bot STARTED* in {mode} mode!\n\n"
            f"Strategy: {Config.ACTIVE_STRATEGY}\n"
            f"Game: {Config.GAME_ID}\n"
            f"Scan interval: {Config.SCAN_INTERVAL}s\n\n"
            f"Use 📊 STATUS to monitor progress."
        )
    except Exception as e:
        is_running = False
        logger.exception("Failed to start bot")
        await message.answer(f"❌ *Failed to start:* `{e}`")


@router.message(Command("stop_bot"))
@router.message(F.text == "🛑 STOP BOT")
async def cmd_stop_bot(message: types.Message):
    """Stop the sniping loop."""
    global is_running, sniping_task
    if not is_admin(message.from_user.id):
        return

    if not is_running:
        await message.answer("⚠️ *Bot is not running.*")
        return

    is_running = False
    if sniping_task:
        sniping_task.cancel()
        try:
            await sniping_task
        except asyncio.CancelledError:
            pass
        sniping_task = None

    if sniping_loop and sniping_loop.client:
        await sniping_loop.client.close()

    await message.answer(
        "🛑 *Bot STOPPED.*\n\n"
        "Active orders remain on DMarket (cancel manually if needed)."
    )


@router.message(Command("panic"))
@router.message(F.text == "🔥 PANIC")
async def cmd_panic(message: types.Message):
    """Emergency stop + cancel all offers."""
    global is_running, sniping_task
    if not is_admin(message.from_user.id):
        return

    await message.answer("🔥 *PANIC PROTOCOL INITIATED*\nStopping bot and cancelling all offers...")

    # 1. Stop loop
    is_running = False
    if sniping_task:
        sniping_task.cancel()
        try:
            await sniping_task
        except asyncio.CancelledError:
            pass
        sniping_task = None

    # 2. Cancel all offers
    try:
        from src.utils.vault import vault
        client = DMarketAPIClient(
            Config.PUBLIC_KEY,
            vault.get_dmarket_secret() if hasattr(vault, 'get_dmarket_secret') else Config.SECRET_KEY
        )
        try:
            offers = await client.get_user_offers_v2(Config.GAME_ID, limit=100)
            offer_ids = [o.get("offerId", "") for o in offers.get("items", []) if o.get("offerId")]
            if offer_ids:
                # Batch close
                result = await client.batch_delete_offers_v2(offer_ids)
                await message.answer(f"🗑 Cancelled {len(offer_ids)} offers.")
            else:
                await message.answer("✅ No active offers found.")
        finally:
            await client.close()
    except Exception as e:
        await message.answer(f"⚠️ Could not cancel offers: `{e}`\nCancel manually if needed.")

    await message.answer("🔥 *Panic complete. You are safe.*")


@router.message(Command("balance"))
@router.message(F.text == "💰 BALANCE")
async def cmd_balance(message: types.Message):
    """Show real DMarket balance."""
    if not is_admin(message.from_user.id):
        return
    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await client.get_real_balance()
            equity = price_db.get_total_equity(balance)
            text = (
                f"💰 *DMarket Balance*\n\n"
                f"💵 Cash: `${balance:.2f}`\n"
                f"📦 Locked in items: `${equity['assets']:.2f}` ({equity['count']} items)\n"
                f"💎 *Total Equity:* `${equity['total']:.2f}`"
            )
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:balance")]
            ]))
        finally:
            await client.close()
    except Exception as e:
        await message.answer(f"❌ Error: `{e}`")


@router.message(Command("status"))
@router.message(F.text == "📊 STATUS")
async def cmd_status(message: types.Message):
    """Show bot status with inline keyboard."""
    if not is_admin(message.from_user.id):
        return

    state = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE TRADING"

    # Clock sync status
    cs = clock_sync.get_status()
    clock_str = (
        f"   Offset: {cs['offset_seconds']}s\n"
        f"   Synced: {cs['sync_count']}x | Healthy: {cs['is_healthy']}"
    )

    # Get quick balance
    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await client.get_real_balance()
            equity = price_db.get_total_equity(balance)
            locked_str = f"${equity['assets']:.2f} ({equity['count']} items)"
            cash_str = f"${equity['cash']:.2f}"
            total_str = f"${equity['total']:.2f}"
        finally:
            await client.close()
    except Exception:
        cash_str = "N/A"
        locked_str = "N/A"
        total_str = "N/A"

    text = (
        f"📊 *Bot Status*\n\n"
        f"*State:* {state}\n"
        f"*Mode:* {mode}\n"
        f"*Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"*Version:* v{Config.BOT_VERSION}\n\n"
        f"💰 *Equity:*\n"
        f"   Cash: {cash_str}\n"
        f"   Locked: {locked_str}\n"
        f"   *Total:* {total_str}\n\n"
        f"⚙️ *Risk:*\n"
        f"   Min spread: {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"   Max position: {Config.MAX_POSITION_RISK_PCT}%\n"
        f"   Fee rate: {Config.FEE_RATE*100:.1f}%\n\n"
        f"🕐 *Clock Sync:*\n{clock_str}"
    )

    global last_status_msg
    last_status_msg = await message.answer(text, reply_markup=get_inline_status_kb())


@router.message(Command("inventory"))
@router.message(F.text == "📦 INVENTORY")
async def cmd_inventory(message: types.Message):
    """Show virtual inventory."""
    if not is_admin(message.from_user.id):
        return

    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    selling = price_db.get_virtual_inventory(status='selling')
    sold = price_db.get_virtual_inventory(status='sold')

    locked = [it for it in idle if it['unlock_at'] > time.time()]
    unlocked = [it for it in idle if it['unlock_at'] <= time.time()]

    text = (
        f"📦 *Virtual Inventory*\n\n"
        f"🔒 Locked (trade protection): {len(locked)}\n"
        f"🔓 Unlocked (ready to sell): {len(unlocked)}\n"
        f"🏪 Listed for sale: {len(selling)}\n"
        f"✅ Sold: {len(sold)}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *Total items:* {len(idle) + len(selling) + len(sold)}\n"
    )

    # Show top 5 items by value
    all_items = list(idle) + list(selling)
    if all_items:
        top = sorted(all_items, key=lambda x: -x['buy_price'])[:5]
        text += f"\n*Top items by value:*\n"
        for it in top:
            status_emoji = "🔒" if it['unlock_at'] > time.time() else "🔓"
            text += f"  {status_emoji} `{it['hash_name'][:30]}` — ${it['buy_price']:.2f}\n"

    await message.answer(text, reply_markup=get_inline_inventory_kb())


@router.message(Command("profits"))
@router.message(F.text == "📈 PROFITS")
async def cmd_profits(message: types.Message):
    """Show realized + unrealized profit."""
    if not is_admin(message.from_user.id):
        return

    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    selling = price_db.get_virtual_inventory(status='selling')

    realized = sum(it['profit'] or 0 for it in sold)
    realized_count = len(sold)
    win_count = sum(1 for it in sold if (it['profit'] or 0) > 0)
    win_rate = (win_count / realized_count * 100) if realized_count > 0 else 0

    # Unrealized = (current_list - buy_price) for listed items
    unrealized = 0.0
    for it in idle:
        # Estimate unrealized as 5% target minus fees
        target = it['buy_price'] * 1.05
        unrealized += (target - it['buy_price']) * 0.95

    total = realized + unrealized
    total_fees = sum(it['fee_paid'] or 0 for it in sold)

    text = (
        f"📈 *Profit & Loss*\n\n"
        f"💵 *Realized:*\n"
        f"   Total: `${realized:+.2f}`\n"
        f"   Trades: {realized_count} (win rate: {win_rate:.1f}%)\n"
        f"   Fees paid: `${total_fees:.2f}`\n\n"
        f"📊 *Unrealized (estimated):*\n"
        f"   Items listed: {len(idle) + len(selling)}\n"
        f"   Estimated value: `${unrealized:+.2f}`\n\n"
        f"💎 *Total P&L:* `${total:+.2f}`\n"
    )

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:profits")],
        [InlineKeyboardButton(text="⬅️ Status", callback_data="btn:refresh_status")],
    ]))


@router.message(Command("settings"))
@router.message(F.text == "⚙️ SETTINGS")
async def cmd_settings(message: types.Message):
    """Show configuration."""
    if not is_admin(message.from_user.id):
        return

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


@router.message(Command("test"))
@router.message(F.text == "🧪 TEST ITEM")
async def cmd_test(message: types.Message):
    """Test arbitrage for a specific item."""
    if not is_admin(message.from_user.id):
        return

    # Get item name from message text
    if message.text.startswith("/test"):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "🧪 *Test Arbitrage*\n\n"
                "Usage: `/test <Item Name>`\n"
                "Example: `/test AK-47 | Redline (Field-Tested)`"
            )
            return
        item_name = args[1].strip()
    else:
        await message.answer("Please use: `/test <Item Name>`")
        return

    await message.answer(f"⏳ Testing `{item_name}`...")

    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            # Get DMarket price
            market = await client.get_market_items_v2(Config.GAME_ID, limit=100)
            found = None
            for it in market.get("objects", []):
                if it.get("title", "").lower() == item_name.lower():
                    found = it
                    break

            if not found:
                await message.answer(f"❌ `{item_name}` not found on DMarket.")
                return

            dm_price = float(found.get("price", {}).get("USD", 0)) / 100.0

            # Get aggregated prices
            agg = await client.get_aggregated_prices(Config.GAME_ID, [item_name])
            ag = agg.get(item_name, {})

            # Get CS2Cap oracle price
            oracle = CS2CapOracle(os.getenv("CS2C_API_KEY", ""), tier=os.getenv("CS2C_TIER", "free"))
            try:
                cs_price = await oracle.get_item_price(item_name)
            except Exception:
                cs_price = 0.0
            finally:
                await oracle.close()

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

            # Recommendation
            if best_bid > best_ask * 1.05:
                text += f"✅ *VIABLE:* Spread >5%, profit potential!\n"
                est_profit = (best_bid - 0.01) * 0.95 - best_ask
                text += f"   Est. net profit: `${est_profit:+.2f}` per item"
            elif best_bid > best_ask:
                text += f"⚠️ *MARGINAL:* Spread exists but <5%"
            else:
                text += f"❌ *NOT VIABLE:* No positive spread"

            await message.answer(text)
        finally:
            await client.close()
    except Exception as e:
        await message.answer(f"❌ Error: `{e}`")


@router.message(Command("clock"))
async def cmd_clock(message: types.Message):
    """Show clock sync status."""
    if not is_admin(message.from_user.id):
        return
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
async def cmd_refresh(message: types.Message):
    """Force refresh of clocksync + caches."""
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔄 Refreshing clocksync + caches...")
    try:
        await clock_sync.sync_with_dmarket()
        await message.answer(f"✅ Refreshed!\n\n{cmd_clock.__name__}\nNew offset: `{clock_sync.offset}s`")
    except Exception as e:
        await message.answer(f"❌ Refresh failed: `{e}`")


# ============================================================
# Inline Button Callbacks
# ============================================================

@router.callback_query(F.data == "btn:start")
async def cb_start(callback: types.CallbackQuery):
    await callback.message.answer("Use 🚀 START BOT button or /start_bot command.")
    await callback.answer()


@router.callback_query(F.data == "btn:stop")
async def cb_stop(callback: types.CallbackQuery):
    await callback.message.answer("Use 🛑 STOP BOT button or /stop_bot command.")
    await callback.answer()


@router.callback_query(F.data == "btn:balance")
async def cb_balance(callback: types.CallbackQuery):
    """Re-render balance in current chat."""
    await callback.message.edit_text("💰 Fetching balance...")
    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await client.get_real_balance()
            equity = price_db.get_total_equity(balance)
            text = (
                f"💰 *DMarket Balance*\n\n"
                f"💵 Cash: `${balance:.2f}`\n"
                f"📦 Locked: `${equity['assets']:.2f}` ({equity['count']} items)\n"
                f"💎 *Total:* `${equity['total']:.2f}`"
            )
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:balance")]
                ])
            )
        finally:
            await client.close()
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: `{e}`")
    await callback.answer()


@router.callback_query(F.data == "btn:inventory")
async def cb_inventory(callback: types.CallbackQuery):
    """Re-render inventory."""
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    selling = price_db.get_virtual_inventory(status='selling')
    sold = price_db.get_virtual_inventory(status='sold')
    locked = [it for it in idle if it['unlock_at'] > time.time()]
    unlocked = [it for it in idle if it['unlock_at'] <= time.time()]

    text = (
        f"📦 *Virtual Inventory*\n\n"
        f"🔒 Locked: {len(locked)} | 🔓 Unlocked: {len(unlocked)}\n"
        f"🏪 Listed: {len(selling)} | ✅ Sold: {len(sold)}\n"
    )
    all_items = list(idle) + list(selling)
    if all_items:
        top = sorted(all_items, key=lambda x: -x['buy_price'])[:5]
        text += f"\n*Top items:*\n"
        for it in top:
            status_emoji = "🔒" if it['unlock_at'] > time.time() else "🔓"
            text += f"  {status_emoji} `{it['hash_name'][:30]}` — ${it['buy_price']:.2f}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_inline_inventory_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "btn:profits")
async def cb_profits(callback: types.CallbackQuery):
    """Re-render profits."""
    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)

    realized = sum(it['profit'] or 0 for it in sold)
    realized_count = len(sold)
    win_count = sum(1 for it in sold if (it['profit'] or 0) > 0)
    win_rate = (win_count / realized_count * 100) if realized_count > 0 else 0

    unrealized = sum((it['buy_price'] * 0.05 * 0.95) for it in idle)
    total = realized + unrealized

    text = (
        f"📈 *P&L Summary*\n\n"
        f"💵 Realized: `${realized:+.2f}` ({realized_count} trades, {win_rate:.0f}% win)\n"
        f"📊 Unrealized: `${unrealized:+.2f}` ({len(idle)} items)\n"
        f"💎 *Total:* `${total:+.2f}`"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:profits")],
            [InlineKeyboardButton(text="⬅️ Status", callback_data="btn:refresh_status")],
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "btn:refresh_status")
async def cb_refresh_status(callback: types.CallbackQuery):
    """Re-render full status."""
    state = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"

    cs = clock_sync.get_status()

    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await client.get_real_balance()
            equity = price_db.get_total_equity(balance)
            cash_str = f"${equity['cash']:.2f}"
            locked_str = f"${equity['assets']:.2f} ({equity['count']} items)"
            total_str = f"${equity['total']:.2f}"
        finally:
            await client.close()
    except Exception:
        cash_str = locked_str = total_str = "N/A"

    text = (
        f"📊 *Bot Status*\n\n"
        f"*State:* {state}\n"
        f"*Mode:* {mode}\n"
        f"*Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"*Version:* v{Config.BOT_VERSION}\n\n"
        f"💰 *Equity:*\n"
        f"   Cash: {cash_str}\n"
        f"   Locked: {locked_str}\n"
        f"   *Total:* {total_str}\n\n"
        f"🕐 *Clock:* offset={cs['offset_seconds']}s, healthy={cs['is_healthy']}"
    )
    await callback.message.edit_text(text, reply_markup=get_inline_status_kb())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: types.CallbackQuery):
    await callback.answer()


# ============================================================
# Bot Lifecycle
# ============================================================

async def set_commands(bot: Bot):
    """Register commands in Telegram menu."""
    commands = [
        types.BotCommand(command="start", description="🚀 Open Control Panel"),
        types.BotCommand(command="start_bot", description="▶️ Start sniping loop"),
        types.BotCommand(command="stop_bot", description="⏸ Stop sniping loop"),
        types.BotCommand(command="panic", description="🔥 Emergency stop + cancel offers"),
        types.BotCommand(command="balance", description="💰 Real DMarket balance"),
        types.BotCommand(command="status", description="📊 Bot status"),
        types.BotCommand(command="inventory", description="📦 View inventory"),
        types.BotCommand(command="profits", description="📈 P&L summary"),
        types.BotCommand(command="test", description="🧪 Test arbitrage for an item"),
        types.BotCommand(command="settings", description="⚙️ View config"),
        types.BotCommand(command="clock", description="🕐 Clock sync status"),
        types.BotCommand(command="refresh", description="🔄 Refresh clocksync"),
        types.BotCommand(command="help", description="🆘 Show all commands"),
    ]
    await bot.set_my_commands(commands)
    logger.info(f"✅ Registered {len(commands)} commands for admin_id={ADMIN_ID}")


async def on_startup(bot: Bot):
    """Called on bot startup."""
    me = await bot.get_me()
    logger.info(f"🤖 Bot started: @{me.username} (id={me.id})")
    logger.info(f"🔐 Admin ID: {ADMIN_ID}")
    logger.info(f"📌 Mode: {'DRY_RUN' if Config.DRY_RUN else 'LIVE TRADING'}")
    # Notify admin
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🤖 *Bot Online!*\n\n"
            f"Version: v{Config.BOT_VERSION}\n"
            f"Mode: {'🧪 SIMULATION' if Config.DRY_RUN else '💸 LIVE'}\n"
            f"Time: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            f"Use /help for commands."
        )
    except Exception as e:
        logger.error(f"Could not notify admin: {e}")


async def main():
    logger.info("🤖 Telegram Control Bot v12.2 starting...")
    await set_commands(bot)
    await on_startup(bot)
    logger.info("📡 Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
