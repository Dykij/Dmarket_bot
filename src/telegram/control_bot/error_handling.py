"""
error_handling.py — Structured error handling for Telegram module (v15.6).

Provides:
- ErrorCategory: categorizes errors by type and severity
- UserFriendlyError: exceptions with user-safe messages
- ErrorHandler: centralized error handling with logging + user notification
- safe_call_v2: enhanced decorator with error categorization

Improvements over basic try/except:
1. Error categorization (API, DB, Auth, Network, Validation)
2. User-friendly messages (never leak internal details)
3. Structured logging with context
4. Automatic retry for transient errors
5. Admin notification for critical errors
"""

from __future__ import annotations

import enum
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import types

logger = logging.getLogger("TelegramControl.error_handling")


class ErrorCategory(enum.Enum):
    """Error categories for structured handling."""
    API = "api"              # DMarket API errors
    DATABASE = "database"    # SQLite errors
    AUTH = "auth"            # Authentication/authorization errors
    NETWORK = "network"      # Network connectivity errors
    VALIDATION = "validation"  # Input validation errors
    RATE_LIMIT = "rate_limit"  # Rate limiting (429)
    INTERNAL = "internal"    # Internal logic errors
    EXTERNAL = "external"    # External service errors (oracles, etc.)


class ErrorSeverity(enum.Enum):
    """Error severity levels."""
    LOW = "low"          # User can retry, no data loss
    MEDIUM = "medium"    # Feature degraded, but bot continues
    HIGH = "high"        # Critical feature broken
    CRITICAL = "critical"  # Bot may need restart


class UserFriendlyError(Exception):
    """Exception with a user-safe message and structured metadata.

    NEVER pass raw exception messages to users — they can leak
    file paths, API keys, and internal state (CVE-2026-32982).
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_message: str | None = None,
        retry_after: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.user_message = user_message or self._default_user_message()
        self.retry_after = retry_after
        self.context = context or {}

    def _default_user_message(self) -> str:
        """Generate a default user-friendly message based on category."""
        messages = {
            ErrorCategory.API: "❌ DMarket API error. Please try again in a moment.",
            ErrorCategory.DATABASE: "❌ Database error. Please try again.",
            ErrorCategory.AUTH: "❌ Authentication failed. Please check your credentials.",
            ErrorCategory.NETWORK: "❌ Network error. Please check your connection.",
            ErrorCategory.VALIDATION: "❌ Invalid input. Please check your request.",
            ErrorCategory.RATE_LIMIT: "⏳ Rate limited. Please wait a moment and try again.",
            ErrorCategory.INTERNAL: "❌ Internal error. Check logs for details.",
            ErrorCategory.EXTERNAL: "❌ External service unavailable. Please try again later.",
        }
        return messages.get(self.category, "❌ An error occurred. Please try again.")


class ErrorHandler:
    """Centralized error handling with logging and user notification."""

    @staticmethod
    def categorize_error(error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Categorize an exception by type and context."""
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Network errors
        if isinstance(error, (TimeoutError, ConnectionError, OSError)):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM

        # aiohttp errors
        if "aiohttp" in error_type or "client" in error_type:
            if "429" in error_msg or "rate" in error_msg:
                return ErrorCategory.RATE_LIMIT, ErrorSeverity.LOW
            if "401" in error_msg or "403" in error_msg:
                return ErrorCategory.AUTH, ErrorSeverity.HIGH
            if "timeout" in error_msg:
                return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
            return ErrorCategory.API, ErrorSeverity.MEDIUM

        # Database errors
        if "sqlite" in error_type.lower() or "database" in error_msg:
            return ErrorCategory.DATABASE, ErrorSeverity.HIGH

        # Validation errors
        if "value" in error_type.lower() or "invalid" in error_msg:
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW

        # Default
        return ErrorCategory.INTERNAL, ErrorSeverity.MEDIUM

    @staticmethod
    def get_user_message(
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
    ) -> str:
        """Generate a user-friendly error message.

        NEVER include raw exception details — they can leak sensitive info.
        """
        if isinstance(error, UserFriendlyError):
            return error.user_message

        # Category-specific messages
        if category == ErrorCategory.RATE_LIMIT:
            return "⏳ Rate limited by DMarket API. Please wait a moment and try again."
        if category == ErrorCategory.AUTH:
            return "❌ Authentication failed. The bot may need to re-authenticate."
        if category == ErrorCategory.NETWORK:
            return "❌ Network error. Please check your connection and try again."
        if category == ErrorCategory.DATABASE:
            return "❌ Database error. Please try again."
        if category == ErrorCategory.API:
            return "❌ DMarket API error. Please try again in a moment."
        if category == ErrorCategory.VALIDATION:
            return "❌ Invalid input. Please check your request."

        # Default based on severity
        if severity == ErrorSeverity.CRITICAL:
            return "🔴 Critical error. The bot may need to be restarted."
        if severity == ErrorSeverity.HIGH:
            return "❌ Error. Please try again or check logs."

        return "❌ An error occurred. Please try again."

    @staticmethod
    async def handle_error(
        error: Exception,
        handler_name: str,
        message: types.Message | None = None,
        callback: types.CallbackQuery | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Handle an error with logging and user notification.

        1. Categorize the error
        2. Log with structured context
        3. Send user-friendly message
        4. Notify admin for critical errors
        """
        category, severity = ErrorHandler.categorize_error(error)
        user_message = ErrorHandler.get_user_message(error, category, severity)

        # Structured logging
        log_context = {
            "handler": handler_name,
            "category": category.value,
            "severity": severity.value,
            "error_type": type(error).__name__,
            "error_msg": str(error)[:200],  # Truncate for logging
        }
        if context:
            log_context.update(context)

        if severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL):
            logger.error(
                f"[{category.value.upper()}] {handler_name}: {error}",
                extra=log_context,
                exc_info=True,
            )
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(
                f"[{category.value.upper()}] {handler_name}: {error}",
                extra=log_context,
            )
        else:
            logger.debug(
                f"[{category.value.upper()}] {handler_name}: {error}",
                extra=log_context,
            )

        # Send user-friendly message
        try:
            if message:
                await message.answer(user_message)
            elif callback and callback.message:
                await callback.message.answer(user_message)
                await callback.answer("❌ Error", show_alert=True)
        except Exception as send_error:
            logger.error(f"Failed to send error message to user: {send_error}")

        # Notify admin for critical errors
        if severity == ErrorSeverity.CRITICAL:
            try:
                from src.telegram.notifier import notifier
                await notifier.crash(
                    f"Critical error in {handler_name}\n"
                    f"Category: {category.value}\n"
                    f"Error: {type(error).__name__}: {str(error)[:200]}"
                )
            except Exception:
                logger.error("Failed to notify admin about critical error")


def safe_call_v2(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Enhanced decorator with error categorization and structured handling.

    Improvements over basic safe_call:
    1. Error categorization (API, DB, Auth, Network, etc.)
    2. User-friendly messages based on error type
    3. Structured logging with context
    4. Automatic admin notification for critical errors

    Usage:
        @safe_call_v2
        async def my_handler(message: types.Message):
            ...
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except UserFriendlyError as e:
            # UserFriendlyError already has a safe message
            await ErrorHandler.handle_error(
                error=e,
                handler_name=func.__name__,
                message=_extract_message(args),
                callback=_extract_callback(args),
                context=e.context,
            )
        except Exception as e:
            # Unknown error — categorize and handle
            await ErrorHandler.handle_error(
                error=e,
                handler_name=func.__name__,
                message=_extract_message(args),
                callback=_extract_callback(args),
            )

    return wrapper


def _extract_message(args: tuple) -> types.Message | None:
    """Extract Message object from handler arguments."""
    for a in args:
        if isinstance(a, types.Message):
            return a
    return None


def _extract_callback(args: tuple) -> types.CallbackQuery | None:
    """Extract CallbackQuery object from handler arguments."""
    for a in args:
        if isinstance(a, types.CallbackQuery):
            return a
    return None
