"""
DMarket API Client (Clean Architecture Implementation).
Follows Google Cloud Application Development guidelines for robustness and structure.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import os
from typing import Any, Dict, List, Optional
import httpx

# Dependencies
try:
    import nacl.signing
    from nacl.encoding import HexEncoder
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

# Core Config (One-way dependency)
from src.core.config import CONFIG

logger = logging.getLogger("api.dmarket")

class DMarketAPI:
    """
    Robust DMarket API Client.
    Handles authentication, rate limiting, and multi-game switching.
    """

    BASE_URL = "https://api.dmarket.com"

    def __init__(self, public_key: str, secret_key: str, rate_limit: float = 0.2):
        """
        Initialize the client.
        
        Args:
            public_key: API Public Key
            secret_key: API Secret Key
            rate_limit: Minimum seconds between requests (basic throttling)
        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.rate_limit = rate_limit
        self.last_request_time = 0.0
        
        # Initialize HTTP client with timeouts
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "OpenClaw-TradingBot/2.0",
                "Accept": "application/json"
            }
        )

    def _generate_signature(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Generates DMarket API Signature (Ed25519 or HMAC-SHA256).
        """
        timestamp = str(int(time.time()))
        string_to_sign = f"{method}{path}{body}{timestamp}"
        
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "Content-Type": "application/json"
        }

        # Try Ed25519 first (Preferred by DMarket)
        if HAS_NACL and len(self.secret_key) == 128: # Hex representation of 64 bytes
            try:
                signing_key = nacl.signing.SigningKey(bytes.fromhex(self.secret_key))
                signed = signing_key.sign(string_to_sign.encode('utf-8'))
                signature = signed.signature.hex()
                headers["X-Request-Sign"] = f"dmar ed25519 {signature}"
                return headers
            except Exception as e:
                logger.warning(f"Ed25519 signing failed, falling back to HMAC: {e}")

        # Fallback to HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        headers["X-Request-Sign"] = signature
        return headers

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute request with Retry logic (Exponential Backoff).
        """
        # Rate Limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        
        url = f"{self.BASE_URL}{endpoint}"
        body_str = json.dumps(data) if data else ""
        
        # Build path for signature (must include query params)
        path_for_sign = endpoint
        if params:
            # Sort params strictly for signature consistency if required (though DMarket signs path+body usually)
            # DMarket typically doesn't require params in signature for GET, but let's follow protocol if needed.
            # Official doc: method + api_path_value + body + timestamp
            pass 

        for attempt in range(retries):
            try:
                headers = self._generate_signature(method, path_for_sign, body_str)
                
                response = await self.client.request(
                    method, 
                    url, 
                    params=params, 
                    content=body_str, 
                    headers=headers
                )
                
                self.last_request_time = time.time()

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit. Sleeping... (Attempt {attempt+1}/{retries})")
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
                else:
                    logger.error(f"API Error {response.status_code}: {response.text}")
                    # Don't retry on client errors (400-403) unless it's strictly network
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        return {"objects": []} # Return empty to avoid crash
            
            except httpx.RequestError as e:
                logger.error(f"Network error: {e}")
                await asyncio.sleep(1)
        
        return {"objects": []} # Fallback

    async def get_market_items(
        self,
        game: str,
        limit: int = 50,
        price_from: float = 0.0,
        price_to: float = 0.0,
        currency: str = "USD",
        sort: str = "price"
    ) -> Dict[str, Any]:
        """
        Fetch items for a specific game using GAME_CONFIG.
        """
        game_config = CONFIG.GAMES.get(game)
        if not game_config:
            logger.error(f"Game '{game}' not found in CONFIG.")
            return {"objects": []}

        params = {
            "gameId": game_config.dmarket_id,
            "limit": limit,
            "currency": currency,
            "orderBy": sort,
            "priceFrom": int(price_from * 100), # Convert to cents
            "priceTo": int(price_to * 100)
        }
        
        return await self._request("GET", "/exchange/v1/market/items", params=params)

    async def close(self):
        await self.client.aclose()

# --- Consilium Test Runner ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Configure Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def test_multigame():
        pub = os.getenv("DMARKET_PUBLIC_KEY")
        sec = os.getenv("DMARKET_SECRET_KEY")
        
        if not pub or not sec:
            print("❌ Keys missing.")
            return

        api = DMarketAPI(pub, sec)
        print("🤖 DMarketAPI Initialized. Starting Multigame Test...\n")

        games = ["csgo", "dota2", "rust", "tf2"]
        
        for game in games:
            print(f"📡 Requesting {game.upper()}...")
            data = await api.get_market_items(game, limit=5, price_from=1.0, price_to=10.0)
            items = data.get("objects", [])
            
            if items:
                first = items[0]
                price = float(first['price']['USD']) / 100
                print(f"✅ {game.upper()}: Success! Found {len(items)} items.")
                print(f"   Sample: {first['title']} (${price})")
            else:
                print(f"⚠️ {game.upper()}: No items returned (or error).")
            
            print("-" * 30)
        
        await api.close()

    asyncio.run(test_multigame())
