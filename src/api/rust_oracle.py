import aiohttp
import asyncio
import logging
import time
from src.db.price_history import price_db

logger = logging.getLogger("RustOracle")

class RustOracle:
    """
    Rust Pricing Oracle using SCMM (rust.scmm.app).
    """
    BASE_URL = "https://rust.scmm.app/api"
    CACHE_TTL = 21600  # 6 hours for Rust as it's less volatile than CS2

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = None
        self._lock = asyncio.Lock()
        self._request_delay = 1.0
        self._last_request_time = 0.0

    async def get_session(self):
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session is not None and not self._session.closed:
                return self._session
            self._session = aiohttp.ClientSession()
            return self._session

    async def _throttle(self):
        async with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._request_delay:
                await asyncio.sleep(self._request_delay - elapsed)
            self._last_request_time = time.time()

    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Fetches the index/market price for Rust items.
        Supports offset-based pagination (v7.7).
        """
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            return cached

        await self._throttle()
        session = await self.get_session()
        try:
            url = f"{self.BASE_URL}/stats/item/{hash_name}?offset={offset}"
            async with session.get(url) as response:
                if response.status == 429:
                    self._request_delay = min(self._request_delay * 2.0, 30.0)
                    logger.warning(f"[SCMM] Rate limited, delay now {self._request_delay:.1f}s")
                    return 0.0
                if response.status != 200:
                    logger.debug(f"[SCMM] HTTP {response.status} for {hash_name}")
                    return 0.0
                data = await response.json()
                price = data.get("price", {}).get("median", 0) / 100.0 if isinstance(data.get("price"), dict) and "median" in data["price"] else data.get("value", 0) / 100.0

                if price > 0:
                    price_db.record_price(hash_name, price, source="scmm")
                    self._request_delay = max(self._request_delay * 0.98, 1.0)
                    return price

                self._request_delay = max(self._request_delay * 0.98, 1.0)
        except Exception as e:
            logger.error(f"SCMM fetch failed for {hash_name}: {e}", exc_info=True)

        return 0.0

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
