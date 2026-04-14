"""
Script: src/telegram_bot.py (Control Center)
Description: Telegram Interface for the TargetSniper Bot.
Commands:
/start - Shows control panel
/status - Current P/L and active targets
/balance - DMarket Balance
/inventory - Items in stock
/stop - Emergency Stop (Kill Switch)
"""

import asyncio
import logging
import os
import sys
from typing import Optional

# Add project root
sys.path.append("D:\\Dmarket_bot")

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.csfloat_oracle import CSFloatOracle
from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
from src.utils.vault import vault
# We import main bot logic to run it as a task
from src.core.autonomous_scanner import run_autonomous_scanner as TargetSniper_main
from src.db.profit_tracker import db as profit_db

load_dotenv()

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramControl")

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("TELEGRAM_CHAT_ID")  # Only owner can control

if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN missing!")
    sys.exit(1)

# --- Bot Setup ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- Global State ---
trading_task: Optional[asyncio.Task] = None
is_running = False

# --- Keyboards ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 START BOT"), KeyboardButton(text="🛑 STOP BOT")],
        [KeyboardButton(text="💰 BALANCE"), KeyboardButton(text="📊 STATUS")],
        [KeyboardButton(text="📦 INVENTORY"), KeyboardButton(text="⚙️ CONFIG")]
    ],
    resize_keyboard=True
)

# --- Handlers ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return # Ignore unauthorized users
    
    await message.answer(
        "🤖 **DMarket TargetSniper Control Center**\n"
        "Ready to dominate the market.\n\n"
        "Current Mode: " + ("SIMULATION (Dry Run)" if Config.DRY_RUN else "LIVE TRADING (Real Money)"),
        reply_markup=main_kb,
        parse_mode="Markdown"
    )

@router.message(F.text == "🚀 START BOT")
async def btn_start(message: types.Message):
    global trading_task, is_running
    
    if is_running:
        await message.answer("⚠️ Bot is already running!")
        return
    
    is_running = True
    # Run the TargetSniper loop in background
    trading_task = asyncio.create_task(run_TargetSniper_wrapper())
    await message.answer("✅ **Bot STARTED!** Scanning market...", parse_mode="Markdown")

@router.message(F.text == "🛑 STOP BOT")
async def btn_stop(message: types.Message):
    global trading_task, is_running
    
    if not is_running:
        await message.answer("⚠️ Bot is not running.")
        return
    
    is_running = False
    if trading_task:
        trading_task.cancel()
        try:
            await trading_task
        except asyncio.CancelledError:
            pass
    
    await message.answer("🛑 **Bot STOPPED.** Orders remain active (check manually).", parse_mode="Markdown")

@router.message(F.text == "💰 BALANCE")
async def btn_balance(message: types.Message):
    api = DMarketAPIClient(Config.PUBLIC_KEY, vault.get_dmarket_secret())
    try:
        usd = await api.get_real_balance()
        await message.answer(f"💰 **Balance:** ${usd:.2f}", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        await api.close()

@router.message(F.text == "📦 INVENTORY")
async def btn_inventory(message: types.Message):
    api = DMarketAPIClient(Config.PUBLIC_KEY, vault.get_dmarket_secret())
    try:
        resp = await api.get_user_inventory("a8db")
        # Handle both list and dict formats from different API versions
        items = resp.get("objects", []) if isinstance(resp, dict) else []
        if not items and hasattr(resp, "get"):
            items = resp.get("Items", [])
        
        count = len(items)
        msg = f"📦 **Inventory ({count} items):**\n"
        
        for item in items[:5]:
            title = item.get("title", "Unknown")
            msg += f"- {title}\n"
        
        if count > 5:
            msg += f"...and {count - 5} more."
            
        await message.answer(msg, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        await api.close()

@router.message(Command("test_trade"))
async def cmd_test_trade(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /test_trade <Item Name>\nExample: `/test_trade AK-47 | Redline (Field-Tested)`", parse_mode="Markdown")
        return
        
    item_name = args[1].strip()
    safe_item_name = item_name.replace("*", "\\*").replace("_", "\\_")
    await message.answer(f"⏳ **Testing Arbitrage for**: `{safe_item_name}`\n1. Fetching DMarket Orderbook...\n2. Validating with CSFloat Oracle...", parse_mode="Markdown")
    
    dm_api = DMarketAPIClient(Config.PUBLIC_KEY, vault.get_dmarket_secret())
    cs_api = CSFloatOracle(os.getenv("CSFLOAT_API_KEY", ""))
    
    try:
        # Simulate check
        # DMarket check
        dm_resp = await dm_api.get_market_items_v2("a8db", title=item_name, limit=1)
        dm_objects = dm_resp.get("objects", [])
        if not dm_objects:
            await message.answer("❌ Item not found on DMarket at this moment.")
            return
            
        dm_best_price = float(dm_objects[0].get("price", {}).get("USD", 0)) / 100.0
        
        # CSFloat oracle
        cs_price = await cs_api.get_item_price(item_name)
        if cs_price <= 0:
            await message.answer(f"❌ CSFloat Oracle failed to find reliable Reference Price for `{item_name}`.")
            return
            
        # Mathematical Validation (DMarket -> CSFloat resale logic limit)
        try:
            # Check if buying at DM and selling at CSFloat is feasible based on our 5% margin
            margin = validate_arbitrage_profit(dm_best_price, cs_price, fee_markup=0.05, min_profit_margin=0.05)
            await message.answer(
                f"✅ **Arbitrage Validated!**\n"
                f"🎯 Target: `{safe_item_name}`\n"
                f"📉 DMarket Best: `${dm_best_price:.2f}`\n"
                f"📈 CSFloat Oracle: `${cs_price:.2f}`\n"
                f"💰 **Net Margin:** {margin*100:.1f}%\n"
                f"*(Decision: APPROVED by Quantitative Model)*",
                parse_mode="Markdown"
            )
        except PriceValidationError as pe:
            await message.answer(
                f"⛔ **Trade Blocked by Risk Constraints!**\n"
                f"🎯 Target: `{safe_item_name}`\n"
                f"📉 DMarket Best: `${dm_best_price:.2f}`\n"
                f"📈 CSFloat Oracle: `${cs_price:.2f}`\n"
                f"⚠️ *Reason:* {pe}\n"
                f"*(Decision: REJECTED by Quantitative Model)*",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        await message.answer(f"❌ **API Error Encountered**: `{e}`\nCheck IP Whitelists and Keys.", parse_mode="Markdown")
        logger.error(f"Test trade error: {e}")
    finally:
        await dm_api.close()
        await cs_api.close()

@router.message(F.text == "📊 STATUS")
async def btn_status(message: types.Message):
    status = "RUNNING 🟢" if is_running else "STOPPED 🔴"
    mode = "SIMULATION 🧪" if Config.DRY_RUN else "REAL MONEY 💸"
    
    await message.answer(
        f"📊 **System Status:**\n"
        f"State: {status}\n"
        f"Mode: {mode}\n"
        f"Strategy: {Config.ACTIVE_STRATEGY}\n"
        f"Spread Target: >{Config.MIN_SPREAD_PCT}%\n"
        f"Game: CS2",
        parse_mode="Markdown"
    )

@router.message(Command("daily"))
async def cmd_daily_briefing(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
        
    pnl_data = profit_db.get_today_pnl()
    profit = pnl_data["profit"]
    trades = pnl_data["trades"]
    
    emoji = "📈" if profit > 0 else "📉" if profit < 0 else "⚖️"
    
    await message.answer(
        f"🌅 **DAILY BRIEFING**\n\n"
        f"{emoji} **Today's P&L:** ${profit:.2f}\n"
        f"🔄 **Completed Trades:** {trades}\n\n"
        f"*(Dashboard stubs operational. Fetching live inventory targets...)*\n\n"
        f"**Active Mode:** {Config.ACTIVE_STRATEGY}\n"
        f"**Risk Cap:** {Config.MAX_POSITION_RISK_PCT}% per item",
        parse_mode="Markdown"
    )

@router.message(F.text == "⚙️ CONFIG")
async def btn_config(message: types.Message):
    # Toggle Dry Run (Logic to be implemented or just display)
    await message.answer(
        f"⚙️ **Configuration:**\n"
        f"Dry Run: {Config.DRY_RUN}\n"
        f"Fee Rate: {Config.FEE_RATE * 100}%\n"
        f"Max Price: ${Config.MAX_PRICE_USD}\n"
        f"\n*To change settings, edit src/config.py and restart.*",
        parse_mode="Markdown"
    )

async def run_TargetSniper_wrapper():
    """Wrapper to run the main TargetSniper loop and handle errors."""
    try:
        # We need to adapt main() to be stoppable or run it as a coroutine
        # Since main.py runs an infinite loop, we rely on task cancellation
        await TargetSniper_main()
    except asyncio.CancelledError:
        logger.info("TargetSniper Task Cancelled")
    except Exception as e:
        logger.error(f"TargetSniper Crash: {e}")
        # Notify admin
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"⚠️ **CRITICAL ERROR:** {e}", parse_mode="Markdown")

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    await message.answer(
        f"⚙️ **Configuration:**\n"
        f"Dry Run: {Config.DRY_RUN}\n"
        f"Fee Rate: {Config.FEE_RATE * 100}%\n"
        f"Max Price: ${Config.MAX_PRICE_USD}\n"
        f"\n*To change settings, edit src/config.py and restart.*",
        parse_mode="Markdown"
    )

@router.message(Command("panic"))
async def cmd_panic(message: types.Message):
    global is_running
    
    # 1. Kill the loop
    is_running = False
    if trading_task:
        trading_task.cancel()
    
    await message.answer("🔥 **PANIC PROTOCOL INITIATED** 🔥\nStopping bot and deleting ALL targets...", parse_mode="Markdown")
    
    # 2. Delete targets via API
    async with AsyncDMarketClient(Config.PUBLIC_KEY, Config.SECRET_KEY) as client:
        try:
            # Fetch active targets
            resp = await client.get_user_targets(game=Config.GAME_ID)
            items = resp.get("Items", [])
            
            if not items:
                await message.answer("✅ No active targets found. You are safe.")
                return
            
            # Prepare delete payload
            targets_to_delete = [{"TargetID": item["TargetID"]} for item in items]
            count = len(targets_to_delete)
            
            # Execute mass delete
            await client.delete_target(targets_to_delete)
            await message.answer(f"🗑 **Deleted {count} targets!**\nInventory/Balance preserved.", parse_mode="Markdown")
            
        except Exception as e:
            await message.answer(f"❌ **CRITICAL ERROR during Panic:** {e}\nCHECK MANUALLY!")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🆘 **TargetSniper Bot Help Guide**\n\n"
        "**Basic Commands:**\n"
        "🚀 `/start` - Start Trading (Open Control Panel)\n"
        "🛑 `/stop` - Emergency Stop (Does not cancel orders)\n"
        "🧪 `/test_trade <item>` - Run DMarket->CSFloat Arbitrage Test\n\n"
        "**Info:**\n"
        "💰 `/balance` - Check DMarket USD Balance\n"
        "📦 `/inventory` - View bought items\n"
        "📊 `/status` - Check if bot is RUNNING or STOPPED\n"
        "🌅 `/daily` - View Daily P&L Briefing\n"
        "⚙️ `/settings` - View current config (Risk/Profit)\n\n"
        "**Support:**\n"
        "If bot crashes, check logs or restart script.",
        parse_mode="Markdown"
    )

async def set_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="🚀 Open Control Panel"),
        types.BotCommand(command="stop", description="🛑 EMERGENCY STOP"),
        types.BotCommand(command="test_trade", description="🧪 Test Arbitrage (DMarket > CSFloat)"),
        types.BotCommand(command="balance", description="💰 Check Balance"),
        types.BotCommand(command="status", description="📊 Bot Status"),
        types.BotCommand(command="daily", description="🌅 Daily Briefing"),
        types.BotCommand(command="inventory", description="📦 Show Inventory"),
        types.BotCommand(command="settings", description="⚙️ Settings"),
        types.BotCommand(command="help", description="🆘 Help & Guide")
    ]
    await bot.set_my_commands(commands)

async def main():
    logger.info("🤖 Telegram Bot Starting...")
    await set_commands(bot) # Set menu button
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
