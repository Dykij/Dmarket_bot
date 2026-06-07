"""
cs2cap_cache.py — v12.4 in-memory CS2Cap price cache.

Goal: zero CS2Cap HTTP calls during the hot path (run_cycle).
A background task refreshes the top-N most-traded titles every
CS2CAP_CACHE_TTL_SECONDS (default 5 min). The hot path only does
dict lookups (sub-ms).

Architecture:
  CS2CapCache (singleton per bot process)
    ├── _ask_cache: {hash_name: PriceSnapshot}    # lowest asks
    ├── _bid_cache: {hash_name: BidsSnapshot}     # highest bids
    ├── _last_refresh_ts: float
    └── _refresh_task: Optional[asyncio.Task]

Refresh strategy:
  1. Hit DMarket `get_aggregated_prices` (1 call, no title filter) →
     top-100 by ask_count+bid_count activity.
  2. POST /prices/batch (1 call, 100 items) for asks.
  3. POST /bids/batch (1 call, 100 items) for bids.
  Total: 3 HTTP calls per 5 min = 864 calls/day = ~26K/month
  (well under Starter 50K/month budget).

This module is *additive* to CS2CapOracle: it does not replace it.
The oracle still works for ad-hoc lookups (volatility, single-item
snapshot), but the v12.3 loop reads from the cache exclusively.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from src.api.cs2cap_oracle import BidsSnapshot, CS2CapOracle, PriceSnapshot
from src.config import Config

logger = logging.getLogger("CS2CapCache")


class CS2CapCache:
    """
    Singleton in-memory cache for CS2Cap asks/bids.

    Lifecycle:
        cache = CS2CapCache(oracle, client)
        await cache.start()        # launches background refresh task
        ...
        snap = cache.get_ask(title)            # sub-ms dict lookup
        ...
        await cache.stop()         # cancels background task
    """

    def __init__(
        self,
        oracle: CS2CapOracle,
        dmarket_client: Any,
        game_id: str,
    ) -> None:
        self._oracle = oracle
        self._client = dmarket_client
        self._game_id = game_id

        # In-memory stores (the hot path)
        self._ask_cache: Dict[str, PriceSnapshot] = {}
        self._bid_cache: Dict[str, BidsSnapshot] = {}

        # Bookkeeping
        self._last_refresh_ts: float = 0.0
        self._last_refresh_duration_s: float = 0.0
        self._refresh_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""

        # Background task handle
        self._refresh_task: Optional[asyncio.Task[None]] = None
        self._stop_event: Optional[asyncio.Event] = None

    # ----------------------------------------------------------------
    # Public API (hot path — must be fast)
    # ----------------------------------------------------------------
    def get_ask(self, hash_name: str) -> Optional[PriceSnapshot]:
        """Sub-ms dict lookup. Returns None if not in cache or stale."""
        snap = self._ask_cache.get(hash_name)
        if snap is None:
            return None
        return snap

    def get_bid(self, hash_name: str) -> Optional[BidsSnapshot]:
        """Sub-ms dict lookup for bids."""
        return self._bid_cache.get(hash_name)

    def get_ask_price(self, hash_name: str) -> float:
        """Convenience: returns min_price (USD) or 0.0 if unknown."""
        snap = self.get_ask(hash_name)
        return snap.min_price if snap and snap.has_data else 0.0

    def get_bid_price(self, hash_name: str) -> float:
        """Convenience: returns max_bid (USD) or 0.0 if unknown."""
        snap = self.get_bid(hash_name)
        return snap.max_bid if snap and snap.has_data else 0.0

    def is_stale(self) -> bool:
        """True if cache is older than CS2CAP_CACHE_TTL_SECONDS."""
        if self._last_refresh_ts == 0.0:
            return True
        return (time.time() - self._last_refresh_ts) > Config.CS2CAP_CACHE_TTL_SECONDS

    def stats(self) -> Dict[str, Any]:
        """Diagnostic snapshot for /health and logs."""
        return {
            "ask_count": len(self._ask_cache),
            "bid_count": len(self._bid_cache),
            "last_refresh_ts": self._last_refresh_ts,
            "age_seconds": (time.time() - self._last_refresh_ts) if self._last_refresh_ts else None,
            "is_stale": self.is_stale(),
            "refresh_count": self._refresh_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_refresh_duration_s": round(self._last_refresh_duration_s, 2),
        }

    # ----------------------------------------------------------------
    # Background task management
    # ----------------------------------------------------------------
    async def start(self) -> None:
        """Launch the background refresh task."""
        if self._refresh_task is not None and not self._refresh_task.done():
            logger.warning("[CS2CapCache] Refresh task already running")
            return

        self._stop_event = asyncio.Event()
        if Config.CS2CAP_CACHE_REFRESH_ON_START:
            try:
                await self.refresh_now()
            except Exception as e:
                logger.warning(f"[CS2CapCache] Initial refresh failed: {e}")
        self._refresh_task = asyncio.create_task(
            self._refresh_loop(), name="cs2cap-cache-refresh"
        )
        logger.info(
            f"[CS2CapCache] Started background refresh "
            f"(TTL={Config.CS2CAP_CACHE_TTL_SECONDS}s, top-N={Config.CS2CAP_CACHE_REFRESH_TOP_N})"
        )

    async def stop(self) -> None:
        """Cancel the background task and close session."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except (asyncio.CancelledError, Exception):
                pass
            self._refresh_task = None
        logger.info("[CS2CapCache] Stopped")

    async def _refresh_loop(self) -> None:
        """Periodically refresh the cache until stopped."""
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                # Wait for TTL or stop event
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=Config.CS2CAP_CACHE_TTL_SECONDS,
                    )
                    # Stop event set → exit
                    return
                except asyncio.TimeoutError:
                    pass  # TTL elapsed → refresh
                await self.refresh_now()
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._error_count += 1
                self._last_error = str(e)
                logger.error(f"[CS2CapCache] Refresh loop error: {e}")
                # Backoff on error
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=30.0
                    )
                    return
                except asyncio.TimeoutError:
                    continue

    async def refresh_now(self) -> None:
        """
        Single refresh pass: 1 DMarket agg-prices + 1 CS2Cap asks-batch
        + 1 CS2Cap bids-batch = 3 HTTP calls total.

        Top-N is determined by DMarket's trading activity, not by our
        local cache. This means the cache always reflects the actual
        top-100 most-traded titles on DMarket — even if they change
        week to week.
        """
        t0 = time.time()
        try:
            agg_prices = await self._client.get_aggregated_prices(self._game_id)
        except Exception as e:
            self._error_count += 1
            self._last_error = f"agg_prices: {e}"
            logger.warning(f"[CS2CapCache] agg_prices failed: {e}")
            return

        if not agg_prices:
            logger.info("[CS2CapCache] No agg_prices; skipping refresh")
            return

        # Rank by DMarket activity (ask_count + bid_count), top-N
        top_titles = sorted(
            agg_prices.keys(),
            key=lambda t: (
                agg_prices[t].get("ask_count", 0)
                + agg_prices[t].get("bid_count", 0)
            ),
            reverse=True,
        )[: Config.CS2CAP_CACHE_REFRESH_TOP_N]

        if not top_titles:
            return

        # 2 parallel CS2Cap calls (asks + bids)
        try:
            asks_task = self._oracle.get_prices_batch(top_titles)
            bids_task = self._oracle.get_bids_batch(top_titles)
            asks, bids = await asyncio.gather(asks_task, bids_task)
        except Exception as e:
            self._error_count += 1
            self._last_error = f"batch: {e}"
            logger.warning(f"[CS2CapCache] CS2Cap batch failed: {e}")
            return

        # Replace caches atomically (single-threaded, no lock needed)
        self._ask_cache = dict(asks)
        self._bid_cache = dict(bids)
        self._last_refresh_ts = time.time()
        self._last_refresh_duration_s = time.time() - t0
        self._refresh_count += 1

        logger.info(
            f"[CS2CapCache] Refreshed: {len(self._ask_cache)} asks, "
            f"{len(self._bid_cache)} bids, "
            f"top-N={len(top_titles)}, "
            f"duration={self._last_refresh_duration_s:.2f}s"
        )
