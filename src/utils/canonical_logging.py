"""Canonical log line processor for structlog.

This module provides a processor that generates canonical log lines -
single, comprehensive log entries per request/operation that contain
all relevant context, reducing log noise while maintaining observability.

Based on SkillsMP Logging recommendations and Stripe's canonical log lines pattern.
"""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
from typing import Any, Callable, Generator

import structlog


class AuditEventType(enum.StrEnum):
    """Типы аудит событий."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    API_KEY_ADD = "api_key_add"
    API_KEY_UPDATE = "api_key_update"
    API_KEY_DELETE = "api_key_delete"
    API_KEY_VIEW = "api_key_view"
    TARGET_CREATE = "target_create"
    TARGET_DELETE = "target_delete"
    TARGET_UPDATE = "target_update"
    ITEM_BUY = "item_buy"
    ITEM_SELL = "item_sell"
    ARBITRAGE_SCAN = "arbitrage_scan"
    ARBITRAGE_OPPORTUNITY = "arbitrage_opportunity"
    SETTINGS_UPDATE = "settings_update"
    LANGUAGE_CHANGE = "language_change"
    ADMIN_USER_BAN = "admin_user_ban"
    ADMIN_USER_UNBAN = "admin_user_unban"
    ADMIN_RATE_LIMIT_CHANGE = "admin_rate_limit_change"
    ADMIN_FEATURE_FLAG_CHANGE = "admin_feature_flag_change"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SECURITY_VIOLATION = "security_violation"


# Context variable to hold canonical log data per request
_canonical_context: ContextVar[dict[str, Any]] = ContextVar(
    "canonical_context", default={}
)


@dataclass
class CanonicalLogEntry:
    """Container for canonical log line data."""

    # Request metadata
    request_id: str | None = None
    user_id: int | None = None
    operation: str | None = None

    # Timing
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None

    # Counts and metrics
    db_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls: int = 0
    errors: int = 0

    # Custom fields
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Calculate operation duration in milliseconds."""
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000

    def increment(self, field: str, value: int = 1) -> None:
        """Increment a counter field."""
        current = getattr(self, field, 0)
        if isinstance(current, int):
            setattr(self, field, current + value)

    def add_extra(self, key: str, value: Any) -> None:
        """Add extra context field."""
        self.extra[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        result = {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "operation": self.operation,
            "duration_ms": round(self.duration_ms, 2),
            "db_queries": self.db_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "api_calls": self.api_calls,
            "errors": self.errors,
        }
        # Only include non-None and non-zero values
        result = {k: v for k, v in result.items() if v is not None and v != 0}
        # Add extra fields
        result.update(self.extra)
        return result


class CanonicalLogManager:
    """Manager for canonical log lines.

    Example:
        >>> with canonical_log.operation("process_arbitrage") as log:
        ...     log.user_id = 123456
        ...     items = await fetch_items()
        ...     log.api_calls += 1
        ...     for item in items:
        ...         await process(item)
        ...         log.db_queries += 1
        ...     # Single log line emitted at end with all context
    """

    def __init__(self, logger: structlog.BoundLogger | None = None):
        """Initialize canonical log manager.

        Args:
            logger: Structlog logger instance
        """
        self._logger = logger or structlog.get_logger("canonical")

    @contextmanager
    def operation(
        self,
        name: str,
        request_id: str | None = None,
        user_id: int | None = None,
        log_level: str = "info",
    ) -> Generator[CanonicalLogEntry, None, None]:
        """Context manager for a canonical log operation.

        Args:
            name: Operation name (e.g., "process_arbitrage", "handle_command")
            request_id: Unique request identifier
            user_id: User ID if applicable
            log_level: Log level for the canonical line

        Yields:
            CanonicalLogEntry to populate with context
        """
        entry = CanonicalLogEntry(
            operation=name,
            request_id=request_id,
            user_id=user_id,
        )

        # Store in context var for access in nested calls
        token = _canonical_context.set(entry.to_dict())

        try:
            yield entry
        except Exception as e:
            entry.errors += 1
            entry.add_extra("error", str(e))
            entry.add_extra("error_type", type(e).__name__)
            raise
        finally:
            entry.end_time = time.perf_counter()
            _canonical_context.reset(token)

            # Emit canonical log line
            log_method = getattr(self._logger, log_level, self._logger.info)
            log_method(
                f"{name}_complete",
                **entry.to_dict(),
            )

    def get_current_context(self) -> dict[str, Any]:
        """Get current canonical context from context var."""
        return _canonical_context.get()

    def add_to_current(self, **kwargs: Any) -> None:
        """Add fields to current canonical context."""
        ctx = _canonical_context.get()
        ctx.update(kwargs)
        _canonical_context.set(ctx)

    def audit(
        self,
        event_type: AuditEventType | str,
        action: str,
        user_id: int | None = None,
        success: bool = True,
        severity: str = "info",
        **kwargs: Any,
    ) -> None:
        """Emit an audit log entry."""
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        log_method = getattr(self._logger, severity.lower(), self._logger.info)
        log_method(
            "audit_event",
            is_audit=True,
            event_type=event_type_str,
            action=action,
            user_id=user_id,
            success=success,
            severity=severity,
            **kwargs,
        )


def canonical_log_processor(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor that adds canonical context to all log entries.

    Add this processor to your structlog configuration to automatically
    include canonical context in all log entries within an operation.

    Example:
        >>> structlog.configure(
        ...     processors=[
        ...         canonical_log_processor,
        ...         structlog.processors.JSONRenderer(),
        ...     ]
        ... )
    """
    # Get canonical context if available
    ctx = _canonical_context.get()
    if ctx:
        # Add canonical fields as prefix
        for key in ["request_id", "user_id", "operation"]:
            if key in ctx and ctx[key] is not None:
                event_dict.setdefault(key, ctx[key])

    return event_dict


def add_timing_processor(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Processor that adds timing information to log entries.

    Adds timestamp and duration if start_time is present.
    """
    # Add ISO timestamp (timezone-aware UTC)
    event_dict.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

    # Calculate duration if start_time present
    if "_start_time" in event_dict:
        start = event_dict.pop("_start_time")
        event_dict["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)

    return event_dict


# Global canonical log manager
_canonical_manager: CanonicalLogManager | None = None


def get_canonical_log_manager() -> CanonicalLogManager:
    """Get or create global canonical log manager.

    Returns:
        CanonicalLogManager instance
    """
    global _canonical_manager
    if _canonical_manager is None:
        _canonical_manager = CanonicalLogManager()
    return _canonical_manager


# Convenience function
def canonical_operation(
    name: str,
    request_id: str | None = None,
    user_id: int | None = None,
) -> contextmanager[CanonicalLogEntry]:
    """Convenience function to start a canonical log operation.

    Args:
        name: Operation name
        request_id: Request ID
        user_id: User ID

    Returns:
        Context manager yielding CanonicalLogEntry
    """
    manager = get_canonical_log_manager()
    return manager.operation(name, request_id, user_id)
