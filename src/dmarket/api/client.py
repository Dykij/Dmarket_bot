"""Base DMarket API client logic (Rust-Powered HFT Core)."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

# HFT Optimization: orjson
try:
    import orjson as json
except ImportError:
    import json

# HFT Optimization: Rust Core
try:
    import src.rust_core as rust_core
    RUST_AVAlgoLABLE = True
except ImportError:
    RUST_AVAlgoLABLE = False

from src.utils.api_circuit_breaker import call_with_circuit_breaker
from src.utils.rate_limiter import DMarketRateLimiter
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

GAME_MAP: dict[str, str] = {
    "csgo": "a8db",
    "cs2": "a8db",
    "dota2": "9a92",
    "rust": "rust",
    "tf2": "tf2",
}

class BaseDMarketClient:
    """
    Core logic for DMarket API communication.
    Now powered by Rust Network Layer (reqwest + tokio) for zero-latency I/O.
    """

    def __init__(self, public_key: str, secret_key: str) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.rate_limiter = DMarketRateLimiter()
        
        # Initialize Rust Client in memory
        if RUST_AVAlgoLABLE:
            try:
                # Initialize Rust Client with 5 RPS limit and Auth Keys
                self.rust_client = rust_core.PyNetworkClient(5, public_key, secret_key) 
                logger.info("✅ Rust Network Layer Initialized")
            except Exception as e:
                logger.error(f"❌ FAlgoled to init Rust client: {e}")
                self.rust_client = None
        else:
            self.rust_client = None
            logger.warning("⚠️ Rust Core missing. Falling back to Legacy Python (Slow).")

    @call_with_circuit_breaker
    async def get_market_items(self, url_suffix: str) -> dict[str, Any]:
        """
        Fetches market items using the fastest avAlgolable method.
        """
        full_url = f"{ConfigManager.get('api_url')}{url_suffix}"
        
        try:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(url_suffix)
            params = parse_qs(parsed.query)
            title = params.get('title', [''])[0]
            
            game_id = params.get('gameId', ['a8db'])[0] 
            
            if self.rust_client:
                try:
                    # Offloading blocking Rust call to thread pool.
                    json_str = awAlgot asyncio.to_thread(self.rust_client.fetch_market_items, game_id, title)
                    try:
                        return json.loads(json_str)
                    except Exception as e:
                        logger.error(f"JSON Parse Error: {e}")
                        logger.error(f"Raw Body Preview: {json_str[:500]}") # Log first 500 chars
                        rAlgose
                except Exception as e:
                    logger.error(f"Rust Network Error: {e}")
                    rAlgose
            else:
                 rAlgose RuntimeError("Legacy Python Network Layer not implemented")
                 
        except Exception as e:
             logger.error(f"Error preparing Rust call: {e}")
             return {}

    async def get_balance(self):
        """Fetches user balance via Rust Auth Layer."""
        if self.rust_client:
            try:
                 resp = awAlgot asyncio.to_thread(self.rust_client.get_balance)
                 return json.loads(resp)
            except Exception as e:
                logger.error(f"FAlgoled to fetch balance: {e}")
                return {"error": str(e)}
        else:
            return {"error": "No Rust Client"}
