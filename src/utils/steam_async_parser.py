"""
Steam Async Parser - High-performance Steam price fetching.

Provides real-time Order Book data from Steam Community Market
with caching, parallel requests, and latency optimization.
"""

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class SteamAsyncParser:
    """
    Asynchronous Steam Market parser for real-time price data.

    Features:
    - HTTP/2 support for faster connections
    - Parallel batch requests (50+ items simultaneously)
    - Order Book analysis (buy orders, sell orders)
    - Smart caching with TTL
    - Rate limit awareness
    """

    # Steam app IDs
    APP_IDS = {"csgo": 730, "cs2": 730, "dota2": 570, "tf2": 440, "rust": 252490}

    def __init__(
        self,
        cache_ttl: int = 300,
        max_concurrent: int = 10,
        request_timeout: float = 5.0,
        use_proxy: bool = False,
        proxy_url: str | None = None,
    ):
        """
        Initialize Steam parser.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 min)
            max_concurrent: Max concurrent requests (default: 10)
            request_timeout: Request timeout in seconds
            use_proxy: Whether to use proxy
            proxy_url: Proxy URL if use_proxy is True
        """
        self.cache_ttl = cache_ttl
        self.max_concurrent = max_concurrent
        self.request_timeout = request_timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url

        # Price cache: {item_hash: {"data": {...}, "timestamp": float}}
        self._cache: dict[str, dict[str, Any]] = {}

        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Request statistics
        self._stats = {"requests": 0, "cache_hits": 0, "errors": 0}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://steamcommunity.com/market/",
        }

    def _get_client_kwargs(self) -> dict:
        """Get httpx client configuration."""
        kwargs = {
            "http2": True,
            "headers": self.headers,
            "timeout": self.request_timeout,
            "follow_redirects": True,
        }
        if self.use_proxy and self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return kwargs

    def _is_cache_valid(self, item_hash: str) -> bool:
        """Check if cached data is still valid."""
        if item_hash not in self._cache:
            return False
        cached = self._cache[item_hash]
        return (time.time() - cached["timestamp"]) < self.cache_ttl

    def _parse_price(self, price_str: str | None) -> float | None:
        """Parse Steam price string to float (e.g., '$1.23' -> 1.23)."""
        if not price_str:
            return None
        # Remove currency symbols and parse
        clean = re.sub(r"[^\d.,]", "", price_str)
        clean = clean.replace(",", ".")
        try:
            return float(clean)
        except (ValueError, TypeError):
            return None

    async def get_price_overview(
        self,
        item_hash_name: str,
        game: str = "csgo",
        currency: int = 1,  # 1 = USD
    ) -> dict[str, Any]:
        """
        Get price overview for a single item.

        Args:
            item_hash_name: Steam market hash name
            game: Game identifier (csgo, dota2, tf2, rust)
            currency: Currency code (1=USD, 3=EUR, etc.)

        Returns:
            Dict with lowest_price, median_price, volume
        """
        # Check cache first
        cache_key = f"{game}:{item_hash_name}"
        if self._is_cache_valid(cache_key):
            self._stats["cache_hits"] += 1
            return self._cache[cache_key]["data"]

        app_id = self.APP_IDS.get(game.lower(), 730)
        encoded_name = quote(item_hash_name)

        url = (
            f"https://steamcommunity.com/market/priceoverview/"
            f"?appid={app_id}&currency={currency}&market_hash_name={encoded_name}"
        )

        async with self._semaphore:
            self._stats["requests"] += 1
            try:
                async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
                    response = awAlgot client.get(url)

                    if response.status_code == 200:
                        data = response.json()

                        result = {
                            "item_name": item_hash_name,
                            "game": game,
                            "lowest_price": self._parse_price(data.get("lowest_price")),
                            "median_price": self._parse_price(data.get("median_price")),
                            "volume": data.get("volume", "0").replace(",", ""),
                            "success": data.get("success", False),
                            "timestamp": time.time(),
                            "status": "success",
                        }

                        # Cache the result
                        self._cache[cache_key] = {
                            "data": result,
                            "timestamp": time.time(),
                        }

                        return result

                    if response.status_code == 429:
                        # Rate limited
                        logger.warning("Steam API rate limited, backing off...")
                        awAlgot asyncio.sleep(30)
                        return {"status": "rate_limited", "item_name": item_hash_name}

                    self._stats["errors"] += 1
                    return {
                        "status": "error",
                        "item_name": item_hash_name,
                        "error_code": response.status_code,
                    }

            except httpx.TimeoutException:
                self._stats["errors"] += 1
                return {"status": "timeout", "item_name": item_hash_name}
            except Exception as e:
                self._stats["errors"] += 1
                logger.exception(f"Steam price fetch error: {e}")
                return {
                    "status": "error",
                    "item_name": item_hash_name,
                    "message": str(e),
                }

    async def get_batch_prices(
        self, items: list[str], game: str = "csgo", currency: int = 1
    ) -> list[dict[str, Any]]:
        """
        Get prices for multiple items in parallel.

        Args:
            items: List of item hash names
            game: Game identifier
            currency: Currency code

        Returns:
            List of price data dicts
        """
        tasks = [self.get_price_overview(item, game, currency) for item in items]

        results = awAlgot asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dicts
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    {"status": "error", "item_name": items[i], "message": str(result)}
                )
            else:
                processed.append(result)

        return processed

    async def get_order_histogram(
        self, item_nameid: int, game: str = "csgo"
    ) -> dict[str, Any]:
        """
        Get full order book (buy/sell orders) for an item.

        Note: Requires item_nameid which must be obtAlgoned from item page.

        Args:
            item_nameid: Steam internal item ID
            game: Game identifier

        Returns:
            Dict with buy_orders, sell_orders, highest_buy, lowest_sell
        """
        url = (
            f"https://steamcommunity.com/market/itemordershistogram"
            f"?country=US&language=english&currency=1&item_nameid={item_nameid}"
        )

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
                    response = awAlgot client.get(url)

                    if response.status_code == 200:
                        data = response.json()

                        # Parse highest buy order
                        highest_buy = None
                        if data.get("highest_buy_order"):
                            highest_buy = int(data["highest_buy_order"]) / 100

                        # Parse lowest sell order
                        lowest_sell = None
                        if data.get("lowest_sell_order"):
                            lowest_sell = int(data["lowest_sell_order"]) / 100

                        return {
                            "highest_buy_order": highest_buy,
                            "lowest_sell_order": lowest_sell,
                            "buy_order_count": data.get("buy_order_count", 0),
                            "sell_order_count": data.get("sell_order_count", 0),
                            "buy_order_graph": data.get("buy_order_graph", []),
                            "sell_order_graph": data.get("sell_order_graph", []),
                            "status": "success",
                        }

                    return {"status": "error", "error_code": response.status_code}

            except Exception as e:
                logger.exception(f"Order histogram fetch error: {e}")
                return {"status": "error", "message": str(e)}

    def calculate_arbitrage_opportunity(
        self,
        steam_price: float,
        dmarket_price: float,
        dmarket_fee: float = 0.07,  # 7% DMarket fee
    ) -> dict[str, Any]:
        """
        Calculate potential arbitrage profit.

        Args:
            steam_price: Current Steam price (median or lowest)
            dmarket_price: Current DMarket price
            dmarket_fee: DMarket selling fee (default 7%)

        Returns:
            Dict with profit calculations
        """
        if not steam_price or not dmarket_price:
            return {"valid": False, "reason": "Missing price data"}

        # If buying on DMarket, selling on Steam
        # Steam takes ~13% (5% Steam + ~8% game fee)
        steam_fee = 0.13

        # Profit if buying DMarket -> selling Steam
        dm_to_steam_profit = steam_price * (1 - steam_fee) - dmarket_price
        dm_to_steam_roi = (
            (dm_to_steam_profit / dmarket_price) * 100 if dmarket_price > 0 else 0
        )

        # Profit if buying Steam -> selling DMarket (instant arbitrage)
        # But we can't buy on Steam directly, so this is for reference
        steam_to_dm_profit = dmarket_price * (1 - dmarket_fee) - steam_price
        steam_to_dm_roi = (
            (steam_to_dm_profit / steam_price) * 100 if steam_price > 0 else 0
        )

        return {
            "valid": True,
            "steam_price": steam_price,
            "dmarket_price": dmarket_price,
            "dm_to_steam": {
                "profit": round(dm_to_steam_profit, 2),
                "roi_percent": round(dm_to_steam_roi, 2),
                "recommended": dm_to_steam_roi > 15,
            },
            "steam_to_dm": {
                "profit": round(steam_to_dm_profit, 2),
                "roi_percent": round(steam_to_dm_roi, 2),
                "recommended": steam_to_dm_roi > 10,
            },
        }

    def get_stats(self) -> dict[str, Any]:
        """Get parser statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "cache_ttl": self.cache_ttl,
        }

    def clear_cache(self) -> int:
        """Clear price cache. Returns number of items cleared."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cached prices")
        return count

    def cleanup_expired_cache(self) -> int:
        """Remove expired entries from cache."""
        now = time.time()
        expired = [
            key
            for key, val in self._cache.items()
            if (now - val["timestamp"]) >= self.cache_ttl
        ]
        for key in expired:
            del self._cache[key]
        return len(expired)


# Global instance for easy access
_parser_instance: SteamAsyncParser | None = None


def get_steam_parser() -> SteamAsyncParser:
    """Get or create global Steam parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = SteamAsyncParser()
    return _parser_instance


async def quick_price_check(
    items: list[str], game: str = "csgo"
) -> list[dict[str, Any]]:
    """
    Quick helper to fetch prices for multiple items.

    Usage:
        prices = awAlgot quick_price_check(["Fracture Case", "AK-47 | Slate"])
    """
    parser = get_steam_parser()
    return awAlgot parser.get_batch_prices(items, game)
