"""
db_retry.py — Decorator for SQLite write operations with exponential
backoff. Catches "database is locked" transient errors and retries
the operation up to N times with a growing delay.

Why:
The bot has two long-lived SQLite connections (state + history DBs).
Concurrent writes from background tasks (oracle cache refresh,
briefing scheduler) and the hot-path sniping loop can hit
"database is locked" (SQLite returns SQLITE_BUSY / SQLITE_LOCKED).
The current code uses `with self.state_conn:` which is a transaction
context — if the inner operation raises, the transaction is
rolled back but the operation is NOT retried. One lost write =
one lost trade or one lost price observation.

This module is a focused, reusable decorator that:
1. Catches `sqlite3.OperationalError` whose message contains
   "locked" or "busy" (transient).
2. Retries with exponential backoff: 50ms, 100ms, 200ms, ...
3. Caps the total wait time (~1.5s for default 3 attempts).
4. Lets non-transient errors (e.g. syntax error, constraint violation)
   propagate immediately.
5. Logs each retry at WARNING level so the operator knows there
   is contention.

Usage:
    from src.db.db_retry import with_db_retry

    class MyDb:
        @with_db_retry(max_attempts=3, base_delay=0.05)
        def add_virtual_item(self, hash_name, ...):
            with self.state_conn:
                self.state_conn.execute(...)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import sqlite3
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("DBRetry")

F = TypeVar("F", bound=Callable[..., Any])

# Substrings in the error message that indicate a transient lock.
# Anything else is treated as a hard error and propagated.
_TRANSIENT_SUBSTRINGS = ("locked", "busy")


def _is_transient(exc: BaseException) -> bool:
    """True if `exc` is a SQLite transient lock/busy error worth retrying."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return any(s in msg for s in _TRANSIENT_SUBSTRINGS)


def with_db_retry(
    max_attempts: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
    operation_name: str = "",
) -> Callable[[F], F]:
    """
    Decorator: retry the wrapped function on transient SQLite lock
    errors with exponential backoff.

    Args:
        max_attempts: Total attempts including the first try.
          3 → up to 2 retries (3 total). Default 3.
        base_delay: Initial sleep in seconds. Default 0.05 (50ms).
          Doubles after each retry: 0.05, 0.10, 0.20, ...
        max_delay: Cap on per-retry sleep. Default 0.5s. So even with
          many retries we never sleep more than half a second.
        operation_name: Optional human-readable name for logging.
          If empty, we use the function's __qualname__.

    Retries:
      - sqlite3.OperationalError containing "locked" or "busy"
      - All other exceptions (including other OperationalError types)
        propagate immediately on the first occurrence.

    Total max wait time: sum of base_delay * 2^(i-1) for i in
    1..max_attempts-1, capped at max_delay each.
    """
    def decorator(func: F) -> F:
        op = operation_name or func.__qualname__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:
                        if not _is_transient(exc) or attempt >= max_attempts:
                            raise
                        last_exc = exc
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(
                            f"[db_retry] {op} attempt {attempt}/{max_attempts} "
                            f"failed: {exc}. Retrying in {delay:.3f}s"
                        )
                        await asyncio.sleep(delay)
                # Should never reach here (we either return or raise), but
                # the type checker needs an explicit exit.
                assert last_exc is not None
                raise last_exc

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if not _is_transient(exc) or attempt >= max_attempts:
                        raise
                    last_exc = exc
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"[db_retry] {op} attempt {attempt}/{max_attempts} "
                        f"failed: {exc}. Retrying in {delay:.3f}s"
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return sync_wrapper  # type: ignore[return-value]

    return decorator
