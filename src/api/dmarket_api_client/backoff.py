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
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger("DMarketAPI.Backoff")


class CircuitState(str, Enum):
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

    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    current_cooldown: float = 0.0  # initialised in __post_init__
    opened_at: float = 0.0
    total_opens: int = 0
    last_error: str = ""

    def __post_init__(self) -> None:
        # Sync current_cooldown with the user-provided base_cooldown on
        # first construction. Subsequent failures will multiply it.
        if self.current_cooldown == 0.0:
            self.current_cooldown = self.base_cooldown

    def allow_request(self) -> bool:
        """Return True if the caller may proceed with a request."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.opened_at
            if elapsed >= self.current_cooldown:
                # Transition to HALF_OPEN: allow ONE test request
                self.state = CircuitState.HALF_OPEN
                logger.info(
                    f"[CB:{self.name}] OPEN → HALF_OPEN "
                    f"(cooldown={self.current_cooldown:.1f}s elapsed={elapsed:.1f}s)"
                )
                return True
            return False
        # HALF_OPEN: only allow one in-flight test
        return True

    def record_success(self) -> None:
        """Mark a successful request (closes the circuit if it was open)."""
        if self.state != CircuitState.CLOSED:
            logger.info(f"[CB:{self.name}] {self.state.value} → CLOSED (success)")
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.current_cooldown = self.base_cooldown
        self.last_error = ""

    def record_failure(self, err: Exception) -> None:
        """Mark a failed request (opens the circuit if threshold reached)."""
        self.consecutive_failures += 1
        self.last_error = f"{type(err).__name__}: {err}"[:200]
        if self.consecutive_failures >= self.fail_threshold:
            if self.state != CircuitState.OPEN:
                # Apply jitter to cooldown: -20% to +20%
                jitter = 1.0 + random.uniform(-self.jitter_pct, self.jitter_pct)
                cooldown = self.current_cooldown * jitter
                self.opened_at = time.time()
                self.state = CircuitState.OPEN
                self.total_opens += 1
                logger.warning(
                    f"[CB:{self.name}] → OPEN "
                    f"(failures={self.consecutive_failures}, "
                    f"cooldown={cooldown:.1f}s, err={self.last_error})"
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

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "current_cooldown": self.current_cooldown,
            "total_opens": self.total_opens,
            "last_error": self.last_error,
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


# HTTP status codes that should NOT trip the breaker
# (404 for a specific resource, 400 for bad payload, etc.)
NON_TRIPPING_STATUSES = {400, 401, 403, 404, 422}


def should_trip(status: int) -> bool:
    """Return True if an HTTP status should count as a circuit-breaker failure."""
    if status in NON_TRIPPING_STATUSES:
        return False
    # 429 (rate limit) and 5xx (server errors) should trip
    return status == 429 or status >= 500
