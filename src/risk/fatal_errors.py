"""
Fatal error classification for the DMarket bot (v14.9).

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

v14.9: Integrated unified exception hierarchy from src.utils.exceptions.
    All bot exceptions now inherit from BotError with structured context.
    Exception chaining supported via `raise ... from ...` pattern.
"""

from __future__ import annotations

import asyncio


class FatalError(Exception):
    """Marker base class for errors that must halt the bot."""


class ConfigError(FatalError):
    """Missing or invalid configuration (.env, schema)."""


class AuthError(FatalError):
    """DMarket / Oracle / Telegram returned 401/403 — key invalid."""


class DatabaseCorruption(FatalError):
    """SQLite corruption (not 'database is locked')."""


class LogicBug(FatalError):
    """Uncaught bug in our code (KeyError/AttributeError wrapped)."""


class RateLimitError(FatalError):
    """API rate limit hit (429). Transient but worth tracking separately."""


class CircuitBreakerOpen(FatalError):
    """Circuit breaker is open (too many consecutive failures)."""


class QuotaExhausted(FatalError):
    """API quota exhausted (oracle monthly limit, DMarket secret limit)."""


# Transient: bot may safely retry without user intervention.
TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
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

# Unified exception hierarchy (v14.9)
try:
    from src.utils.exceptions import (
        AuthenticationError,
        RateLimitExceeded,
    )
    from src.utils.exceptions import (
        CircuitBreakerOpen as UnifiedCircuitBreakerOpen,
    )
    from src.utils.exceptions import (
        ConfigError as UnifiedConfigError,
    )
    from src.utils.exceptions import (
        DatabaseCorruption as UnifiedDatabaseCorruption,
    )
    from src.utils.exceptions import (
        QuotaExhausted as UnifiedQuotaExhausted,
    )

    # Map unified exceptions to classification
    _UNIFIED_TRANSIENT: tuple[type[BaseException], ...] = (
        RateLimitExceeded,
        UnifiedCircuitBreakerOpen,
    )
    _UNIFIED_FATAL: tuple[type[BaseException], ...] = (
        AuthenticationError,
        UnifiedConfigError,
        UnifiedDatabaseCorruption,
        UnifiedQuotaExhausted,
    )
except ImportError:
    _UNIFIED_TRANSIENT = ()
    _UNIFIED_FATAL = ()

# These are almost always bugs in our code. We treat them as FATAL
# (raise up, log with traceback, exit). The user fixes the code.
_LOGIC_BUG_EXCEPTIONS: tuple[type[BaseException], ...] = (
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
    - Unified hierarchy (BotError subclasses)  → mapped by type
    - anything else                            → UNKNOWN (treat as FATAL)

    v14.9: Integrated unified exception hierarchy.
    """
    # Legacy: Rate limit / circuit breaker are transient (auto-resolve)
    if isinstance(exc, (RateLimitError, CircuitBreakerOpen, QuotaExhausted)):
        return "TRANSIENT"
    if isinstance(exc, FatalError):
        return "FATAL"
    # Unified hierarchy (v14.9)
    if _UNIFIED_TRANSIENT and isinstance(exc, _UNIFIED_TRANSIENT):
        return "TRANSIENT"
    if _UNIFIED_FATAL and isinstance(exc, _UNIFIED_FATAL):
        return "FATAL"
    # Network / IO transient errors
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
        10 = risk error (drawdown freeze, pump detected)
        11 = trading error (price validation, order rejected)
    """
    # Legacy exceptions
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
    # Unified hierarchy (v14.9)
    if _UNIFIED_FATAL:
        from src.utils.exceptions import (
            AuthenticationError,
        )
        from src.utils.exceptions import (
            ConfigError as UConfigError,
        )
        from src.utils.exceptions import (
            DatabaseCorruption as UDBCorruption,
        )
        from src.utils.exceptions import (
            QuotaExhausted as UQuota,
        )
        if isinstance(exc, UConfigError):
            return 2
        if isinstance(exc, AuthenticationError):
            return 3
        if isinstance(exc, UDBCorruption):
            return 4
        if isinstance(exc, UQuota):
            return 9
    if _UNIFIED_TRANSIENT:
        from src.utils.exceptions import CircuitBreakerOpen as UCB
        from src.utils.exceptions import RateLimitExceeded
        if isinstance(exc, RateLimitExceeded):
            return 7
        if isinstance(exc, UCB):
            return 8
    from src.utils.exceptions import DrawdownFreeze, PumpDetected, TradingError
    if isinstance(exc, (DrawdownFreeze, PumpDetected)):
        return 10
    if isinstance(exc, TradingError):
        return 11
    # Fallback
    if isinstance(exc, FatalError):
        return 1
    if isinstance(exc, _LOGIC_BUG_EXCEPTIONS):
        return 5
    return 6
