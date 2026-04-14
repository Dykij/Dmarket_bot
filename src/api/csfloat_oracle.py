import aiohttp
import asyncio
import logging
import time
import urllib.parse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.db.price_history import price_db

logger = logging.getLogger("CSFloatOracle")

class RateLimitException(Exception):
    pass

class CSFloatOracle:
    """
    External Pricing Oracle.
    Uses SQLite PriceHistoryDB for persistent caching and trend analysis.
    """
    BASE_URL = "https://csfloat.com/api/v1"
    CACHE_TTL = 10800  # 3 hours

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self.request_delay = 1.0  # Strict 1 second minimum delay

    async def get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": self.api_key} if self.api_key else {}
            )
        return self._session

    async def _throttle(self):
        """Exponential Backoff / Throttling Mechanism."""
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
    async def get_item_price(self, hash_name: str) -> float:
        """
        Retrieves the lowest listed price for an item on CSFloat.
        First checks SQLite cache; only hits the API if the cached price is stale.
        Every observation is persisted to the price_history table for trend analysis.
        """
        # --- SQLite Cache Check ---
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            return cached

        # --- Live API fetch ---
        await self._throttle()
        session = await self.get_session()
        
        encoded_name = urllib.parse.quote(hash_name)
        url = f"{self.BASE_URL}/listings?market_hash_name={encoded_name}&sort_by=lowest_price&type=buy_now&limit=1"
        
        async with session.get(url) as response:
            if response.status == 429:
                logger.warning(f"[CSFloat] Rate Limited (429)! Backing off...")
                self.request_delay = min(self.request_delay * 1.5, 10.0) 
                raise RateLimitException("429 Too Many Requests")
            
            response.raise_for_status()
            res_json = await response.json()
            
            data = res_json.get('data', [])
            if data and isinstance(data, list) and len(data) > 0:
                listed_price = data[0].get('price', 0) / 100.0

                ref = data[0].get('reference', {})
                predicted = ref.get('predicted_price', 0) / 100.0
                
                final_price = listed_price if listed_price > 0 else predicted

                # --- Persist to SQLite ---
                price_db.record_price(hash_name, final_price, source="csfloat")
                return final_price
            
            price_db.record_price(hash_name, 0.0, source="csfloat")
            return 0.0

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
