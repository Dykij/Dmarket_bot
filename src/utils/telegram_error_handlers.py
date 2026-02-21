"""Error boundaries for Telegram bot handlers.

This module provides decorators and base handlers with comprehensive
error handling for Telegram bot commands and callbacks.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, NamedTuple

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from src.utils.sentry_integration import (
    add_breadcrumb,
    capture_exception,
    set_user_context,
)

logger = logging.getLogger(__name__)


class UpdateContext(NamedTuple):
    """Context extracted from Telegram Update."""

    user_id: int | None
    username: str | None
    command: str | None
    message_text: str | None


def _extract_update_context(update: Update) -> UpdateContext:
    """Extract user and message context from Telegram Update.

    Args:
        update: Telegram update object

    Returns:
        UpdateContext with user_id, username, command, and message_text
    """
    user_id = None
    username = None
    command = None
    message_text = None

    if update.effective_user:
        user_id = update.effective_user.id
        username = update.effective_user.username

    if update.message:
        message_text = update.message.text
        if message_text and message_text.startswith("/"):
            command = message_text.split()[0]
    elif update.callback_query:
        command = "callback_query"
        if update.callback_query.data:
            message_text = update.callback_query.data

    return UpdateContext(user_id, username, command, message_text)


def _log_handler_start(
    handler_name: str,
    ctx: UpdateContext,
) -> None:
    """Log handler start with context information.

    Args:
        handler_name: Name of the handler function
        ctx: Extracted update context
    """
    logger.info(
        f"Handler {handler_name} started",
        extra={
            "handler": handler_name,
            "user_id": ctx.user_id,
            "username": ctx.username,
            "command": ctx.command,
            "message_text": ctx.message_text,
        },
    )


def _setup_sentry_context(
    handler_name: str,
    ctx: UpdateContext,
) -> None:
    """Set Sentry user context and add breadcrumb.

    Args:
        handler_name: Name of the handler function
        ctx: Extracted update context
    """
    if ctx.user_id:
        set_user_context(user_id=ctx.user_id, username=ctx.username)

    add_breadcrumb(
        message=f"Executing handler: {handler_name}",
        category="handler",
        level="info",
        data={
            "user_id": ctx.user_id,
            "command": ctx.command,
        },
    )


def _log_handler_success(
    handler_name: str,
    user_id: int | None,
) -> None:
    """Log successful handler completion.

    Args:
        handler_name: Name of the handler function
        user_id: User ID if available
    """
    logger.info(
        f"Handler {handler_name} completed successfully",
        extra={
            "handler": handler_name,
            "user_id": user_id,
        },
    )


async def _send_error_to_user(
    update: Update,
    error_message: str,
) -> None:
    """Send error message to user via appropriate channel.

    Args:
        update: Telegram update object
        error_message: Error message to send
    """
    if update.message:
        await update.message.reply_text(error_message)
    elif update.callback_query:
        await update.callback_query.answer(error_message, show_alert=True)


async def _handle_validation_error(
    error: ValidationError,
    update: Update,
    handler_name: str,
    user_id: int | None,
) -> None:
    """Handle ValidationError from user input.

    Args:
        error: The validation error
        update: Telegram update object
        handler_name: Name of the handler function
        user_id: User ID if available
    """
    logger.warning(
        f"Validation error in {handler_name}",
        extra={
            "handler": handler_name,
            "user_id": user_id,
            "error": str(error),
        },
    )
    error_message = f"❌ Ошибка валидации: {error}"
    await _send_error_to_user(update, error_message)


async def _handle_authentication_error(
    error: AuthenticationError,
    update: Update,
    handler_name: str,
    user_id: int | None,
) -> None:
    """Handle AuthenticationError from API key issues.

    Args:
        error: The authentication error
        update: Telegram update object
        handler_name: Name of the handler function
        user_id: User ID if available
    """
    logger.error(
        "Authentication error in %s",
        handler_name,
        extra={
            "handler": handler_name,
            "user_id": user_id,
            "error": str(error),
        },
    )
    error_message = "❌ Ошибка аутентификации. Проверьте API ключи в /settings"
    await _send_error_to_user(update, error_message)

    capture_exception(
        error,
        level="error",
        tags={"handler": handler_name, "error_type": "authentication"},
        extra={"user_id": user_id},
    )


async def _handle_rate_limit_error(
    error: RateLimitError,
    update: Update,
    handler_name: str,
    user_id: int | None,
) -> None:
    """Handle RateLimitError from API rate limiting.

    Args:
        error: The rate limit error
        update: Telegram update object
        handler_name: Name of the handler function
        user_id: User ID if available
    """
    retry_after = getattr(error, "retry_after", 60)
    logger.warning(
        f"Rate limit error in {handler_name}",
        extra={
            "handler": handler_name,
            "user_id": user_id,
            "error": str(error),
            "retry_after": retry_after,
        },
    )
    error_message = f"⏳ Превышен лимит запросов. Попробуйте через {retry_after} секунд"
    await _send_error_to_user(update, error_message)


async def _handle_api_error(
    error: APIError,
    update: Update,
    handler_name: str,
    user_id: int | None,
) -> None:
    """Handle generic APIError from DMarket API.

    Args:
        error: The API error
        update: Telegram update object
        handler_name: Name of the handler function
        user_id: User ID if available
    """
    status_code = getattr(error, "status_code", None)
    logger.error(
        "API error in %s",
        handler_name,
        extra={
            "handler": handler_name,
            "user_id": user_id,
            "status_code": status_code,
            "error": str(error),
        },
    )
    error_message = "❌ Ошибка при обращении к API DMarket. Попробуйте позже"
    await _send_error_to_user(update, error_message)

    capture_exception(
        error,
        level="error",
        tags={"handler": handler_name, "error_type": "api"},
        extra={
            "user_id": user_id,
            "status_code": status_code,
        },
    )


async def _handle_unexpected_error(
    error: Exception,
    update: Update,
    handler_name: str,
    ctx: UpdateContext,
    user_friendly_message: str,
) -> None:
    """Handle unexpected exceptions.

    Args:
        error: The unexpected exception
        update: Telegram update object
        handler_name: Name of the handler function
        ctx: Extracted update context
        user_friendly_message: Message to show user
    """
    logger.error(
        f"Unexpected error in {handler_name}",
        extra={
            "handler": handler_name,
            "user_id": ctx.user_id,
            "command": ctx.command,
            "error": str(error),
            "error_type": type(error).__name__,
        },
    )

    await _send_error_to_user(update, user_friendly_message)

    capture_exception(
        error,
        level="error",
        tags={
            "handler": handler_name,
            "error_type": type(error).__name__,
        },
        extra={
            "user_id": ctx.user_id,
            "command": ctx.command,
            "message_text": ctx.message_text,
        },
    )


def telegram_error_boundary(
    user_friendly_message: str = "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
    log_context: bool = True,
) -> Callable:
    """Decorator for Telegram handlers with comprehensive error handling.

    This decorator:
    - Catches and logs all exceptions
    - Sends user-friendly error messages
    - Captures errors in Sentry
    - Logs request context (user_id, command, parameters)

    Args:
        user_friendly_message: Message to send to user on error
        log_context: Whether to log full context (user_id, command, etc.)

    Returns:
        Decorated handler function

    Example:
        >>> @telegram_error_boundary(
        >>>     user_friendly_message="❌ Не удалось выполнить команду"
        >>> )
        >>> async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        >>> # Handler logic
        >>>     pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            ctx = _extract_update_context(update)

            try:
                if log_context:
                    _log_handler_start(func.__name__, ctx)

                _setup_sentry_context(func.__name__, ctx)

                result = await func(update, context, *args, **kwargs)

                if log_context:
                    _log_handler_success(func.__name__, ctx.user_id)

                return result

            except ValidationError as e:
                await _handle_validation_error(e, update, func.__name__, ctx.user_id)

            except AuthenticationError as e:
                await _handle_authentication_error(
                    e, update, func.__name__, ctx.user_id
                )

            except RateLimitError as e:
                await _handle_rate_limit_error(e, update, func.__name__, ctx.user_id)

            except APIError as e:
                await _handle_api_error(e, update, func.__name__, ctx.user_id)

            except Exception as e:
                await _handle_unexpected_error(
                    e, update, func.__name__, ctx, user_friendly_message
                )

        return wrapper

    return decorator


class BaseHandler:
    """Base class for Telegram handlers with error handling.

    This class provides common functionality and error handling
    for all Telegram bot handlers.
    """

    def __init__(self, logger_name: str | None = None):
        """Initialize base handler.

        Args:
            logger_name: Name for the logger (defaults to class name)
        """
        self.logger = logging.getLogger(logger_name or self.__class__.__name__)

    async def handle_error(
        self,
        update: Update,
        error: Exception,
        user_message: str = "❌ Произошла ошибка",
    ) -> None:
        """Handle error and notify user.

        Args:
            update: Telegram update object
            error: Exception that occurred
            user_message: Message to send to user
        """
        # Extract user info
        user_id = update.effective_user.id if update.effective_user else None

        # Log error
        self.logger.error(
            "Error occurred: %s",
            error,
            extra={
                "user_id": user_id,
                "error_type": type(error).__name__,
            },
        )

        # Notify user
        if update.message:
            await update.message.reply_text(user_message)
        elif update.callback_query:
            await update.callback_query.answer(user_message, show_alert=True)

        # Capture in Sentry
        capture_exception(
            error,
            level="error",
            tags={"handler": self.__class__.__name__},
            extra={"user_id": user_id},
        )

    async def validate_user(self, update: Update) -> bool:
        """Validate that user exists and is authorized.

        Args:
            update: Telegram update object

        Returns:
            True if user is valid, False otherwise
        """
        if not update.effective_user:
            self.logger.warning("Update without effective_user")
            return False

        return True

    async def safe_reply(
        self,
        update: Update,
        text: str,
        **kwargs: Any,
    ) -> None:
        """Safely send reply to user, handling different update types.

        Args:
            update: Telegram update object
            text: Text to send
            **kwargs: Additional arguments for reply_text
        """
        try:
            if update.message:
                await update.message.reply_text(text, **kwargs)
            elif update.callback_query:
                await update.callback_query.message.reply_text(text, **kwargs)  # type: ignore[union-attr]
                await update.callback_query.answer()
        except Exception:
            self.logger.exception(
                "Failed to send reply",
                extra={"text": text},
            )
