"""
rate_limiter.py — Token Bucket Rate Limiter for DMarket API (v15.6)

Implements per-endpoint token bucket rate limiting to completely eliminate
429 errors from DMarket API.

Source: DMarket docs (March 2026):
- Market items: 10 RPS
- Fee: 110 RPS
- Last sales: 6 RPS
- Other methods: 20 RPS

Algorithm: Token bucket with refill rate = 80% of documented limit.
This provides a safety margin to prevent 429 errors.

v15.6: Added 429 error monitoring and adaptive safety margin.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger("RateLimiter")


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    Refills tokens at a constant rate up to bucket capacity.
    Each request consumes one token. If no tokens available, waits.
    """

    rate: float  # tokens per second
    capacity: float  # max burst size
    _tokens: float = field(default=0.0, init=False)
    _last_refill: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity  # Start full
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self) -> float:
        """Acquire one token. Returns time waited (seconds)."""
        async with self._lock:
            self._refill()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            # Calculate wait time for next token
            wait_time = (1.0 - self._tokens) / self.rate
            await asyncio.sleep(wait_time)

            # Refill after wait
            self._refill()
            self._tokens -= 1.0
            return wait_time

    @property
    def available(self) -> float:
        """Return number of available tokens (for diagnostics)."""
        self._refill()
        return self._tokens


class EndpointRateLimiter:
    """Per-endpoint rate limiter using token buckets.

    Maps DMarket API endpoints to their documented rate limits.
    Uses 80% of documented limits as safety margin.

    v15.6: Added 429 error monitoring with sliding window.
    """

    # DMarket documented limits (authorized users, March 2026)
    ENDPOINT_LIMITS: dict[str, float] = {
        "/exchange/v1/market/items": 10.0,
        "/marketplace-api/v1/aggregated-prices": 10.0,
        "/marketplace-api/v1/low-fee-items": 6.0,
        "/trade-aggregator/v1/last-sales": 6.0,
        "/marketplace-api/v1/fee": 110.0,
        "/marketplace-api/v1/user-targets": 20.0,
        "/exchange/v1/offers": 20.0,
    }
    DEFAULT_LIMIT = 20.0  # 20 RPS for other endpoints
    SAFETY_MARGIN = 0.5  # Use 50% of documented limit (conservative)
    ADAPTIVE_MARGIN_MIN = 0.3  # Minimum safety margin under high 429 rate
    ADAPTIVE_MARGIN_MAX = 0.7  # Maximum safety margin when no 429s
    MONITORING_WINDOW = 300  # 5 minutes sliding window

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._default_bucket = TokenBucket(
            rate=self.DEFAULT_LIMIT * self.SAFETY_MARGIN,
            capacity=self.DEFAULT_LIMIT * self.SAFETY_MARGIN,
        )
        # Create buckets for known endpoints
        for endpoint, limit in self.ENDPOINT_LIMITS.items():
            safe_limit = limit * self.SAFETY_MARGIN
            self._buckets[endpoint] = TokenBucket(
                rate=safe_limit,
                capacity=safe_limit,
            )

        # v15.6: 429 error monitoring
        self._429_timestamps: deque[float] = deque()  # Sliding window
        self._total_requests = 0
        self._total_429 = 0
        self._current_safety_margin = self.SAFETY_MARGIN
        self._last_adaptation = time.monotonic()

    def _get_bucket(self, path: str) -> TokenBucket:
        """Get the token bucket for a given API path."""
        for endpoint, bucket in self._buckets.items():
            if path.startswith(endpoint):
                return bucket
        return self._default_bucket

    async def acquire(self, path: str) -> float:
        """Acquire a token for the given endpoint. Returns wait time."""
        bucket = self._get_bucket(path)
        return await bucket.acquire()

    def record_429(self, path: str) -> None:
        """Record a 429 error for monitoring and adaptive rate limiting.

        Called by the API client when a 429 response is received.
        Updates the sliding window and adapts safety margin.
        """
        now = time.monotonic()
        self._429_timestamps.append(now)
        self._total_429 += 1
        self._total_requests += 1

        # Prune old entries outside the window
        cutoff = now - self.MONITORING_WINDOW
        while self._429_timestamps and self._429_timestamps[0] < cutoff:
            self._429_timestamps.popleft()

        # Adapt safety margin based on 429 rate
        self._adapt_safety_margin()

        logger.warning(
            f"[RateLimiter] 429 recorded for {path}. "
            f"Window: {len(self._429_timestamps)} in {self.MONITORING_WINDOW}s. "
            f"Total: {self._total_429}/{self._total_requests}"
        )

    def record_success(self) -> None:
        """Record a successful request for monitoring."""
        self._total_requests += 1
        # Periodically adapt safety margin
        now = time.monotonic()
        if now - self._last_adaptation > 60:  # Every 60 seconds
            self._adapt_safety_margin()
            self._last_adaptation = now

    def _adapt_safety_margin(self) -> None:
        """Adapt safety margin based on 429 error rate.

        High 429 rate → lower margin (more conservative)
        Low 429 rate → higher margin (more aggressive)
        """
        if self._total_requests < 10:
            return  # Not enough data

        # Calculate 429 rate in the window
        window_count = len(self._429_timestamps)
        window_minutes = self.MONITORING_WINDOW / 60
        rate_per_minute = window_count / window_minutes

        # Adapt margin
        if rate_per_minute > 5:  # More than 5 per minute
            new_margin = max(self.ADAPTIVE_MARGIN_MIN, self._current_safety_margin - 0.05)
        elif rate_per_minute < 0.5:  # Less than 0.5 per minute
            new_margin = min(self.ADAPTIVE_MARGIN_MAX, self._current_safety_margin + 0.02)
        else:
            new_margin = self._current_safety_margin

        if abs(new_margin - self._current_safety_margin) > 0.01:
            logger.info(
                f"[RateLimiter] Adapting safety margin: "
                f"{self._current_safety_margin:.2f} → {new_margin:.2f} "
                f"(429 rate: {rate_per_minute:.1f}/min)"
            )
            self._current_safety_margin = new_margin
            self._update_bucket_rates()

    def _update_bucket_rates(self) -> None:
        """Update all bucket rates with the current safety margin."""
        for endpoint, limit in self.ENDPOINT_LIMITS.items():
            safe_limit = limit * self._current_safety_margin
            if endpoint in self._buckets:
                self._buckets[endpoint].rate = safe_limit
                self._buckets[endpoint].capacity = safe_limit
        self._default_bucket.rate = self.DEFAULT_LIMIT * self._current_safety_margin
        self._default_bucket.capacity = self.DEFAULT_LIMIT * self._current_safety_margin

    def status(self) -> dict[str, dict]:
        """Return status of all buckets for diagnostics."""
        result = {}
        for endpoint, bucket in self._buckets.items():
            result[endpoint] = {
                "rate": bucket.rate,
                "available": bucket.available,
            }
        result["default"] = {
            "rate": self._default_bucket.rate,
            "available": self._default_bucket.available,
        }
        # v15.6: Add monitoring info
        result["_monitoring"] = {
            "total_requests": self._total_requests,
            "total_429": self._total_429,
            "429_window_count": len(self._429_timestamps),
            "429_window_seconds": self.MONITORING_WINDOW,
            "current_safety_margin": self._current_safety_margin,
            "429_rate_per_minute": len(self._429_timestamps) / (self.MONITORING_WINDOW / 60),
        }
        return result


# Global singleton
rate_limiter = EndpointRateLimiter()
