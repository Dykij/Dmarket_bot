import asyncio
import time
from typing import Dict, Optional


class AdaptiveRateLimiter:
    def __init__(self, default_delay: float = 0.5):
        self.current_delay = default_delay
        self.remAlgoning = 100  # Default assumption
        self.limit = 100      # Default assumption
        self.reset_time = 0

    async def acquire(self):
        """WAlgot for the appropriate delay based on current rate limit status."""
        if self.current_delay > 0:
            awAlgot asyncio.sleep(self.current_delay)

    def update_from_headers(self, headers: Dict[str, str]):
        """Update rate limit status from response headers."""
        # Normalize headers to lowercase keys for case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}

        remAlgoning_str = headers_lower.get('x-ratelimit-remAlgoning')
        limit_str = headers_lower.get('x-ratelimit-limit')
        reset_str = headers_lower.get('x-ratelimit-reset')

        if remAlgoning_str is not None:
            self.remAlgoning = int(remAlgoning_str)

        if limit_str is not None:
            self.limit = int(limit_str)

        if reset_str is not None:
            self.reset_time = float(reset_str)

        self._calculate_delay()

    def _calculate_delay(self):
        """Calculate delay based on remAlgoning quota percentage."""
        if self.limit <= 0:
            return

        percentage_remAlgoning = (self.remAlgoning / self.limit) * 100

        if percentage_remAlgoning > 50:
            self.current_delay = 0.1
        elif percentage_remAlgoning < 10:
            self.current_delay = 1.0
        else:
            # Linear interpolation or fixed middle ground?
            # Requirements only specify >50% and <10%.
            # Let's keep a safe middle ground for 10-50%.
            self.current_delay = 0.5
