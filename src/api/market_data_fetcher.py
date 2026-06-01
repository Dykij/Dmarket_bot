import aiohttp
import asyncio
import urllib.parse
from typing import Dict, Any, Tuple, Optional

class LiveMarketDataFetcher:
    """
    Fetches live market data (Asks and Bids) from DMarket Public API.
    Strictly adheres to <= 2 RPS limit using aiohttp and asyncio.sleep.
    """
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self):
        self._last_request_time = 0.0
        self._min_request_interval = 0.51  # Strict <= 2 RPS (~0.5s spacing)
        self.session = None
        
        # Initialize Authentication for Private/Protected Endpoints
        from .dmarket_auth import DMarketAuth
        self.auth = DMarketAuth()

    async def _wait_for_rate_limit(self):
        """Enforces strictly <= 2 requests per second mapping without blocking the event loop."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _make_request(self, path: str, method: str = "GET", requires_auth: bool = False, auth_path: Optional[str] = None) -> Dict[str, Any]:
        """Generic async request wrapper."""
        await self._wait_for_rate_limit()
        
        url = f"{self.BASE_URL}{path}"
        headers = {}
        
        if requires_auth:
            # If an explicit auth_path is provided (usually un-encoded), use it for the signature
            sign_path = auth_path if auth_path else path
            auth_headers = self.auth.generate_headers(method, sign_path, "")
            headers.update(auth_headers)
        
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"[API Error] {response.status}: {await response.text()}")
            response.raise_for_status()
            return await response.json()

    async def get_best_ask(self, game_id: str, title: str) -> Optional[float]:
        """Fetches the lowest Sell Offer (Ask) for the item."""
        encoded_title = urllib.parse.quote(title)
        path = f"/exchange/v1/market/items?gameId={game_id}&title={encoded_title}&limit=10&currency=USD"
        
        data = await self._make_request(path)
        items = data.get("objects", [])
        
        if not items:
            return None
            
        prices = []
        for item in items:
            price = item.get("price", {}).get("USD")
            if price:
                prices.append(float(price) / 100.0)
                
        if prices:
            return min(prices)
        return None

    async def get_best_bid(self, game_id: str, title: str) -> Optional[float]:
        """Fetches the highest Buy Target (Bid) for the item."""
        encoded_title = urllib.parse.quote(title)
        path = f"/marketplace-api/v1/targets-by-title/{game_id}/{encoded_title}"
        raw_path = f"/marketplace-api/v1/targets-by-title/{game_id}/{title}"
        
        try:
            data = await self._make_request(path, method="GET", requires_auth=True, auth_path=raw_path)
            targets = data.get("targets", [])
            
            if not targets:
                return None
                
            prices = []
            for target in targets:
                price = target.get("price", {}).get("amount", 0)
                if price:
                    prices.append(float(price))
                    
            if prices:
                return max(prices)
            return None
        except Exception as e:
            print(f"[Warning] Could not fetch bids from {path}: {e}")
            return None

    async def get_order_book(self, game_id: str, title: str) -> Tuple[Optional[float], Optional[float]]:
        """Returns (best_bid, best_ask) for the item."""
        best_ask = await self.get_best_ask(game_id, title)
        best_bid = await self.get_best_bid(game_id, title)
        return best_bid, best_ask

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
