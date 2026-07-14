"""
waxpeer_oracle.py — Waxpeer price oracle.

Free API, no auth required. Returns full dump of all CS2 items
with prices, counts, and Steam reference prices.

Endpoint: GET https://api.waxpeer.com/v1/prices?game=csgo
Response: {"items": [{"name": "...", "count": 388, "min": 31449,
           "steam_price": 29626, ...}, ...]}

Price unit: mills (1/1000 USD) — 31848 = $31.848

Rate limit: ~1 req/sec (no official docs, community reports)
Source: Reddit r/csgomarketforum, community testing

Limitations:
  - Prices in mills (need /1000)
  - No float/phase data
  - Steam price reference is also in mills
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from src.db.price_history import price_db

logger = logging.getLogger("WaxpeerOracle")


class WaxpeerOracle:
    """Free Waxpeer price oracle (batch, 21K+ items)."""

    BASE_URL = "https://api.waxpeer.com/v1/prices"
    CACHE_TTL = 900        # 15 minutes (full dump refresh)
    MEM_TTL = 900          # 15 minutes (in-memory)
    RATE_LIMIT = 1.0       # ~1 req/sec (community estimate)
    SAFETY_MARGIN = 0.5    # Use 50% of limit = 0.5 RPS

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._items_cache: dict[str, dict[str, Any]] = {}
        self._items_cache_ts: float = 0.0
        # v15.6: Rate limiting
        self._last_request_time = 0.0
        self._request_delay = 1.0 / (self.RATE_LIMIT * self.SAFETY_MARGIN)  # 2.0s

    async def _throttle(self) -> None:
        """v15.6: Enforce rate limit (~1 RPS documented, 0.5 RPS safe)."""
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
        """Load all items from Waxpeer (1 API call). Returns item count."""
        now = time.time()
        if self._items_cache and now - self._items_cache_ts < self.CACHE_TTL:
            return len(self._items_cache)

        await self._throttle()
        session = await self._get_session()
        try:
            async with session.get(
                self.BASE_URL, params={"game": "csgo"}
            ) as resp:
                if resp.status == 429:
                    # v15.6: Handle 429 with exponential backoff
                    retry_after = resp.headers.get("Retry-After", "5")
                    try:
                        wait_time = float(retry_after) + 1.0
                    except (ValueError, TypeError):
                        wait_time = 5.0
                    logger.warning(f"[Waxpeer] 429 Rate Limited, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    return len(self._items_cache)  # Return cached data

                if resp.status != 200:
                    logger.warning(f"[Waxpeer] Fetch failed: {resp.status}")
                    return 0
                data = await resp.json()
                items = data.get("items", [])
                self._items_cache = {}
                for item in items:
                    name = item.get("name", "")
                    min_cents = item.get("min", 0)
                    count = item.get("count", 0)
                    steam_cents = item.get("steam_price", 0)
                    if name:
                        try:
                            # Waxpeer returns prices in mills (1/1000 USD)
                            # e.g., 31848 = $31.848
                            price = float(min_cents) / 1000.0
                            volume = int(count)
                            steam_price = float(steam_cents) / 1000.0
                        except (ValueError, TypeError):
                            continue
                        self._items_cache[name] = {
                            "price": price,
                            "volume": volume,
                            "steam_price": steam_price,
                        }
                self._items_cache_ts = now

                # Persist to SQLite
                for name, item_data in self._items_cache.items():
                    price_db.record_price(
                        f"waxpeer:{name}",
                        item_data["price"],
                        source="waxpeer",
                    )

                logger.info(f"[Waxpeer] Loaded {len(self._items_cache)} items")
                return len(self._items_cache)

        except Exception as e:
            logger.warning(f"[Waxpeer] Load failed: {e}")
            return 0

    async def get_item_price(self, hash_name: str) -> float:
        """Get price for a single item."""
        await self.load_items()
        item = self._items_cache.get(hash_name)
        return item["price"] if item else 0.0

    async def get_item_steam_price(self, hash_name: str) -> float:
        """Get Steam reference price for a single item."""
        await self.load_items()
        item = self._items_cache.get(hash_name)
        return item["steam_price"] if item else 0.0

    async def get_item_volume(self, hash_name: str) -> int:
        """Get volume (count) for a single item."""
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
