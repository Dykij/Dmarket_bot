"""
core.py — The main SnipingLoop orchestrator.

Composes:
    _PricingMixin    (float premium, low-fee cache)
    _ResaleMixin     (auto_resale, reprice_unsold_offers)
    _InventoryMixin  (sync_inventory_statuses, skip_if_locked)
    _SandboxMixin    (DRY_RUN helpers: competition, latency, errors)
    _FilterMixin     (per-item candidate evaluation)
    _ExecutionMixin  (instant-buy execution)

Provides the public entry points:
    - SnipingLoop.__init__
    - start             — the main async loop
    - run_cycle         — the actual scan + buy + record pipeline
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from typing import Any, Dict, List

from src.api.cs2cap_oracle import RateLimitException
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.cs2cap_cache import CS2CapCache
from src.api.oracle_factory import OracleFactory
from src.analytics.rare_valuation import RareValuationEngine
from src.analytics.stickers_evaluator import StickerEvaluator
from src.config import Config
from src.core.event_shield import event_shield
from src.core.sandbox_scenarios import scenario_engine
from src.core.target_sniping.execution import _ExecutionMixin
from src.core.target_sniping.filter import _FilterMixin
from src.core.target_sniping.inventory import _InventoryMixin
from src.core.target_sniping.pricing import _PricingMixin
from src.core.target_sniping.resale import _ResaleMixin
from src.core.target_sniping.sandbox import _SandboxMixin
from src.db.price_history import price_db
from src.risk.liquidity_manager import LiquidityManager

logger = logging.getLogger("SnipingBot")


class SnipingLoop(  # type: ignore[misc]
    _PricingMixin,
    _ResaleMixin,
    _InventoryMixin,
    _SandboxMixin,
    _FilterMixin,
    _ExecutionMixin,
):
    """
    Main Autonomous Loop for DMarket Sniping & Re-sale (v12.0 Intra-Spread).
    """

    def __init__(self, client: DMarketAPIClient) -> None:
        self.client = client
        self.valuation = RareValuationEngine()
        self.stickers = StickerEvaluator()
        self.liquidity = LiquidityManager()
        self.inventory_mgr = None

        from src.config import Config

        self.target_games = [Config.GAME_ID]

        self.deep_scan_counter = 0
        self.buy_budget = Config.MAX_PRICE_USD
        self.running = False
        self.empty_page_count = 0
        self.resale_cycle_limit = 10
        self.reprice_counter = 0

        # v12.4: In-memory CS2Cap cache (initialised in start())
        self.cs2cap_cache: Optional[CS2CapCache] = None

    async def _fetch_cheapest_listings(
        self, game_id: str, titles: List[str]
    ) -> List[Dict[str, Any]]:
        """
        v12.3: For each top-traded title, fetch the N cheapest DMarket
        listings and return a list of buy candidates (one per title: the
        cheapest listing available).

        This replaces the v12.0 page-of-100-listings scan, which was
        dominated by overpriced listings (a single page contains random
        listings, not necessarily the cheapest). With the agg-prices-first
        approach, we know which items are interesting (high market
        activity, wide bid-ask spread) and then find the actual cheapest
        listing for each.

        Returns: list of listing dicts (same shape as
        get_market_items_v2["objects"]), ready for the existing per-item
        filter.
        """
        if not titles:
            return []

        # Parallel fetch: DMarket market-items endpoint has 600 RPM, so
        # 20 titles in parallel is safe.
        async def _fetch_one(title: str) -> List[Dict[str, Any]]:
            try:
                resp = await self.client.get_market_items_v2(
                    game_id,
                    limit=Config.LISTINGS_FETCH_LIMIT,
                    title=title,
                )
                return resp.get("objects", [])
            except Exception as e:
                logger.debug(f"Listing fetch failed for {title!r}: {e}")
                return []

        results = await asyncio.gather(*[_fetch_one(t) for t in titles])

        # Pick the cheapest listing per title. If multiple titles return
        # the same listing object (rare), dedupe.
        cheapest: List[Dict[str, Any]] = []
        seen_ids = set()
        for title, listings in zip(titles, results):
            if not listings:
                continue
            sorted_by_price = sorted(
                listings,
                key=lambda x: int(x.get("price", {}).get("USD", 0)),
            )
            for cand in sorted_by_price:
                item_id = cand.get("itemId", "")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                cheapest.append(cand)
                break  # only need the cheapest per title

        logger.info(
            f"[v12.3 SCAN] top_titles={len(titles)} "
            f"fetched_listings={sum(len(r) for r in results)} "
            f"buy_candidates={len(cheapest)}"
        )
        return cheapest

    @property
    def min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier (v7.8)."""
        from src.config import Config

        return (Config.MIN_SPREAD_PCT / 100.0) * event_shield.get_margin_multiplier()

    async def start(self) -> None:
        self.running = True
        logger.info(f"Starting DMarket Intra-Spread Loop v12.4 | Targets: {self.target_games}")

        gc.disable()

        # v12.4: launch in-memory CS2Cap cache (background refresh task)
        await self._init_cs2cap_cache()

        try:
            while self.running:
                for game_id in self.target_games:
                    await self.run_cycle(game_id)

                gc.collect()

                # Phase 4: honour Config.SCAN_INTERVAL (was hardcoded 5s —
                # would burn DMarket + CS2Cap quotas in minutes on Starter).
                from src.config import Config

                if self.empty_page_count > 0:
                    delay = min(Config.SCAN_INTERVAL * self.empty_page_count, 300)
                    logger.info(f"Market appears quiet. Sleeping for {delay}s...")
                else:
                    delay = Config.SCAN_INTERVAL

                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("Sniping loop cancelled.")
        except Exception as e:
            logger.error(f"Critical error in sniping cycle: {e}")
            await asyncio.sleep(30)
        finally:
            if self.cs2cap_cache is not None:
                await self.cs2cap_cache.stop()
            await OracleFactory.close_all()
            if self.client:
                await self.client.close()

    async def _init_cs2cap_cache(self) -> None:
        """
        v12.4: initialise the in-memory CS2Cap cache.

        The cache is fed by a background task (CS2CapCache.start) that
        refreshes the top-100 most-traded titles every CS2CAP_CACHE_TTL_SECONDS.
        The hot path (run_cycle) reads from the cache, so no per-cycle
        CS2Cap HTTP calls are made.
        """
        oracle = OracleFactory.get_oracle(Config.GAME_ID)
        if oracle is None:
            logger.warning(
                "[v12.4] No oracle available for CS2Cap cache; will fall back to per-cycle batch."
            )
            return
        self.cs2cap_cache = CS2CapCache(
            oracle=oracle,
            dmarket_client=self.client,
            game_id=Config.GAME_ID,
        )
        await self.cs2cap_cache.start()

    async def run_cycle(self, game_id: str) -> None:
        """
        v12.0 Strategy A: Intra-DMarket Spread.
        1. Scan 50 items
        2. Get aggregated prices (best_bid, best_ask)
        3. Filter: 5%+ spread
        4. Validate with CS2Cap oracle
        5. Buy at ask, list at bid - 0.01
        6. v12.2: Sync asset statuses (trade_protected, reverted)
        """
        try:
            self.deep_scan_counter += 1
            self.reprice_counter += 1
            is_fresh_cycle = self.deep_scan_counter % 5 == 0
            cursor_key = f"dmarket_cursor_{game_id}"

            # v12.2: Sync inventory statuses every 20 cycles
            if self.deep_scan_counter % 20 == 0:
                await self._sync_inventory_statuses(game_id)

            if is_fresh_cycle:
                logger.info(f"FRESH CYCLE (Page 1) for {game_id} to catch new listings.")
                current_cursor = ""
            else:
                current_cursor = price_db.get_state(cursor_key) or ""

            logger.info(f"Scanning {game_id} (Cursor: {current_cursor or 'START'})...")
            current_balance = await self.client.get_real_balance()
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                return

            # --- Step 1: Scan market (v12.3: aggregated-prices-first) ---
            # v12.0 used `get_market_items_v2` (page of 100 listings, sorted
            # by recency, not price). That means most listings in the page
            # were OVERPRICED vs. market best_ask, so cross-market arbs
            # detected (e.g. "buy on DM at $0.06, sell on Steam for $0.11")
            # couldn't be executed — the bot would only see the $1.00
            # listing, not the $0.06 one.
            #
            # v12.3 fix: use `get_aggregated_prices` (no title filter) to
            # get DMarket's top-100 most-traded items WITH their best_bid
            # and best_ask. Then for each top item, fetch the actual
            # cheapest listing via `get_market_items_v2(title=...)` so we
            # can buy at the real market ask (best_ask) instead of an
            # arbitrary page listing.
            try:
                await self._simulate_network_latency()
                self._maybe_inject_error("get_aggregated_prices_top")
                agg_prices = await self.client.get_aggregated_prices(game_id)
            except Exception as e:
                logger.warning(f"get_aggregated_prices (top) failed: {e}")
                return

            if not agg_prices:
                logger.warning(f"No aggregated prices for {game_id}; skipping cycle.")
                return

            # v12.3: Pick top N items by market volume (ask_count + bid_count)
            # to keep the cycle under ~10s. N=20 → 20 listing fetches
            # (~2s at 10 RPS market-items limit).
            top_titles = sorted(
                agg_prices.keys(),
                key=lambda t: (
                    agg_prices[t].get("ask_count", 0)
                    + agg_prices[t].get("bid_count", 0)
                ),
                reverse=True,
            )[: Config.AGG_SCAN_TOP_N]

            # Fetch the actual cheapest listing for each top item (parallel)
            await self._simulate_network_latency()
            self._maybe_inject_error("get_market_items_per_title")
            items = await self._fetch_cheapest_listings(
                game_id=game_id, titles=top_titles
            )
            next_cursor = ""  # cursor-based pagination is replaced by agg-prices scan

            if not items:
                self.empty_page_count += 1
                if next_cursor and not is_fresh_cycle:
                    logger.warning(f"Empty deep page for {game_id}. Resetting.")
                    price_db.save_state(cursor_key, "")
                return

            self.empty_page_count = 0

            if not is_fresh_cycle:
                if next_cursor:
                    price_db.save_state(cursor_key, next_cursor)
                else:
                    price_db.save_state(cursor_key, "")

            # --- Step 2: agg_prices already fetched in Step 1 (v12.3) ---
            # In v12.0 we re-fetched agg_prices for the listing-page titles
            # here. In v12.3 we already have agg_prices (top-100 most-traded
            # items from Step 1), so we just need the per-listing titles
            # to look up fees.

            # --- Step 3: Pre-fetch bulk fees ---
            candidate_item_ids = [
                item.get("itemId")
                for item in items
                if item.get("title")
                and item.get("itemId")
                and int(item.get("price", {}).get("USD", 0)) > 0
            ]

            bulk_fees: Dict[str, float] = {}
            if candidate_item_ids:
                bulk_fees = await self.client.get_item_fee_bulk(game_id, candidate_item_ids)

            # --- Step 4: Filter and validate (delegated) ---
            current_margin = self.min_profit_margin
            instant_buys: List[Dict[str, Any]] = []

            # v12.4: Read CS2Cap asks/bids from in-memory cache (P0-B).
            # The cache is refreshed by a background task every
            # CS2CAP_CACHE_TTL_SECONDS (default 5 min). Per-cycle HTTP
            # calls to CS2Cap are eliminated — validation is a sub-ms
            # dict lookup. Falls back to legacy per-cycle batch if the
            # cache is unavailable (e.g. oracle import failed).
            cs_snapshots: Dict[str, Any] = {}
            cs_bids: Dict[str, Any] = {}
            cache_used = False
            if self.cs2cap_cache is not None and not self.cs2cap_cache.is_stale():
                cache_used = True
                # Cap ranker at items we can actually afford to avoid wasting
                # CS2Cap quota on $1000 Karambits we can't buy. We use
                # min(balance, MAX_SNIPING_PRICE_USD) — the per-item 5% risk
                # check happens later in _evaluate_candidate.
                max_price_cap = min(current_balance, Config.MAX_SNIPING_PRICE_USD)
                ranked = self._rank_candidates_by_spread(
                    items, agg_prices, max_price_usd=max_price_cap
                )
                top_titles = [
                    t for t, _ in ranked[: Config.CS2CAP_TOP_K_VALIDATE]
                ]
                for t in top_titles:
                    ask = self.cs2cap_cache.get_ask(t)
                    bid = self.cs2cap_cache.get_bid(t)
                    if ask is not None:
                        cs_snapshots[t] = ask
                    if bid is not None:
                        cs_bids[t] = bid
                if top_titles:
                    cache_stats = self.cs2cap_cache.stats()
                    logger.info(
                        f"[CS2CapCache HIT] top_titles={len(top_titles)} "
                        f"snapshots={len(cs_snapshots)} bids={len(cs_bids)} "
                        f"age={cache_stats['age_seconds']:.0f}s "
                        f"refreshes={cache_stats['refresh_count']}"
                    )
            elif oracle is not None and Config.CS2CAP_SELECTIVE_MODE and items:
                # Legacy path: cache not available (e.g. CS2Cap API key missing)
                max_price_cap = min(current_balance, Config.MAX_SNIPING_PRICE_USD)
                ranked = self._rank_candidates_by_spread(
                    items, agg_prices, max_price_usd=max_price_cap
                )
                top_titles = [
                    t for t, _ in ranked[: Config.CS2CAP_TOP_K_VALIDATE]
                ]
                if top_titles and hasattr(oracle, "get_prices_batch"):
                    try:
                        asks_task = oracle.get_prices_batch(top_titles)
                        bids_task = oracle.get_bids_batch(top_titles) if hasattr(oracle, "get_bids_batch") else None
                        cs_snapshots = await asks_task
                        if bids_task is not None:
                            cs_bids = await bids_task
                        logger.info(
                            f"CS2Cap selective validation (legacy path): "
                            f"{len(cs_snapshots)}/{len(top_titles)} asks, "
                            f"{len(cs_bids)}/{len(top_titles)} bids"
                        )
                    except Exception as e:
                        logger.debug(f"CS2Cap batch failed (non-fatal): {e}")
                        cs_snapshots = {}
                        cs_bids = {}
            if not cache_used and self.cs2cap_cache is not None:
                logger.debug(
                    f"[CS2CapCache MISS] cache_stale={self.cs2cap_cache.is_stale()} "
                    f"ask_count={len(self.cs2cap_cache._ask_cache)}"
                )

            for item in items:
                # Reload candidate_item_ids was unused; reuse
                if not item.get("title") or not item.get("itemId"):
                    continue
                candidate = await self._evaluate_candidate(
                    item=item,
                    game_id=game_id,
                    oracle=oracle,
                    agg_prices=agg_prices,
                    bulk_fees=bulk_fees,
                    current_balance=current_balance,
                    current_margin=current_margin,
                    cs_snapshots=cs_snapshots,
                    cs_bids=cs_bids,
                )
                if candidate is not None:
                    instant_buys.append(candidate)

            # --- Step 5: Execute instant buys (delegated) ---
            if instant_buys:
                await self._execute_instant_buys(
                    instant_buys=instant_buys, current_balance=current_balance
                )

            if self.deep_scan_counter % self.resale_cycle_limit == 0:
                await self.auto_resale(game_id)

            # Periodic repricing
            if self.reprice_counter % 60 == 0:  # Every ~60 cycles
                await self.reprice_unsold_offers(game_id)

            # v12.0 Phase 1.1: Refresh low-fee cache every 100 cycles
            if self.deep_scan_counter % 100 == 0:
                await self._refresh_low_fee_cache(game_id)

            # Equity report
            equity = price_db.get_total_equity(current_balance)
            logger.info(
                f"[EQUITY] Cash: ${equity['cash']:.2f} | "
                f"Assets: ${equity['assets']:.2f} | "
                f"TOTAL: ${equity['total']:.2f} (Items: {equity['count']})"
            )

            # v12.4: Periodic diagnostic snapshot (every 10 cycles)
            if self.deep_scan_counter % 10 == 0:
                cache_stats = (
                    self.cs2cap_cache.stats()
                    if self.cs2cap_cache is not None
                    else {"ask_count": 0, "bid_count": 0, "is_stale": True}
                )
                cb_stats = self.client.circuit_breaker_status()
                logger.info(
                    f"[v12.4 DIAG] CS2Cap cache: {cache_stats['ask_count']} asks, "
                    f"{cache_stats['bid_count']} bids, "
                    f"stale={cache_stats['is_stale']}, "
                    f"age={cache_stats.get('age_seconds')}s, "
                    f"refreshes={cache_stats['refresh_count']} | "
                    f"CB: state={cb_stats['state']}, "
                    f"opens={cb_stats['total_opens']}, "
                    f"fails={cb_stats['consecutive_failures']}"
                )

            if self.deep_scan_counter % 200 == 0:
                price_db.cleanup_old_targets()

        except Exception as e:
            # v12.4: Distinguish circuit-breaker opens (expected) from
            # real cycle failures (unexpected). Breaker open means
            # DMarket is rate-limiting or down; the outer loop's
            # SCAN_INTERVAL sleep will throttle us back to normal.
            from src.api.dmarket_api_client.backoff import CircuitOpenError

            if isinstance(e, CircuitOpenError):
                logger.warning(
                    f"[v12.4] Cycle paused — {e.breaker_name} circuit OPEN "
                    f"({e.cooldown_remaining:.1f}s remaining)"
                )
            elif "RateLimit" not in str(e):
                logger.error(f"Cycle failed for {game_id}: {e}")


if __name__ == "__main__":
    pass
