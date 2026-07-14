"""
steam_oracle.py — Steam Community Market price oracle.

Uses Steam's public priceoverview endpoint for reference prices.
Rate limit: ~10 requests/sec (no official limit, but aggressive
throttling to avoid IP bans).

Limitations:
  - Only returns median price (no lowest ask / highest bid)
  - No batch endpoint (1 item per request)
  - Prices in Steam Wallet (not real cash) — typically 15% higher
    than cash marketplace prices
"""

import asyncio
import logging
import os
import time

import aiohttp

from src.db.price_history import price_db

logger = logging.getLogger("SteamOracle")

# Steam prices are ~15% higher than cash marketplaces due to
# Steam Wallet non-convertibility. Adjust factor to estimate
# cash-equivalent price.
STEAM_TO_CASH_FACTOR = 0.85


class SteamOracle:
    """Free Steam Community Market price oracle."""

    BASE_URL = "https://steamcommunity.com/market/priceoverview/"
    CACHE_TTL = 10800   # 3 hours (SQLite)
    MEM_TTL = 900        # 15 minutes (in-memory)

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.getenv("STEAM_API_KEY", "")
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._request_delay = 0.15  # ~6-7 req/sec to be safe
        self._mem_cache: dict[str, tuple[float, float]] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session is not None and not self._session.closed:
                return self._session
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15, connect=5)
            )
            return self._session

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._request_delay:
                await asyncio.sleep(self._request_delay - elapsed)
            self._last_request_time = time.monotonic()

    async def get_item_price(self, hash_name: str) -> float:
        """
        Get Steam median price for an item.
        Returns cash-equivalent price (adjusted for Steam Wallet factor).
        """
        now = time.time()

        # Layer 1: Memory cache
        if hash_name in self._mem_cache:
            price, ts = self._mem_cache[hash_name]
            if now - ts < self.MEM_TTL:
                return price

        # Layer 2: SQLite cache
        cached = price_db.get_latest_price(
            f"steam:{hash_name}", max_age_seconds=self.CACHE_TTL
        )
        if cached is not None:
            self._mem_cache[hash_name] = (cached, now)
            return cached

        # Layer 3: Live API
        await self._throttle()
        session = await self._get_session()

        params = {
            "appid": 730,
            "currency": 1,  # USD
            "market_hash_name": hash_name,
        }

        for attempt in range(3):
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    if resp.status == 429:
                        wait = 5.0 * (attempt + 1)
                        logger.warning(f"[Steam] Rate limited, backing off {wait}s (attempt {attempt+1})")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        logger.debug(f"[Steam] HTTP {resp.status} for {hash_name}")
                        return 0.0

                data = await resp.json()
                if not data.get("success"):
                    return 0.0

                # Parse "median_price" or "lowest_price" field
                # Format: "$12.34" or "12,34"
                median_str = data.get("median_price") or data.get("lowest_price", "")
                if not median_str:
                    return 0.0

                price = self._parse_price(median_str)
                if price > 0:
                    # Convert Steam price to cash-equivalent
                    cash_price = round(price * STEAM_TO_CASH_FACTOR, 2)
                    price_db.record_price(f"steam:{hash_name}", cash_price, source="steam")
                    self._mem_cache[hash_name] = (cash_price, now)
                    return cash_price

                return 0.0

            except Exception as e:
                logger.debug(f"[Steam] Error fetching {hash_name}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                return 0.0
        return 0.0

    async def get_prices_batch(self, hash_names: list[str]) -> dict[str, float]:
        """
        Fetch prices for multiple items (sequential with throttle).
        Returns {hash_name: cash_equivalent_price}.
        """
        results: dict[str, float] = {}
        for name in hash_names:
            price = await self.get_item_price(name)
            results[name] = price
        return results

    @staticmethod
    def _parse_price(price_str: str) -> float:
        """Parse Steam price string like '$12.34' or '12,34' to float."""
        cleaned = price_str.replace("$", "").replace(",", ".").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
