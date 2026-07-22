"""
resilience.py — Error handling decorators and retry utilities.

Provides:
- safe_call: wraps a handler so exceptions are reported to the user, not the dispatcher
- retry_async: exponential backoff for retriable errors
- dmarket_client: async context manager that creates + closes DMarketAPIClient safely

v15.2: Uses tenacity for retry logic.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from aiogram import types

from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

logger = logging.getLogger("TelegramControl.resilience")


def safe_call(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Wrap a handler so any uncaught exception is logged and reported to the user.

    CVE-2026-32982: NEVER send the raw exception string to the user.
    Exception messages can leak file paths, API keys, and internal state.
    The full traceback is logged server-side for debugging.

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
                err_text = "❌ Internal error.\n\nCheck logs for details."
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

    v15.2: Uses tenacity for consistent retry behavior.
    """
    import aiohttp
    import tenacity

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(
            (TimeoutError, ConnectionError, OSError, aiohttp.ClientError)
        ),
        stop=tenacity.stop_after_attempt(max_attempts),
        wait=tenacity.wait_exponential(multiplier=base_delay, max=max_delay),
        before_sleep=tenacity.before_sleep_log(logger, 30),  # WARNING level
        reraise=True,
    )
    async def _do_retry() -> Any:
        return await coro_factory()

    try:
        return await _do_retry()
    except (TimeoutError, ConnectionError, OSError, aiohttp.ClientError) as e:
        logger.error(f"{operation} failed after {max_attempts} attempts: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"{operation} non-retriable error: {e}", exc_info=True)
        raise


def get_dmarket_secret() -> str:
    """Get DMarket secret key from vault (prod) or Config (dev).

    Centralized to avoid 4+ copy-pasted implementations.
    """
    from src.utils.vault import vault
    return (
        vault.get_dmarket_secret()
        if hasattr(vault, "get_dmarket_secret")
        else Config.SECRET_KEY
    )


@asynccontextmanager
async def dmarket_client():
    """Async context manager that creates + closes DMarketAPIClient safely.

    Uses vault for secret key (falls back to Config.SECRET_KEY in dev).
    See state.py:start() for the same pattern.

    Example:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="balance",
            )
    """
    secret = get_dmarket_secret()
    client = DMarketAPIClient(Config.PUBLIC_KEY, secret)
    try:
        yield client
    finally:
        try:
            await client.close()
        except Exception:
            logger.exception("Error closing DMarket client")


async def fetch_balance_data() -> dict | None:
    """Fetch balance + equity from DMarket API. Shared by callbacks and views.

    Returns dict with cash_str/avail_str/frozen_str/locked_str/total_str,
    or None on failure. Used by /status, STATUS button, and cb_refresh_status.
    """
    from src.db.price_history import price_db
    try:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="fetch_balance_data",
            )
            equity = price_db.get_total_equity(balance)
            frozen = equity.get("frozen", 0)
            return {
                "cash_str": f"${equity['cash']:.2f}",
                "avail_str": f"${equity['available']:.2f}",
                "frozen_str": f"${frozen:.2f}" if frozen > 0 else "",
                "locked_str": f"${equity['assets']:.2f} ({equity['count']} items)",
                "total_str": f"${equity['total']:.2f}",
            }
    except Exception as e:
        logger.debug("fetch_balance_data failed: %s", e)
        return None
