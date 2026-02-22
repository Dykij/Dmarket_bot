"""Callback Router - Modern dispatcher for Telegram callback queries.

This module implements a clean callback routing system using the Command pattern
to replace the massive button_callback_handler with 83 elif statements.

Phase 2 Refactoring: Early returns, small functions, clear responsibilities.
"""

import logging
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.telegram_error_handlers import telegram_error_boundary

logger = logging.getLogger(__name__)

# Type alias for callback handlers
CallbackHandler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


class CallbackRouter:
    """Routes callback queries to appropriate handlers using Command pattern."""

    def __init__(self) -> None:
        """Initialize the callback router with empty registry."""
        self._exact_handlers: dict[str, CallbackHandler] = {}
        self._prefix_handlers: list[tuple[str, CallbackHandler]] = []
        self._pattern_handlers: list[tuple[Callable[[str], bool], CallbackHandler]] = []

    def register_exact(self, callback_data: str, handler: CallbackHandler) -> None:
        """Register handler for exact callback_data match.

        Args:
            callback_data: Exact callback data string to match
            handler: Async handler function

        """
        self._exact_handlers[callback_data] = handler

    def register_prefix(self, prefix: str, handler: CallbackHandler) -> None:
        """Register handler for callback_data starting with prefix.

        Args:
            prefix: Prefix to match
            handler: Async handler function

        """
        self._prefix_handlers.append((prefix, handler))

    def register_pattern(
        self, matcher: Callable[[str], bool], handler: CallbackHandler
    ) -> None:
        """Register handler with custom matcher function.

        Args:
            matcher: Function that returns True if callback_data matches
            handler: Async handler function

        """
        self._pattern_handlers.append((matcher, handler))

    async def route(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Route callback query to appropriate handler.

        Args:
            update: Telegram update object
            context: Callback context

        Returns:
            True if handler was found and executed, False otherwise

        """
        if not update.callback_query or not update.callback_query.data:
            logger.warning("Received update without callback_query or data")
            return False

        callback_data = update.callback_query.data

        # Answer callback query immediately
        await update.callback_query.answer()

        # Try exact match first (fastest)
        if callback_data in self._exact_handlers:
            handler = self._exact_handlers[callback_data]
            await handler(update, context)
            return True

        # Try prefix matches
        for prefix, handler in self._prefix_handlers:
            if callback_data.startswith(prefix):
                await handler(update, context)
                return True

        # Try pattern matches
        for matcher, handler in self._pattern_handlers:
            if matcher(callback_data):
                await handler(update, context)
                return True

        # No handler found
        logger.warning("No handler found for callback_data: %s", callback_data)
        return False


@telegram_error_boundary(user_friendly_message="❌ Ошибка обработки кнопки")
async def button_callback_handler_v2(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Modern callback handler using router pattern.

    Replaces the old 973-line function with 83 elif statements.

    Args:
        update: Telegram update object
        context: Callback context

    """
    router = context.bot_data.get("callback_router")

    if router is None:
        logger.error("Callback router not initialized in bot_data")
        if update.callback_query:
            await update.callback_query.answer("❌ Ошибка: роутер не инициализирован")
        return

    await router.route(update, context)
