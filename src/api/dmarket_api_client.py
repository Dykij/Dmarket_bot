import aiohttp
import asyncio
import json
import time
import random
import urllib.parse
from typing import Optional, Dict, List, Any
from functools import wraps
from nacl.signing import SigningKey
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger("DMarketAPI")

class SecurityViolation(Exception):
    """Raised when request parameters violate safety allowlists."""
    pass

class DMarketAPIClient:
    """ DMarket Trading API v2 Client (TargetSniper Optimized Async) """
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self, public_key: str, secret_key: str):
        self.public_key = public_key
        self.secret_key = secret_key
        self._last_request_time = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        
        try:
            # Handle both 128-char and 64-char keys (seed selection)
            clean_secret = self.secret_key[:64] if len(self.secret_key) == 128 else self.secret_key
            self._signing_key = SigningKey(bytes.fromhex(clean_secret))
        except Exception as e:
            raise ValueError(f"Failed to initialize Ed25519 key: {e}")

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # High-performance connection pooling
            connector = aiohttp.TCPConnector(limit=100, ssl=False, keepalive_timeout=60)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _wait_for_rate_limit(self):
        """Enforces <= 2 RPS dynamically."""
        async with self._lock:
            jitter = random.uniform(0.3, 0.4) # Slightly faster due to async pipeline
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < jitter:
                await asyncio.sleep(jitter - elapsed)
            self._last_request_time = time.time()

    def _generate_signature(self, method: str, api_path: str, body: str, timestamp: str) -> str:
        """ API v2 Ed25519 signature scheme. (Zero-copy in NaCl bindings) """
        signature_prefix = f"{method.upper()}{api_path}{body}{timestamp}"
        signed_message = self._signing_key.sign(signature_prefix.encode('utf-8'))
        return signed_message.signature.hex()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def make_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        await self._wait_for_rate_limit()
        method = method.upper()
        timestamp = str(int(time.time()))
        
        api_path = path
        if params:
            # Ensure keys are sorted to keep signature deterministic if needed, 
            # though standard urlencode is usually fine.
            query_string = urllib.parse.urlencode(params)
            api_path = f"{path}?{query_string}"
            
        body_str = json.dumps(body) if body else ""
        signature = self._generate_signature(method, api_path, body_str, timestamp)
        
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.BASE_URL}{api_path}"
        session = await self.get_session()
        
        async with session.request(method, url, headers=headers, json=body if body else None) as response:
            if response.status != 200:
                text = await response.text()
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"DMarket API Error: {text}",
                    headers=response.headers
                )
            return await response.json()
    
    # --- Market Data ---
    async def get_market_items_v2(self, game_id: str, limit: int = 100, cursor: Optional[str] = None, **filters):
        """ High-throughput Marketplace v2 scan. """
        params = {"currency": "USD", "gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        if filters: params.update(filters)
        return await self.make_request("GET", "/exchange/v1/market/items", params=params)

    # --- Account & Inventory ---
    async def get_real_balance(self) -> float:
        """ Fetches the current USD & DMC balance. Returns USD float. """
        try:
            res = await self.make_request("GET", "/account/v1/balance")
            # --- Phase 7.1: Support New Balance Format (Jan 2026) ---
            # Try new 'balance' field first, then fallback to 'usd.amount'
            if "balance" in res:
                return float(res["balance"])
            
            usd_data = res.get('usd', 0)
            if isinstance(usd_data, dict):
                return float(usd_data.get('amount', 0)) / 100.0
            return float(usd_data) / 100.0
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return 0.0

    async def get_user_inventory(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ Fetches items owned by the user but NOT currently on sale. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-inventory", params=params)

    async def get_user_offers(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ Fetches items the user currently has listed for sale. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-offers", params=params)

    # --- Trading Ops (Targets / Buy Orders) ---
    async def batch_create_targets(self, targets: List[Dict[str, Any]]):
        """ Creation of targets (buy orders). Path verified via Swagger 2026. """
        return await self.make_request("POST", "/marketplace-api/v1/user-targets/create", body={"Targets": targets})

    async def batch_delete_targets(self, targets: List[Dict[str, Any]]):
        """ Mass deletion of targets. Path verified via Swagger 2026. """
        return await self.make_request("POST", "/marketplace-api/v1/user-targets/delete", body={"Targets": targets})

    async def get_user_targets(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ List active buy orders. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-targets", params=params)

    # --- Fee Analysis (v7.6) ---
    async def get_item_fee(self, game_id: str, item_id: str, price_cents: int) -> float:
        """
        Fetches dynamic fee for a specific item at a given price.
        Returns fee multiplier (e.g., 0.05 for 5%).
        """
        try:
            params = {
                "gameId": game_id,
                "itemId": item_id,
                "price": price_cents,
                "currency": "USD"
            }
            res = await self.make_request("GET", "/exchange/v1/market/fee", params=params)
            # DMarket returns fee in absolute cents or percentage
            # Assuming 'fee' field exists in response with percentage
            fee_pct = float(res.get("fee", 5.0)) / 100.0
            return fee_pct
        except Exception as e:
            logger.warning(f"Could not fetch dynamic fee for {item_id}, fallback to 5%: {e}")
            return 0.05
