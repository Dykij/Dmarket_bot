"""
Async DMarket Client (Pure Python Core).
Standardized according to SACS-2026.
Replaces legacy synchronous wrappers and Rust dependencies for pure Python operations.

Features:
- Asynchronous I/O via aiohttp
- High-performance JSON parsing (orjson/ujson)
- Ed25519 Request Signing (via src.dmarket.api.auth)
- Token Bucket Rate Limiting
- Keep-Alive Connection Pooling
"""

import asyncio
import logging
import time
import os
from typing import Any, Dict, Optional, Union, List

import aiohttp

# High-performance JSON handling
try:
    import orjson as json
except ImportError:
    try:
        import ujson as json
    except ImportError:
        import json

from src.dmarket.api.auth import generate_signature_ed25519

logger = logging.getLogger(__name__)

class AsyncDMarketClient:
    """
    Pure Python Async Client for DMarket API.
    Optimized for high-frequency trading without native Rust dependencies.
    """

    BASE_URL = "https://api.dmarket.com"

    def __init__(
        self, 
        public_key: str, 
        secret_key: str, 
        limit_per_second: int = 5,
        aiohttp_connector: Optional[aiohttp.TCPConnector] = None
    ):
        self.public_key = public_key
        self.secret_key = secret_key
        
        # Concurrency & Rate Limiting
        self._rate_limit = limit_per_second
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        
        # Networking
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector = aiohttp_connector

    async def __aenter__(self) -> "AsyncDMarketClient":
        """Initialize the session with optimal TCP settings."""
        if not self._session:
            if not self._connector:
                # Optimized TCP settings for HFT
                self._connector = aiohttp.TCPConnector(
                    limit=100,              # Max concurrent connections
                    ttl_dns_cache=300,      # Cache DNS for 5 minutes
                    keepalive_timeout=60,   # Keep connections open
                    enable_cleanup_closed=True
                )
            
            # Use optimized JSON serializer if available
            json_serialize = lambda x: json.dumps(x).decode('utf-8') if hasattr(json, 'dumps') and 'orjson' in json.__name__ else json.dumps

            self._session = aiohttp.ClientSession(
                base_url=self.BASE_URL,
                connector=self._connector,
                json_serialize=json_serialize
            )
            logger.info(f"AsyncDMarketClient initialized (JSON: {json.__name__})")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Graceful shutdown."""
        if self._session:
            await self._session.close()
            logger.info("AsyncDMarketClient session closed")

    async def _throttle(self) -> None:
        """
        Simple Token Bucket implementation for rate limiting.
        Ensures we don't exceed the defined RPS.
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            wait_time = (1.0 / self._rate_limit) - elapsed
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()

    async def request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        body: Any = None,
        sign: bool = True
    ) -> Union[Dict, List, str]:
        """
        Execute an HTTP request with automatic signing and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API Endpoint (e.g. "/account/v1/balance")
            params: Query parameters
            body: Request body (will be serialized to JSON)
            sign: Whether to sign the request (Ed25519)
        """
        if not self._session:
            await self.__aenter__()

        await self._throttle()

        # Prepare payload for signing
        json_body = ""
        if body is not None:
            if 'orjson' in json.__name__:
                json_body = json.dumps(body).decode('utf-8')
            else:
                json_body = json.dumps(body)

        headers = {}
        
        # Construct full path with query params for signing
        full_path = endpoint
        if params:
            # Sort params to ensure consistent signature if needed (though DMarket usually takes raw query string)
            # A simple urlencode is safer.
            from urllib.parse import urlencode
            query_string = urlencode(params)
            full_path = f"{endpoint}?{query_string}"

        if sign:
            # Generate Ed25519 signature
            headers = generate_signature_ed25519(
                self.public_key, 
                self.secret_key, 
                method, 
                full_path, 
                json_body
            )

        try:
            # aiohttp handles params encoding
            # We must be careful: if we sign full_path, we must request full_path.
            # aiohttp with params argument appends them.
            # So if we pass params to aiohttp, the URL becomes endpoint?params... which matches full_path.
            # But let's verify aiohttp encoding matches urllib.
            
            async with self._session.request(
                method, 
                endpoint, 
                params=params, 
                data=json_body if body is not None else None,
                headers=headers
            ) as resp:
                
                # Handling Rate Limits (429)
                if resp.status == 429:
                    logger.warning(f"Rate limit hit on {endpoint}. Backing off 2s...")
                    await asyncio.sleep(2.0)
                    return await self.request(method, endpoint, params, body, sign)

                response_text = await resp.text()
                
                if resp.status >= 400:
                    logger.error(f"API Error {resp.status}: {response_text}")
                    raise aiohttp.ClientResponseError(
                        resp.request_info, 
                        resp.history, 
                        status=resp.status, 
                        message=response_text
                    )

                try:
                    return json.loads(response_text)
                except Exception:
                    return response_text

        except Exception as e:
            logger.error(f"Request failed [{method} {endpoint}]: {str(e)}")
            raise

    # --- Convenience Methods ---

    async def get_balance(self) -> Dict:
        """Fetch user balance."""
        return await self.request("GET", "/account/v1/balance")

    async def get_market_items(self, game: str = "a8db", limit: int = 100, title: str = "") -> Dict:
        """Fetch market items (public endpoint, often no auth needed, but we sign anyway)."""
        params = {
            "gameId": game,
            "limit": limit,
            "title": title,
            "currency": "USD"
        }
        return await self.request("GET", "/exchange/v1/market/items", params=params)

    async def get_user_inventory(self, game: str = "a8db") -> Dict:
        """Fetch user inventory."""
        params = {
            "gameId": game,
            "limit": 100,
            "currency": "USD"
        }
        return await self.request("GET", "/exchange/v1/user/items", params=params)

    # --- Target (Buy Order) Methods ---

    async def create_target(self, game: str, targets: List[Dict]) -> Dict:
        """
        Create buy targets (bids).
        
        Args:
            game: Game ID (e.g. 'a8db')
            targets: List of dicts like:
                {
                    "Amount": 1,
                    "Price": {"Amount": 1200, "Currency": "USD"},
                    "Title": "AK-47 | Redline (Field-Tested)"
                }
        """
        body = {
            "GameID": game,
            "Targets": targets
        }
        return await self.request("POST", "/marketplace-api/v1/user-targets/create", body=body)

    async def get_user_targets(
        self, 
        game: str = "a8db", 
        limit: str = "100", 
        status: str = "TargetStatusActive",
        cursor: str = ""
    ) -> Dict:
        """Fetch active user targets."""
        params = {
            "GameID": game,
            "Limit": limit,
            "BasicFilters.Status": status,
            "Cursor": cursor
        }
        return await self.request("GET", "/marketplace-api/v1/user-targets", params=params)

    async def delete_target(self, target_ids: List[Dict]) -> Dict:
        """
        Delete targets.
        
        Args:
            target_ids: List of dicts [{"TargetID": "..."}]
        """
        body = {
            "Targets": target_ids
        }
        return await self.request("POST", "/marketplace-api/v1/user-targets/delete", body=body)

    # --- Market Analysis Methods ---

    async def get_aggregated_prices(self, names: List[str], game: str = "a8db") -> Dict:
        """
        Get Best Bid and Best Ask for a list of items.
        Crucial for Spread Trading.
        """
        body = {
            "filter": {
                "game": game,
                "titles": names
            },
            "limit": "100"
        }
        return await self.request("POST", "/marketplace-api/v1/aggregated-prices", body=body)
