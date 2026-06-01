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

Resilience (v12.2 hardening):
- sys.path auto-fix (works from any cwd)
- No sys.exit() at import time
- Global error handler catches all unhandled exceptions
- safe_call decorator wraps every command (never crashes mid-flow)
- Retry with exponential backoff for API calls
- Thread-safe state with asyncio.Lock
- Graceful shutdown on SIGTERM / SIGINT
- Logs to file + stdout

Run:
    python -m src.telegram.control_bot
or:
    ./scripts/start_telegram_bot.sh
"""

import asyncio
import functools
import logging
import os
import signal
import sys
import time
import traceback
from typing import Any, Awaitable, Callable, Optional

# --- sys.path auto-fix (variant 4 from plan) ---
# Ensures the bot works even if launched from a wrong directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # src/telegram/
_SRC_DIR = os.path.dirname(_THIS_DIR)                      # src/
_PROJECT_ROOT = os.path.dirname(_SRC_DIR)                  # /tmp/opencode/Dmarket_bot/
for p in (_PROJECT_ROOT, _SRC_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# --- Now safe to import third-party ---
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "telegram_bot.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
# Quiet down aiogram's chatty event log; keep warnings only
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)

logger = logging.getLogger("TelegramControl")

# --- State machine for /test flow ---
class TestItemFSM(StatesGroup):
    waiting_for_item = State()


# ============================================================
# Configuration
# ============================================================
def _load_config() -> tuple[Optional[str], Optional[int]]:
    """Load token + admin id; returns (token, admin_id) or raises."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")

    if not token or token.strip() == "":
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env!")
    if not admin_id_str or admin_id_str.strip() == "":
        raise ValueError("TELEGRAM_ADMIN_ID not set in .env!")
    try:
        admin_id = int(admin_id_str)
    except (TypeError, ValueError):
        raise ValueError(f"TELEGRAM_ADMIN_ID must be numeric, got: {admin_id_str!r}")
    return token.strip(), admin_id


# ============================================================
# Resilience: safe_call decorator + retry + lock
# ============================================================
def safe_call(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """
    Wrap a handler so any uncaught exception is logged and reported to the user
    instead of crashing the dispatcher.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled error in {func.__name__}: {e}")
            # Find the message-like object to reply to (real aiogram types or duck-typed mocks)
            message = None
            callback_obj = None
            for a in args:
                if isinstance(a, types.Message):
                    message = a
                    break
                if isinstance(a, types.CallbackQuery):
                    callback_obj = a
                    message = a.message
                    break
                # Duck-typed fallback (for unit tests)
                if hasattr(a, "answer") and callable(getattr(a, "answer", None)):
                    message = a
                    break
            try:
                err_text = f"❌ Internal error: `{e}`\n\nCheck logs/telegram_bot.log for details."
                if message:
                    await message.answer(err_text)
                if callback_obj is not None:
                    await callback_obj.answer("❌ Error", show_alert=True)
            except Exception:
                logger.exception("Failed to send error message to user")
    return wrapper


async def retry_async(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    retriable_exceptions: tuple = (TimeoutError, ConnectionError, Exception),
    operation: str = "API call",
) -> Any:
    """
    Run an async callable with exponential backoff.
    Treats (TimeoutError, ConnectionError, OSError, aiohttp.ClientError) as retriable.
    Other exceptions fail fast.
    """
    import aiohttp

    retriable = (TimeoutError, ConnectionError, OSError, aiohttp.ClientError)
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except retriable as e:
            last_exc = e
            if attempt == max_attempts:
                logger.error(f"{operation} failed after {max_attempts} attempts: {e}")
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(f"{operation} attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-retriable: re-raise immediately
            logger.error(f"{operation} non-retriable error: {e}")
            raise
    raise last_exc  # type: ignore[misc]


# ============================================================
# Access control
# ============================================================
def is_admin(user_id: int) -> bool:
    """Only the configured admin can control the bot."""
    return user_id == _ADMIN_ID


# ============================================================
# Router (module-level; decorators below attach handlers to this)
# ============================================================
router = Router(name="telegram-control")


# ============================================================
# Bot Setup (done lazily after config validation)
# ============================================================
def create_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure aiogram instances."""
    bot = Bot(
        token=_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return bot, dp


# ============================================================
# Global State (thread-safe via _state_lock)
# ============================================================
class BotState:
    """Container for the sniping loop + flags with a single async lock."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.sniping_loop: Optional[SnipingLoop] = None
        self.sniping_task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self.client: Optional[DMarketAPIClient] = None

    async def start(self) -> None:
        async with self.lock:
            if self.is_running:
                return False
            # Build client once and reuse
            from src.utils.vault import vault
            secret = (
                vault.get_dmarket_secret()
                if hasattr(vault, "get_dmarket_secret")
                else Config.SECRET_KEY
            )
            self.client = DMarketAPIClient(Config.PUBLIC_KEY, secret)
            self.sniping_loop = SnipingLoop(client=self.client)
            self.is_running = True
            self.sniping_task = asyncio.create_task(self.sniping_loop.start())
            return True

    async def stop(self) -> bool:
        async with self.lock:
            if not self.is_running:
                return False
            self.is_running = False
            if self.sniping_task:
                self.sniping_task.cancel()
                try:
                    await self.sniping_task
                except asyncio.CancelledError:
                    pass
                self.sniping_task = None
            if self.client:
                try:
                    await self.client.close()
                except Exception:
                    logger.exception("Error closing client")
                self.client = None
            self.sniping_loop = None
            return True

    async def status(self) -> dict:
        async with self.lock:
            return {
                "is_running": self.is_running,
                "has_task": self.sniping_task is not None,
                "has_client": self.client is not None,
            }


state = BotState()

# ============================================================
# Keyboards
# ============================================================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard — always visible."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 START BOT"), KeyboardButton(text="🛑 STOP BOT")],
            [KeyboardButton(text="💰 BALANCE"), KeyboardButton(text="📊 STATUS")],
            [KeyboardButton(text="📦 INVENTORY"), KeyboardButton(text="📈 PROFITS")],
            [KeyboardButton(text="🧪 TEST ITEM"), KeyboardButton(text="⚙️ SETTINGS")],
            [KeyboardButton(text="🔥 PANIC"), KeyboardButton(text="🆘 HELP")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose action or /help",
    )


def get_inline_status_kb(is_running: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟡 RUNNING" if is_running else "🟢 START",
                callback_data="noop" if is_running else "btn:start",
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:inventory"),
            InlineKeyboardButton(text="📈 Profits", callback_data="btn:profits"),
        ],
        [InlineKeyboardButton(text="⬅️ Back to Status", callback_data="btn:refresh_status")],
    ])


# ============================================================
# Access filters (silently drop non-admins)
# ============================================================
@router.message(lambda m: not is_admin(m.from_user.id))
async def reject_non_admin(message: types.Message):
    logger.warning(f"Unauthorized access attempt from user_id={message.from_user.id}")


@router.callback_query(lambda c: not is_admin(c.from_user.id))
async def reject_non_admin_callback(callback: types.CallbackQuery):
    logger.warning(f"Unauthorized callback from user_id={callback.from_user.id}")
    await callback.answer("⛔ Access denied", show_alert=True)


# ============================================================
# Global error handler
# ============================================================
@router.errors()
async def on_router_error(event: types.ErrorEvent):
    """Catches exceptions raised inside any handler — never lets the dispatcher die."""
    logger.exception(
        f"Router error in update {event.update.update_id}: {event.exception}"
    )


# ============================================================
# Commands
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


@router.message(Command("start_bot"))
@router.message(F.text == "🚀 START BOT")
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
@router.message(F.text == "🛑 STOP BOT")
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
@router.message(F.text == "🔥 PANIC")
@safe_call
async def cmd_panic(message: types.Message):
    await message.answer("🔥 *PANIC PROTOCOL INITIATED*\nStopping bot and cancelling all offers...")

    # 1. Stop loop (reuses the SAME client)
    await state.stop()

    # 2. Reuse client's existing offers endpoint to cancel everything
    cancelled = 0
    err = None
    try:
        if state.client is None:
            # Bot was not running; create a temp client just for cancellation
            from src.utils.vault import vault
            secret = (
                vault.get_dmarket_secret()
                if hasattr(vault, "get_dmarket_secret")
                else Config.SECRET_KEY
            )
            state.client = DMarketAPIClient(Config.PUBLIC_KEY, secret)
        offers_resp = await retry_async(
            lambda: state.client.get_user_offers_v2(Config.GAME_ID, limit=100),  # type: ignore[union-attr]
            operation="PANIC: list offers",
        )
        offer_ids = [o.get("offerId", "") for o in offers_resp.get("items", []) if o.get("offerId")]
        if offer_ids:
            result = await retry_async(
                lambda: state.client.batch_delete_offers_v2(offer_ids),  # type: ignore[union-attr]
                operation="PANIC: cancel offers",
            )
            cancelled = len(offer_ids)
        else:
            cancelled = 0
    except Exception as e:
        err = e
        logger.exception("PANIC cancellation failed")
    finally:
        # Always close the temp/used client after panic
        if state.client is not None:
            try:
                await state.client.close()
            except Exception:
                pass
            state.client = None

    if err is None:
        if cancelled:
            await message.answer(f"🗑 Cancelled {cancelled} offers.")
        else:
            await message.answer("✅ No active offers found.")
    else:
        await message.answer(
            f"⚠️ Could not cancel offers: `{err}`\nCancel manually if needed."
        )
    await message.answer("🔥 *Panic complete. You are safe.*")
    logger.warning(f"PANIC executed by admin {message.from_user.id}")


@router.message(Command("balance"))
@router.message(F.text == "💰 BALANCE")
@safe_call
async def cmd_balance(message: types.Message):
    async def _do() -> DMarketAPIClient:
        return DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)

    client = await _do()
    try:
        balance = await retry_async(
            lambda: client.get_real_balance(),
            operation="balance",
        )
        equity = price_db.get_total_equity(balance)
        text = (
            f"💰 *DMarket Balance*\n\n"
            f"💵 Cash: `${balance:.2f}`\n"
            f"📦 Locked in items: `${equity['assets']:.2f}` ({equity['count']} items)\n"
            f"💎 *Total Equity:* `${equity['total']:.2f}`"
        )
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:balance")]
            ]),
        )
    finally:
        await client.close()


@router.message(Command("status"))
@router.message(F.text == "📊 STATUS")
@safe_call
async def cmd_status(message: types.Message):
    st = await state.status()
    is_running = st["is_running"]
    state_str = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE TRADING"

    cs = clock_sync.get_status()
    clock_str = (
        f"   Offset: {cs['offset_seconds']}s\n"
        f"   Synced: {cs['sync_count']}x | Healthy: {cs['is_healthy']}"
    )

    cash_str = locked_str = total_str = "N/A"
    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="status.balance",
            )
            equity = price_db.get_total_equity(balance)
            locked_str = f"${equity['assets']:.2f} ({equity['count']} items)"
            cash_str = f"${equity['cash']:.2f}"
            total_str = f"${equity['total']:.2f}"
        finally:
            await client.close()
    except Exception:
        pass

    text = (
        f"📊 *Bot Status*\n\n"
        f"*State:* {state_str}\n"
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

    await message.answer(text, reply_markup=get_inline_status_kb(is_running))


@router.message(Command("inventory"))
@router.message(F.text == "📦 INVENTORY")
@safe_call
async def cmd_inventory(message: types.Message):
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
@safe_call
async def cmd_profits(message: types.Message):
    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    selling = price_db.get_virtual_inventory(status='selling')

    realized = sum(it['profit'] or 0 for it in sold)
    realized_count = len(sold)
    win_count = sum(1 for it in sold if (it['profit'] or 0) > 0)
    win_rate = (win_count / realized_count * 100) if realized_count > 0 else 0

    unrealized = 0.0
    for it in idle:
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

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="btn:profits")],
            [InlineKeyboardButton(text="⬅️ Status", callback_data="btn:refresh_status")],
        ]),
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


@router.message(Command("test"))
@router.message(F.text == "🧪 TEST ITEM")
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
    """Receive the item name after the user pressed the button or /test without args."""
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
    await message.answer(f"⏳ Testing `{item_name}`...")

    client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    oracle = CS2CapOracle(os.getenv("CS2C_API_KEY", ""), tier=os.getenv("CS2C_TIER", "free"))
    try:
        market = await retry_async(
            lambda: client.get_market_items_v2(Config.GAME_ID, limit=100),
            operation="test.market",
        )
        found = None
        for it in market.get("objects", []):
            if it.get("title", "").lower() == item_name.lower():
                found = it
                break

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
            text += f"✅ *VIABLE:* Spread >5%, profit potential!\n"
            est_profit = (best_bid - 0.01) * 0.95 - best_ask
            text += f"   Est. net profit: `${est_profit:+.2f}` per item"
        elif best_bid > best_ask:
            text += f"⚠️ *MARGINAL:* Spread exists but <5%"
        else:
            text += f"❌ *NOT VIABLE:* No positive spread"

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


# ============================================================
# Inline Button Callbacks
# ============================================================
@router.callback_query(F.data == "btn:start")
@safe_call
async def cb_start(callback: types.CallbackQuery):
    await callback.message.answer("Use 🚀 START BOT button or /start_bot command.")
    await callback.answer()


@router.callback_query(F.data == "btn:stop")
@safe_call
async def cb_stop(callback: types.CallbackQuery):
    await callback.message.answer("Use 🛑 STOP BOT button or /stop_bot command.")
    await callback.answer()


@router.callback_query(F.data == "btn:balance")
@safe_call
async def cb_balance(callback: types.CallbackQuery):
    await callback.message.edit_text("💰 Fetching balance...")
    client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        balance = await retry_async(
            lambda: client.get_real_balance(),
            operation="cb.balance",
        )
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
            ]),
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: `{e}`")
    finally:
        await client.close()
    await callback.answer()


@router.callback_query(F.data == "btn:inventory")
@safe_call
async def cb_inventory(callback: types.CallbackQuery):
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

    await callback.message.edit_text(text, reply_markup=get_inline_inventory_kb())
    await callback.answer()


@router.callback_query(F.data == "btn:profits")
@safe_call
async def cb_profits(callback: types.CallbackQuery):
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
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "btn:refresh_status")
@safe_call
async def cb_refresh_status(callback: types.CallbackQuery):
    st = await state.status()
    is_running = st["is_running"]
    state_str = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"

    cs = clock_sync.get_status()

    cash_str = locked_str = total_str = "N/A"
    try:
        client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
        try:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="cb.refresh_status",
            )
            equity = price_db.get_total_equity(balance)
            cash_str = f"${equity['cash']:.2f}"
            locked_str = f"${equity['assets']:.2f} ({equity['count']} items)"
            total_str = f"${equity['total']:.2f}"
        finally:
            await client.close()
    except Exception:
        pass

    text = (
        f"📊 *Bot Status*\n\n"
        f"*State:* {state_str}\n"
        f"*Mode:* {mode}\n"
        f"*Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"*Version:* v{Config.BOT_VERSION}\n\n"
        f"💰 *Equity:*\n"
        f"   Cash: {cash_str}\n"
        f"   Locked: {locked_str}\n"
        f"   *Total:* {total_str}\n\n"
        f"🕐 *Clock:* offset={cs['offset_seconds']}s, healthy={cs['is_healthy']}"
    )
    await callback.message.edit_text(text, reply_markup=get_inline_status_kb(is_running))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: types.CallbackQuery):
    await callback.answer()


# ============================================================
# Bot Lifecycle
# ============================================================
async def set_commands(bot: Bot) -> None:
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
    logger.info(f"Registered {len(commands)} commands for admin_id={_ADMIN_ID}")


async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username} (id={me.id})")
    logger.info(f"Admin ID: {_ADMIN_ID}")
    logger.info(f"Mode: {'DRY_RUN' if Config.DRY_RUN else 'LIVE TRADING'}")
    try:
        await bot.send_message(
            _ADMIN_ID,
            f"🤖 *Bot Online!*\n\n"
            f"Version: v{Config.BOT_VERSION}\n"
            f"Mode: {'🧪 SIMULATION' if Config.DRY_RUN else '💸 LIVE'}\n"
            f"Time: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            f"Use /help for commands.",
        )
    except Exception as e:
        logger.error(f"Could not notify admin: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Graceful shutdown: stop the loop, close the bot, notify admin."""
    logger.info("Shutdown signal received...")
    try:
        await state.stop()
    except Exception:
        logger.exception("Error stopping sniping loop on shutdown")
    try:
        await bot.send_message(
            _ADMIN_ID,
            "🛑 *Bot shutting down.*\n"
            f"Time: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        )
    except Exception:
        pass
    try:
        await bot.session.close()
    except Exception:
        pass
    # Clean up PID file if launcher set one
    pid_file = os.getenv("TELEGRAM_BOT_PID_FILE")
    if pid_file and os.path.exists(pid_file):
        try:
            os.unlink(pid_file)
            logger.info(f"Removed PID file: {pid_file}")
        except OSError as e:
            logger.warning(f"Could not remove PID file {pid_file}: {e}")
    logger.info("Shutdown complete.")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, bot: Bot, dp: Dispatcher) -> None:
    """Handle SIGTERM/SIGINT gracefully.

    We cancel the polling task and let the dispatcher unwind, instead of
    calling `loop.stop()` directly (which can leave pending futures dangling).
    """
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(_graceful_shutdown(bot, dp)),
            )
        except NotImplementedError:
            # Windows fallback: not supported
            pass


async def _graceful_shutdown(bot: Bot, dp: Dispatcher) -> None:
    """Stop polling, run cleanup, let the loop finish naturally."""
    try:
        # Cancel the polling cycle
        await dp.stop_polling()
    except Exception:
        logger.exception("Error stopping polling")
    try:
        await on_shutdown(bot)
    except Exception:
        logger.exception("Error during on_shutdown")


# ============================================================
# Module-level config: validate eagerly, expose constants
# ============================================================
try:
    _TOKEN, _ADMIN_ID = _load_config()
    logger.info(f"Configuration loaded (admin_id={_ADMIN_ID})")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    logger.error("Please create a .env file with TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID")
    _TOKEN = ""
    _ADMIN_ID = 0


_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None


def _lazy_bot() -> tuple[Bot, Dispatcher]:
    global _bot, _dp
    if _bot is None:
        if not _TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set — cannot create bot")
        _bot, _dp = create_bot()
    return _bot, _dp


async def main() -> None:
    logger.info(f"Telegram Control Bot v{Config.BOT_VERSION} starting...")
    if not _TOKEN:
        logger.error("Aborting: no TELEGRAM_BOT_TOKEN")
        return
    bot, dp = _lazy_bot()
    dp.include_router(router)
    _install_signal_handlers(asyncio.get_running_loop(), bot, dp)

    await set_commands(bot)
    await on_startup(bot)
    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.exception(f"Polling crashed: {e}")
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)
