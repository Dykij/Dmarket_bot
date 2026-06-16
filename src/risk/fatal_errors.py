"""
Fatal error classification for the DMarket bot (v12.7).

The contract is:
    TRANSIENT  → bot may safely retry (network blip, rate limit)
    FATAL      → bot must stop; the user must investigate
    UNKNOWN    → bot must stop; safer to halt than loop pointlessly

Rule of thumb: when in doubt, classify as FATAL. The watchdog will
respect the exit code and not auto-restart. The user can fix the
issue, edit the .env / code, and relaunch manually.

This module is the single source of truth for "is this exception
fatal?" — both the outer supervisor (`autonomous_scanner.py`) and
the inner cycle (`target_sniping/core.py`) call `classify()`.

v12.7: Added granular error codes for better diagnostics:
    7 = rate limit (transient but worth tracking)
    8 = circuit breaker open (transient)
    9 = quota exhausted (needs attention)
"""

from __future__ import annotations

import asyncio
from typing import Tuple, Type


class FatalError(Exception):
    """Marker base class for errors that must halt the bot."""


class ConfigError(FatalError):
    """Missing or invalid configuration (.env, schema)."""


class AuthError(FatalError):
    """DMarket / CS2Cap / Telegram returned 401/403 — key invalid."""


class DatabaseCorruption(FatalError):
    """SQLite corruption (not 'database is locked')."""


class LogicBug(FatalError):
    """Uncaught bug in our code (KeyError/AttributeError wrapped)."""


class RateLimitError(FatalError):
    """API rate limit hit (429). Transient but worth tracking separately."""


class CircuitBreakerOpen(FatalError):
    """Circuit breaker is open (too many consecutive failures)."""


class QuotaExhausted(FatalError):
    """API quota exhausted (CS2Cap monthly limit, DMarket secret limit)."""


# Transient: bot may safely retry without user intervention.
TRANSIENT_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    asyncio.TimeoutError,
    asyncio.CancelledError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
)

try:
    import aiohttp

    TRANSIENT_EXCEPTIONS = TRANSIENT_EXCEPTIONS + (
        aiohttp.ClientError,
        aiohttp.ClientConnectionError,
        aiohttp.ClientResponseError,
        aiohttp.ServerDisconnectedError,
    )
except ImportError:
    pass

try:
    from src.api.dmarket_api_client.backoff import CircuitOpenError

    TRANSIENT_EXCEPTIONS = TRANSIENT_EXCEPTIONS + (CircuitOpenError,)
except ImportError:
    pass


# These are almost always bugs in our code. We treat them as FATAL
# (raise up, log with traceback, exit). The user fixes the code.
_LOGIC_BUG_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    AttributeError,
    KeyError,
    NameError,
    TypeError,
    IndexError,
    AssertionError,
    RecursionError,
    NotImplementedError,
    UnboundLocalError,
)


def classify(exc: BaseException) -> str:
    """
    Classify an exception as 'FATAL', 'TRANSIENT', or 'UNKNOWN'.

    - FatalError subclasses (explicit markers) → FATAL
    - TRANSIENT_EXCEPTIONS (network/CB)       → TRANSIENT
    - LOGIC_BUG_EXCEPTIONS (our bugs)          → FATAL
    - anything else                            → UNKNOWN (treat as FATAL)

    v12.7: RateLimitError and CircuitBreakerOpen are TRANSIENT
    (not FATAL) since they resolve automatically.
    """
    # Rate limit / circuit breaker are transient (auto-resolve)
    if isinstance(exc, (RateLimitError, CircuitBreakerOpen, QuotaExhausted)):
        return "TRANSIENT"
    if isinstance(exc, FatalError):
        return "FATAL"
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return "TRANSIENT"
    if isinstance(exc, _LOGIC_BUG_EXCEPTIONS):
        return "FATAL"
    return "UNKNOWN"


def is_fatal(exc: BaseException) -> bool:
    """True if `exc` requires user intervention (bot must stop)."""
    return classify(exc) in ("FATAL", "UNKNOWN")


def exit_code_for(exc: BaseException) -> int:
    """
    Return the process exit code for a given exception.

    Distinct codes let the watchdog / shell script decide whether
    to restart. Convention:
        0 = clean shutdown
        1 = generic fatal
        2 = config error
        3 = auth error
        4 = database corruption
        5 = logic bug (our code)
        6 = unknown
        7 = rate limit (transient, but worth tracking)
        8 = circuit breaker open (transient)
        9 = quota exhausted (needs attention)
    """
    if isinstance(exc, ConfigError):
        return 2
    if isinstance(exc, AuthError):
        return 3
    if isinstance(exc, DatabaseCorruption):
        return 4
    if isinstance(exc, LogicBug):
        return 5
    if isinstance(exc, RateLimitError):
        return 7
    if isinstance(exc, CircuitBreakerOpen):
        return 8
    if isinstance(exc, QuotaExhausted):
        return 9
    if isinstance(exc, FatalError):
        return 1
    if isinstance(exc, _LOGIC_BUG_EXCEPTIONS):
        return 5
    return 6
