"""
resilience.py — Error handling decorators and retry utilities.

Provides:
- safe_call: wraps a handler so exceptions are reported to the user, not the dispatcher
- retry_async: exponential backoff for retriable errors
- dmarket_client: async context manager that creates + closes DMarketAPIClient safely
"""

import asyncio
import functools
import logging
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from aiogram import types
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

logger = logging.getLogger("TelegramControl.resilience")


def safe_call(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Wrap a handler so any uncaught exception is logged and reported to the user.

    Searches the args for an aiogram Message / CallbackQuery, or a duck-typed
    object with an `answer()` method. Reports the error to that object.

    Failure to deliver the error message is silently logged — never raises.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled error in {func.__name__}: {e}")
            # Find the message-like object to reply to (real aiogram types or duck-typed mocks)
            message = None
            callback_obj = None
            for a in args:
                if isinstance(a, types.Message):
                    message = a
                    break
                if isinstance(a, types.CallbackQuery):
                    callback_obj = a
                    message = a.message
                    break
                # Duck-typed fallback (for unit tests)
                if hasattr(a, "answer") and callable(getattr(a, "answer", None)):
                    message = a
                    break
            try:
                err_text = f"❌ Internal error: `{e}`\n\nCheck logs/telegram_bot.log for details."
                if message:
                    await message.answer(err_text)
                if callback_obj is not None:
                    await callback_obj.answer("❌ Error", show_alert=True)
            except Exception:
                logger.exception("Failed to send error message to user")
    return wrapper


async def retry_async(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    operation: str = "API call",
) -> Any:
    """Run an async callable with exponential backoff.

    Retriable exceptions: TimeoutError, ConnectionError, OSError, aiohttp.ClientError.
    Other exceptions fail fast (re-raised immediately).
    """
    import aiohttp

    retriable = (TimeoutError, ConnectionError, OSError, aiohttp.ClientError)
    last_exc: Any = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except retriable as e:
            last_exc = e
            if attempt == max_attempts:
                logger.error(f"{operation} failed after {max_attempts} attempts: {e}", exc_info=True)
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                f"{operation} attempt {attempt}/{max_attempts} failed: {e}. "
                f"Retrying in {delay:.1f}s",
                exc_info=True,
            )
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-retriable: re-raise immediately
            logger.error(f"{operation} non-retriable error: {e}", exc_info=True)
            raise
    raise last_exc


@asynccontextmanager
async def dmarket_client():
    """Async context manager that creates + closes DMarketAPIClient safely.

    Example:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="balance",
            )
    """
    client = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        yield client
    finally:
        try:
            await client.close()
        except Exception:
            logger.exception("Error closing DMarket client")
