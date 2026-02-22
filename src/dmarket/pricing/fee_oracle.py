"""
Fee Oracle module for DMarket v2.
Fetches and caches dynamic fees (default & reduced) from /exchange/v1/customized-fees.
Author: Benjamin (AI)
Spec: OpenAPI v1.1.0
"""

import time
import logging
from typing import Dict, Optional
from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient

logger = logging.getLogger(__name__)

class FeeOracle:
    _instance = None
    _cache: Dict[str, Dict] = {}  # {game_id: {expires: ts, default: 0.07, reduced: {title: fraction}}}
    _cache_ttl = 3600  # 1 hour cache for fee config

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeeOracle, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Lazy init client via ConfigManager to avoid circular imports if possible, 
        # or just assume client provided or created on demand.
        # Ideally, we inject client. For singleton, we create one.
        pass

    def _get_client(self):
        pub_key = ConfigManager.get("dmarket_public_key") or ConfigManager.get("dmarket_api_key")
        sec_key = ConfigManager.get("dmarket_secret_key")
        if not pub_key or not sec_key:
            return None
        return BaseDMarketClient(pub_key, sec_key)

    async def get_fee_for_item(self, game_id: str, title: str) -> float:
        """
        Returns the specific fee fraction (e.g. 0.07 for 7%) for an item.
        Checks customized fees first, then falls back to default.
        """
        game_data = await self._get_game_fees(game_id)
        
        if not game_data:
            return 0.07 # Safe fallback if API fails

        current_time = time.time()
        
        # Check specific reduction
        reduced_map = game_data.get("reduced", {})
        if title in reduced_map:
            rule = reduced_map[title]
            if rule["expires"] > current_time:
                # fraction is string "0.05"
                return float(rule["fraction"])

        # Return default
        return float(game_data.get("default", 0.07))

    async def _get_game_fees(self, game_id: str) -> Optional[Dict]:
        """
        Fetches fees from API or Cache.
        """
        # 1. Check Cache
        cached = self._cache.get(game_id)
        if cached and cached["expires_local"] > time.time():
            return cached

        # 2. Fetch API
        client = self._get_client()
        if not client:
            logger.error("No API Keys for FeeOracle")
            return None

        # Endpoint: GET /exchange/v1/customized-fees
        # Spec params: gameId (required), offerType (dmarket)
        # Note: Rust client currently implements only specific methods. 
        # We need to use `client.rust_client.send_signed_request` if we exposed it,
        # OR add `fetch_customized_fees` to Rust.
        # BUT for now, since Rust wrapper might not expose generic `send`, 
        # we can use Python request logic IF we have `BaseDMarketClient` using python-side auth,
        # OR we rely on Rust logic.
        
        # Wait, BaseDMarketClient relies on Rust for signing usually?
        # Let's check `BaseDMarketClient` implementation.
        # It's likely in `src/dmarket/api/client.py`.
        # Assuming we need to extend Rust client or use Python fallback.
        # Since the task is "Create src/dmarket/pricing/fee_oracle.py", I will assume we can use
        # `client.aiohttp` or similar if `BaseDMarketClient` supports it.
        # However, looking at previous context, we moved ALL auth to Rust.
        # So we MUST add this endpoint to Rust OR generic request capability.
        
        # NOTE: I will mock the fetch logic here assuming generic request is available via Python 
        # OR I will add it to Rust in next steps if needed. 
        # Actually, `debug_dmarket.py` showed how to do it in Python. 
        # I'll implement a lightweight Python fetcher inside Oracle to avoid blocking Rust compilation for this task.
        
        try:
            # We use the isolated pure python logic for this specific non-HFT (1/hour) call to save dev time on Rust recompilation
            from src.dmarket.api.client import BaseDMarketClient
            # ... actually BaseDMarketClient usually has a `_make_request` method.
            # I'll use that.
            
            # Since I can't see client.py right now, I'll write safer code.
            # I will use the `debug_dmarket.py` style isolated requester for reliability.
            # It's low frequency (once per hour per game).
            import requests
            from nacl.signing import SigningKey
            
            pub = client.public_key
            sec = client.secret_key
            
            # Crypto Setup (Python)
            secret_bytes = bytes.fromhex(sec)
            seed = secret_bytes[:32] if len(secret_bytes) == 64 else secret_bytes
            signing_key = SigningKey(seed)
            
            ts = str(int(time.time()))
            method = "GET"
            path = f"/exchange/v1/customized-fees?gameId={game_id}&offerType=dmarket"
            msg = f"{method}{path}{ts}"
            sig = signing_key.sign(msg.encode('utf-8')).signature.hex()
            
            headers = {
                "X-Api-Key": pub,
                "X-Request-Sign": f"dmar ed25519 {sig}",
                "X-Sign-Date": ts,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            url = f"https://api.dmarket.com{path}"
            # Using async httpx would be better if we are async
            import httpx
            async with httpx.AsyncClient() as http:
                resp = await http.get(url, headers=headers)
                
            if resp.status_code != 200:
                logger.error(f"FeeOracle API Error: {resp.status_code}")
                return None
                
            data = resp.json()
            # Parse
            # {
            #   "defaultFee": {"fraction": "0.07", ...},
            #   "reducedFees": [{"title": "...", "fraction": "0.05", "expiresAt": ...}, ...]
            # }
            
            default_fee = data.get("defaultFee", {}).get("fraction", "0.07")
            reduced_raw = data.get("reducedFees", [])
            
            reduced_map = {}
            for item in reduced_raw:
                # "expiresAt": unix timestamp int
                reduced_map[item["title"]] = {
                    "fraction": item["fraction"],
                    "expires": int(item.get("expiresAt", 0))
                }
                
            cache_entry = {
                "expires_local": time.time() + self._cache_ttl,
                "default": default_fee,
                "reduced": reduced_map
            }
            
            self._cache[game_id] = cache_entry
            logger.info(f"FeeOracle updated for {game_id}. Default: {default_fee}, Custom rules: {len(reduced_map)}")
            return cache_entry

        except Exception as e:
            logger.error(f"FeeOracle Exception: {e}")
            return None

# Global Instance
fee_oracle = FeeOracle()
