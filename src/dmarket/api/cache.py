"""Request caching module for DMarket API.

This module provides caching functionality for API responses.
"""

import time
from typing import Any

# TTL for cache in seconds
CACHE_TTL = {
    "short": 30,  # 30 seconds for frequently changing data
    "medium": 300,  # 5 minutes for moderately stable data
    "long": 1800,  # 30 minutes for stable data
}

# Cache storage
_api_cache: dict[str, Any] = {}


def get_cache_key(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    """Create unique cache key based on request.

    Args:
        method: HTTP method
        path: Request path
        params: GET parameters
        data: POST data

    Returns:
        str: Cache key
    """
    key_parts = [method, path]

    if params:
        sorted_params = sorted(params.items())
        key_parts.append(str(sorted_params))

    if data:
        sorted_data = sorted(data.items()) if isinstance(data, dict) else str(data)
        key_parts.append(str(sorted_data))

    return ":".join(key_parts)


def is_cacheable(method: str, path: str) -> tuple[bool, str]:
    """Determine if a request should be cached.

    Args:
        method: HTTP method
        path: Request path

    Returns:
        Tuple[bool, str]: (is_cacheable, ttl_type)
    """
    # Only cache GET requests
    if method.upper() != "GET":
        return False, ""

    # Long TTL endpoints - rarely changing data
    long_ttl_endpoints = [
        "/game/v1/games",
        "/exchange/v1/market/meta",
    ]

    # Medium TTL endpoints - moderately changing data
    medium_ttl_endpoints = [
        "/exchange/v1/market/aggregated-prices",
        "/trade-aggregator/v1/last-sales",
        "/account/v1/sales-history",
        "/exchange/v1/market/price-history",
    ]

    # Short TTL endpoints - frequently changing data
    short_ttl_endpoints = [
        "/exchange/v1/market/items",
        "/exchange/v1/market/best-offers",
        "/account/v1/balance",
    ]

    # Check endpoint matches
    for endpoint in long_ttl_endpoints:
        if endpoint in path:
            return True, "long"

    for endpoint in medium_ttl_endpoints:
        if endpoint in path:
            return True, "medium"

    for endpoint in short_ttl_endpoints:
        if endpoint in path:
            return True, "short"

    return False, ""


def get_from_cache(cache_key: str) -> dict[str, Any] | None:
    """Get cached response if valid.

    Args:
        cache_key: Cache key

    Returns:
        Cached data or None if not found/expired
    """
    if cache_key not in _api_cache:
        return None

    cached = _api_cache[cache_key]
    if time.time() > cached.get("expires_at", 0):
        # Cache expired
        del _api_cache[cache_key]
        return None

    return cached.get("data")


def save_to_cache(
    cache_key: str,
    data: dict[str, Any],
    ttl_type: str = "medium",
) -> None:
    """Save response to cache.

    Args:
        cache_key: Cache key
        data: Data to cache
        ttl_type: TTL type (short, medium, long)
    """
    ttl = CACHE_TTL.get(ttl_type, CACHE_TTL["medium"])

    _api_cache[cache_key] = {
        "data": data,
        "expires_at": time.time() + ttl,
        "ttl_type": ttl_type,
    }


def clear_cache() -> None:
    """Clear all cached data."""
    _api_cache.clear()


def clear_cache_for_endpoint(endpoint_path: str) -> None:
    """Clear cache for specific endpoint.

    Args:
        endpoint_path: Endpoint path to clear cache for
    """
    keys_to_delete = [key for key in _api_cache if endpoint_path in key]
    for key in keys_to_delete:
        del _api_cache[key]
