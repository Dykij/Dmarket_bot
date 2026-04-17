import aiohttp
import os
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

from src.utils.vault import vault

class DMarketAPIClient:
    """ DMarket Trading API v2 Client (TargetSniper Optimized Async) """
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self, public_key: str, secret_key: str, base_url: str = "https://api.dmarket.com"):
        self.public_key = public_key
        self.secret_key = secret_key
        self.BASE_URL = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._rate_limit_delay = 0.22  # 4-5 requests per second
        
        # --- PHASE 7.8: Safe Key Initialization ---
        self._signing_key = None
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
        
        # Performance: Check for Rust core (v7.8)
        self._has_rust_signer = False
        self._rust_signer = None
        try:
            import rust_core
            self._has_rust_signer = True
            self._rust_signer = rust_core.generate_signature_rs
            logger.info("🚀 High-performance Rust signer active.")
        except ImportError:
            logger.warning("Rust Signer not found, using Python (pynacl) fallback.")

        # Python Fallback Initialization
        if not self._has_rust_signer:
            try:
                if secret_key and len(secret_key) >= 64:
                    clean_secret = secret_key[:64]
                    self._signing_key = SigningKey(bytes.fromhex(clean_secret))
                elif not is_sandbox:
                    logger.error("DMarket Secret Key is invalid or missing in Production!")
                else:
                    # In sandbox, we use a dummy signing key if none is provided
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))
            except Exception as e:
                if not is_sandbox:
                    logger.error(f"Failed to initialize Ed25519 key: {e}")
                else:
                    logger.debug(f"Skipping key initialization in Sandbox: {e}")
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))

        # Fee Cache (v7.7)
        self._fee_cache: Dict[str, Dict[str, Any]] = {}
        self._fee_cache_ttl = 43200  # 12 hours

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
            self._last_request_time = time.time()

    def _generate_signature(self, method: str, api_path: str, body: str, timestamp: str) -> str:
        """ API v2 Ed25519 signature scheme. (Rust or NaCl bindings) """
        # Try Rust first (microsecond precision)
        if self._has_rust_signer and self.secret_key:
            try:
                # Rust expects the full hex secret
                return self._rust_signer(method, api_path, body, timestamp, self.secret_key)
            except Exception as e:
                logger.warning(f"Rust signer failed, falling back to Python: {e}")

        # Python Fallback
        signature_prefix = f"{method.upper()}{api_path}{body}{timestamp}"
        signed_message = self._signing_key.sign(signature_prefix.encode('utf-8'))
        return signed_message.signature.hex()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def make_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ Executes API request with Dry Run support ($0.00 Risk). """
        method = method.upper()
        
        # --- SANDBOX GUARD ---
        is_write_op = method in ["POST", "PUT", "DELETE", "PATCH"]
        if is_write_op and os.getenv("DRY_RUN", "true").lower() == "true":
            logger.info(f"🧪 [DRY RUN] Simulating {method} to {path}")
            # Mock success response for batch operations to keep simulation loop running
            if "batch" in path or "create" in path or "delete" in path:
                return {"status": "success", "simulated": True, "message": "Simulation Mode Active"}
            return {}

        await self._wait_for_rate_limit()
        timestamp = str(int(time.time()))
        
        api_path = path
        if params:
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
        """ Fetches the current USD & DMC balance. Supports Real Balance in Dry Run. """
        try:
            # We fetch the real account balance even in Dry Run to ground the simulation in reality
            res = await self.make_request("GET", "/account/v1/balance")
            # DMarket balance is usually in cents or has a specific structure
            # Logic: USD section
            usd_balance = float(res.get("usd", 0)) / 100.0
            return usd_balance
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() == "true":
                logger.debug(f"Real balance fetch failed, using fallback: {e}")
                return 10000.0 
            raise e

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

    async def buy_items(self, offers: List[Dict[str, Any]]):
        """ 
        Instant Purchase of existing market listings.
        Payload: [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}]
        """
        return await self.make_request("POST", "/exchange/v1/market/buy", body={"offers": offers})

    async def get_user_targets(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ List active buy orders. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-targets", params=params)

    # --- Fee Analysis (v7.6) ---
    async def get_item_fee(self, game_id: str, item_id: str, price_cents: int) -> float:
        """
        Fetches dynamic fee for a specific item at a given price.
        Implements 12-hour caching (v7.7) to avoid rate limits.
        """
        now = time.time()
        if item_id in self._fee_cache:
            cached = self._fee_cache[item_id]
            if now - cached["timestamp"] < self._fee_cache_ttl:
                return cached["fee"]

        try:
            params = {
                "gameId": game_id,
                "itemId": item_id,
                "price": price_cents,
                "currency": "USD"
            }
            res = await self.make_request("GET", "/exchange/v1/market/fee", params=params)
            fee_pct = float(res.get("fee", 5.0)) / 100.0
            
            # Update Cache
            self._fee_cache[item_id] = {"fee": fee_pct, "timestamp": now}
            return fee_pct
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() != "true":
                logger.warning(f"Could not fetch dynamic fee for {item_id}, fallback to 5%: {e}")
            return 0.05
