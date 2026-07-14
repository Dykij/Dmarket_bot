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
"""

from __future__ import annotations

import asyncio
import logging
import time
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
        return result


# Global singleton
rate_limiter = EndpointRateLimiter()
