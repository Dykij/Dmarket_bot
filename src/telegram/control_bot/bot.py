"""
bot.py — Main entry point: create bot/dispatcher, wire routers, run main().

- create_bot(): instantiates Bot + Dispatcher with FSM storage
- _lazy_bot(): singleton wrapper, raises if no token
- main(): wires everything together, starts polling
"""

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .callbacks import router as cb_router
from .commands import router as cmds_router
from .filters import router as filter_router
from .lifecycle import (
    _install_signal_handlers,
    on_shutdown,
    on_startup,
    set_commands,
)
from .state import _TOKEN, is_admin

logger = logging.getLogger("TelegramControl.bot")

# Master router — combines all sub-routers (filter → commands → callbacks)
# Filters run first (reject non-admins), then commands, then callbacks.
master_router = filter_router
master_router.include_router(cmds_router)
master_router.include_router(cb_router)

# Alias for tests/scripts that import `router` (back-compat with old control_bot.py)
router = master_router


# ============================================================
# Rate limiting middleware
# ============================================================

class ThrottlingMiddleware:
    """Limits how fast a user can send commands/callbacks.

    Prevents rapid-fire abuse even from admin — protects DMarket API
    from accidental hammering (e.g. /balance × 100 creates 100 API
    calls instantly).

    arXiv Large-Scale Study (CMU 2026): financial bots without command
    throttling are in the highest-risk group for accidental DoS.
    Reddit 2025: 1600+ leaked AI agents had no rate limiting.

    The per-user cooldown is Config-dependent so devs can loosen it
    during testing.
    """

    def __init__(self, rate_limit: float = 0.5) -> None:
        self.rate_limit = rate_limit
        self._user_last: dict[int, float] = {}

    async def __call__(
        self,
        handler,
        event,
        data: dict,
    ) -> object:
        from aiogram.types import CallbackQuery, Message

        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
            if user_id is not None:
                now = time.monotonic()
                last = self._user_last.get(user_id, 0.0)
                if now - last < self.rate_limit:
                    logger.debug(
                        f"Throttled user_id={user_id} "
                        f"({(now - last):.2f}s < {self.rate_limit}s)"
                    )
                    return  # Drop the event silently — no feedback to spammer
                self._user_last[user_id] = now
        return await handler(event, data)


class AdminOnlyMiddleware:
    """Blocks all non-admin messages and callbacks before they reach handlers.

    This MUST run before the ThrottlingMiddleware so unauthorized
    users cannot cause rate-limiting side-effects.
    """

    async def __call__(
        self,
        handler,
        event,
        data: dict,
    ) -> object:
        from aiogram.types import CallbackQuery, Message

        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
            if user_id is None or not is_admin(user_id):
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Access denied", show_alert=True)
                return  # Block the event silently
        return await handler(event, data)


# ============================================================
# Lazy bot/dispatcher singleton
# ============================================================
_bot: Bot | None = None
_dp: Dispatcher | None = None


def create_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure aiogram instances with FSM storage."""
    assert _TOKEN, "TELEGRAM_BOT_TOKEN not set"
    bot = Bot(
        token=_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.message.middleware(AdminOnlyMiddleware())
    dp.callback_query.middleware(AdminOnlyMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    return bot, dp


def _lazy_bot() -> tuple[Bot, Dispatcher]:
    """Singleton wrapper around create_bot(). Raises if no token."""
    global _bot, _dp
    if _bot is None:
        if not _TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set — cannot create bot")
        _bot, _dp = create_bot()
    assert _dp is not None
    return _bot, _dp


# ============================================================
# Main entry point
# ============================================================
async def main() -> None:
    """Main entry point: wire routers, install signal handlers, start polling."""
    logger.info("Telegram Control Bot starting...")
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
