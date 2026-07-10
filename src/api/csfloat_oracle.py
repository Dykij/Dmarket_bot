import asyncio
import logging
import time
import urllib.parse
from typing import Any

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.db.price_history import price_db

logger = logging.getLogger("CSFloatOracle")

from src.api.exceptions import RateLimitException


class CSFloatOracle:
    """
    External Pricing Oracle.
    Uses SQLite PriceHistoryDB for persistent caching and trend analysis.
    """
    BASE_URL = "https://csfloat.com/api/v1"
    CACHE_TTL = 10800  # 3 hours (SQLite)
    MEM_TTL = 900      # 15 minutes (In-Memory)

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = None
        self._lock = asyncio.Lock()
        
        # --- Engine v8.0 Persistent Throttling (State DB) ---
        saved_delay = price_db.get_state("csfloat_delay")
        self.request_delay = float(saved_delay) if saved_delay else 1.0
        self._last_request_time = 0.0
        
        # --- In-Memory Quick Cache (High-frequency layer) ---
        self._mem_cache: dict[str, tuple[float, float]] = {}  # {hash_name: (price, timestamp)}

    async def get_session(self):
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session is not None and not self._session.closed:
                return self._session
            headers = {
                "User-Agent": "DMarketBot/15.0",
                "Accept": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
            return self._session

    async def _throttle(self):
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.request_delay:
                await asyncio.sleep(self.request_delay - elapsed)
            self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type(RateLimitException),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60)
    )
    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Retrieves price with Layered Architecture (v8.0 Optimized):
        1. Memory   (Instant)
        2. State DB (Fast - persistent state) -> Wait, price history is in History DB now.
        3. History DB (Analytical)
        4. Live API (Throttled)
        """
        now = time.time()
        
        # --- 1. Memory Layer ---
        cache_key = f"{hash_name}_{offset}"
        if cache_key in self._mem_cache:
            m_price, m_time = self._mem_cache[cache_key]
            if now - m_time < self.MEM_TTL:
                return m_price

        # --- 2. History DB Layer (Bifurcated SQLite) ---
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            self._mem_cache[cache_key] = (cached, now)
            return cached

        # --- 3. Live API Layer ---
        await self._throttle()
        session = await self.get_session()
        
        encoded_name = urllib.parse.quote(hash_name)
        url = f"{self.BASE_URL}/listings?market_hash_name={encoded_name}&sort_by=lowest_price&type=buy_now&limit=1&offset={offset}"
        
        try:
            async with session.get(url) as response:
                if response.status == 429:
                    logger.warning("[CSFloat] 429 Rate Limit! Penalizing delay in State DB.")
                    self.request_delay = min(self.request_delay * 2.0, 20.0) 
                    price_db.save_state("csfloat_delay", str(self.request_delay))
                    raise RateLimitException("429 Too Many Requests")
                
                if self.request_delay > 1.0:
                    self.request_delay = max(self.request_delay * 0.98, 1.0)
                    price_db.save_state("csfloat_delay", str(self.request_delay))

                if response.status == 404:
                    logger.debug(f"[CSFloat] No listing for {hash_name}")
                    return 0.0
                response.raise_for_status()
                res_json = await response.json()
                
                data = res_json.get('data', [])
                if data and len(data) > 0:
                    listed_price = data[0].get('price', 0) / 100.0
                    ref = data[0].get('reference', {})
                    predicted = ref.get('predicted_price', 0) / 100.0
                    final_price = listed_price if listed_price > 0 else predicted

                    # Sync All Layers
                    price_db.record_price(hash_name, final_price, source="csfloat")
                    self._mem_cache[cache_key] = (final_price, now)
                    return final_price
                
                return 0.0

        except RateLimitException:
            raise
        except Exception as e:
            logger.error(f"[CSFloat] Oracle Error: {e}", exc_info=True)
            return 0.0

    async def get_sales_history(
        self, hash_name: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Fetch recent sales from CSFloat.
        Returns list of {"price": float, "date": str, "float_value": float}.
        """
        await self._throttle()
        session = await self.get_session()

        encoded_name = urllib.parse.quote(hash_name)
        url = f"{self.BASE_URL}/history?market_hash_name={encoded_name}&limit={limit}"

        try:
            async with session.get(url) as response:
                if response.status == 429:
                    logger.warning("[CSFloat] 429 on sales history")
                    return []
                if response.status != 200:
                    return []

                data = await response.json()
                sales = []
                for entry in data.get("data", []):
                    price_cents = entry.get("price", 0)
                    float_val = entry.get("float_value", 0)
                    sold_at = entry.get("sold_at", "")
                    if price_cents > 0:
                        sales.append({
                            "price": price_cents / 100.0,
                            "float_value": float_val,
                            "date": sold_at,
                        })
                return sales

        except Exception as e:
            logger.debug(f"[CSFloat] Sales history error for {hash_name}: {e}")
            return []

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
