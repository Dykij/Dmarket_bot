"""
dmarket_api.py — DMarket API client wrapper.

Provides a simplified interface for DMarket market operations.
Makes actual HTTP calls via httpx.

v15.2: Uses tenacity for retry logic (replaces 40+ lines of manual retry).
"""

from typing import Any

import httpx
import tenacity


class _RetryableHTTPError(Exception):
    """Raised for transient HTTP errors that should be retried."""


class _RateLimitError(Exception):
    """Raised on 429 Too Many Requests."""


class DMarketAPI:
    """DMarket API client."""

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        api_url: str = "https://api.dmarket.com",
        enable_cache: bool = True,
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.api_url = api_url
        self.enable_cache = enable_cache
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.api_url, timeout=30.0)
        return self._client

    async def _do_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single HTTP request (no retry)."""
        client = await self._get_client()
        headers = {
            "X-Api-Key": self.public_key,
            "X-Api-Secret": self.secret_key,
            "Content-Type": "application/json",
        }
        resp = await client.request(method, path, params=params, json=json, headers=headers)

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            raise _RateLimitError(f"Rate limited: {resp.headers.get('Retry-After', '1')}s")

        if resp.status_code >= 500:
            raise _RetryableHTTPError(f"Server error {resp.status_code}")

        # Auth errors and other client errors — don't retry
        return {"error": True, "status_code": resp.status_code}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with tenacity retry for transient errors.

        v15.2: Replaces 40+ lines of manual retry with tenacity decorator.
        """
        @tenacity.retry(
            retry=tenacity.retry_any(
                tenacity.retry_if_exception_type(_RetryableHTTPError),
                tenacity.retry_if_exception_type(_RateLimitError),
                tenacity.retry_if_exception_type(httpx.TimeoutException),
                tenacity.retry_if_exception_type((
                    httpx.ConnectError, httpx.ReadError,
                    httpx.WriteError, httpx.PoolTimeout,
                )),
            ),
            stop=tenacity.stop_after_attempt(4),
            wait=tenacity.wait_exponential(multiplier=1, max=5),
            reraise=True,
        )
        async def _do_retry() -> dict[str, Any]:
            return await self._do_request(method, path, params=params, json=json)

        try:
            return await _do_retry()
        except _RateLimitError:
            return {"error": True, "status_code": 429, "retry_after": 60}
        except (
            httpx.TimeoutException, httpx.ConnectError,
            httpx.ReadError, httpx.WriteError, httpx.PoolTimeout,
        ):
            return {"error": True, "message": "Network/timeout error"}
        except Exception:
            return {}

    async def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        try:
            return await self._request("GET", "/account/v1/balance")
        except Exception as e:
            return {"error": True, "status_code": getattr(e, "status_code", 500)}

    async def get_market_items(
        self,
        game: str = "csgo",
        limit: int = 100,
        price_from: int = 0,
        price_to: int = 0,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get market items."""
        params: dict[str, Any] = {"gameId": game, "limit": limit, "currency": "USD"}
        if cursor:
            params["cursor"] = cursor
        if price_from:
            params["priceFrom"] = price_from
        if price_to:
            params["priceTo"] = price_to
        try:
            return await self._request("GET", "/exchange/v1/market/items", params=params)
        except Exception:
            return {"objects": [], "cursor": ""}

    async def get_all_market_items(
        self,
        game: str = "csgo",
        max_items: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all market items (paginated)."""
        all_items: list[dict[str, Any]] = []
        cursor = ""
        while len(all_items) < max_items:
            result = await self.get_market_items(game=game, limit=100, cursor=cursor)
            items = result.get("objects", [])
            if not items:
                break
            all_items.extend(items)
            cursor = result.get("cursor", "")
            if not cursor:
                break
        return all_items[:max_items]

    async def get_aggregated_prices(
        self,
        titles: list[str],
        game_id: str = "a8db",
    ) -> dict[str, Any]:
        """Get aggregated prices for titles."""
        return await self._request(
            "POST",
            "/exchange/v1/market/aggregate-prices",
            json={"gameId": game_id, "titles": titles},
        )

    async def create_targets(
        self,
        game_id: str,
        targets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create buy targets."""
        return await self._request(
            "POST",
            "/exchange/v1/targets/create",
            json={"gameId": game_id, "targets": targets},
        )

    async def get_targets(
        self,
        game_id: str,
        limit: int = 100,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get active targets."""
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/exchange/v1/targets", params=params)

    async def get_user_targets(
        self,
        game: str = "a8db",
        game_id: str = "a8db",
        limit: int = 100,
        cursor: str = "",
        offset: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get user's active targets."""
        return await self.get_targets(game_id=game_id or game, limit=limit, cursor=cursor)

    async def get_closed_targets(
        self,
        game_id: str = "a8db",
        limit: int = 100,
        cursor: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get closed (completed) targets."""
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/exchange/v1/targets/closed", params=params)

    async def delete_targets(
        self,
        game_id: str = "a8db",
        target_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Delete targets."""
        return await self._request(
            "POST",
            "/exchange/v1/targets/delete",
            json={"gameId": game_id, "targetIds": target_ids or []},
        )

    async def get_user_inventory(
        self,
        game_id: str = "a8db",
        limit: int = 100,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get user's inventory."""
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/exchange/v1/user/inventory", params=params)

    async def get_user_offers(
        self,
        game_id: str,
        limit: int = 100,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get user's active offers."""
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/exchange/v1/user-offers/get", params=params)

    async def get_closed_offers(
        self,
        game_id: str,
        limit: int = 100,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get closed (sold) offers."""
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/exchange/v1/user-offers/closed", params=params)

    async def create_sell_offer(
        self,
        asset_id: str,
        price_usd: float,
    ) -> dict[str, Any]:
        """Create a sell offer."""
        return await self._request(
            "POST",
            "/exchange/v1/user-offers/create",
            json={"assetId": asset_id, "price": {"amount": int(price_usd * 100), "currency": "USD"}},
        )

    async def get_item_fee(
        self,
        game_id: str,
        item_id: str,
        price_cents: int,
    ) -> float:
        """Get fee rate for an item."""
        return 0.05

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
