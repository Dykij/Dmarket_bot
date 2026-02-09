"""User rate limiter module for Telegram bot.

This module provides user-specific rate limiting with configurable limits,
whitelist support, and statistics tracking.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""

    requests: int
    window: int  # seconds
    burst: int | None = None


class UserRateLimiter:
    """User-specific rate limiter with configurable limits."""

    def __init__(self, default_limits: dict[str, RateLimitConfig] | None = None):
        """Initialize the rate limiter.

        Args:
            default_limits: Default rate limits per action type.
        """
        self.limits: dict[str, RateLimitConfig] = default_limits or {
            "command": RateLimitConfig(requests=10, window=60),
            "scan": RateLimitConfig(requests=5, window=60),
            "api_call": RateLimitConfig(requests=30, window=60),
        }

        # Track request timestamps per user per action
        self._user_requests: dict[int, dict[str, list[datetime]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Whitelist for users exempt from rate limiting
        self._whitelist: set[int] = set()

        # Track violations
        self._violations: dict[int, list[dict[str, Any]]] = defaultdict(list)

    async def check_limit(self, user_id: int, action: str = "command") -> bool:
        """Check if user is within rate limits for an action.

        Args:
            user_id: Telegram user ID.
            action: Type of action being rate limited.

        Returns:
            True if within limits, False if rate limited.
        """
        if user_id in self._whitelist:
            return True

        config = self.limits.get(action, self.limits.get("command"))
        if not config:
            return True

        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=config.window)

        # Clean old requests
        user_requests = self._user_requests[user_id][action]
        user_requests[:] = [r for r in user_requests if r > window_start]

        # Check limit
        if len(user_requests) >= config.requests:
            self._record_violation(user_id, action)
            logger.warning(
                "rate_limit_exceeded",
                user_id=user_id,
                action=action,
                requests=len(user_requests),
                limit=config.requests,
            )
            return False

        # Record this request
        user_requests.append(now)
        return True

    async def acquire(self, user_id: int, action: str = "command") -> bool:
        """Acquire a rate limit slot (alias for check_limit)."""
        return await self.check_limit(user_id, action)

    def _record_violation(self, user_id: int, action: str) -> None:
        """Record a rate limit violation."""
        self._violations[user_id].append({
            "action": action,
            "timestamp": datetime.now(UTC),
        })

        # Keep only last hour of violations
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        self._violations[user_id] = [
            v for v in self._violations[user_id] if v["timestamp"] > cutoff
        ]

    async def get_user_stats(self, user_id: int) -> dict[str, dict[str, int]]:
        """Get rate limit statistics for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Dictionary with stats per action.
        """
        now = datetime.now(UTC)
        stats: dict[str, dict[str, int]] = {}

        for action, config in self.limits.items():
            window_start = now - timedelta(seconds=config.window)
            requests = self._user_requests[user_id][action]
            current_requests = [r for r in requests if r > window_start]

            stats[action] = {
                "remaining": config.requests - len(current_requests),
                "limit": config.requests,
                "window": config.window,
            }

        return stats

    async def reset_user_limits(self, user_id: int, action: str | None = None) -> None:
        """Reset rate limits for a user.

        Args:
            user_id: Telegram user ID.
            action: Specific action to reset, or None for all actions.
        """
        if action:
            self._user_requests[user_id][action] = []
        else:
            self._user_requests[user_id] = defaultdict(list)

        logger.info("rate_limit_reset", user_id=user_id, action=action)

    async def add_whitelist(self, user_id: int) -> None:
        """Add user to whitelist (exempt from rate limiting)."""
        self._whitelist.add(user_id)
        logger.info("rate_limit_whitelist_add", user_id=user_id)

    async def remove_whitelist(self, user_id: int) -> None:
        """Remove user from whitelist."""
        self._whitelist.discard(user_id)
        logger.info("rate_limit_whitelist_remove", user_id=user_id)

    async def is_whitelisted(self, user_id: int) -> bool:
        """Check if user is in whitelist."""
        return user_id in self._whitelist

    def update_limit(self, action: str, config: RateLimitConfig) -> None:
        """Update rate limit configuration for an action.

        Args:
            action: Action name.
            config: New rate limit configuration.
        """
        self.limits[action] = config
        logger.info(
            "rate_limit_config_updated",
            action=action,
            requests=config.requests,
            window=config.window,
        )


# Global instance
_user_rate_limiter: UserRateLimiter | None = None


def get_user_rate_limiter() -> UserRateLimiter:
    """Get or create global UserRateLimiter instance."""
    global _user_rate_limiter
    if _user_rate_limiter is None:
        _user_rate_limiter = UserRateLimiter()
    return _user_rate_limiter
