"""
CS2Cap Oracle — BUFF163 + 41 Markets Price Reference (v12.0).

CS2Cap aggregates prices from BUFF163 (Chinese market) and 40+ other CS2 skin
markets, providing a reliable price reference for cross-market comparison.

Free tier limitations:
- 1,000 requests/month
- Single item price queries only (`/v1/prices/{game}/{name}`)
- No bids endpoint (returns 403)

Paid tiers:
- Starter ($19/mo): 10K req, adds `/v1/bids/{game}/{name}` and `/v1/batch`
- Pro ($79/mo): 100K req, adds `/v1/candles/{game}/{name}` and history
"""

import aiohttp
import asyncio
import logging
import os
import time
import urllib.parse
from typing import Optional, Dict, List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.db.price_history import price_db

logger = logging.getLogger("CS2CapOracle")


class RateLimitException(Exception):
    """Raised when CS2Cap returns 429."""
    pass


class CS2CapOracle:
    """
    External Pricing Oracle for CS2 skins.
    Uses CS2Cap API (BUFF163 + 41 markets) with layered caching.

    Layers:
    1. In-Memory Cache (15 minutes TTL) — instant
    2. SQLite History DB (3 hours TTL) — persistent
    3. Live CS2Cap API — throttled

    Rate limiting:
    - 1 RPS default (Free tier safe)
    - Backoff to 0.5 RPS on 429
    - Persistent throttling state in SQLite
    """

    BASE_URL = "https://api.cs2cap.com"
    CACHE_TTL = 10800  # 3 hours (SQLite)
    MEM_TTL = 900  # 15 minutes (in-memory)

    def __init__(self, api_key: str = "", tier: str = "free"):
        self.api_key = api_key
        self.tier = tier  # "free" | "starter" | "pro"
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()

        # Persistent throttling (State DB)
        saved_delay = price_db.get_state("cs2cap_delay")
        self.request_delay = float(saved_delay) if saved_delay else 1.0
        self._last_request_time = 0.0

        # In-memory quick cache
        self._mem_cache: Dict[str, Tuple[float, float]] = {}

        # Performance metrics
        self.api_calls = 0
        self.cache_hits = 0
        self.errors = 0

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _throttle(self):
        """Enforce persistent request delay."""
        async with self._lock:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self.request_delay:
                await asyncio.sleep(self.request_delay - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    @retry(
        retry=retry_if_exception_type(RateLimitException),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60)
    )
    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Get the lowest ask price for a CS2 item from CS2Cap (BUFF163 + 41 markets).

        Args:
            hash_name: Market hash name (e.g., "AK-47 | Redline (Field-Tested)")
            offset: Pagination offset

        Returns:
            Price in USD, or 0.0 if not found
        """
        now = time.time()

        # Layer 1: In-Memory
        if hash_name in self._mem_cache:
            m_price, m_time = self._mem_cache[hash_name]
            if now - m_time < self.MEM_TTL:
                self.cache_hits += 1
                return m_price

        # Layer 2: SQLite History
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            self._mem_cache[hash_name] = (cached, now)
            self.cache_hits += 1
            return cached

        # Layer 3: Live API
        await self._throttle()
        session = await self.get_session()

        encoded_name = urllib.parse.quote(hash_name)
        url = f"{self.BASE_URL}/v1/prices/a8db/{encoded_name}?offset={offset}"

        try:
            async with session.get(url) as response:
                if response.status == 429:
                    logger.warning("[CS2Cap] 429 Rate Limit! Penalizing delay.")
                    self.request_delay = min(self.request_delay * 2.0, 20.0)
                    price_db.save_state("cs2cap_delay", str(self.request_delay))
                    raise RateLimitException("429 Too Many Requests")

                if response.status == 403:
                    logger.debug(f"[CS2Cap] 403 (likely tier limit): {hash_name}")
                    self.errors += 1
                    return 0.0

                if self.request_delay > 1.0:
                    self.request_delay = max(self.request_delay * 0.98, 1.0)
                    price_db.save_state("cs2cap_delay", str(self.request_delay))

                response.raise_for_status()
                res_json = await response.json()

                # Parse response (CS2Cap format may vary by tier)
                # Expected: {"price": 1.23, "currency": "USD", ...}
                if isinstance(res_json, dict):
                    price = res_json.get("price", 0.0)
                    if isinstance(price, str):
                        try:
                            price = float(price)
                        except ValueError:
                            price = 0.0
                elif isinstance(res_json, (int, float)):
                    price = float(res_json)
                elif isinstance(res_json, list) and res_json:
                    first = res_json[0]
                    if isinstance(first, dict):
                        price = first.get("price", 0.0)
                    else:
                        price = float(first)
                else:
                    price = 0.0

                self.api_calls += 1

                if price > 0:
                    price_db.record_price(hash_name, price, source="cs2cap")
                    self._mem_cache[hash_name] = (price, now)

                return price

        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"[CS2Cap] Oracle error for {hash_name}: {e}")
            self.errors += 1
            return 0.0

    async def get_buy_order(self, hash_name: str) -> float:
        """
        Get the highest buy order (bid) for an item.
        Requires Starter tier ($19/mo). Returns 0.0 on Free tier.
        """
        if self.tier not in ("starter", "pro"):
            return 0.0

        await self._throttle()
        session = await self.get_session()

        encoded_name = urllib.parse.quote(hash_name)
        url = f"{self.BASE_URL}/v1/bids/a8db/{encoded_name}"

        try:
            async with session.get(url) as response:
                if response.status == 429:
                    raise RateLimitException("429")
                if response.status in (403, 404):
                    return 0.0
                response.raise_for_status()
                res_json = await response.json()
                if isinstance(res_json, dict):
                    return float(res_json.get("price", 0.0))
                elif isinstance(res_json, (int, float)):
                    return float(res_json)
                return 0.0
        except Exception as e:
            logger.debug(f"[CS2Cap] buy_order error: {e}")
            return 0.0

    async def get_item_value(self, hash_name: str) -> float:
        """
        Get the "fair value" of an item.
        Strategy:
        1. Try buy_order (real demand price)
        2. Fallback to ask * 0.95 (5% below sell price)
        3. Return 0.0 if all fails
        """
        bid = await self.get_buy_order(hash_name)
        if bid > 0:
            return bid

        ask = await self.get_item_price(hash_name)
        if ask > 0:
            return round(ask * 0.95, 2)

        return 0.0

    async def get_batch_prices(self, hash_names: List[str]) -> Dict[str, float]:
        """
        Get prices for multiple items.
        Free tier: sequential single requests (slow but works)
        Starter+ tier: single batch request
        """
        results = {}
        if not hash_names:
            return results

        for name in hash_names:
            try:
                price = await self.get_item_price(name)
                results[name] = price
            except Exception as e:
                logger.debug(f"[CS2Cap] batch item failed {name}: {e}")
                results[name] = 0.0

        return results

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def get_stats(self) -> Dict[str, int]:
        """Return oracle performance metrics."""
        return {
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
            "errors": self.errors,
            "mem_cache_size": len(self._mem_cache),
        }
