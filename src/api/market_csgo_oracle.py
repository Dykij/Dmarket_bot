"""
market_csgo_oracle.py — Market.CSGO price oracle.

Free API, no auth required. Returns full dump of all CS2 items
with prices and volume.

Endpoint: GET https://market.csgo.com/api/v2/prices/USD.json
Response: {"items": [{"market_hash_name": "...", "volume": "442", "price": "30.546"}, ...]}

Rate limit: 5 req/sec (hard limit, API key auto-deleted if exceeded)
Source: market.csgo.com/api/v2 documentation

Limitations:
  - Prices may lag behind real-time by ~1-5 minutes
  - No float/phase data
  - Russian marketplace (slightly different liquidity profile)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from src.db.price_history import price_db

logger = logging.getLogger("MarketCsgoOracle")


class MarketCsgoOracle:
    """Free Market.CSGO price oracle (batch, 26K+ items)."""

    BASE_URL = "https://market.csgo.com/api/v2/prices/USD.json"
    CACHE_TTL = 900        # 15 minutes (full dump refresh)
    MEM_TTL = 900          # 15 minutes (in-memory)
    RATE_LIMIT = 5.0       # 5 req/sec (documented limit)
    SAFETY_MARGIN = 0.5    # Use 50% of limit = 2.5 RPS

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._items_cache: dict[str, dict[str, Any]] = {}
        self._items_cache_ts: float = 0.0
        # v15.6: Rate limiting
        self._last_request_time = 0.0
        self._request_delay = 1.0 / (self.RATE_LIMIT * self.SAFETY_MARGIN)  # 0.4s

    async def _throttle(self) -> None:
        """v15.6: Enforce rate limit (5 RPS documented, 2.5 RPS safe)."""
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._request_delay:
                await asyncio.sleep(self._request_delay - elapsed)
            self._last_request_time = time.monotonic()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session is not None and not self._session.closed:
                return self._session
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "DMarketBot/15.0"},
                timeout=aiohttp.ClientTimeout(total=15, connect=5),
            )
            return self._session

    async def load_items(self) -> int:
        """Load all items from Market.CSGO (1 API call). Returns item count."""
        now = time.time()
        if self._items_cache and now - self._items_cache_ts < self.CACHE_TTL:
            return len(self._items_cache)

        await self._throttle()
        session = await self._get_session()
        try:
            async with session.get(self.BASE_URL) as resp:
                if resp.status == 429:
                    # v15.6: Handle 429 with exponential backoff
                    retry_after = resp.headers.get("Retry-After", "5")
                    try:
                        wait_time = float(retry_after) + 1.0
                    except (ValueError, TypeError):
                        wait_time = 5.0
                    logger.warning(f"[Market.CSGO] 429 Rate Limited, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    return len(self._items_cache)  # Return cached data

                if resp.status != 200:
                    logger.warning(f"[Market.CSGO] Fetch failed: {resp.status}")
                    return 0
                data = await resp.json()
                items = data.get("items", [])
                self._items_cache = {}
                for item in items:
                    name = item.get("market_hash_name", "")
                    price_str = item.get("price", "0")
                    volume_str = item.get("volume", "0")
                    if name:
                        try:
                            price = float(price_str)
                            volume = int(volume_str)
                        except (ValueError, TypeError):
                            continue
                        self._items_cache[name] = {
                            "price": price,
                            "volume": volume,
                        }
                self._items_cache_ts = now

                # Persist to SQLite
                for name, item_data in self._items_cache.items():
                    price_db.record_price(
                        f"marketcsgo:{name}",
                        item_data["price"],
                        source="marketcsgo",
                    )

                logger.info(f"[Market.CSGO] Loaded {len(self._items_cache)} items")
                return len(self._items_cache)

        except Exception as e:
            logger.warning(f"[Market.CSGO] Load failed: {e}")
            return 0

    async def get_item_price(self, hash_name: str) -> float:
        """Get price for a single item."""
        await self.load_items()
        item = self._items_cache.get(hash_name)
        return item["price"] if item else 0.0

    async def get_item_volume(self, hash_name: str) -> int:
        """Get volume for a single item."""
        await self.load_items()
        item = self._items_cache.get(hash_name)
        return item["volume"] if item else 0

    async def get_prices_batch(self, hash_names: list[str]) -> dict[str, float]:
        """Get prices for multiple items (from cache)."""
        await self.load_items()
        return {
            name: self._items_cache[name]["price"]
            for name in hash_names
            if name in self._items_cache
        }

    def get_stats(self) -> dict[str, Any]:
        """Get oracle statistics."""
        return {
            "items_cached": len(self._items_cache),
            "cache_age_sec": round(time.time() - self._items_cache_ts, 1)
            if self._items_cache_ts > 0
            else None,
        }

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
