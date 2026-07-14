"""
multi_source_oracle.py — Unified price beacon.

Combines Market.CSGO, Waxpeer, CSFloat, Steam, and DMarket
to provide fair pricing without paid subscription.

Architecture:
  MultiSourceOracle
    ├── MarketCsgoOracle  (26K items, batch, free)
    ├── WaxpeerOracle     (21K items, batch, free)
    ├── CSFloatOracle     (per-item, free with key)
    ├── SteamOracle       (per-item, free)
    ├── CandleBuilder     (from DMarket snapshots)
    └── FairPriceCalculator (median with outlier removal)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.api.candle_builder import Candle, candle_builder
from src.api.fair_price_calculator import FairPriceCalculator, FairPriceResult
from src.api.market_csgo_oracle import MarketCsgoOracle
from src.api.steam_oracle import SteamOracle
from src.api.waxpeer_oracle import WaxpeerOracle

logger = logging.getLogger("MultiSourceOracle")


@dataclass
class PriceReference:
    """Multi-source price reference for a single item."""
    title: str
    marketcsgo_price: float = 0.0
    waxpeer_price: float = 0.0
    waxpeer_steam_price: float = 0.0
    csfloat_price: float = 0.0
    steam_price: float = 0.0
    dmarket_best_ask: float = 0.0
    dmarket_best_bid: float = 0.0
    sources_count: int = 0
    marketcsgo_volume: int = 0
    waxpeer_volume: int = 0

    @property
    def has_data(self) -> bool:
        return self.sources_count > 0


class MultiSourceOracle:
    """
    Unified price beacon using free marketplace APIs.
    Replaces paid oracles for pricing decisions.
    """

    def __init__(self) -> None:
        import os
        self.marketcsgo = MarketCsgoOracle()
        self.waxpeer = WaxpeerOracle()
        self.steam = SteamOracle(api_key=os.getenv("STEAM_API_KEY", ""))
        self.csfloat: Any = None  # lazy init (needs API key)
        self.candles = candle_builder
        self.fair_price = FairPriceCalculator()

        self._ref_cache: dict[str, PriceReference] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 900.0  # 15 minutes (default)

        # v15.3: Dynamic TTL based on volatility
        self._ttl_low_vol: float = 1800.0   # 30 min for stable items
        self._ttl_medium_vol: float = 900.0  # 15 min for normal items
        self._ttl_high_vol: float = 300.0    # 5 min for volatile items

        # Stats
        self._api_calls = 0
        self._cache_hits = 0

        # v15.1: Circuit breaker per source
        self._source_failures: dict[str, int] = {}
        self._source_open_until: dict[str, float] = {}
        self._failure_threshold = 5
        self._recovery_timeout = 60.0

    def _is_source_available(self, source: str) -> bool:
        """Check if source circuit breaker is closed (available)."""
        import time
        until = self._source_open_until.get(source, 0.0)
        if until > 0 and time.time() < until:
            return False
        if until > 0 and time.time() >= until:
            # Half-open: allow one attempt
            self._source_open_until[source] = 0.0
            self._source_failures[source] = 0
        return True

    def _record_source_failure(self, source: str) -> None:
        """Record source failure, open circuit if threshold reached."""
        import time
        self._source_failures[source] = self._source_failures.get(source, 0) + 1
        if self._source_failures[source] >= self._failure_threshold:
            self._source_open_until[source] = time.time() + self._recovery_timeout
            logger.warning(f"[CircuitBreaker] {source} OPEN — {self._source_failures[source]} failures")

    def _record_source_success(self, source: str) -> None:
        """Record source success, reset circuit breaker."""
        self._source_failures[source] = 0
        self._source_open_until[source] = 0.0

    def _init_csfloat(self) -> Any:
        """Lazy init CSFloat oracle (needs API key)."""
        if self.csfloat is None:
            try:
                import os

                from src.api.csfloat_oracle import CSFloatOracle
                key = os.getenv("CSFLOAT_API_KEY", "")
                self.csfloat = CSFloatOracle(api_key=key)
            except Exception:
                pass
        return self.csfloat

    async def load_all_sources(self) -> dict[str, int]:
        """Load batch data from Market.CSGO and Waxpeer."""
        results = {}
        mc, wp = await asyncio.gather(
            self.marketcsgo.load_items(),
            self.waxpeer.load_items(),
            return_exceptions=True,
        )
        results["marketcsgo"] = mc if isinstance(mc, int) else 0
        results["waxpeer"] = wp if isinstance(wp, int) else 0
        return results

    async def get_fair_price(
        self,
        title: str,
        dmarket_buy_price: float = 0.0,
    ) -> FairPriceResult:
        """
        Calculate fair sell price for an item using all available sources.
        This is the main method for the pricing beacon.

        v15.6: Each oracle has its own rate limiter (prevents 429).
        Circuit breaker per source prevents cascade failures.
        """
        now = time.time()

        # v15.3: Dynamic TTL based on volatility
        ttl = self._get_dynamic_ttl(title)

        # Check cache
        if title in self._ref_cache and now - self._cache_ts < ttl:
            self._cache_hits += 1
            ref = self._ref_cache[title]
        else:
            self._api_calls += 1

            # v15.6: Query sources with circuit breaker protection
            async def _safe_call(source: str, coro):
                """Wrap oracle call with circuit breaker."""
                if not self._is_source_available(source):
                    logger.debug(f"[Oracle] {source} circuit breaker OPEN, skipping")
                    return 0.0
                try:
                    result = await coro
                    self._record_source_success(source)
                    return result
                except Exception as e:
                    self._record_source_failure(source)
                    logger.debug(f"[Oracle] {source} failed: {e}")
                    return 0.0

            # v15.6: Sequential calls with per-oracle rate limiting
            # Each oracle has its own internal rate limiter, so parallel
            # calls will be serialized automatically
            mc_price = await _safe_call("marketcsgo", self.marketcsgo.get_item_price(title))
            wp_price = await _safe_call("waxpeer", self.waxpeer.get_item_price(title))
            st_price = await _safe_call("steam", self.steam.get_item_price(title))
            mc_vol = await _safe_call("marketcsgo_vol", self.marketcsgo.get_item_volume(title))
            wp_vol = await _safe_call("waxpeer_vol", self.waxpeer.get_item_volume(title))
            wp_steam = await _safe_call("waxpeer_steam", self.waxpeer.get_item_steam_price(title))

            # CSFloat (optional, lazy init)
            cs = self._init_csfloat()
            cs_price = await _safe_call("csfloat", cs.get_item_price(title)) if cs else 0.0

            ref = PriceReference(
                title=title,
                marketcsgo_price=mc_price if isinstance(mc_price, (int, float)) else 0.0,
                waxpeer_price=wp_price if isinstance(wp_price, (int, float)) else 0.0,
                waxpeer_steam_price=wp_steam if isinstance(wp_steam, (int, float)) else 0.0,
                csfloat_price=cs_price if isinstance(cs_price, (int, float)) else 0.0,
                steam_price=st_price if isinstance(st_price, (int, float)) else 0.0,
                sources_count=sum(1 for p in [mc_price, wp_price, cs_price, st_price] if isinstance(p, (int, float)) and p > 0),
                marketcsgo_volume=mc_vol if isinstance(mc_vol, int) else 0,
                waxpeer_volume=wp_vol if isinstance(wp_vol, int) else 0,
            )
            self._ref_cache[title] = ref

        # Build prices dict for FairPriceCalculator
        prices: dict[str, float] = {}
        volumes: dict[str, int] = {}

        if ref.marketcsgo_price > 0:
            prices["marketcsgo"] = ref.marketcsgo_price
            volumes["marketcsgo"] = ref.marketcsgo_volume
        if ref.waxpeer_price > 0:
            prices["waxpeer"] = ref.waxpeer_price
            volumes["waxpeer"] = ref.waxpeer_volume
        if ref.csfloat_price > 0:
            prices["csfloat"] = ref.csfloat_price
        if ref.steam_price > 0:
            prices["steam"] = ref.steam_price

        return self.fair_price.calculate(
            title=title,
            prices=prices,
            volumes=volumes,
            dmarket_buy_price=dmarket_buy_price,
        )

    async def get_fair_prices_batch(
        self,
        titles: list[str],
        dmarket_buy_price: float = 0.0,
    ) -> dict[str, FairPriceResult]:
        """Calculate fair prices for multiple items in parallel."""
        sem = asyncio.Semaphore(10)  # cap concurrent oracle calls

        async def _fetch_one(t: str) -> tuple[str, FairPriceResult]:
            async with sem:
                result = await self.get_fair_price(t, dmarket_buy_price)
                return t, result

        pairs = await asyncio.gather(
            *[_fetch_one(t) for t in titles],
            return_exceptions=True,
        )
        results: dict[str, FairPriceResult] = {}
        for pair in pairs:
            if isinstance(pair, tuple):
                results[pair[0]] = pair[1]
        return results

    def record_dmarket_snapshot(self, agg_prices: dict[str, Any]) -> None:
        """Record DMarket snapshot for candle building."""
        self.candles.record_snapshot(agg_prices)

    def _get_dynamic_ttl(self, title: str) -> float:
        """Get cache TTL based on item volatility from candle data.

        Stable items → longer cache (30 min)
        Volatile items → shorter cache (5 min)
        Unknown → default (15 min)
        """
        try:
            vol_data = self.candles.get_volatility(title)
            vol_pct = vol_data.get("volatility_pct", 0.0)
            if vol_pct <= 0:
                return self._ttl_medium_vol  # No data → default
            if vol_pct < 5.0:
                return self._ttl_low_vol     # Stable → 30 min
            if vol_pct > 20.0:
                return self._ttl_high_vol    # Volatile → 5 min
            return self._ttl_medium_vol      # Normal → 15 min
        except Exception:
            return self._ttl_medium_vol

    def get_candles(
        self, title: str, interval: str = "1h", count: int = 100
    ) -> list[Candle]:
        """Get OHLCV candles from DMarket snapshots."""
        return self.candles.get_candles(title, interval=interval, count=count)

    def get_volatility(self, title: str) -> dict[str, float]:
        """Get volatility metrics from DMarket candles."""
        return self.candles.get_volatility(title)

    def get_stats(self) -> dict[str, Any]:
        """Get oracle statistics."""
        return {
            "marketcsgo": self.marketcsgo.get_stats(),
            "waxpeer": self.waxpeer.get_stats(),
            "candle_stats": self.candles.get_stats(),
            "cached_refs": len(self._ref_cache),
            "api_calls": self._api_calls,
            "cache_hits": self._cache_hits,
        }

    async def close(self) -> None:
        """Close all oracle sessions."""
        await asyncio.gather(
            self.marketcsgo.close(),
            self.waxpeer.close(),
            self.steam.close(),
            return_exceptions=True,
        )
        if self.csfloat and hasattr(self.csfloat, "close"):
            await self.csfloat.close()


# Singleton
multi_source_oracle = MultiSourceOracle()
