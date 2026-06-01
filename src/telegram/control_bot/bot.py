"""
bot.py — Main entry point: create bot/dispatcher, wire routers, run main().

- create_bot(): instantiates Bot + Dispatcher with FSM storage
- _lazy_bot(): singleton wrapper, raises if no token
- main(): wires everything together, starts polling
"""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import Config

from .callbacks import router as cb_router
from .commands import router as cmds_router
from .filters import router as filter_router
from .lifecycle import (
    _install_signal_handlers,
    on_shutdown,
    on_startup,
    set_commands,
)
from .state import _TOKEN

logger = logging.getLogger("TelegramControl.bot")

# Master router — combines all sub-routers (filter → commands → callbacks)
# Filters run first (reject non-admins), then commands, then callbacks.
master_router = filter_router
master_router.include_router(cmds_router)
master_router.include_router(cb_router)

# Alias for tests/scripts that import `router` (back-compat with old control_bot.py)
router = master_router


# ============================================================
# Lazy bot/dispatcher singleton
# ============================================================
_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None


def create_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure aiogram instances with FSM storage."""
    bot = Bot(
        token=_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return bot, dp


def _lazy_bot() -> tuple[Bot, Dispatcher]:
    """Singleton wrapper around create_bot(). Raises if no token."""
    global _bot, _dp
    if _bot is None:
        if not _TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set — cannot create bot")
        _bot, _dp = create_bot()
    return _bot, _dp


# ============================================================
# Main entry point
# ============================================================
async def main() -> None:
    """Main entry point: wire routers, install signal handlers, start polling."""
    logger.info(f"Telegram Control Bot v{Config.BOT_VERSION} starting...")
    if not _TOKEN:
        logger.error("Aborting: no TELEGRAM_BOT_TOKEN")
        return

    bot, dp = _lazy_bot()
    dp.include_router(master_router)
    _install_signal_handlers(asyncio.get_running_loop(), bot, dp)

    await set_commands(bot)
    await on_startup(bot)
    logger.info("Starting polling...")
    try:
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.exception(f"Polling crashed: {e}")
    finally:
        await on_shutdown(bot)
