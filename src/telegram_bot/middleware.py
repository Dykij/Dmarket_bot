"""Middleware for Telegram bot.

Best practices from python-telegram-bot and Algoogram communities.
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class BotMiddleware:
    """Middleware for logging and metrics collection."""

    def __init__(self):
        """Initialize middleware."""
        self.request_count = 0
        self.error_count = 0
        self.command_stats = {}

    def logging_middleware(self, func: Callable) -> Callable:
        """Log all incoming updates.

        Args:
            func: Handler function

        Returns:
            Wrapped function
        """

        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
            """Wrapper function."""
            start_time = time.time()
            self.request_count += 1

            # Log update info
            user_id = update.effective_user.id if update.effective_user else None
            chat_id = update.effective_chat.id if update.effective_chat else None

            if update.message and update.message.text:
                command = update.message.text.split()[0]
                self.command_stats[command] = self.command_stats.get(command, 0) + 1
                logger.info(
                    f"Request #{self.request_count}: user={user_id}, "
                    f"chat={chat_id}, command={command}"
                )
            elif update.callback_query and update.callback_query.data:
                callback = update.callback_query.data
                logger.info(
                    f"Callback #{self.request_count}: user={user_id}, "
                    f"chat={chat_id}, data={callback}"
                )

            try:
                result = await func(update, context)
                elapsed = (time.time() - start_time) * 1000
                logger.info(
                    f"Request #{self.request_count} completed in {elapsed:.2f}ms"
                )
                return result
            except Exception as e:
                self.error_count += 1
                elapsed = (time.time() - start_time) * 1000
                logger.error(
                    f"Request #{self.request_count} failed after {elapsed:.2f}ms: {e}",
                    exc_info=True,
                )
                raise

        return wrapper

    def rate_limit_middleware(
        self, max_requests: int = 30, window_seconds: int = 60
    ) -> Callable:
        """Rate limiting middleware for users.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds

        Returns:
            Decorator function
        """
        user_requests = {}

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(
                update: Update, context: ContextTypes.DEFAULT_TYPE
            ) -> Any:
                """Wrapper function."""
                if not update.effective_user:
                    return await func(update, context)

                user_id = update.effective_user.id
                current_time = time.time()

                # Clean old requests
                if user_id in user_requests:
                    user_requests[user_id] = [
                        req_time
                        for req_time in user_requests[user_id]
                        if current_time - req_time < window_seconds
                    ]
                else:
                    user_requests[user_id] = []

                # Check rate limit
                if len(user_requests[user_id]) >= max_requests:
                    logger.warning(
                        f"Rate limit exceeded for user {user_id}: "
                        f"{len(user_requests[user_id])} requests in {window_seconds}s"
                    )
                    if update.message:
                        await update.message.reply_text(
                            "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
                        )
                    elif update.callback_query:
                        await update.callback_query.answer(
                            "⚠️ Слишком много запросов", show_alert=True
                        )
                    return None

                # Add current request
                user_requests[user_id].append(current_time)

                return await func(update, context)

            return wrapper

        return decorator

    def get_stats(self) -> dict[str, Any]:
        """Get middleware statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": (
                self.error_count / self.request_count if self.request_count > 0 else 0
            ),
            "command_stats": self.command_stats,
        }


# Global middleware instance
middleware = BotMiddleware()
