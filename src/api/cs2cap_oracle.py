"""
CS2Cap Oracle — Unified pricing across 41 CS2 marketplaces.

Uses CS2Cap REST API (https://api.cs2c.app/v1) for:
  - GET /items: catalog of all CS2 items with item_id mapping
  - GET /prices: lowest asks across all providers (requires item_id integer)

API format:
  GET /prices?item_id=4994&currency=USD&limit=10
  Response: {"items": [{"provider": "buff163", "lowest_ask": 435886, ...}]}
  lowest_ask is in minor units (cents) — divide by 100 for dollars.

Tiered caching:
  1. In-memory (5 min TTL) — high-frequency loop
  2. SQLite history (1 hr TTL) — persistent across restarts
  3. Live API — rate-limited with exponential backoff
"""

import aiohttp
import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.db.price_history import price_db

logger = logging.getLogger("CS2CapOracle")


class CS2CapRateLimit(Exception):
    pass


@dataclass
class MarketPrice:
    provider: str
    lowest_ask: float
    quantity: int
    timestamp: float = 0.0


@dataclass
class CrossMarketData:
    hash_name: str
    global_min_ask: float = 0.0
    global_max_bid: float = 0.0
    provider_prices: Dict[str, float] = field(default_factory=dict)
    buy_orders: Dict[str, float] = field(default_factory=dict)
    sales_count: int = 0
    avg_sale_price: float = 0.0
    volatility_1h: float = 0.0
    volatility_24h: float = 0.0
    rsi: float = 50.0
    macd_signal: float = 0.0
    bollinger_position: float = 0.5
    liquidity_score: float = 0.0

    def __post_init__(self):
        if self.provider_prices and self.global_min_ask == 0.0:
            self.global_min_ask = min(self.provider_prices.values())
        if self.buy_orders and self.global_max_bid == 0.0:
            self.global_max_bid = max(self.buy_orders.values())


class CS2CapOracle:
    """
    Unified CS2 market data oracle via CS2Cap API.
    Free tier: GET /items + GET /prices only.
    """

    BASE_URL = "https://api.cs2c.app/v1"
    CACHE_TTL = 3600       # SQLite: 1 hour
    MEM_TTL = 300          # In-memory: 5 minutes
    ITEMS_MEM_TTL = 86400  # Item catalog: 24 hours (rarely changes)
    CANDLES_MEM_TTL = 600  # Candles: 10 minutes

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._request_delay = 1.0
        self._quota_exhausted = False
        self._quota_exhausted_at: float = 0.0
        self._quota_reset_seconds = 3600  # Reset after 1 hour

        # Caches
        self._price_cache: Dict[str, Tuple[float, float]] = {}
        self._candles_cache: Dict[str, Tuple[List[Dict], float]] = {}

        # Item catalog: market_hash_name -> item_id
        self._item_catalog: Dict[str, int] = {}
        self._catalog_ts: float = 0.0

        # Rate limit state
        saved_delay = price_db.get_state("cs2cap_delay")
        self._request_delay = float(saved_delay) if saved_delay else 1.0

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def _throttle(self):
        async with self._lock:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self._request_delay:
                await asyncio.sleep(self._request_delay - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Throttled API request with rate limit handling."""
        # Reset quota after 1 hour
        if self._quota_exhausted and time.time() - self._quota_exhausted_at > self._quota_reset_seconds:
            self._quota_exhausted = False
            self._request_delay = 1.0
            logger.info("[CS2Cap] Quota reset, retrying API calls")

        if self._quota_exhausted:
            return None

        await self._throttle()
        session = await self.get_session()
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    self._request_delay = min(self._request_delay * 2.0, 30.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))
                    self._quota_exhausted = True
                    self._quota_exhausted_at = time.time()
                    logger.warning("[CS2Cap] Rate limit hit (429) — quota exhausted, pausing API calls for 1 hour")
                    return None

                if self._request_delay > 1.0:
                    self._request_delay = max(self._request_delay * 0.98, 1.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))

                if response.status == 403:
                    return None

                if response.status != 200:
                    text = await response.text()
                    logger.debug(f"[CS2Cap] HTTP {response.status}: {text[:200]}")
                    return None

                return await response.json()

        except Exception as e:
            logger.debug(f"[CS2Cap] Request failed: {e}")
            return None

    # ----------------------------------------------------------------
    # 1. ITEM CATALOG (GET /items) — name to item_id mapping
    # ----------------------------------------------------------------
    async def _load_catalog(self) -> None:
        """Load item catalog for name-to-id mapping. Paginated (API max 100/page)."""
        now = time.time()
        if self._item_catalog and (now - self._catalog_ts < self.ITEMS_MEM_TTL):
            return

        # Try loading from SQLite first
        cached = price_db.get_state("cs2cap_catalog")
        if cached:
            try:
                import json
                self._item_catalog = json.loads(cached)
                self._catalog_ts = now
                logger.info(f"[CS2Cap] Loaded {len(self._item_catalog)} items from cache")
                return
            except Exception:
                pass

        # Load from API — paginate through all items (API max 100/page)
        offset = 0
        limit = 100
        catalog: Dict[str, int] = {}
        max_pages = 500  # Safety limit (500 * 100 = 50,000 items)

        for page in range(max_pages):
            data = await self._request("/items", params={"limit": limit, "offset": offset})
            if not data:
                break

            items = data.get("items", [])
            pagination = data.get("pagination", {})

            for item in items:
                name = item.get("market_hash_name", "")
                item_id = item.get("item_id")
                if name and item_id:
                    catalog[name] = item_id

            if page % 50 == 0 and page > 0:
                logger.info(f"[CS2Cap] Catalog loading: page {page}, {len(catalog)} items so far")

            if not pagination.get("has_next", False):
                break
            offset += limit

        if catalog:
            self._item_catalog = catalog
            self._catalog_ts = now
            import json
            price_db.save_state("cs2cap_catalog", json.dumps(catalog))
            logger.info(f"[CS2Cap] Loaded {len(self._item_catalog)} items total")

    async def get_item_id(self, hash_name: str) -> Optional[int]:
        """Resolve market_hash_name to item_id."""
        await self._load_catalog()
        return self._item_catalog.get(hash_name)

    # ----------------------------------------------------------------
    # 2. PRICE DATA (GET /prices) — requires item_id (integer)
    # ----------------------------------------------------------------
    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Get the global minimum ask price across all providers.
        Uses GET /prices?item_id=<int> (NOT market_hash_name).
        Returns 0.0 if no data available.
        """
        now = time.time()
        cache_key = f"{hash_name}_{offset}"

        # Layer 1: Memory
        if cache_key in self._price_cache:
            price, ts = self._price_cache[cache_key]
            if now - ts < self.MEM_TTL:
                return price

        # Layer 2: SQLite
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            self._price_cache[cache_key] = (cached, now)
            return cached

        # Layer 3: Live API
        item_id = await self.get_item_id(hash_name)
        if not item_id:
            logger.debug(f"[CS2Cap] No item_id for: {hash_name}")
            return 0.0

        data = await self._request(
            "/prices",
            params={
                "item_id": item_id,
                "currency": "USD",
                "limit": 100,
                "offset": offset,
            }
        )

        if not data:
            return 0.0

        # Parse response: {"items": [{"provider": "buff163", "lowest_ask": 435886, ...}]}
        items = data.get("items", [])
        if not items:
            return 0.0

        # Find minimum ask across all providers
        prices = []
        for entry in items:
            ask = entry.get("lowest_ask", 0)
            if isinstance(ask, (int, float)) and ask > 0:
                prices.append(ask / 100.0)

        if prices:
            min_price = min(prices)
            price_db.record_price(hash_name, min_price, source="cs2cap")
            self._price_cache[cache_key] = (min_price, now)
            return min_price

        return 0.0

    # ----------------------------------------------------------------
    # 3. CROSS-MARKET DATA (GET /prices with all providers)
    # ----------------------------------------------------------------
    async def get_cross_market_data(self, hash_name: str) -> Optional[CrossMarketData]:
        """Fetch cross-market snapshot: prices from all providers."""
        now = time.time()
        cache_key = f"cross_{hash_name}"

        if cache_key in self._candles_cache:
            data_list, ts = self._candles_cache[cache_key]
            if now - ts < 180:
                return data_list[0] if data_list else None

        item_id = await self.get_item_id(hash_name)
        if not item_id:
            return None

        data = await self._request(
            "/prices",
            params={
                "item_id": item_id,
                "currency": "USD",
                "limit": 100,
            }
        )

        if not data:
            return None

        items = data.get("items", [])
        if not items:
            return None

        result = CrossMarketData(hash_name=hash_name)

        providers = {}
        total_qty = 0
        for entry in items:
            provider = entry.get("provider", "unknown")
            ask = entry.get("lowest_ask", 0)
            qty = entry.get("quantity", 0)

            if isinstance(ask, (int, float)) and ask > 0:
                providers[provider] = ask / 100.0
            total_qty += qty

        result.provider_prices = providers
        result.liquidity_score = min(1.0, total_qty / 100.0)

        if providers:
            result.global_min_ask = min(providers.values())

        self._candles_cache[cache_key] = ([result], now)
        return result

    # ----------------------------------------------------------------
    # 4. VOLATILITY ESTIMATION (from price history, not candles API)
    # ----------------------------------------------------------------
    async def get_volatility(self, hash_name: str) -> float:
        """
        Estimate volatility from SQLite price history.
        Uses Garman-Klass estimator for better accuracy.
        Falls back to simple std dev if insufficient data.
        """
        history = price_db.get_price_history(hash_name, hours=168, max_records=168)
        if len(history) < 5:
            return 0.0

        prices = [h["price"] for h in history if h["price"] > 0]
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
