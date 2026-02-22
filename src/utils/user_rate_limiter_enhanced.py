"""Enhanced User Rate Limiter.

Provides per-user rate limiting with multiple strategies and persistence.

Features:
- Sliding window rate limiting
- Token bucket algorithm
- Fixed window rate limiting
- Per-user and per-operation limits
- Cooldown periods
- Priority users (higher limits)
- Burst handling

Usage:
    ```python
    from src.utils.user_rate_limiter_enhanced import EnhancedUserRateLimiter

    limiter = EnhancedUserRateLimiter()

    # Check if user can perform action
    if await limiter.check_rate_limit(user_id, "scan_market"):
        # Perform action
        await scan_market()
    else:
        # Rate limited
        retry_after = await limiter.get_retry_after(user_id, "scan_market")
        print(f"Rate limited. Try agAlgon in {retry_after}s")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RateLimitStrategy(StrEnum):
    """Rate limiting strategies."""

    SLIDING_WINDOW = "sliding_window"  # Most accurate, higher memory
    TOKEN_BUCKET = "token_bucket"  # Allows bursts
    FIXED_WINDOW = "fixed_window"  # Simple, least memory


class RateLimitResult(StrEnum):
    """Rate limit check result."""

    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    COOLDOWN = "cooldown"
    BANNED = "banned"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    # Default limits
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    requests_per_day: int = 5000

    # Burst settings (for token bucket)
    burst_limit: int = 10
    refill_rate: float = 0.5  # Tokens per second

    # Strategy
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW

    # Cooldown
    cooldown_after_limit: int = 60  # Seconds to wait after being limited
    max_violations: int = 5  # Violations before temporary ban
    ban_duration: int = 3600  # 1 hour ban

    # Priority users get multiplier
    priority_multiplier: float = 2.0


@dataclass
class OperationLimit:
    """Limits for specific operation."""

    operation: str
    requests_per_minute: int
    requests_per_hour: int | None = None
    cooldown_seconds: int = 0


@dataclass
class UserState:
    """User rate limit state."""

    user_id: int
    requests: deque[datetime] = field(default_factory=lambda: deque(maxlen=10000))
    tokens: float = 10.0
    last_refill: datetime = field(default_factory=lambda: datetime.now(UTC))
    violations: int = 0
    banned_until: datetime | None = None
    cooldown_until: datetime | None = None
    is_priority: bool = False
    last_request: datetime | None = None

    # Per-operation tracking
    operation_requests: dict[str, deque[datetime]] = field(
        default_factory=lambda: defaultdict(lambda: deque(maxlen=1000))
    )


@dataclass
class RateLimitInfo:
    """Information about rate limit status."""

    result: RateLimitResult
    allowed: bool
    remaining: int
    limit: int
    reset_at: datetime | None = None
    retry_after: int = 0
    message: str = ""


class EnhancedUserRateLimiter:
    """Enhanced user-based rate limiter with multiple strategies."""

    # Default operation limits
    DEFAULT_OPERATION_LIMITS = {
        "scan_market": OperationLimit("scan_market", 10, 100, 5),
        "buy_item": OperationLimit("buy_item", 5, 50, 10),
        "sell_item": OperationLimit("sell_item", 5, 50, 10),
        "create_target": OperationLimit("create_target", 10, 100, 2),
        "get_balance": OperationLimit("get_balance", 20, 200, 0),
        "get_inventory": OperationLimit("get_inventory", 10, 100, 0),
        "api_request": OperationLimit("api_request", 30, 500, 0),
    }

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        operation_limits: dict[str, OperationLimit] | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration
            operation_limits: Custom operation limits
        """
        self.config = config or RateLimitConfig()
        self.operation_limits = operation_limits or self.DEFAULT_OPERATION_LIMITS.copy()

        # User states
        self._users: dict[int, UserState] = {}
        self._lock = asyncio.Lock()

        # Metrics
        self._total_requests = 0
        self._total_limited = 0

    def _get_user_state(self, user_id: int) -> UserState:
        """Get or create user state.

        Args:
            user_id: User ID

        Returns:
            User state
        """
        if user_id not in self._users:
            self._users[user_id] = UserState(
                user_id=user_id,
                tokens=self.config.burst_limit,
            )
        return self._users[user_id]

    async def check_rate_limit(
        self,
        user_id: int,
        operation: str = "api_request",
    ) -> RateLimitInfo:
        """Check if request is allowed.

        Args:
            user_id: User ID
            operation: Operation type

        Returns:
            Rate limit info
        """
        async with self._lock:
            self._total_requests += 1

            state = self._get_user_state(user_id)
            now = datetime.now(UTC)

            # Check ban
            if state.banned_until and now < state.banned_until:
                return RateLimitInfo(
                    result=RateLimitResult.BANNED,
                    allowed=False,
                    remaining=0,
                    limit=0,
                    retry_after=int((state.banned_until - now).total_seconds()),
                    message="User temporarily banned due to excessive violations",
                )

            # Check cooldown
            if state.cooldown_until and now < state.cooldown_until:
                return RateLimitInfo(
                    result=RateLimitResult.COOLDOWN,
                    allowed=False,
                    remaining=0,
                    limit=0,
                    retry_after=int((state.cooldown_until - now).total_seconds()),
                    message="In cooldown period",
                )

            # Get limits
            op_limit = self.operation_limits.get(operation)
            if op_limit:
                limit_per_minute = op_limit.requests_per_minute
            else:
                limit_per_minute = self.config.requests_per_minute

            # Apply priority multiplier
            if state.is_priority:
                limit_per_minute = int(
                    limit_per_minute * self.config.priority_multiplier
                )

            # Check based on strategy
            if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                result = self._check_sliding_window(
                    state, operation, limit_per_minute, now
                )
            elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                result = self._check_token_bucket(state, now)
            else:  # FIXED_WINDOW
                result = self._check_fixed_window(
                    state, operation, limit_per_minute, now
                )

            # Handle result
            if not result.allowed:
                self._total_limited += 1
                state.violations += 1

                # Apply cooldown
                if state.violations >= 3:
                    state.cooldown_until = now + timedelta(
                        seconds=self.config.cooldown_after_limit
                    )

                # Apply ban
                if state.violations >= self.config.max_violations:
                    state.banned_until = now + timedelta(
                        seconds=self.config.ban_duration
                    )
                    state.violations = 0
                    result.result = RateLimitResult.BANNED
                    result.message = "User banned due to excessive violations"

                logger.warning(
                    "rate_limited",
                    user_id=user_id,
                    operation=operation,
                    violations=state.violations,
                )
            else:
                # Record request
                state.requests.append(now)
                state.operation_requests[operation].append(now)
                state.last_request = now

            return result

    def _check_sliding_window(
        self,
        state: UserState,
        operation: str,
        limit: int,
        now: datetime,
    ) -> RateLimitInfo:
        """Check using sliding window algorithm.

        Args:
            state: User state
            operation: Operation type
            limit: Requests per minute
            now: Current time

        Returns:
            Rate limit info
        """
        window_start = now - timedelta(minutes=1)

        # Count requests in window
        op_requests = state.operation_requests.get(operation, deque())
        requests_in_window = sum(1 for r in op_requests if r > window_start)

        remaining = limit - requests_in_window
        reset_at = now + timedelta(minutes=1)

        if requests_in_window >= limit:
            # Calculate retry after
            if op_requests:
                oldest_in_window = next(
                    (r for r in op_requests if r > window_start), now
                )
                retry_after = int(
                    (oldest_in_window + timedelta(minutes=1) - now).total_seconds()
                )
            else:
                retry_after = 60

            return RateLimitInfo(
                result=RateLimitResult.RATE_LIMITED,
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                retry_after=max(1, retry_after),
                message=f"Rate limit exceeded: {requests_in_window}/{limit} per minute",
            )

        return RateLimitInfo(
            result=RateLimitResult.ALLOWED,
            allowed=True,
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
        )

    def _check_token_bucket(
        self,
        state: UserState,
        now: datetime,
    ) -> RateLimitInfo:
        """Check using token bucket algorithm.

        Args:
            state: User state
            now: Current time

        Returns:
            Rate limit info
        """
        # Refill tokens
        elapsed = (now - state.last_refill).total_seconds()
        new_tokens = elapsed * self.config.refill_rate
        state.tokens = min(self.config.burst_limit, state.tokens + new_tokens)
        state.last_refill = now

        if state.tokens < 1:
            # Calculate when 1 token will be avAlgolable
            tokens_needed = 1 - state.tokens
            retry_after = int(tokens_needed / self.config.refill_rate)

            return RateLimitInfo(
                result=RateLimitResult.RATE_LIMITED,
                allowed=False,
                remaining=0,
                limit=self.config.burst_limit,
                retry_after=max(1, retry_after),
                message="No tokens avAlgolable",
            )

        # Consume token
        state.tokens -= 1

        return RateLimitInfo(
            result=RateLimitResult.ALLOWED,
            allowed=True,
            remaining=int(state.tokens),
            limit=self.config.burst_limit,
        )

    def _check_fixed_window(
        self,
        state: UserState,
        operation: str,
        limit: int,
        now: datetime,
    ) -> RateLimitInfo:
        """Check using fixed window algorithm.

        Args:
            state: User state
            operation: Operation type
            limit: Requests per minute
            now: Current time

        Returns:
            Rate limit info
        """
        # Window based on current minute
        window_start = now.replace(second=0, microsecond=0)
        window_end = window_start + timedelta(minutes=1)

        op_requests = state.operation_requests.get(operation, deque())
        requests_in_window = sum(1 for r in op_requests if r >= window_start)

        remaining = limit - requests_in_window

        if requests_in_window >= limit:
            retry_after = int((window_end - now).total_seconds())

            return RateLimitInfo(
                result=RateLimitResult.RATE_LIMITED,
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=window_end,
                retry_after=max(1, retry_after),
                message=f"Rate limit exceeded: {requests_in_window}/{limit} per minute",
            )

        return RateLimitInfo(
            result=RateLimitResult.ALLOWED,
            allowed=True,
            remaining=remaining,
            limit=limit,
            reset_at=window_end,
        )

    async def get_retry_after(
        self,
        user_id: int,
        operation: str = "api_request",
    ) -> int:
        """Get seconds until retry is allowed.

        Args:
            user_id: User ID
            operation: Operation type

        Returns:
            Seconds to wait
        """
        result = await self.check_rate_limit(user_id, operation)
        return result.retry_after

    async def set_priority_user(self, user_id: int, is_priority: bool = True) -> None:
        """Set user priority status.

        Args:
            user_id: User ID
            is_priority: Priority status
        """
        async with self._lock:
            state = self._get_user_state(user_id)
            state.is_priority = is_priority
            logger.info(
                "user_priority_updated", user_id=user_id, is_priority=is_priority
            )

    async def reset_user(self, user_id: int) -> None:
        """Reset user rate limit state.

        Args:
            user_id: User ID
        """
        async with self._lock:
            if user_id in self._users:
                is_priority = self._users[user_id].is_priority
                self._users[user_id] = UserState(
                    user_id=user_id,
                    tokens=self.config.burst_limit,
                    is_priority=is_priority,
                )
                logger.info("user_rate_limit_reset", user_id=user_id)

    async def unban_user(self, user_id: int) -> None:
        """Remove user ban.

        Args:
            user_id: User ID
        """
        async with self._lock:
            state = self._get_user_state(user_id)
            state.banned_until = None
            state.cooldown_until = None
            state.violations = 0
            logger.info("user_unbanned", user_id=user_id)

    def get_user_status(self, user_id: int) -> dict[str, Any]:
        """Get user rate limit status.

        Args:
            user_id: User ID

        Returns:
            Status dict
        """
        state = self._get_user_state(user_id)
        now = datetime.now(UTC)

        # Count requests in last minute
        minute_ago = now - timedelta(minutes=1)
        requests_last_minute = sum(1 for r in state.requests if r > minute_ago)

        return {
            "user_id": user_id,
            "is_priority": state.is_priority,
            "requests_last_minute": requests_last_minute,
            "violations": state.violations,
            "is_banned": state.banned_until is not None and now < state.banned_until,
            "banned_until": (
                state.banned_until.isoformat() if state.banned_until else None
            ),
            "is_in_cooldown": state.cooldown_until is not None
            and now < state.cooldown_until,
            "cooldown_until": (
                state.cooldown_until.isoformat() if state.cooldown_until else None
            ),
            "tokens": (
                round(state.tokens, 2)
                if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET
                else None
            ),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Statistics dict
        """
        now = datetime.now(UTC)

        return {
            "total_users": len(self._users),
            "total_requests": self._total_requests,
            "total_limited": self._total_limited,
            "limit_rate": round(
                self._total_limited / max(1, self._total_requests) * 100, 2
            ),
            "priority_users": sum(1 for u in self._users.values() if u.is_priority),
            "banned_users": sum(
                1
                for u in self._users.values()
                if u.banned_until and now < u.banned_until
            ),
            "strategy": self.config.strategy.value,
        }

    async def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """Clean up old request data.

        Args:
            max_age_hours: Maximum age of data to keep

        Returns:
            Number of users cleaned
        """
        async with self._lock:
            cleaned = 0
            cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

            for user_id, state in list(self._users.items()):
                # Remove if no recent activity
                if state.last_request and state.last_request < cutoff:
                    del self._users[user_id]
                    cleaned += 1

            if cleaned > 0:
                logger.info("rate_limiter_cleanup", cleaned_users=cleaned)

            return cleaned


# Global instance
_rate_limiter: EnhancedUserRateLimiter | None = None


def get_user_rate_limiter() -> EnhancedUserRateLimiter:
    """Get rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = EnhancedUserRateLimiter()
    return _rate_limiter


def init_user_rate_limiter(
    config: RateLimitConfig | None = None,
) -> EnhancedUserRateLimiter:
    """Initialize rate limiter.

    Args:
        config: Rate limit configuration

    Returns:
        Rate limiter instance
    """
    global _rate_limiter
    _rate_limiter = EnhancedUserRateLimiter(config=config)
    return _rate_limiter
