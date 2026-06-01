"""
lifecycle.py — Bot startup, shutdown, signal handlers.

- set_commands(bot): register /commands in Telegram menu
- on_startup(bot): log info, notify admin that bot is online
- on_shutdown(bot): graceful cleanup, notify admin, close session, remove PID file
- _install_signal_handlers(loop, bot, dp): wire SIGTERM/SIGINT to graceful shutdown
- _graceful_shutdown(bot, dp): cancel polling + run on_shutdown
"""

import asyncio
import logging
import os
import signal
import time

from aiogram import Bot, Dispatcher, types

from src.config import Config

from .state import _ADMIN_ID, state

logger = logging.getLogger("TelegramControl.lifecycle")


# ============================================================
# Commands registration
# ============================================================
async def set_commands(bot: Bot) -> None:
    """Register all 13 commands in the Telegram bot menu."""
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


# ============================================================
# Startup
# ============================================================
async def on_startup(bot: Bot) -> None:
    """Called on bot startup: log info + notify admin."""
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


# ============================================================
# Shutdown
# ============================================================
async def on_shutdown(bot: Bot) -> None:
    """Graceful shutdown: stop the loop, close the bot, notify admin.

    Cleans up the PID file (if the launcher set one) so subsequent runs
    don't refuse to start due to a stale PID file.
    """
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


# ============================================================
# Signal handlers
# ============================================================
def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    bot: Bot,
    dp: Dispatcher,
) -> None:
    """Handle SIGTERM/SIGINT gracefully via _graceful_shutdown.

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
            # Windows fallback: signal handlers not supported
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
