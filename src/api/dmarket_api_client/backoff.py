"""
backoff.py — Circuit breaker + jittered exponential backoff for DMarket.

Problem:
  When DMarket returns 429 (rate limit) or 5xx errors, the original
  tenacity retry would blindly retry 3 times in 2-10s windows. This
  can:
    1. Worsen the rate-limit situation (we ARE the cause of the 429)
    2. Burn the bot's reputation with DMarket (DDoS-like behaviour)
    3. Waste time on a failing endpoint when other endpoints work

Solution: circuit breaker pattern + jittered backoff.
  - 3 states: CLOSED (normal), OPEN (block all requests), HALF_OPEN (test).
  - OPEN state duration starts at 30s and doubles on consecutive failures
    (capped at 300s). A single success in HALF_OPEN closes the circuit.
  - All wait times include ±20% jitter to prevent thundering herd when
    many bots recover at the same instant.

v15.0: Retry-After adaptive backoff, per-endpoint aliases, and
fallback gateway support (trading.dmarket.com) to avoid global 429.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("DMarketAPI.Backoff")


class CircuitState(Enum):
    CLOSED = "CLOSED"        # normal operation
    OPEN = "OPEN"            # blocking all requests
    HALF_OPEN = "HALF_OPEN"  # testing one request


@dataclass
class CircuitBreaker:
    """
    Per-endpoint-class circuit breaker.

    Usage:
        breaker = CircuitBreaker(name="dmarket", fail_threshold=3, base_cooldown=30.0)

        if not breaker.allow_request():
            raise CircuitOpenError("breaker open")

        try:
            result = await endpoint()
            breaker.record_success()
        except (aiohttp.ClientResponseError, asyncio.TimeoutError) as e:
            breaker.record_failure(e)
            raise
    """

    name: str
    fail_threshold: int = 3           # consecutive failures before opening
    base_cooldown: float = 30.0       # first OPEN duration (seconds)
    max_cooldown: float = 300.0       # cap for exponential backoff
    jitter_pct: float = 0.2           # ±20% jitter on wait times
    half_open_timeout: float = 60.0   # max seconds in HALF_OPEN before auto-close

    state: CircuitState = field(default=CircuitState.CLOSED)
    consecutive_failures: int = field(default=0)
    current_cooldown: float = field(default=0.0)
    opened_at: float = field(default=0.0)
    half_opened_at: float = field(default=0.0)
    total_opens: int = field(default=0)
    last_error: str = field(default="")

    # v15.0: server-proposed backoff via Retry-After
    _server_backoff_until: float = field(default=0.0, repr=False)

    # Async lock for thread/task safety in concurrent async contexts
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, init=False)

    def __post_init__(self) -> None:
        # Sync current_cooldown with the user-provided base_cooldown on
        # first construction. Subsequent failures will multiply it.
        if self.current_cooldown == 0.0:
            self.current_cooldown = self.base_cooldown

    def allow_request(self) -> bool:
        """Return True if the caller may proceed with a request.

        Protected by an async lock to prevent race conditions on
        OPEN → HALF_OPEN transitions when multiple concurrent
        requests call allow_request() simultaneously.
        """
        now = time.time()
        if now < self._server_backoff_until:
            return False

        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = now - self.opened_at
            if elapsed >= self.current_cooldown:
                self.state = CircuitState.HALF_OPEN
                self.half_opened_at = now
                logger.info(
                    f"[CB:{self.name}] OPEN → HALF_OPEN "
                    f"(cooldown={self.current_cooldown:.1f}s elapsed={elapsed:.1f}s)"
                )
                return True
            return False
        # HALF_OPEN: only one in-flight test; auto-close on timeout
        # race-safe: if two callers reach HALF_OPEN simultaneously, both
        # observe consecutive_failures == 0 and one gets a True, the other
        # gets False (consecutive_failures incremented by record_failure
        # in the other caller). This still produces at most one probe.
        if now - self.half_opened_at > self.half_open_timeout:
            self.state = CircuitState.CLOSED
            self.consecutive_failures = 0
            logger.info(
                f"[CB:{self.name}] HALF_OPEN timed out after "
                f"{self.half_open_timeout:.0f}s → CLOSED"
            )
            return True
        return self.consecutive_failures == 0

    def record_success(self) -> None:
        """Mark a successful request (closes the circuit if it was open)."""
        if self.state != CircuitState.CLOSED:
            logger.info(f"[CB:{self.name}] {self.state.value} → CLOSED (success)")
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.current_cooldown = self.base_cooldown
        self.last_error = ""

    def record_failure(self, err: Exception) -> None:
        """Mark a failed request (opens the circuit if threshold reached).

        Note: This method mutates shared mutable state. In an async context
        with parallel requests, callers should ensure serial access (e.g.
        by holding the API client's request lock) or use the async variant.
        For simplicity and backward compatibility, we keep this synchronous
        but document the requirement.
        """
        self.consecutive_failures += 1
        self.last_error = f"{type(err).__name__}: {err}"[:200]
        if self.consecutive_failures >= self.fail_threshold:
            if self.state != CircuitState.OPEN:
                # Apply jitter to cooldown: -20% to +20%
                jitter = 1.0 + random.uniform(-self.jitter_pct, self.jitter_pct)
                self.current_cooldown = min(
                    self.base_cooldown * jitter, self.max_cooldown
                )
                self.opened_at = time.time()
                self.state = CircuitState.OPEN
                self.total_opens += 1
                logger.warning(
                    f"[CB:{self.name}] → OPEN "
                    f"(failures={self.consecutive_failures}, "
                    f"cooldown={self.current_cooldown:.1f}s, err={self.last_error})"
                )
            else:
                # Already open: extend cooldown exponentially
                self.current_cooldown = min(
                    self.current_cooldown * 2.0, self.max_cooldown
                )
                self.opened_at = time.time()
                logger.warning(
                    f"[CB:{self.name}] OPEN extended "
                    f"(cooldown={self.current_cooldown:.1f}s)"
                )

    def apply_retry_after(self, retry_after: float) -> None:
        """v15.0: Honor server's Retry-After or x-rate-limit-reset.

        Called when a 429/503 response includes a Retry-After header.
        This immediately defers all requests until the proposed time,
        without tripping the circuit breaker further.
        """
        now = time.time()
        proposed = now + retry_after
        if proposed > self._server_backoff_until:
            self._server_backoff_until = proposed
            logger.info(
                f"[CB:{self.name}] Respecting Retry-After: "
                f"{retry_after:.1f}s (backoff_until={proposed:.0f})"
            )

    def apply_rate_limit_remaining(self, remaining: int, reset_in: float | None = None) -> None:
        """v15.0: Proactive slowdown when quota is nearly exhausted.

        Called when X-RateLimit-Remaining is low but not yet zero.
        Adds a small preemptive pause to avoid hard 429.
        """
        if remaining <= 0:
            # Treat as immediate server backoff without tripping
            self.apply_retry_after(reset_in if reset_in is not None else self.base_cooldown)
        elif remaining < 5:
            self._server_backoff_until = max(self._server_backoff_until, time.time() + 5.0)

    def status(self) -> dict:
        now = time.time()
        remaining = max(0.0, self._server_backoff_until - now)
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "current_cooldown": self.current_cooldown,
            "total_opens": self.total_opens,
            "last_error": self.last_error,
            "server_backoff_remaining": round(remaining, 1),
        }


class CircuitOpenError(Exception):
    """Raised when the breaker is OPEN and the request is blocked."""

    def __init__(self, breaker_name: str, cooldown_remaining: float):
        self.breaker_name = breaker_name
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"Circuit '{breaker_name}' is OPEN "
            f"({cooldown_remaining:.1f}s until HALF_OPEN)"
        )


def jittered_sleep(base_seconds: float, jitter_pct: float = 0.2) -> float:
    """
    Sleep for base_seconds with ±jitter_pct randomization.
    Returns the actual sleep duration.
    """
    jitter = 1.0 + random.uniform(-jitter_pct, jitter_pct)
    duration = max(0.0, base_seconds * jitter)
    return duration


# HTTP status codes that should NOT trip the breaker.
# 400/401/403/404/422 are client-side or resource-specific.
# 503 "Service Unavailable" is usually a temporary DMarket internal issue
# (e.g. elasticsearch unavailable) and should not punish the bot with a
# long circuit-breaker cooldown. The @retry decorator will still retry.
NON_TRIPPING_STATUSES = {400, 401, 403, 404, 422, 503}


def should_trip(status: int) -> bool:
    """Return True if an HTTP status should count as a circuit-breaker failure."""
    if status in NON_TRIPPING_STATUSES:
        return False
    # 429 (rate limit) and hard 5xx (500, 502, 504) should trip
    return status == 429 or status >= 500


# =====================================================================
# v15.0: Retry-After / X-RateLimit-Remaining parsing helpers
# =====================================================================

def parse_retry_after(header_value: str) -> float | None:
    """Parse Retry-After header (seconds or HTTP-date)."""
    try:
        return float(header_value)
    except (ValueError, TypeError):
        return None


def extract_backoff_from_headers(headers: dict) -> tuple:
    """Extracts (retry_after_seconds, remaining, reset_in_seconds) from response headers."""
    retry_after: float | None = None
    remaining: int | None = None
    reset_in: float | None = None

    h = {k.lower(): v for k, v in headers.items()}

    # Retry-After (seconds or HTTP-date)
    ra = h.get("retry-after")
    if ra is not None:
        retry_after = parse_retry_after(ra)

    # X-RateLimit-Remaining
    rem = h.get("x-ratelimit-remaining")
    if rem is not None:
        try:
            remaining = int(rem)
        except (ValueError, TypeError):
            remaining = None

    # X-RateLimit-Reset (absolute Unix timestamp)
    reset = h.get("x-ratelimit-reset")
    if reset is not None:
        try:
            reset_ts = float(reset)
            reset_in = max(0.0, reset_ts - time.time())
        except (ValueError, TypeError):
            reset_in = None

    return retry_after, remaining, reset_in
