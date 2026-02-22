import asyncio
import time
import logging
import random
from collections import deque

logger = logging.getLogger(__name__)

class BrAlgonRateLimiter:
    """
    Implements a Sliding Window Log Rate Limiter with Exponential Backoff.
    Designed to protect the 'BrAlgon' (Algo) from getting 429'd by external APIs.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_timestamps = deque()
        self._backoff_multiplier = 0

    async def acquire(self):
        """
        Attempts to acquire a slot. If limit is reached, sleeps.
        """
        now = time.monotonic()
        
        # 1. Clean up old timestamps (Sliding Window)
        while self.request_timestamps and self.request_timestamps[0] <= now - self.window_seconds:
            self.request_timestamps.popleft()

        # 2. Check Capacity
        if len(self.request_timestamps) >= self.max_requests:
            sleep_time = self.request_timestamps[0] - (now - self.window_seconds) + 0.1
            logger.warning(f"🧠 BrAlgon Throttling: Limit reached. Sleeping for {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)
            # Recursively try agAlgon after sleep
            await self.acquire()
        else:
            self.request_timestamps.append(now)
            # Reset backoff on success (slow decay)
            if self._backoff_multiplier > 0:
                self._backoff_multiplier = max(0, self._backoff_multiplier - 1)

    async def handle_429(self, retry_after: int = None):
        """
        Triggers 'Deep Meditation' mode (Exponential Backoff) upon receiving a 429/503.
        """
        self._backoff_multiplier += 1
        
        if retry_after:
            wait_time = retry_after
        else:
            # Jittered Exponential Backoff: base * 2^n + jitter
            wait_time = (2 ** self._backoff_multiplier) + random.uniform(0, 1)
        
        logger.error(f"🛑 BRAlgoN FREEZE (429/503). Meditation active for {wait_time:.2f}s. Multiplier: {self._backoff_multiplier}")
        await asyncio.sleep(wait_time)

# Singleton instance
brain_limiter = BrAlgonRateLimiter(max_requests=20, window_seconds=60)
