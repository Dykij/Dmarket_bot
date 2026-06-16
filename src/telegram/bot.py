"""
Telegram Control Center — v10.0 with CS2Cap Integration.

Commands:
/start       — Control panel
/status      — Bot status + CS2Cap connection
/balance     — DMarket balance
/inventory   — Items in stock (with CS2Cap prices)
/sell        — List items for sale using CS2Cap pricing
/portfolio   — Full portfolio summary with PnL
/test_trade  — Test arbitrage DMarket → CS2Cap
/reflection  — Self-reflection stats
/pagination  — Test pagination across all pages
/panic       — Emergency stop + cancel all
/settings    — Current config
/daily       — Daily P&L briefing
/help        — Help guide
"""

"""
WARNING: This module is DEPRECATED (v10 legacy).
Use src/telegram/control_bot/ instead.

Security issues in this file (v12.9+):
- 9 instances of raw exception `{e}` leaked to users (CVE-2026-32982)
- 9 instances of Config.SECRET_KEY bypassing vault (vault discipline)
- No ThrottlingMiddleware (CVE-2026-35628)
- No SecurityAuditor logging filter
- No HealthServer integration

All fixes below are hot-patches. The module should be removed once
control_bot/ fully replaces it.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
from src.db.price_history import price_db
from src.core.resale_pipeline import ResalePipeline
from src.inventory_manager import InventoryManager
from src.analytics.self_reflection import self_reflection

load_dotenv()

from src.utils.logging_setup import configure_logging
configure_logging(component="bot_legacy")
logger = logging.getLogger("TelegramControl")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_IDS_STR = os.getenv("TELEGRAM_ADMIN_IDS", "")
ADMIN_IDS: set[str] = set()
if ADMIN_IDS_STR:
    ADMIN_IDS = {x.strip() for x in ADMIN_IDS_STR.split(",") if x.strip()}
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)


def _is_admin(user_id: int | None) -> bool:
    """Check if user is an authorized admin."""
    if user_id is None:
        return False
    return str(user_id) in ADMIN_IDS


def _get_api_client() -> DMarketAPIClient:
    """Create DMarketAPIClient using vault (not Config.SECRET_KEY raw).

    v12.9: All production code must go through vault so the secret key
    is encrypted in memory via Fernet.
    """
    from src.utils.vault import vault
    secret = (
        vault.get_dmarket_secret()
        if hasattr(vault, "get_dmarket_secret")
        else Config.SECRET_KEY
    )
    return DMarketAPIClient(Config.PUBLIC_KEY, secret)


if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN missing!")
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

trading_task: Optional[asyncio.Task] = None
is_running = False

# --- Keyboards ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="START BOT"), KeyboardButton(text="STOP BOT")],
        [KeyboardButton(text="BALANCE"), KeyboardButton(text="STATUS")],
        [KeyboardButton(text="INVENTORY"), KeyboardButton(text="SELL")],
        [KeyboardButton(text="PORTFOLIO"), KeyboardButton(text="CONFIG")],
    ],
    resize_keyboard=True,
)


# =================================================================
# CORE COMMANDS
# =================================================================

def _admin_only(handler):
    """Decorator to restrict handler to authorized admins only."""
    from functools import wraps

    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        if not _is_admin(message.from_user.id if message.from_user else None):
            logger.warning(
                f"Unauthorized command attempt from user_id={message.from_user.id if message.from_user else 'unknown'}"
            )
            return
        return await handler(message, *args, **kwargs)
    return wrapper


@router.message(Command("start"))
@_admin_only
async def cmd_start(message: types.Message):
    cs2cap_status = "Connected" if os.getenv("CS2CAP_API_KEY") else "Not configured"
    oracle = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
    oracle_type = "CS2Cap (41 markets)" if oracle else "CSFloat (fallback)"

    await message.answer(
        f"DMarket Quantitative Engine\n"
        f"Mode: {'SIMULATION' if Config.DRY_RUN else 'LIVE TRADING'}\n"
        f"Oracle: {oracle_type}\n"
        f"CS2Cap: {cs2cap_status}\n\n"
        f"Ready.",
        reply_markup=main_kb,
    )


@router.message(F.text == "START BOT")
@_admin_only
async def btn_start(message: types.Message):
    global trading_task, is_running

    if is_running:
        await message.answer("Bot is already running!")
        return

    is_running = True
    trading_task = asyncio.create_task(run_trading_wrapper())
    await message.answer("Bot STARTED. Scanning market...")


@router.message(F.text == "STOP BOT")
@_admin_only
async def btn_stop(message: types.Message):
    global trading_task, is_running

    if not is_running:
        await message.answer("Bot is not running.")
        return

    is_running = False
    if trading_task:
        trading_task.cancel()
        try:
            await trading_task
        except asyncio.CancelledError:
            pass

    await message.answer("Bot STOPPED. Orders remain active.")


# =================================================================
# BALANCE & STATUS
# =================================================================

@router.message(F.text == "BALANCE")
@_admin_only
async def btn_balance(message: types.Message):
    api = _get_api_client()
    try:
        usd = await api.get_real_balance()
        await message.answer(f"Balance: ${usd:.2f} USD")
    except Exception as e:
        logger.exception(f"btn_balance failed: {e}")
        await message.answer("❌ Error fetching balance. Check logs.")
    finally:
        await api.close()


@router.message(F.text == "STATUS")
@_admin_only
async def btn_status(message: types.Message):
    status = "RUNNING" if is_running else "STOPPED"
    mode = "SIMULATION" if Config.DRY_RUN else "LIVE"
    oracle = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
    oracle_type = "CS2Cap" if oracle else "CSFloat"

    daily_trades = price_db.state_conn.execute(
        "SELECT COUNT(*) FROM active_targets WHERE created_at > ?",
        (price_db.state_conn.execute("SELECT MAX(created_at) - 86400 FROM active_targets").fetchone()[0] or 0,),
    ).fetchone()[0] or 0

    await message.answer(
        f"Status: {status}\n"
        f"Mode: {mode}\n"
        f"Strategy: {Config.ACTIVE_STRATEGY}\n"
        f"Oracle: {oracle_type}\n"
        f"Spread Target: >{Config.MIN_SPREAD_PCT}%\n"
        f"Daily Trades: {daily_trades}/{Config.MAX_DAILY_TRADES}\n"
        f"Game: CS2"
    )


# =================================================================
# INVENTORY
# =================================================================

@router.message(F.text == "INVENTORY")
@_admin_only
async def btn_inventory(message: types.Message):
    api = _get_api_client()
    try:
        inv_mgr = InventoryManager(api)
        data = await inv_mgr.fetch_all_with_cs2cap(Config.GAME_ID)

        msg = f"INVENTORY ({data['total_items']} items)\n\n"

        for item in data["inventory"][:10]:
            title = item["title"]
            status = item["status"]
            buy = item.get("buy_price", 0)
            cs2cap = item.get("cs2cap_price", 0)
            pnl = item.get("profit_pct", 0)

            if status == "inventory":
                pnl_str = f" | PnL: {pnl:+.1f}%" if cs2cap > 0 else ""
                msg += f"- {title}\n  Buy: ${buy:.2f} | CS2Cap: ${cs2cap:.2f}{pnl_str}\n"
            elif status == "on_sale":
                list_p = item.get("list_price", 0)
                msg += f"- {title}\n  Listed: ${list_p:.2f} | CS2Cap: ${cs2cap:.2f}\n"

        if data["total_items"] > 10:
            msg += f"...and {data['total_items'] - 10} more.\n"

        msg += f"\nInventory: {data['inventory_count']} | On Sale: {data['offers_count']}"
        await message.answer(msg)
    except Exception as e:
        logger.exception(f"btn_inventory failed: {e}")
        await message.answer("❌ Error fetching inventory. Check logs.")
    finally:
        await api.close()


# =================================================================
# SELL
# =================================================================

@router.message(F.text == "SELL")
@_admin_only
async def btn_sell(message: types.Message):
    api = _get_api_client()
    try:
        pipeline = ResalePipeline(api)
        listed = await pipeline.sell_inventory_items(max_items=5)

        if not listed:
            await message.answer("No items ready for sale.\nEither no items past trade lock or margins too low.")
            return

        msg = f"LISTED {len(listed)} items for sale:\n\n"
        for item in listed:
            msg += (
                f"- {item['title']}\n"
                f"  Buy: ${item['buy_price']:.2f} -> Sell: ${item['sell_price']:.2f}\n"
                f"  Profit: {item['profit_pct']:.1f}%\n"
            )

        await message.answer(msg)
    except Exception as e:
        logger.exception(f"btn_sell failed: {e}")
        await message.answer("❌ Error listing items. Check logs.")
    finally:
        await api.close()


# =================================================================
# PORTFOLIO
# =================================================================

@router.message(F.text == "PORTFOLIO")
@_admin_only
async def btn_portfolio(message: types.Message):
    api = _get_api_client()
    try:
        balance = await api.get_real_balance()
        inv_mgr = InventoryManager(api)
        summary = inv_mgr.get_portfolio_summary(current_balance=balance)

        msg = (
            f"PORTFOLIO SUMMARY\n\n"
            f"Cash: ${summary['cash']:.2f}\n"
            f"Assets: ${summary['assets_value']:.2f}\n"
            f"Total Equity: ${summary['total_equity']:.2f}\n\n"
            f"Holding: {summary['items_holding']} items\n"
            f"Sold: {summary['items_sold']} items\n"
            f"Total Invested: ${summary['total_invested']:.2f}\n"
            f"Realized PnL: ${summary['total_realized_pnl']:.2f}\n"
            f"Avg Buy Price: ${summary['avg_buy_price']:.2f}"
        )
        await message.answer(msg)
    except Exception as e:
        logger.exception(f"btn_portfolio failed: {e}")
        await message.answer("❌ Error fetching portfolio. Check logs.")
    finally:
        await api.close()


# =================================================================
# TEST TRADE (with CS2Cap)
# =================================================================

@router.message(Command("test_trade"))
@_admin_only
async def cmd_test_trade(message: types.Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Usage: /test_trade <Item Name>\n"
            "Example: /test_trade AK-47 | Redline (Field-Tested)"
        )
        return

    item_name = args[1].strip()
    await message.answer(f"Testing arbitrage for: {item_name}\nFetching DMarket + CS2Cap data...")

    dm_api = _get_api_client()
    cs2cap = OracleFactory.get_cross_market_oracle(Config.GAME_ID)

    try:
        # DMarket check
        dm_resp = await dm_api.get_market_items_v2(Config.GAME_ID, title=item_name, limit=1)
        dm_objects = dm_resp.get("objects", [])
        if not dm_objects:
            await message.answer("Item not found on DMarket.")
            return

        dm_best_price = float(dm_objects[0].get("price", {}).get("USD", 0)) / 100.0

        # CS2Cap check
        cs2cap_price = 0.0
        if cs2cap:
            cs2cap_price = await cs2cap.get_item_price(item_name)

        if cs2cap_price <= 0:
            await message.answer(f"CS2Cap could not find price for {item_name}.")
            return

        # Cross-market data
        cross_data = None
        if cs2cap:
            cross_data = await cs2cap.get_cross_market_data(item_name)

        # NOTE (Phase 8): get_market_indicators (RSI/MACD) is a Quant-tier
        # feature. On Starter/Pro it always returns None — removed to avoid
        # a wasted await on every /test_trade command.

        # Validate
        estimated_sell = cs2cap_price * 0.98
        try:
            margin = validate_arbitrage_profit(
                buy_price=dm_best_price,
                expected_sell_price=estimated_sell,
                fee_markup=0.05,
                min_profit_margin=Config.MIN_SPREAD_PCT / 100.0,
            )

            msg = (
                f"ARBITRAGE VALIDATED\n\n"
                f"Item: {item_name}\n"
                f"DMarket Best: ${dm_best_price:.2f}\n"
                f"CS2Cap (41 markets): ${cs2cap_price:.2f}\n"
                f"Sell Target: ${estimated_sell:.2f}\n"
                f"Net Margin: {margin*100:.1f}%\n"
            )

            if cross_data and cross_data.provider_prices:
                msg += f"\nCross-market prices ({len(cross_data.provider_prices)} providers):\n"
                for prov, price in sorted(cross_data.provider_prices.items(), key=lambda x: x[1])[:5]:
                    msg += f"  {prov}: ${price:.2f}\n"

            await message.answer(msg)

        except PriceValidationError as pe:
            await message.answer(
                f"TRADE BLOCKED\n\n"
                f"Item: {item_name}\n"
                f"DMarket: ${dm_best_price:.2f}\n"
                f"CS2Cap: ${cs2cap_price:.2f}\n"
                f"Reason: {pe}"
            )

    except Exception as e:
        logger.exception(f"cmd_test_trade failed: {e}")
        await message.answer("❌ API Error during test. Check logs.")
    finally:
        await dm_api.close()
        if cs2cap:
            await cs2cap.close()


# =================================================================
# PAGINATION TEST
# =================================================================

@router.message(Command("pagination"))
@_admin_only
async def cmd_pagination(message: types.Message):
    """Test pagination across all DMarket pages."""
    api = _get_api_client()
    try:
        total_items = 0
        page = 0
        cursor = None

        while page < 10:  # Limit to 10 pages for test
            response = await api.get_market_items_v2(Config.GAME_ID, limit=Config.BATCH_SIZE, cursor=cursor)
            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")

            total_items += len(items)
            page += 1

            if not next_cursor or next_cursor == cursor or len(items) < Config.BATCH_SIZE:
                break
            cursor = next_cursor

        await message.answer(
            f"PAGINATION TEST\n\n"
            f"Pages scanned: {page}\n"
            f"Total items found: {total_items}\n"
            f"Batch size: {Config.BATCH_SIZE}\n"
            f"Status: {'OK' if total_items > 0 else 'No items found'}"
        )
    except Exception as e:
        logger.exception(f"cmd_pagination failed: {e}")
        await message.answer("❌ Pagination error. Check logs.")
    finally:
        await api.close()


# =================================================================
# SELF-REFLECTION
# =================================================================

@router.message(Command("reflection"))
@_admin_only
async def cmd_reflection(message: types.Message):
    reflection = await self_reflection.analyze_recent_trades()
    if reflection is None:
        await message.answer("Not enough trade data for reflection.\nNeed at least 10 trades.")
        return

    msg = (
        f"SELF-REFLECTION\n\n"
        f"Trades Analyzed: {reflection.total_trades_analyzed}\n"
        f"Win Rate: {reflection.win_rate:.1%}\n"
        f"Sharpe Ratio: {reflection.sharpe_ratio:.2f}\n"
        f"Sortino Ratio: {reflection.sortino_ratio:.2f}\n"
        f"Max Drawdown: {reflection.max_drawdown:.2%}\n"
        f"Confidence: {reflection.confidence:.1%}\n\n"
        f"Recommendations:\n"
        f"  Spread adj: {reflection.recommended_spread_adjustment:+.2f}%\n"
        f"  Risk adj: {reflection.recommended_risk_adjustment:+.2f}%\n"
        f"  Vol adj: {reflection.recommended_volatility_adjustment:+.2f}%"
    )
    await message.answer(msg)


# =================================================================
# HOLD ITEMS PRICE CHECK
# =================================================================

@router.message(Command("prices"))
@_admin_only
async def cmd_prices(message: types.Message):
    """Check CS2Cap prices for all held items."""
    api = _get_api_client()
    try:
        inv_mgr = InventoryManager(api)
        items = await inv_mgr.check_held_items_prices()

        if not items:
            await message.answer("No items in inventory.")
            return

        msg = "CS2Cap PRICES FOR HELD ITEMS\n\n"
        for item in items[:10]:
            msg += (
                f"- {item['title']}\n"
                f"  Buy: ${item['buy_price']:.2f}\n"
                f"  CS2Cap: ${item['cs2cap_price']:.2f}\n"
                f"  Unrealized: {item['unrealized_pnl_pct']:+.1f}%\n"
            )

        await message.answer(msg)
    except Exception as e:
        await message.answer(f"Error: {e}")
    finally:
        await api.close()


# =================================================================
# CONFIG & SETTINGS
# =================================================================

@router.message(F.text == "CONFIG")
@router.message(Command("settings"))
@_admin_only
async def btn_config(message: types.Message):
    oracle = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
    oracle_type = "CS2Cap" if oracle else "CSFloat"

    await message.answer(
        f"CONFIGURATION\n\n"
        f"Dry Run: {Config.DRY_RUN}\n"
        f"Fee Rate: {Config.FEE_RATE * 100}%\n"
        f"Min Spread: {Config.MIN_SPREAD_PCT}%\n"
        f"Max Price: ${Config.MAX_PRICE_USD}\n"
        f"Oracle: {oracle_type}\n"
        f"Strategy: {Config.ACTIVE_STRATEGY}\n"
        f"Volatility: {Config.VOLATILITY_METHOD}\n"
        f"Sharpe Optimization: {Config.SHARPE_OPTIMIZATION_ENABLED}\n"
        f"Turnover Limit: {Config.MAX_DAILY_TRADES}/day\n"
        f"Cross-Market: {Config.CROSS_MARKET_ENABLED}\n"
        f"Self-Reflection: {Config.PARAMETER_ADJUSTMENT_ENABLED}"
    )


# =================================================================
# DAILY BRIEFING
# =================================================================

@router.message(Command("daily"))
@_admin_only
async def cmd_daily(message: types.Message):

    api = _get_api_client()
    try:
        balance = await api.get_real_balance()
        inv_mgr = InventoryManager(api)
        summary = inv_mgr.get_portfolio_summary(current_balance=balance)

        emoji = "📈" if summary['total_realized_pnl'] > 0 else "📉" if summary['total_realized_pnl'] < 0 else "⚖️"

        await message.answer(
            f"DAILY BRIEFING\n\n"
            f"{emoji} Today PnL: ${summary['total_realized_pnl']:.2f}\n"
            f"Items Holding: {summary['items_holding']}\n"
            f"Items Sold: {summary['items_sold']}\n"
            f"Total Equity: ${summary['total_equity']:.2f}\n\n"
            f"Active Mode: {Config.ACTIVE_STRATEGY}\n"
            f"Risk Cap: {Config.MAX_POSITION_RISK_PCT}% per item"
        )
    except Exception as e:
        logger.exception(f"cmd_daily failed: {e}")
        await message.answer("❌ Error fetching daily briefing. Check logs.")
    finally:
        await api.close()


# =================================================================
# PANIC
# =================================================================

@router.message(Command("panic"))
@_admin_only
async def cmd_panic(message: types.Message):
    global is_running

    is_running = False
    if trading_task:
        trading_task.cancel()

    await message.answer("PANIC PROTOCOL INITIATED\nStopping bot...")

    api = _get_api_client()
    try:
        resp = await api.get_user_targets(Config.GAME_ID)
        items = resp.get("Items", resp.get("objects", []))

        if not items:
            await message.answer("No active targets found.")
            return

        targets_to_delete = [{"TargetID": item.get("targetId", item.get("TargetID", ""))} for item in items]
        count = len(targets_to_delete)

        await api.batch_delete_targets(targets_to_delete)
        await message.answer(f"Deleted {count} targets!")

    except Exception as e:
        logger.exception(f"cmd_panic failed: {e}")
        await message.answer("❌ Panic error. Check logs.")
    finally:
        await api.close()


# =================================================================
# HELP
# =================================================================

@router.message(Command("help"))
@_admin_only
async def cmd_help(message: types.Message):
    await message.answer(
        "DMarket Bot Help\n\n"
        "Trading:\n"
        "  START BOT - Start scanning & buying\n"
        "  STOP BOT - Stop the bot\n"
        "  SELL - List held items using CS2Cap prices\n\n"
        "Info:\n"
        "  BALANCE - Check DMarket USD balance\n"
        "  INVENTORY - View items (with CS2Cap prices)\n"
        "  PORTFOLIO - Full PnL summary\n"
        "  PRICES - CS2Cap prices for held items\n\n"
        "Commands:\n"
        "  /test_trade <item> - Test arbitrage DMarket→CS2Cap\n"
        "  /pagination - Test market scanning\n"
        "  /reflection - Self-reflection stats\n"
        "  /daily - Daily briefing\n"
        "  /panic - Emergency stop\n"
        "  /settings - Current config"
    )


# =================================================================
# WRAPPER & MAIN
# =================================================================

async def run_trading_wrapper():
    try:
        from src.core.autonomous_scanner import run_autonomous_scanner
        await run_autonomous_scanner()
    except asyncio.CancelledError:
        logger.info("Trading Task Cancelled")
    except Exception as e:
        logger.error(f"Trading Crash: {e}", exc_info=True)
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"CRITICAL ERROR: {e}")


async def set_commands(bot_instance: Bot):
    commands = [
        types.BotCommand(command="start", description="Open Control Panel"),
        types.BotCommand(command="test_trade", description="Test Arbitrage DMarket->CS2Cap"),
        types.BotCommand(command="balance", description="Check Balance"),
        types.BotCommand(command="inventory", description="View Inventory"),
        types.BotCommand(command="sell", description="List Items for Sale"),
        types.BotCommand(command="portfolio", description="Portfolio Summary"),
        types.BotCommand(command="prices", description="CS2Cap Prices"),
        types.BotCommand(command="reflection", description="Self-Reflection Stats"),
        types.BotCommand(command="pagination", description="Test Pagination"),
        types.BotCommand(command="daily", description="Daily Briefing"),
        types.BotCommand(command="panic", description="Emergency Stop"),
        types.BotCommand(command="settings", description="Current Config"),
        types.BotCommand(command="help", description="Help Guide"),
    ]
    await bot_instance.set_my_commands(commands)


async def main():
    logger.info("Telegram Bot Starting...")
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
