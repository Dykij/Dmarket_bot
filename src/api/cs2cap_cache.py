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
import os
import time
from typing import Any, Dict, Optional

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

        # O1: Rate-limit guard state
        self._quota_skipped_count: int = 0
        self._last_quota_warning_ts: float = 0.0

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
        rl: Dict[str, Any] = {}
        try:
            rl = self._oracle.rate_limit_state()
        except Exception:
            rl = {}
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
            # O1: rate-limit awareness
            "quota_skipped_count": self._quota_skipped_count,
            "monthly_used": rl.get("monthly_used", 0),
            "monthly_limit": rl.get("monthly_limit", 50000),
            "remaining_header": rl.get("remaining_header"),
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

        # v12.5: Catalog warmup is OFF by default.
        # Loading 38K items = ~380 API calls per restart = ~11.5K/month
        # of a 50K Starter budget (23%!) just to be able to resolve
        # hash_name → item_id for items we will never trade.
        # The catalog is only needed by get_item_id() which is rarely used;
        # the per-cycle hot path uses aggregated_prices (DMarket) + prices/batch
        # (CS2Cap) and doesn't need the catalog. Skipping warmup saves quota
        # for actual price lookups.
        # Override with CS2CAP_CATALOG_WARMUP_ON_START=1 if your strategy
        # relies on get_item_id().
        if Config.CS2CAP_CATALOG_WARMUP_ON_START:
            self._catalog_warmup_task = asyncio.create_task(
                self._warm_catalog_bg(), name="cs2cap-catalog-warmup"
            )
        else:
            logger.info(
                "[CS2CapCache] Catalog warmup SKIPPED (default) to save ~380 "
                "CS2Cap calls/restart. Set CS2CAP_CATALOG_WARMUP_ON_START=1 "
                "to re-enable."
            )

        if Config.CS2CAP_CACHE_REFRESH_ON_START:
            try:
                await self.refresh_now()
            except Exception as e:
                logger.warning(f"[CS2CapCache] Initial refresh failed: {e}", exc_info=True)
        self._refresh_task = asyncio.create_task(
            self._refresh_loop(), name="cs2cap-cache-refresh"
        )
        logger.info(
            f"[CS2CapCache] Started background refresh "
            f"(TTL={Config.CS2CAP_CACHE_TTL_SECONDS}s, top-N={Config.CS2CAP_CACHE_REFRESH_TOP_N})"
        )

    async def _warm_catalog_bg(self) -> None:
        """
        O4: Background catalog warm-up. Loaded on a separate task so
        the main loop can start trading immediately. Errors are
        logged but never propagate (catalog loading is best-effort).
        """
        try:
            t0 = time.time()
            count = await self._oracle.load_catalog()
            duration = time.time() - t0
            logger.info(
                f"[CS2CapCache] Catalog warm-up: {count} items "
                f"loaded in {duration:.2f}s"
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[CS2CapCache] Catalog warm-up failed: {e}", exc_info=True)

    async def _warm_catalog(self) -> None:
        """
        O4 (synchronous variant, kept for tests that need to await
        the result): Pre-load the CS2Cap item catalog
        (market_hash_name → item_id) on bot startup. Returns the
        number of items loaded.
        """
        return await self._warm_catalog_bg()

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
        # Also cancel catalog warmup if it's still running
        if hasattr(self, '_catalog_warmup_task') and self._catalog_warmup_task is not None:
            self._catalog_warmup_task.cancel()
            try:
                await self._catalog_warmup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._catalog_warmup_task = None
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
                logger.error(f"[CS2CapCache] Refresh loop error: {e}", exc_info=True)
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

        O1 Rate-limit guard: before any CS2Cap call, check the oracle's
        rate-limit state. If the monthly quota is >80% used (or the
        oracle has been blocked by a 429), skip the refresh and keep
        the existing cache (better stale than rate-limited).
        """
        t0 = time.time()

        # O1: Pre-flight rate-limit check
        guard = self._check_rate_limit_guard()
        if not guard["can_proceed"]:
            self._quota_skipped_count += 1
            logger.warning(
                f"[CS2CapCache] Refresh SKIPPED — {guard['reason']} "
                f"(skip #{self._quota_skipped_count})"
            )
            return

        try:
            agg_prices = await self._client.get_aggregated_prices(self._game_id)
        except Exception as e:
            self._error_count += 1
            self._last_error = f"agg_prices: {e}"
            logger.warning(f"[CS2CapCache] agg_prices failed: {e}", exc_info=True)
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
            asks_result, bids_result = await asyncio.gather(
                asks_task, bids_task, return_exceptions=True
            )
            if isinstance(asks_result, Exception) or isinstance(bids_result, Exception):
                self._error_count += 1
                err = asks_result if isinstance(asks_result, Exception) else bids_result
                self._last_error = f"batch: {err}"
                logger.warning(f"[CS2CapCache] CS2Cap batch failed: {err}", exc_info=True)
                return
            asks, bids = asks_result, bids_result
        except Exception as e:
            self._error_count += 1
            self._last_error = f"batch: {e}"
            logger.warning(f"[CS2CapCache] CS2Cap batch failed: {e}", exc_info=True)
            return

        # O1: Post-flight check — if oracle reported quota exhaustion
        # during the batch calls, roll back the cache update.
        post = self._check_rate_limit_guard()
        if not post["can_proceed"]:
            logger.warning(
                f"[CS2CapCache] Cache NOT updated — quota exhausted mid-refresh "
                f"({post['reason']})"
            )
            return

        # Replace caches atomically (single-threaded, no lock needed)
        self._ask_cache = dict(asks)
        self._bid_cache = dict(bids)
        self._last_refresh_ts = time.time()
        self._last_refresh_duration_s = time.time() - t0
        self._refresh_count += 1

        # O1: Surface current monthly usage in logs (every 10th refresh)
        if self._refresh_count % 10 == 0:
            rl = self._oracle.rate_limit_state()
            logger.info(
                f"[CS2CapCache] Rate limit: used={rl['monthly_used']}/"
                f"{rl['monthly_limit']} "
                f"({rl['monthly_used']*100/max(1,rl['monthly_limit']):.1f}%)"
            )

        logger.info(
            f"[CS2CapCache] Refreshed: {len(self._ask_cache)} asks, "
            f"{len(self._bid_cache)} bids, "
            f"top-N={len(top_titles)}, "
            f"duration={self._last_refresh_duration_s:.2f}s"
        )

    def _check_rate_limit_guard(self) -> Dict[str, Any]:
        """
        O1: Pre/post-flight rate-limit check.

        Returns {"can_proceed": bool, "reason": str}.

        Rules:
        - If oracle is already in 429 cooldown, skip (always)
        - If monthly_used > 95% of limit, skip (always)
        - If monthly_used > 80% AND per_min_remaining < 5, skip
        - If monthly_used > 80%, log warning (rate-limited to 1/refresh)
        - Otherwise proceed

        Note: CS2Cap returns X-RateLimit-Remaining as PER-MINUTE calls
        remaining (not monthly). We track monthly usage locally
        via _increment_monthly_counter. The per-minute header is
        used as a real-time guard for the next 60s window.
        """
        try:
            rl = self._oracle.rate_limit_state()
        except Exception as e:
            return {"can_proceed": True, "reason": f"oracle state unavailable: {e}"}

        # Hard block: 429 cooldown
        if rl.get("is_quota_exhausted"):
            return {
                "can_proceed": False,
                "reason": (
                    f"429 cooldown active "
                    f"({rl.get('cooldown_remaining_s', 0):.0f}s remaining)"
                ),
            }

        monthly_limit = max(1, rl.get("monthly_limit", 50000))
        used = rl.get("monthly_used", 0)
        used_pct = (used * 100.0) / monthly_limit

        # Hard block: 95%+ of monthly quota
        if used_pct >= 95.0:
            return {
                "can_proceed": False,
                "reason": f"monthly quota at {used_pct:.1f}% (used {used}/{monthly_limit})",
            }

        # Soft warning: 80-95% (log every 5 minutes, not every refresh)
        if used_pct >= 80.0:
            now = time.time()
            if now - self._last_quota_warning_ts > 300:
                self._last_quota_warning_ts = now
                logger.warning(
                    f"[CS2CapCache] Quota at {used_pct:.1f}% "
                    f"({used}/{monthly_limit}). Continuing, but monitor."
                )

        # Per-minute guard: if the server says we have <5 calls left
        # in the current minute window, skip (proactive cooldown).
        rem = rl.get("remaining_header")
        if rem is not None and rem < 5:
            return {
                "can_proceed": False,
                "reason": f"per-minute rate limit near: {rem} calls left this window",
            }

        return {"can_proceed": True, "reason": "ok"}
