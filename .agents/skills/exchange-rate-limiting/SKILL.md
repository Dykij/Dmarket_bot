---
name: exchange-rate-limiting
description: 'Use when implementing API rate limiting, circuit breakers, backoff strategies, or handling 429 responses. Trigger keywords: "rate limit", "429", "backoff", "throttle", "circuit breaker", "API limits". Essential for DMarket API (10 req/s limit).'
---

# Exchange Rate Limiting

Rate limiting patterns for trading bot API integrations. Prevents 429 errors, implements circuit breakers, and handles backoff strategies.

## When to use

- DMarket API returns 429 (Too Many Requests)
- Implementing request throttling for API calls
- Building circuit breaker patterns for API resilience
- Designing backoff strategies for retries
- Monitoring API usage and limits

## Core Patterns

### Token Bucket Algorithm

```python
import asyncio
import time

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            while self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_refill = now

            self.tokens -= tokens

# Usage for DMarket API (10 req/s)
dmarket_limiter = TokenBucket(rate=10, capacity=10)

async def dmarket_api_call(endpoint: str):
    await dmarket_limiter.acquire()
    return await make_request(endpoint)
```

### Exponential Backoff with Jitter

```python
import asyncio
import random
from typing import TypeVar, Callable, Any

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True
) -> T:
    """Retry with exponential backoff and optional jitter."""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            if jitter:
                delay = delay * (0.5 + random.random())

            await asyncio.sleep(delay)

    raise RuntimeError("Max retries exceeded")
```

### Circuit Breaker Pattern

```python
import asyncio
import time
from enum import Enum
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Any]) -> Any:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise Exception("Circuit breaker is OPEN")

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise Exception("Circuit breaker is HALF_OPEN, max calls reached")
                self.half_open_calls += 1

        try:
            result = await func()
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
            return result
        except Exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()

                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
            raise

# Usage
dmarket_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

async def safe_dmarket_call(endpoint: str):
    return await dmarket_circuit.call(lambda: make_request(endpoint))
```

### DMarket-Specific Rate Limiter

```python
import asyncio
import time
from dataclasses import dataclass

@dataclass
class DMarketRateLimiter:
    """DMarket API rate limiter:10 req/s with burst handling."""
    requests_per_second: float =10.0
    burst_capacity: int =15
    min_request_interval: float =0.1  #100ms between requests

    def __post_init__(self):
        self.tokens = self.burst_capacity
        self.last_refill = time.monotonic()
        self.last_request =0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()

            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(
                self.burst_capacity,
                self.tokens + elapsed * self.requests_per_second
            )
            self.last_refill = now

            # Ensure minimum interval
            time_since_last = now - self.last_request
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)

            # Wait for token if needed
            while self.tokens <1:
                wait_time = (1 - self.tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(
                    self.burst_capacity,
                    self.tokens + elapsed * self.requests_per_second
                )
                self.last_refill = now

            self.tokens -=1
            self.last_request = time.monotonic()

# Global instance for DMarket API
dmarket_limiter = DMarketRateLimiter()
```

### 429 Response Handler

```python
import asyncio
from typing import Any, Callable

async def handle_429(
    func: Callable[..., Any],
    max_retries: int =3
) -> Any:
    """Handle429responses with retry-after header parsing."""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if "429" not in str(e):
                raise

            # Parse retry-after header if available
            retry_after = getattr(e, 'retry_after', None)
            if retry_after:
                delay = float(retry_after)
            else:
                delay =2 ** attempt  # Exponential backoff

            await asyncio.sleep(delay)

    raise Exception("Max retries for429exceeded")
```

## Integration with DMarket Bot

```python
# In your trading loop
async def trading_cycle():
    await dmarket_limiter.acquire()

    try:
        items = await dmarket_circuit.call(
            lambda: fetch_market_items()
        )
    except Exception as e:
        if "429" in str(e):
            await asyncio.sleep(1)
            return  # Skip this cycle
        raise

    for item in items:
        await dmarket_limiter.acquire()
        try:
            await process_item(item)
        except Exception as e:
            log.error(f"Failed to process {item.id}: {e}")
```

## Anti-patterns

### Not respecting rate limits
**Symptom:** Frequent429errors, API key throttling
**Fix:** Always use rate limiter before API calls

### Busy-waiting on429
**Symptom:** High CPU usage during rate limit
**Fix:** Use `asyncio.sleep()` with retry-after value

### No circuit breaker
**Symptom:** Bot keeps calling failing API, wasting resources
**Fix:** Implement circuit breaker with appropriate thresholds

### Ignoring burst capacity
**Symptom:** Intermittent429errors despite rate limiting
**Fix:** Account for burst capacity in limiter design
