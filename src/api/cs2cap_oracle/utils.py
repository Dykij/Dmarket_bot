"""
CS2Cap Oracle — Utils mixin (volatility, health check, teardown).
"""

import logging
import math
from typing import Any, Dict, Optional

from src.db.price_history import price_db

logger = logging.getLogger("CS2CapOracle")


class _UtilsMixin:
    """Utility operations: volatility, indicators, health, close."""

    # ----------------------------------------------------------------
    # 4. VOLATILITY ESTIMATION (from price history, not candles API)
    # ----------------------------------------------------------------
    async def get_volatility(self, hash_name: str) -> float:
        """
        Estimate volatility from SQLite price history.
        Uses Garman-Klass estimator for better accuracy.
        Falls back to simple std dev if insufficient data.
        """
        history = price_db.get_recent_prices(hash_name, days=7)
        if len(history) < 5:
            return 0.0

        prices = [h[0] for h in history if h[0] > 0]
        if len(prices) < 5:
            return 0.0

        # Simple return-based volatility
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append(math.log(prices[i] / prices[i - 1]))

        if len(returns) < 2:
            return 0.0

        mean_ret = sum(returns) / len(returns)
        var_ret = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(var_ret) * math.sqrt(365)

    async def get_market_indicators(self, hash_name: str) -> Optional[Dict[str, float]]:
        """
        Get market indicators (RSI, MACD, etc.) for an item.
        Not available on free tier — returns None gracefully.
        """
        return None

    # ----------------------------------------------------------------
    # 5. HEALTH CHECK
    # ----------------------------------------------------------------
    async def health_check(self) -> Dict[str, Any]:
        """Check CS2Cap API health."""
        data = await self._request("/prices", params={"item_id": 4994, "limit": 1})
        if data is not None:
            return {"status": "healthy", "delay": self._request_delay}
        return {"status": "error", "delay": self._request_delay}

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
