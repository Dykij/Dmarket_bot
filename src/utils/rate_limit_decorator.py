"""
Декоратор для применения rate limiting к командам бота.
"""

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog
from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from src.utils.user_rate_limiter import UserRateLimiter


logger = structlog.get_logger(__name__)


def rate_limit(
    action: str = "default",
    cost: int = 1,
    message: str | None = None,
) -> Callable:
    """
    Декоратор для rate limiting команд бота.

    Args:
        action: Тип действия для rate limiting
        cost: Стоимость действия (для weighted limiting)
        message: Кастомное сообщение при превышении лимита

    Example:
        @rate_limit(action="scan", cost=1)
        async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id

            # Получить rate limiter из context
            rate_limiter: UserRateLimiter | None = getattr(
                context.bot_data, "user_rate_limiter", None
            )

            if not rate_limiter:
                logger.warning("rate_limiter_not_found", user_id=user_id)
                return await func(update, context, *args, **kwargs)

            # Проверить whitelist
            if await rate_limiter.is_whitelisted(user_id):
                return await func(update, context, *args, **kwargs)

            # Проверить лимит
            allowed, info = await rate_limiter.check_limit(user_id, action, cost)

            if not allowed:
                # Отправить сообщение о превышении лимита
                retry_after = info.get("retry_after", 0)

                if message:
                    error_msg = message
                else:
                    error_msg = (
                        f"⚠️ Превышен лимит запросов!\n\n"
                        f"Действие: {action}\n"
                        f"Лимит: {info['limit']} запросов/{info.get('window', 60)} сек\n"
                        f"Попробуйте через: {retry_after} сек"
                    )

                if update.message:
                    await update.message.reply_text(error_msg)
                elif update.callback_query:
                    await update.callback_query.answer(error_msg, show_alert=True)

                logger.info(
                    "rate_limit_blocked",
                    user_id=user_id,
                    action=action,
                    retry_after=retry_after,
                )

                return None

            # Выполнить команду
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator
