"""Rate limiting middleware for Telegram bot."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from aiolimiter import AsyncLimiter

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")


class RateLimiterMiddleware:
    """Rate limiting middleware for bot commands."""

    def __init__(
        self,
        max_requests_per_minute: int = 10,
        max_requests_per_hour: int = 100,
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_hour = max_requests_per_hour

        self.user_limiters: dict[int, dict[str, AsyncLimiter]] = defaultdict(
            lambda: {
                "minute": AsyncLimiter(max_requests_per_minute, 60),
                "hour": AsyncLimiter(max_requests_per_hour, 3600),
            }
        )

        self.global_limiter = AsyncLimiter(max_rate=100, time_period=60)
        self.violations: dict[int, list[datetime]] = defaultdict(list)

    async def check_rate_limit(self, user_id: int) -> None:
        """Check if user is within rate limits."""
        user_limiter = self.user_limiters[user_id]

        if not await user_limiter["minute"].has_capacity():
            logger.warning("rate_limit_exceeded_minute", user_id=user_id)
            self._record_violation(user_id)
            raise RateLimitExceeded(retry_after=60)

        if not await user_limiter["hour"].has_capacity():
            logger.warning("rate_limit_exceeded_hour", user_id=user_id)
            self._record_violation(user_id)
            raise RateLimitExceeded(retry_after=3600)

        async with user_limiter["minute"], user_limiter["hour"]:
            logger.debug("rate_limit_passed", user_id=user_id)

    def _record_violation(self, user_id: int) -> None:
        """Record rate limit violation."""
        now = datetime.now(UTC)
        self.violations[user_id].append(now)

        cutoff = now - timedelta(hours=1)
        self.violations[user_id] = [v for v in self.violations[user_id] if v > cutoff]


# Global rate limiter instance
rate_limiter = RateLimiterMiddleware(
    max_requests_per_minute=10,
    max_requests_per_hour=100,
)
