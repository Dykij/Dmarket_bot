import aiohttp
import asyncio
import logging
from typing import Optional
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

    async def get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Fetches the index/market price for Rust items.
        Supports offset-based pagination (v7.7).
        """
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            return cached

        session = await self.get_session()
        try:
            # Note: Pagination in SCMM is often handled via listing query params
            url = f"{self.BASE_URL}/stats/item/{hash_name}?offset={offset}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # SCMM price is often in USD directly or object
                    price = data.get("price", {}).get("median", 0) / 100.0 if "median" in data.get("price", {}) else data.get("value", 0) / 100.0
                    
                    if price > 0:
                        price_db.record_price(hash_name, price, source="scmm")
                        return price
        except Exception as e:
            logger.error(f"SCMM fetch failed for {hash_name}: {e}")

        return 0.0

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
