"""
Unified exception hierarchy for the DMarket bot.

Follows PythonHub best practices:
- Custom exception hierarchies for domain-specific errors
- Exception chaining with `raise ... from ...`
- Structured context in exception instances
- Single source of truth for error classification

Hierarchy:
    BotError (base)
    ├── APIError
    │   ├── RateLimitExceeded
    │   ├── AuthenticationError
    │   └── CircuitBreakerOpen
    ├── TradingError
    │   ├── PriceValidationError
    │   ├── InsufficientBalance
    │   └── OrderRejected
    ├── ConfigError
    │   └── MissingConfigError
    ├── RiskError
    │   ├── DrawdownFreeze
    │   └── PumpDetected
    └── DataError
        ├── DatabaseCorruption
        └── DataStaleError
"""

from __future__ import annotations

from typing import Any


class BotError(Exception):
    """Base exception for all bot errors. Carries structured context."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}

    def with_context(self, **kwargs: Any) -> BotError:
        """Add context to exception (fluent interface)."""
        self.context.update(kwargs)
        return self


# --- API Errors ---


class APIError(BotError):
    """Base for DMarket/external API errors."""


class RateLimitExceeded(APIError):
    """Rate limit exceeded (429). Transient - auto-resolves."""


class AuthenticationError(APIError):
    """Authentication failed (401/403). Fatal - key invalid."""


class CircuitBreakerOpen(APIError):
    """Circuit breaker is open. Transient - auto-resolves after cooldown."""


class QuotaExhausted(APIError):
    """API quota exhausted. Needs attention."""


# --- Trading Errors ---


class TradingError(BotError):
    """Base for trading-related errors."""


class PriceValidationError(TradingError):
    """Price validation failed (volatility, arbitrage check)."""


class InsufficientBalance(TradingError):
    """Insufficient balance for trade."""


class OrderRejected(TradingError):
    """Order rejected by DMarket."""


# --- Config Errors ---


class ConfigError(BotError):
    """Base for configuration errors."""


class MissingConfigError(ConfigError):
    """Required configuration value missing."""


# --- Risk Errors ---


class RiskError(BotError):
    """Base for risk management errors."""


class DrawdownFreeze(RiskError):
    """Drawdown freeze triggered. Only sells allowed."""


class PumpDetected(RiskError):
    """Price pump detected. Item blacklisted."""


# --- Data Errors ---


class DataError(BotError):
    """Base for data-related errors."""


class DatabaseCorruption(DataError):
    """SQLite corruption detected."""


class DataStaleError(DataError):
    """Data is too stale to use."""
