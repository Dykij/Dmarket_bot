"""Enhanced Polling Engine with best practices from industry standards.

This module provides an advanced polling solution for DMarket API that implements
best practices gathered from GitHub and industry standards:

1. **Exponential Backoff with Jitter** - prevents thundering herd problem
2. **Circuit Breaker Integration** - graceful degradation on API failures
3. **Adaptive Rate Limiting** - respects API limits dynamically
4. **Priority-based Scheduling** - important items polled more frequently
5. **Delta Compression** - only process changed data
6. **Health Monitoring** - tracks polling health metrics

Best practices sources:
- AWS Architecture Blog: Exponential Backoff and Jitter
- Google Cloud: Retry Strategies
- Netflix: Circuit Breaker Pattern
- Stripe: API Rate Limiting

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)


class BackoffStrategy(StrEnum):
    """Backoff strategies for retry logic."""

    CONSTANT = "constant"  # Fixed delay
    LINEAR = "linear"  # delay * attempt
    EXPONENTIAL = "exponential"  # base_delay * (2 ^ attempt)
    EXPONENTIAL_JITTER = "exponential_jitter"  # Exponential with random jitter
    DECORRELATED_JITTER = "decorrelated_jitter"  # AWS-recommended


class PollingHealth(StrEnum):
    """Polling health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class BackoffConfig:
    """Configuration for backoff strategy."""

    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    base_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay cap
    max_attempts: int = 5  # Maximum retry attempts
    jitter_factor: float = 0.5  # Jitter range (0-1)

    def calculate_delay(self, attempt: int, last_delay: float = 0) -> float:
        """Calculate delay for given attempt number.

        Args:
            attempt: Current attempt number (0-indexed)
            last_delay: Previous delay (for decorrelated jitter)

        Returns:
            Delay in seconds
        """
        if self.strategy == BackoffStrategy.CONSTANT:
            delay = self.base_delay

        elif self.strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)

        elif self.strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (2**attempt)

        elif self.strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            # AWS recommendation: full jitter
            exp_delay = self.base_delay * (2**attempt)
            # Non-cryptographic randomness for backoff timing
            delay = random.uniform(0, min(self.max_delay, exp_delay))  # noqa: S311

        elif self.strategy == BackoffStrategy.DECORRELATED_JITTER:
            # AWS recommendation: decorrelated jitter
            # delay = random(base_delay, last_delay * 3)
            if last_delay == 0:
                delay = self.base_delay
            else:
                # Non-cryptographic randomness for backoff timing
                delay = random.uniform(  # noqa: S311
                    self.base_delay,
                    last_delay * 3,
                )
        else:
            delay = self.base_delay

        return min(delay, self.max_delay)


@dataclass
class PollingMetrics:
    """Metrics for monitoring polling health."""

    total_polls: int = 0
    successful_polls: int = 0
    failed_polls: int = 0
    items_processed: int = 0
    changes_detected: int = 0
    avg_response_time_ms: float = 0.0
    last_poll_time: datetime | None = None
    last_success_time: datetime | None = None
    last_failure_time: datetime | None = None
    consecutive_failures: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)

    # Sliding window for response times (last 100)
    _response_times: deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def record_poll(
        self,
        success: bool,
        response_time_ms: float,
        items_count: int = 0,
        changes_count: int = 0,
        error: str | None = None,
    ) -> None:
        """Record poll result."""
        self.total_polls += 1
        self.last_poll_time = datetime.now(UTC)

        if success:
            self.successful_polls += 1
            self.last_success_time = self.last_poll_time
            self.consecutive_failures = 0
            self.items_processed += items_count
            self.changes_detected += changes_count
        else:
            self.failed_polls += 1
            self.last_failure_time = self.last_poll_time
            self.consecutive_failures += 1
            if error:
                self.error_counts[error] = self.error_counts.get(error, 0) + 1

        # Update response time average
        self._response_times.append(response_time_ms)
        if self._response_times:
            self.avg_response_time_ms = sum(self._response_times) / len(
                self._response_times
            )

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_polls == 0:
            return 1.0
        return self.successful_polls / self.total_polls

    @property
    def health_status(self) -> PollingHealth:
        """Determine health status based on metrics."""
        if self.consecutive_failures >= 10:
            return PollingHealth.CRITICAL
        if self.consecutive_failures >= 5:
            return PollingHealth.UNHEALTHY
        if self.success_rate < 0.9:
            return PollingHealth.DEGRADED
        return PollingHealth.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_polls": self.total_polls,
            "successful_polls": self.successful_polls,
            "failed_polls": self.failed_polls,
            "success_rate": round(self.success_rate * 100, 2),
            "items_processed": self.items_processed,
            "changes_detected": self.changes_detected,
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "consecutive_failures": self.consecutive_failures,
            "health_status": self.health_status.value,
            "last_poll_time": (
                self.last_poll_time.isoformat() if self.last_poll_time else None
            ),
            "error_counts": self.error_counts,
        }


@dataclass
class EnhancedPollConfig:
    """Enhanced polling configuration."""

    # Intervals
    base_interval: float = 30.0
    min_interval: float = 5.0
    max_interval: float = 300.0

    # Adaptive settings
    adaptive_enabled: bool = True
    speed_up_on_changes: bool = True
    slow_down_on_idle: bool = True

    # Backoff for errors
    backoff: BackoffConfig = field(default_factory=BackoffConfig)

    # Rate limiting
    max_requests_per_minute: int = 60
    burst_limit: int = 10

    # Circuit breaker thresholds
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    # Batch settings
    batch_size: int = 100
    max_concurrent_requests: int = 3

    # Delta detection
    cache_ttl_seconds: int = 300
    significant_change_percent: float = 1.0


# Type aliases
PriceChangeCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EnhancedPollingEngine:
    """Enhanced polling engine with industry best practices.

    Features:
    - Exponential backoff with jitter for error handling
    - Adaptive intervals based on market activity
    - Circuit breaker for graceful degradation
    - Delta detection for efficient processing
    - Health monitoring and metrics
    """

    def __init__(
        self,
        api_client: DMarketAPI,
        config: EnhancedPollConfig | None = None,
        on_price_change: PriceChangeCallback | None = None,
        on_new_listing: PriceChangeCallback | None = None,
        games: list[str] | None = None,
        whitelist_items: set[str] | None = None,
    ) -> None:
        """Initialize enhanced polling engine.

        Args:
            api_client: DMarket API client
            config: Polling configuration
            on_price_change: Callback for price changes
            on_new_listing: Callback for new listings
            games: Games to monitor
            whitelist_items: Priority items to poll more frequently
        """
        self.api = api_client
        self.config = config or EnhancedPollConfig()
        self.on_price_change = on_price_change
        self.on_new_listing = on_new_listing
        self.games = games or ["csgo"]
        self.whitelist_items = whitelist_items or set()

        # State
        self._running = False
        self._paused = False
        self._current_interval = self.config.base_interval
        self._last_delay = 0.0

        # Circuit breaker state
        self._circuit_open = False
        self._circuit_open_time: datetime | None = None

        # Delta detection cache
        self._price_cache: dict[str, dict[str, Any]] = {}
        self._known_items: set[str] = set()
        self._cache_timestamps: dict[str, datetime] = {}

        # Rate limiting
        self._request_times: deque[datetime] = deque(maxlen=100)
        self._rate_limit_lock = asyncio.Lock()

        # Metrics
        self.metrics = PollingMetrics()

        # Tasks
        self._poll_task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    @property
    def is_running(self) -> bool:
        """Check if polling is active."""
        return self._running and not self._paused

    @property
    def health(self) -> PollingHealth:
        """Get current health status."""
        if self._circuit_open:
            return PollingHealth.CRITICAL
        return self.metrics.health_status

    async def start(self) -> None:
        """Start polling engine."""
        if self._running:
            logger.warning("enhanced_polling_already_running")
            return

        self._running = True
        self._paused = False
        self._poll_task = asyncio.create_task(self._polling_loop())

        logger.info(
            "enhanced_polling_started",
            games=self.games,
            base_interval=self.config.base_interval,
            backoff_strategy=self.config.backoff.strategy.value,
        )

    async def stop(self) -> None:
        """Stop polling engine."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info(
            "enhanced_polling_stopped",
            metrics=self.metrics.to_dict(),
        )

    async def pause(self) -> None:
        """Pause polling (can be resumed)."""
        self._paused = True
        logger.info("enhanced_polling_paused")

    async def resume(self) -> None:
        """Resume paused polling."""
        self._paused = False
        logger.info("enhanced_polling_resumed")

    async def force_poll(self, game: str | None = None) -> list[dict[str, Any]]:
        """Force immediate poll.

        Args:
            game: Specific game to poll (or all if None)

        Returns:
            List of detected changes
        """
        games_to_poll = [game] if game else self.games
        all_changes = []

        for g in games_to_poll:
            changes = await self._poll_game(g)
            all_changes.extend(changes)

        return all_changes

    async def _polling_loop(self) -> None:
        """MAlgon polling loop with adaptive intervals."""
        while self._running:  # noqa: PLR1702
            try:
                # Check if paused
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                # Check circuit breaker
                if self._circuit_open:
                    if await self._should_close_circuit():
                        self._circuit_open = False
                        logger.info("enhanced_polling_circuit_closed")
                    else:
                        await asyncio.sleep(self.config.backoff.base_delay)
                        continue

                # Check rate limit
                await self._wait_for_rate_limit()

                # Poll all games
                start_time = datetime.now(UTC)
                total_changes = 0
                total_items = 0
                poll_success = True

                for game in self.games:
                    if not self._running:
                        break

                    try:
                        changes = await self._poll_game(game)
                        total_changes += len(changes)
                        total_items += len(self._known_items)

                        # Notify callbacks
                        for change in changes:
                            if self.on_price_change:
                                try:
                                    await self.on_price_change(change)
                                except Exception as e:
                                    logger.exception(
                                        "price_change_callback_error", error=str(e)
                                    )

                    except Exception as e:
                        poll_success = False
                        logger.exception("poll_game_error", game=game, error=str(e))

                # Record metrics
                elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                self.metrics.record_poll(
                    success=poll_success,
                    response_time_ms=elapsed_ms,
                    items_count=total_items,
                    changes_count=total_changes,
                )

                # Handle success/failure
                if poll_success:
                    self._last_delay = 0
                    self._adjust_interval(total_changes)
                else:
                    await self._handle_failure()

                # WAlgot for next poll
                await asyncio.sleep(self._current_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("polling_loop_error", error=str(e))
                await asyncio.sleep(self.config.base_interval)

    async def _poll_game(self, game: str) -> list[dict[str, Any]]:
        """Poll items for a specific game.

        Args:
            game: Game to poll

        Returns:
            List of changes detected
        """
        changes = []

        async with self._semaphore:
            # Record request time for rate limiting
            self._request_times.append(datetime.now(UTC))

            response = await self.api.get_market_items(
                game=game,
                limit=self.config.batch_size,
            )

        items = response.get("objects", [])

        for item in items:
            item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
            if not item_id:
                continue

            # Check for new listing
            if item_id not in self._known_items:
                self._known_items.add(item_id)
                if self.on_new_listing:
                    try:
                        await self.on_new_listing(item)
                    except Exception as e:
                        logger.exception("new_listing_callback_error", error=str(e))
                continue

            # Check for price change using delta detection
            change = self._detect_change(item)
            if change:
                changes.append(change)

        return changes

    def _detect_change(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Detect price or quantity changes using delta compression.

        Args:
            item: Current item data

        Returns:
            Change dict or None if no significant change
        """
        item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
        title = item.get("title", "Unknown")

        # Get current price (cents to dollars)
        price_data = item.get("price", {})
        current_price = float(price_data.get("USD", "0")) / 100

        if current_price <= 0:
            return None

        # Check cache
        cached = self._price_cache.get(item_id)
        cache_time = self._cache_timestamps.get(item_id)

        # Check if cache expired
        if cache_time:
            if datetime.now(UTC) - cache_time > timedelta(
                seconds=self.config.cache_ttl_seconds
            ):
                # Cache expired, refresh
                self._price_cache.pop(item_id, None)
                self._cache_timestamps.pop(item_id, None)
                cached = None

        if cached is None:
            # First time - cache it
            self._price_cache[item_id] = {
                "price": current_price,
                "quantity": item.get("amount", 1),
            }
            self._cache_timestamps[item_id] = datetime.now(UTC)
            return None

        # Check for significant change
        old_price = cached["price"]
        if old_price > 0:
            change_percent = abs((current_price - old_price) / old_price) * 100
        else:
            change_percent = 100.0

        if change_percent < self.config.significant_change_percent:
            return None

        # Update cache
        self._price_cache[item_id] = {
            "price": current_price,
            "quantity": item.get("amount", 1),
        }
        self._cache_timestamps[item_id] = datetime.now(UTC)

        return {
            "item_id": item_id,
            "item_name": title,
            "old_price": old_price,
            "new_price": current_price,
            "change_percent": round(change_percent, 2),
            "detected_at": datetime.now(UTC).isoformat(),
        }

    def _adjust_interval(self, changes_count: int) -> None:
        """Adjust polling interval based on activity.

        Args:
            changes_count: Number of changes detected in last poll
        """
        if not self.config.adaptive_enabled:
            return

        if changes_count > 0 and self.config.speed_up_on_changes:
            # More changes = poll faster
            self._current_interval = max(
                self.config.min_interval,
                self._current_interval * 0.8,
            )
        elif changes_count == 0 and self.config.slow_down_on_idle:
            # No changes = poll slower
            self._current_interval = min(
                self.config.max_interval,
                self._current_interval * 1.1,
            )

    async def _handle_failure(self) -> None:
        """Handle polling failure with backoff."""
        # Calculate backoff delay
        attempt = self.metrics.consecutive_failures
        self._last_delay = self.config.backoff.calculate_delay(
            attempt, self._last_delay
        )

        logger.warning(
            "enhanced_polling_failure",
            consecutive_failures=self.metrics.consecutive_failures,
            backoff_delay=self._last_delay,
        )

        # Check if circuit should open
        if self.metrics.consecutive_failures >= self.config.failure_threshold:
            self._circuit_open = True
            self._circuit_open_time = datetime.now(UTC)
            logger.error("enhanced_polling_circuit_opened")

        # Apply backoff delay
        self._current_interval = self._last_delay

    async def _should_close_circuit(self) -> bool:
        """Check if circuit breaker should close.

        Returns:
            True if circuit should close (recover)
        """
        if self._circuit_open_time is None:
            return True

        elapsed = (datetime.now(UTC) - self._circuit_open_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    async def _wait_for_rate_limit(self) -> None:
        """WAlgot if rate limit would be exceeded."""
        async with self._rate_limit_lock:
            now = datetime.now(UTC)
            minute_ago = now - timedelta(minutes=1)

            # Count requests in last minute
            recent_requests = [t for t in self._request_times if t > minute_ago]

            if len(recent_requests) >= self.config.max_requests_per_minute:
                # WAlgot until oldest request expires
                oldest = min(recent_requests)
                wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
                if wait_time > 0:
                    logger.debug(
                        "enhanced_polling_rate_limit_wait", wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return {
            **self.metrics.to_dict(),
            "current_interval": round(self._current_interval, 2),
            "circuit_open": self._circuit_open,
            "cached_items": len(self._price_cache),
            "known_items": len(self._known_items),
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._price_cache.clear()
        self._known_items.clear()
        self._cache_timestamps.clear()


def create_content_hash(data: dict[str, Any]) -> str:
    """Create hash of content for delta detection.

    Args:
        data: Data to hash

    Returns:
        SHA-256 hash string
    """
    content = str(sorted(data.items()))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# Factory function
def create_enhanced_polling(
    api_client: DMarketAPI,
    games: list[str] | None = None,
    on_price_change: PriceChangeCallback | None = None,
    aggressive: bool = False,
) -> EnhancedPollingEngine:
    """Create enhanced polling engine with preset configuration.

    Args:
        api_client: DMarket API client
        games: Games to monitor
        on_price_change: Callback for price changes
        aggressive: Use aggressive polling (more frequent)

    Returns:
        Configured EnhancedPollingEngine
    """
    config = EnhancedPollConfig()

    if aggressive:
        config.base_interval = 15.0
        config.min_interval = 5.0
        config.speed_up_on_changes = True

    return EnhancedPollingEngine(
        api_client=api_client,
        config=config,
        games=games,
        on_price_change=on_price_change,
    )
