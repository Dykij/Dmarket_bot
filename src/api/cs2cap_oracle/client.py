"""
CS2Cap Oracle — Unified pricing across 41 CS2 marketplaces.

Uses CS2Cap REST API (https://api.cs2c.app/v1) for:
  - GET /items: catalog of all CS2 items with item_id mapping
  - GET /prices: lowest asks across all providers (requires item_id integer)
  - POST /prices/batch: lowest asks for up to 100 items in 1 call
  - POST /bids/batch: highest bids for up to 100 items in 1 call

API format (single):
  GET /prices?item_id=4994&currency=USD&limit=10
  Response: {"items": [{"provider": "buff163", "lowest_ask": 435886, ...}]}
  lowest_ask is in minor units (cents) — divide by 100 for dollars.

API format (batch):
  POST /prices/batch
  Body: {"market_hash_names": ["AK-47 | Redline", ...], "currency": "USD"}
  Response: {"items": [{"market_hash_name": "...", "providers": [
              {"provider": "buff163", "lowest_ask": 435886, "quantity": 3}]}, ...]}
  Batch endpoints: 1 HTTP call = 1 unit of quota (Starter+ tier required for batch).

Tiered caching:
  1. In-memory (5 min TTL) — high-frequency loop
  2. SQLite history (1 hr TTL) — persistent across restarts
  3. Live API — rate-limited with exponential backoff (skipped for batch POSTs)
"""

import asyncio
import logging
import time
from typing import Any

import aiohttp

from src.api.dmarket_api_client.backoff import CircuitBreaker
from src.config import Config
from src.db.price_history import price_db

from .catalog import _CatalogMixin
from .prices import _PricesMixin
from .utils import _UtilsMixin

logger = logging.getLogger("CS2CapOracle")


class CS2CapOracle(_CatalogMixin, _PricesMixin, _UtilsMixin):
    """
    Unified CS2 market data oracle via CS2Cap API.
    Free tier: GET /items + GET /prices only.
    """

    BASE_URL = "https://api.cs2c.app/v1"
    CACHE_TTL = 3600       # SQLite: 1 hour
    MEM_TTL = 300          # In-memory: 5 minutes
    ITEMS_MEM_TTL = 86400  # Item catalog: 24 hours (rarely changes)
    CANDLES_MEM_TTL = 600  # Candles: 10 minutes

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._request_delay = 1.0
        self._quota_exhausted = False
        self._quota_exhausted_at: float = 0.0
        self._quota_reset_seconds = 60  # Reset after 60s (per-minute limit, not hourly)

        # v12.7: Circuit breaker for CS2Cap API (P3-5).
        # Opens after 3 consecutive failures (429, 5xx, network errors).
        # Exponential cooldown: 30s → 60s → 120s → 300s with ±20% jitter.
        self._breaker = CircuitBreaker(
            name="cs2cap",
            fail_threshold=3,
            base_cooldown=30.0,
            max_cooldown=300.0,
            jitter_pct=0.2,
        )

        # Caches
        self._price_cache: dict[str, tuple[float, float]] = {}
        self._candles_cache: dict[str, tuple[list[Any], float]] = {}

        # Item catalog: market_hash_name -> item_id
        self._item_catalog: dict[str, int] = {}
        self._catalog_ts: float = 0.0

        # Rate limit state
        saved_delay = price_db.get_state("cs2cap_delay")
        self._request_delay = float(saved_delay) if saved_delay else 1.0
        self._rate_remaining: int | None = None  # Header-driven (X-RateLimit-Remaining)

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._lock:
            if self._session is not None and not self._session.closed:
                return self._session
            headers = {
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            )
            return self._session

    async def _throttle(self):
        """Smart throttle: adapts to X-RateLimit-Remaining header.

        When header shows remaining < 10: slow to 2s/request.
        When header shows remaining < 5: slow to 5s/request.
        Normal operation: 1s/request (Starter tier: 40 RPM = 1.5s/request).
        """
        async with self._lock:
            # Adapt delay based on header-aware remaining quota
            if self._rate_remaining is not None:
                if self._rate_remaining < 5:
                    self._request_delay = max(self._request_delay, 5.0)
                elif self._rate_remaining < 10:
                    self._request_delay = max(self._request_delay, 2.0)

            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._request_delay:
                await asyncio.sleep(self._request_delay - elapsed)
            self._last_request_time = time.monotonic()

    async def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict | None:
        """Throttled API request with rate limit handling and circuit breaker."""
        # Reset quota after 1 hour
        if self._quota_exhausted and time.time() - self._quota_exhausted_at > self._quota_reset_seconds:
            self._quota_exhausted = False
            async with self._lock:
                self._request_delay = 1.0
            price_db.save_state("cs2cap_delay", "1.0")
            logger.info("[CS2Cap] Quota reset, retrying API calls")

        if self._quota_exhausted:
            return None

        # v12.7: Circuit breaker check (P3-5).
        if not self._breaker.allow_request():
            logger.debug("[CS2Cap] Circuit breaker OPEN, skipping request")
            return None

        await self._throttle()
        session = await self.get_session()
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    async with self._lock:
                        self._request_delay = min(self._request_delay * 2.0, 30.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))
                    self._quota_exhausted = True
                    self._quota_exhausted_at = time.time()
                    self._breaker.record_failure(Exception("429 Rate Limit"))
                    logger.warning("[CS2Cap] Rate limit hit (429) — quota exhausted, pausing API calls for 1 hour")
                    return None

                if self._request_delay > 1.0:
                    async with self._lock:
                        self._request_delay = max(self._request_delay * 0.98, 1.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))

                if response.status == 403:
                    self._breaker.record_failure(Exception("403 Forbidden"))
                    return None

                if response.status != 200:
                    text = await response.text()
                    self._breaker.record_failure(Exception(f"HTTP {response.status}"))
                    logger.debug(f"[CS2Cap] HTTP {response.status}: {text[:200]}")
                    return None

                # Success: record in circuit breaker
                self._breaker.record_success()
                self._increment_monthly_counter()
                return await response.json()

        except Exception as e:
            self._breaker.record_failure(e)
            logger.debug(f"[CS2Cap] Request failed: {e}")
            return None

    async def _request_post(
        self,
        endpoint: str,
        body: dict[str, Any],
        bypass_throttle: bool = False,
    ) -> dict | None:
        """
        POST helper for batch endpoints (/prices/batch, /bids/batch).

        Bypasses the per-call throttle (batched endpoints count 1 unit per call,
        not per item). Honours the quota-exhausted gate and tracks per-minute
        budget via X-RateLimit-Remaining headers.
        """
        if self._quota_exhausted and time.time() - self._quota_exhausted_at > self._quota_reset_seconds:
            self._quota_exhausted = False
            logger.info("[CS2Cap] Quota reset, retrying API calls")

        if self._quota_exhausted:
            return None

        # v12.7: Circuit breaker check (P3-5).
        if not self._breaker.allow_request():
            logger.debug("[CS2Cap] Circuit breaker OPEN, skipping POST request")
            return None

        if not bypass_throttle:
            await self._throttle()
        session = await self.get_session()
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with session.post(url, json=body) as response:
                # Header-aware rate limiting (Pro tier surfaces these)
                header_slowed = False
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining is not None:
                    try:
                        async with self._lock:
                            self._rate_remaining = int(remaining)
                            if self._rate_remaining < 5:
                                self._request_delay = max(self._request_delay, 1.5)
                                header_slowed = True
                    except (ValueError, TypeError):
                        pass

                if response.status == 429:
                    async with self._lock:
                        self._request_delay = min(self._request_delay * 2.0, 30.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))
                    self._quota_exhausted = True
                    self._quota_exhausted_at = time.time()
                    self._breaker.record_failure(Exception(f"429 Rate Limit on {endpoint}"))
                    logger.warning(
                        f"[CS2Cap] Rate limit hit (429) on {endpoint} — "
                        f"quota exhausted, pausing API calls for 1 hour"
                    )
                    return None

                # Decay delay on success, but skip if header just raised it
                # (otherwise the 0.98 multiplier undoes the proactive slowdown
                # in the very same call).
                if self._request_delay > 1.0 and not header_slowed:
                    async with self._lock:
                        self._request_delay = max(self._request_delay * 0.98, 1.0)
                    price_db.save_state("cs2cap_delay", str(self._request_delay))

                if response.status == 403:
                    self._breaker.record_failure(Exception(f"403 Forbidden on {endpoint}"))
                    return None

                if response.status != 200:
                    text = await response.text()
                    self._breaker.record_failure(Exception(f"HTTP {response.status} on {endpoint}"))
                    logger.debug(f"[CS2Cap] HTTP {response.status} on {endpoint}: {text[:200]}")
                    return None

                # Success: record in circuit breaker
                self._breaker.record_success()
                # Track monthly quota
                self._increment_monthly_counter()
                return await response.json()

        except Exception as e:
            self._breaker.record_failure(e)
            logger.debug(f"[CS2Cap] POST {endpoint} failed: {e}")
            return None

    def _increment_monthly_counter(self) -> None:
        """Track monthly call count for the Starter 50K/month budget."""
        try:
            yyyymm = time.strftime("%Y-%m")
            raw = price_db.get_state("cs2cap_calls_month")
            if raw:
                saved_month, count_str = raw.split(":", 1)
                count = int(count_str)
            else:
                saved_month, count = yyyymm, 0
            if saved_month != yyyymm:
                saved_month = yyyymm
                count = 0
            count += 1
            price_db.save_state("cs2cap_calls_month", f"{saved_month}:{count}")
            # Soft warning thresholds (Starter = 50K)
            if count >= 45000:
                logger.warning("[CS2Cap] Monthly usage: 45K+/50K (90%+) — critical")
            elif count >= 40000:
                logger.warning("[CS2Cap] Monthly usage: 40K+/50K (80%+) — slow down")
        except Exception:
            pass

    def rate_limit_state(self) -> dict[str, Any]:
        """
        Public read of the rate-limit state for the cache layer.

        Returns:
            {
                "monthly_used": int,       # local counter (best-effort)
                "monthly_limit": int,      # from config (50K for Starter)
                "remaining_header": int|None,  # last seen X-RateLimit-Remaining
                "per_min_remaining": int|None, # currently always None
                "is_quota_exhausted": bool,
                "cooldown_remaining_s": float,
            }
        """
        try:
            yyyymm = time.strftime("%Y-%m")
            raw = price_db.get_state("cs2cap_calls_month")
            if raw:
                saved_month, count_str = raw.split(":", 1)
                count = int(count_str) if saved_month == yyyymm else 0
            else:
                count = 0
        except Exception:
            count = 0
        tier = (getattr(Config, "CS2CAP_TIER", "starter") or "starter").lower()
        limit_map = {"free": 1000, "starter": 50000, "pro": 500000, "quant": 1000000}
        monthly_limit = limit_map.get(tier, 50000)
        cooldown_remaining = 0.0
        if self._quota_exhausted:
            cooldown_remaining = max(
                0.0, self._quota_reset_seconds - (time.time() - self._quota_exhausted_at)
            )
        return {
            "monthly_used": count,
            "monthly_limit": monthly_limit,
            "remaining_header": self._rate_remaining,
            "per_min_remaining": None,
            "is_quota_exhausted": self._quota_exhausted,
            "cooldown_remaining_s": cooldown_remaining,
        }

    def circuit_breaker_status(self) -> dict[str, Any]:
        """v12.7: Circuit breaker diagnostic snapshot (P3-5)."""
        return self._breaker.status()

    def is_price_stale(self, hash_name: str, offset: int = 0, max_age_seconds: float | None = None) -> bool:
        """
        v12.7: Check if cached price for item is stale (P4-3).

        Returns True if:
        - No cached price exists, OR
        - Cached price is older than max_age_seconds (default: MEM_TTL * 2)

        Useful for detecting when to force-refresh vs use cache.
        """
        if max_age_seconds is None:
            max_age_seconds = self.MEM_TTL * 2  # 10 minutes default

        now = time.time()
        cache_key = f"{hash_name}_{offset}"

        # Check in-memory cache
        if cache_key in self._price_cache:
            _, ts = self._price_cache[cache_key]
            if now - ts < max_age_seconds:
                return False  # Fresh

        # Check SQLite cache
        cached_ts = price_db.get_latest_price_timestamp(hash_name)
        if cached_ts is not None and (now - cached_ts) < max_age_seconds:
            return False  # Fresh in SQLite

        return True  # Stale or missing

    def cache_stats(self) -> dict[str, Any]:
        """v12.7: Cache diagnostics for health endpoint."""
        now = time.time()
        mem_fresh = sum(1 for _, ts in self._price_cache.values() if now - ts < self.MEM_TTL)
        mem_stale = sum(1 for _, ts in self._price_cache.values() if now - ts >= self.MEM_TTL)
        return {
            "memory_cache": {"fresh": mem_fresh, "stale": mem_stale, "total": len(self._price_cache)},
            "catalog_size": len(self._item_catalog),
            "catalog_age_s": round(now - self._catalog_ts, 1) if self._catalog_ts > 0 else None,
        }
