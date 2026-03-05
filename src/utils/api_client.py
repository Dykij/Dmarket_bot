"""
Async DMarket Client (Pure Python Core).
Standardized according to SACS-2026.
Replaces legacy synchronous wrappers and Rust dependencies for pure Python operations.

Features:
- Asynchronous I/O via aiohttp
- High-performance JSON parsing (orjson/ujson)
Script: src/utils/api_client.py
Description: Asynchronous client for the DMarket API.
Handles ED25519 request signing, Rate Limiting (Token Bucket),
Circuit Breaker, and generic request processing.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp
import websockets

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


class TokenBucket:
    """
    Async Token Bucket rate limiter.
    Supports burst capacity and separate read/write limits.
    """

    def __init__(self, rate: float, burst: int = 1):
        self.rate = rate  # Tokens per second
        self.burst = burst  # Max tokens (burst capacity)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Wait until a token is available. Returns wait time in seconds."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            # Need to wait for a token
            wait_time = (1.0 - self._tokens) / self.rate
            self._tokens = 0.0

        await asyncio.sleep(wait_time)
        logger.debug(f"Rate limiter: waited {wait_time:.3f}s")
        return wait_time


class CircuitBreaker:
    """
    Simple circuit breaker for API resilience.
    Opens after `threshold` consecutive failures, stays open for `cooldown` seconds.
    """

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self._failure_count = 0
        self._open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._open_until > 0 and time.monotonic() < self._open_until:
            return True
        if self._open_until > 0 and time.monotonic() >= self._open_until:
            # Half-open: allow one request to test
            self._open_until = 0.0
            self._failure_count = 0
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._open_until = 0.0

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.threshold:
            self._open_until = time.monotonic() + self.cooldown
            logger.warning(
                f"Circuit breaker OPEN: {self._failure_count} consecutive failures. "
                f"Cooling down for {self.cooldown}s."
            )


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
        aiohttp_connector: Optional[aiohttp.TCPConnector] = None,
    ):
        self.public_key = public_key
        self.secret_key = secret_key

        # Rate Limiters (Token Bucket)
        self._read_limiter = TokenBucket(rate=limit_per_second, burst=limit_per_second)
        self._write_limiter = TokenBucket(rate=2, burst=2)  # Stricter for mutations

        # Circuit Breaker
        self._circuit_breaker = CircuitBreaker(threshold=3, cooldown=60.0)

        # Networking
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector = aiohttp_connector

    async def __aenter__(self) -> "AsyncDMarketClient":
        """Initialize the session with optimal TCP settings."""
        if not self._session:
            if not self._connector:
                # Optimized TCP settings for HFT
                self._connector = aiohttp.TCPConnector(
                    limit=100,  # Max concurrent connections
                    ttl_dns_cache=300,  # Cache DNS for 5 minutes
                    keepalive_timeout=60,  # Keep connections open
                    enable_cleanup_closed=True,
                )

            # Use optimized JSON serializer if available
            def json_serialize(x):
                if hasattr(json, "dumps") and "orjson" in json.__name__:
                    return json.dumps(x).decode("utf-8")
                return json.dumps(x)

            self._session = aiohttp.ClientSession(
                base_url=self.BASE_URL,
                connector=self._connector,
                json_serialize=json_serialize,
            )
            logger.info(f"AsyncDMarketClient initialized (JSON: {json.__name__})")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Graceful shutdown."""
        if self._session:
            await self._session.close()
            logger.info("AsyncDMarketClient session closed")

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Any = None,
        sign: bool = True,
        _retry: int = 0,
    ) -> Union[Dict, List, str]:
        """
        Execute an HTTP request with automatic signing, rate limiting,
        circuit breaker, and exponential backoff on rate limits.
        """
        if not self._session:
            await self.__aenter__()

        # Circuit Breaker check
        if self._circuit_breaker.is_open:
            raise aiohttp.ClientError(
                "Circuit breaker is OPEN — too many consecutive failures. "
                "Retrying after cooldown."
            )

        # Rate Limiting (use write limiter for mutations)
        if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            await self._write_limiter.acquire()
        else:
            await self._read_limiter.acquire()

        # Prepare payload for signing
        json_body = ""
        if body is not None:
            if "orjson" in json.__name__:
                json_body = json.dumps(body).decode("utf-8")
            else:
                json_body = json.dumps(body)

        headers = {}

        # Construct full path with query params for signing
        full_path = endpoint
        if params:
            from urllib.parse import urlencode

            query_string = urlencode(params)
            full_path = f"{endpoint}?{query_string}"

        if sign:
            headers = generate_signature_ed25519(
                self.public_key, self.secret_key, method, full_path, json_body
            )

        try:
            async with self._session.request(
                method,
                endpoint,
                params=params,
                data=json_body if body is not None else None,
                headers=headers,
            ) as resp:
                # Handling Rate Limits (429) with exponential backoff
                if resp.status == 429:
                    max_retries = 5
                    if _retry >= max_retries:
                        self._circuit_breaker.record_failure()
                        logger.error(
                            f"Rate limit: exhausted {max_retries} retries on {endpoint}"
                        )
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=429,
                            message="Rate limit exceeded after retries",
                        )
                    wait_time = min(2**_retry, 60)
                    logger.warning(
                        f"Rate limit hit on {endpoint}. Retry {_retry + 1}/{max_retries} "
                        f"in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    return await self.request(
                        method, endpoint, params, body, sign, _retry + 1
                    )

                response_text = await resp.text()

                if resp.status >= 400:
                    self._circuit_breaker.record_failure()
                    logger.error(f"API Error {resp.status}: {response_text}")
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=response_text,
                    )

                # Success — reset circuit breaker
                self._circuit_breaker.record_success()

                try:
                    return json.loads(response_text)
                except Exception:
                    return response_text

        except aiohttp.ClientResponseError:
            raise
        except asyncio.TimeoutError:
            self._circuit_breaker.record_failure()
            logger.error(f"Timeout on [{method} {endpoint}]")
            raise
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Request failed [{method} {endpoint}]: {str(e)}")
            raise

    # --- Convenience Methods ---

    async def get_balance(self) -> Dict:
        """Fetch user balance."""
        return await self.request("GET", "/account/v1/balance")

    async def get_market_items(
        self, game: str = "a8db", limit: int = 100, title: str = ""
    ) -> Dict:
        """Fetch market items (public endpoint, often no auth needed, but we sign anyway)."""
        params = {"gameId": game, "limit": limit, "title": title, "currency": "USD"}
        return await self.request("GET", "/exchange/v1/market/items", params=params)

    async def get_user_inventory(self, game: str = "a8db", cursor: str = "") -> Dict:
        """Fetch one page of user inventory (use get_full_inventory for complete list)."""
        params: Dict[str, Any] = {"gameId": game, "limit": 100, "currency": "USD"}
        if cursor:
            params["cursor"] = cursor
        return await self.request("GET", "/exchange/v1/user/items", params=params)

    async def get_full_inventory(self, game: str = "a8db") -> List[Dict]:
        """
        Fetch the COMPLETE user inventory with pagination.
        Handles cursors automatically — returns all items, not just the first 100.
        """
        all_items: List[Dict] = []
        cursor = ""
        page = 0

        while True:
            page += 1
            try:
                response = await self.get_user_inventory(game=game, cursor=cursor)
            except Exception as e:
                logger.error(f"Inventory page {page} fetch failed: {e}")
                break

            # Handle both response formats
            items = response.get("objects") or response.get("Items") or []
            all_items.extend(items)

            # Get next cursor for pagination
            cursor = response.get("cursor") or response.get("Cursor") or ""

            logger.debug(
                f"Inventory page {page}: {len(items)} items fetched (total: {len(all_items)})"
            )

            # Stop if last page (no cursor or no items returned)
            if not cursor or len(items) < 100:
                break

        logger.info(
            f"Full inventory fetched: {len(all_items)} total items across {page} pages"
        )
        return all_items

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
        body = {"GameID": game, "Targets": targets}
        return await self.request(
            "POST", "/marketplace-api/v1/user-targets/create", body=body
        )

    async def get_user_targets(
        self,
        game: str = "a8db",
        limit: str = "100",
        status: str = "TargetStatusActive",
        cursor: str = "",
    ) -> Dict:
        """Fetch active user targets."""
        params = {
            "GameID": game,
            "Limit": limit,
            "BasicFilters.Status": status,
            "Cursor": cursor,
        }
        return await self.request(
            "GET", "/marketplace-api/v1/user-targets", params=params
        )

    async def delete_target(self, target_ids: List[Dict]) -> Dict:
        """
        Delete targets.

        Args:
            target_ids: List of dicts [{"TargetID": "..."}]
        """
        body = {"Targets": target_ids}
        return await self.request(
            "POST", "/marketplace-api/v1/user-targets/delete", body=body
        )

    # --- Market Analysis Methods ---

    async def get_aggregated_prices(self, names: List[str], game: str = "a8db") -> Dict:
        """
        Get Best Bid and Best Ask for a list of items.
        Crucial for Spread Trading.
        """
        body = {"filter": {"game": game, "titles": names}, "limit": "100"}
        return await self.request(
            "POST", "/marketplace-api/v1/aggregated-prices", body=body
        )

    # --- WebSocket Real-time Feed (Feature Preview) ---

    async def subscribe_realtime_feed(self, callback) -> None:
        """
        WebSocket Real-time feed for DMarket (Roadmap Item #9).
        Note: Exact endpoint is undocumented, utilizing stub logic for testing.
        """
        ws_url = "wss://api.dmarket.com/ws-stub"
        logger.info(f"Connecting to WS {ws_url} (Stub)")
        try:
            async with websockets.connect(ws_url) as ws:
                while True:
                    msg = await ws.recv()
                    logger.debug(f"WS Msg: {msg}")
                    await callback(json.loads(msg))
        except Exception as e:
            logger.warning(f"WebSocket sub failed: {e}")
