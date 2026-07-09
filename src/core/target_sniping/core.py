"""
core.py — The main SnipingLoop orchestrator.

Composes:
    _PricingMixin    (float premium, low-fee cache)
    _ResaleMixin     (auto_resale, reprice_unsold_offers)
    _InventoryMixin  (sync_inventory_statuses, skip_if_locked)
    _SandboxMixin    (DRY_RUN helpers: competition, latency, errors)
    _ScannerMixin    (parallel listing fetcher, float/phase scan)
    _FilterMixin     (per-item candidate evaluation)
    _ExecutionMixin  (instant-buy execution)

Provides the public entry points:
    - SnipingLoop.__init__
    - start             — the main async loop
    - run_cycle         — the actual scan + buy + record pipeline
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from src.analytics.rare_valuation import RareValuationEngine
from src.analytics.stickers_evaluator import StickerEvaluator
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.core.daily_briefing import DailyBriefingScheduler
from src.core.event_shield import event_shield
from src.core.target_sniping.execution import _ExecutionMixin
from src.core.target_sniping.filter import _FilterMixin
from src.core.target_sniping.inventory import _InventoryMixin
from src.core.target_sniping.pricing import _PricingMixin
from src.core.target_sniping.resale import _ResaleMixin
from src.core.target_sniping.sandbox import _SandboxMixin
from src.core.target_sniping.scanner import _ScannerMixin
from src.core.target_sniping.scheduler import _SchedulerMixin
from src.core.target_sniping.telemetry import _TelemetryMixin
from src.db.price_history import price_db
from src.risk.error_reporter import ErrorReporter
from src.risk.fatal_errors import classify
from src.risk.liquidity_manager import LiquidityManager
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class SnipingLoop(  # type: ignore[misc]
    _SchedulerMixin,
    _TelemetryMixin,
    _PricingMixin,
    _ResaleMixin,
    _InventoryMixin,
    _SandboxMixin,
    _ScannerMixin,
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
        self.inventory_mgr: Any = None

        from src.config import Config

        self.target_games = [Config.GAME_ID]

        self.deep_scan_counter = 0
        self.buy_budget = Config.MAX_PRICE_USD
        self.running = False
        self.empty_page_count = 0
        self.resale_cycle_limit = 1  # v13.0: resale every cycle (instant)
        self.reprice_counter = 0

        # v15.0: MultiSource oracle (Market.CSGO + Waxpeer + CSFloat + Steam)
        self.multi_source_oracle: Any | None = None

        # v12.5: Risk orchestration + self-reflection
        from src.analytics.self_reflection import self_reflection
        from src.risk.pump_detector import PumpDetector
        from src.risk.risk_manager import RiskManager
        self.self_reflection = self_reflection
        # v12.6: Pump detector — blocks FOMO buys on items with sudden
        # price spikes (>PUMP_THRESHOLD_PCT in 1h, default 15%). The
        # detector reads price_db (already populated by the sniping loop)
        # and shares the Telegram notifier. Late-binding of price_db is
        # done in start() once everything is wired.
        self.pump_detector = PumpDetector(
            price_db=price_db,
            notifier=notifier,
        )
        # v12.7: Restore blacklist from disk (survives watchdog restarts).
        # Done at __init__ time because price_db is the same instance the
        # detector was constructed with — no async needed.
        try:
            restored = self.pump_detector.restore_from_disk()
            if restored > 0:
                logger.info(
                    f"[v12.7] PumpDetector: restored {restored} blacklist "
                    f"entries from persistent store"
                )
        except Exception as e:
            logger.warning(f"[v12.7] PumpDetector restore_from_disk failed: {e} — blacklist treated as empty")
        self.risk = RiskManager(
            daily_loss_limit_usd=float(os.getenv("MAX_DAILY_LOSS_USD", "10.00")),
            daily_trade_limit=int(os.getenv("MAX_DAILY_TRADES", "200")),
            max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "15.0")),
            soft_halt_drawdown_pct=float(os.getenv("SOFT_HALT_DRAWDOWN_PCT", "5.0")),
            pump_detector=self.pump_detector,
        )

        # v12.5: Daily briefing scheduler (started in start())
        self.briefing_scheduler: DailyBriefingScheduler | None = None

        # Rate-limit diagnostics
        self._last_quota_warn: float = 0.0
        self._last_milestone: float = 0.0

    @property
    async def get_min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier + volatility regime adjustment (v12.7)."""
        from src.config import Config

        base = Config.MIN_SPREAD_PCT
        # Apply self-reflection adjustment (from trade history analysis)
        reflection = self.self_reflection._cached_result
        adjusted = self.self_reflection.get_adjusted_spread(base, reflection)
        # Apply volatility regime adjustment (from recent market conditions)
        vol_adj = await self.self_reflection.get_volatility_regime_adjustment()
        adjusted += vol_adj
        # Ensure minimum floor
        adjusted = max(1.0, adjusted)
        return (adjusted / 100.0) * event_shield.get_margin_multiplier()

    async def run_cycle(self, game_id: str) -> None:
        """
        v12.0 Strategy A: Intra-DMarket Spread.
        1. Scan 50 items
        2. Get aggregated prices (best_bid, best_ask)
        3. Filter: 5%+ spread
        4. Validate with MultiSource oracle
        5. Buy at ask, list at bid - 0.01
        6. v12.2: Sync asset statuses (trade_protected, reverted)
        """
        try:
            # v12.7: Mark cycle as in-progress (early-return safe). This
            # makes /healthz report real cycle activity even when the
            # cycle returns early due to no aggregated prices. The
            # full metrics (equity, halts, pump) are updated further
            # down at the end of a successful cycle.
            try:
                from src.utils.health_server import health_state
                health_state.mark_cycle(0.0, 0.0, 0.0)
            except Exception as e:
                logger.debug(f"[HEALTH] mark_cycle failed: {e}")

            # v12.7: Clear per-cycle oracle price cache (P1-5).
            self._clear_oracle_cache()

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
            # v14.4: Reserve buffer — effective balance for trading
            effective_balance = max(0.0, current_balance - Config.BALANCE_RESERVE_USD)
            # v14.4: Dynamic max snipe price (Half Kelly: max(floor, eff_balance * fraction))
            dynamic_max_price = max(
                Config.MAX_SNIPING_PRICE_FLOOR,
                effective_balance * Config.MAX_SNIPING_PRICE_BALANCE_FRACTION,
            )
            # Override with env if explicitly set (backward compat)
            if os.getenv("MAX_SNIPING_PRICE_USD"):
                dynamic_max_price = Config.MAX_SNIPING_PRICE_USD
            dynamic_max_price = min(dynamic_max_price, effective_balance)
            logger.debug(
                f"[v14.4 BALANCE] raw=${current_balance:.2f} "
                f"reserve=${Config.BALANCE_RESERVE_USD} "
                f"effective=${effective_balance:.2f} "
                f"max_item=${dynamic_max_price:.2f}"
            )
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                return

            # v14.4: Capital velocity check — pause buying if capital locked in trades
            if Config.CAPITAL_VELOCITY_ENABLED and effective_balance > 0:
                try:
                    weekly_sales = price_db.get_virtual_inventory_weekly_sales()
                    locked_value = price_db.get_virtual_inventory_locked_value()
                    # With no sales history and no locked inventory, velocity is
                    # undefined; don't block the very first purchases.
                    if weekly_sales <= 0 and locked_value <= 0:
                        pass
                    else:
                        avg_balance = price_db.get_state("avg_balance") or str(effective_balance)
                        avg_balance_f = float(avg_balance)
                        velocity = weekly_sales / max(avg_balance_f, 0.01)
                        if velocity < Config.CAPITAL_VELOCITY_MIN:
                            logger.info(
                                f"[v14.4 VELOCITY] ${weekly_sales:.2f}/week sales "
                                f"vs ${avg_balance_f:.2f} avg balance = {velocity:.2f}x "
                                f"(min {Config.CAPITAL_VELOCITY_MIN}x). "
                                f"Skipping buy cycle — capital locked in trade-hold."
                            )
                            return
                except Exception as e:
                    logger.warning(f"[v14.4 VELOCITY] Capital velocity check failed: {e}")

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
                logger.warning(f"get_aggregated_prices (top) failed: {e}", exc_info=True)
                return

            if not agg_prices:
                logger.warning(f"No aggregated prices for {game_id}; skipping cycle.")
                return

            # v14.0: Save snapshot for OFI (Order Flow Imbalance) on next cycle
            # Rotate: keep previous cycle's data for delta calculations
            self._prev_agg_prices_prior = getattr(self, '_prev_agg_prices', {})
            self._prev_agg_prices = agg_prices.copy()

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

            # --- v14.0 Float/Phase secondary scan ---
            # Some items (Doppler knives, low-float weapons) may be listed
            # at general market price without float/phase premium. A second
            # scan with treeFilters catches these undervalued listings.
            if Config.FLOAT_PHASE_SCAN_ENABLED and items:
                try:
                    float_items = await self._fetch_float_filtered_listings(
                        game_id=game_id, top_titles=top_titles
                    )
                    if float_items:
                        seen = {it.get("itemId") for it in items if it.get("itemId")}
                        new_count = 0
                        for cand in float_items:
                            if cand.get("itemId") not in seen:
                                seen.add(cand.get("itemId"))
                                items.append(cand)
                                new_count += 1
                        if new_count > 0:
                            logger.info(
                                f"[v14.0 FLOAT] Found {new_count} additional "
                                f"low-float/rare-phase candidates"
                            )
                except Exception as e:
                    logger.debug(f"[v14.0 FLOAT] Secondary scan failed: {e}")

            # --- v14.8 Price-Range secondary scan (wide-net conveyor) ---
            # Discover cheap/under-the-radar items by price bucket, then fetch
            # their aggregated prices so they go through the same validator.
            # Throttled: runs every N cycles to respect DMarket rate limits.
            if (
                Config.PRICE_RANGE_SCAN_ENABLED
                and self.deep_scan_counter % Config.PRICE_RANGE_CYCLE_INTERVAL == 0
            ):
                try:
                    pr_items = await self._fetch_price_range_listings(
                        game_id=game_id,
                        min_usd=Config.PRICE_RANGE_MIN_USD,
                        max_usd=min(Config.PRICE_RANGE_MAX_USD, dynamic_max_price),
                        max_pages=Config.PRICE_RANGE_MAX_PAGES,
                        max_titles=Config.PRICE_RANGE_MAX_TITLES,
                    )
                    if pr_items:
                        pr_titles = [
                            it.get("title") for it in pr_items if it.get("title")
                        ]
                        pr_agg = await self.client.get_aggregated_prices(
                            game_id, titles=pr_titles
                        )
                        agg_prices.update(pr_agg)
                        seen = {
                            it.get("itemId") for it in items if it.get("itemId")
                        }
                        new_count = 0
                        for cand in pr_items:
                            if cand.get("itemId") not in seen:
                                seen.add(cand.get("itemId"))
                                items.append(cand)
                                new_count += 1
                        if new_count > 0:
                            logger.info(
                                f"[v14.8 PRICE-RANGE] Added {new_count} "
                                f"price-bucket candidates to the pipeline"
                            )
                except Exception as e:
                    logger.debug(f"[v14.8 PRICE-RANGE] Secondary scan failed: {e}")

            # --- v14.8.1 Low-fee items secondary scan ---
            # Items with reduced DMarket fees have better net margin. Fetch
            # their cheapest listings and merge into the pipeline.
            try:
                lf_items = await self._fetch_low_fee_listings(
                    game_id=game_id,
                    max_titles=Config.LOW_FEE_ITEMS_SCAN_LIMIT,
                )
                if lf_items:
                    lf_titles = [it.get("title") for it in lf_items if it.get("title")]
                    lf_agg = await self.client.get_aggregated_prices(
                        game_id, titles=lf_titles
                    )
                    agg_prices.update(lf_agg)
                    seen = {
                        it.get("itemId") for it in items if it.get("itemId")
                    }
                    new_count = 0
                    for cand in lf_items:
                        if cand.get("itemId") not in seen:
                            seen.add(cand.get("itemId"))
                            items.append(cand)
                            new_count += 1
                    if new_count > 0:
                        logger.info(
                            f"[v14.8.1 LOW-FEE] Added {new_count} "
                            f"low-fee candidates to the pipeline"
                        )
            except Exception as e:
                logger.debug(f"[v14.8.1 LOW-FEE] Secondary scan failed: {e}")

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

            # Build mappings for fee-by-volume estimation
            item_id_to_title: dict[str, str] = {
                item["itemId"]: item["title"]
                for item in items
                if item.get("itemId") and item.get("title")
            }
            title_volume: dict[str, int] = {}
            for title, agg in agg_prices.items():
                ask_cnt = agg.get("ask_count", 0) or 0
                bid_cnt = agg.get("bid_count", 0) or 0
                title_volume[title] = ask_cnt + bid_cnt

            bulk_fees: dict[str, float] = {}
            if candidate_item_ids:
                bulk_fees = await self.client.get_item_fee_bulk(
                    game_id, candidate_item_ids,
                    title_volume=title_volume,
                    item_id_to_title=item_id_to_title,
                )

            # --- Step 4: Filter and validate (delegated) ---
            current_margin = await self.get_min_profit_margin()
            instant_buys: list[dict[str, Any]] = []

            # v14.9: Value Detection Scanner pipeline.
            # Uses the new dual-signal approach: VALUE (rarity-based) + SPREAD (bid-ask edge).
            # This is the core refactor for the "buy cheap, sell at premium" strategy.

            # v15.0: MultiSource oracle validation (Market.CSGO + Waxpeer + CSFloat + Steam).
            # FairPriceCalculator determines optimal sell price from multiple sources.
            # No paid subscriptions required.
            cs_snapshots: dict[str, Any] = {}
            cs_bids: dict[str, Any] = {}

            max_price_cap = min(effective_balance, dynamic_max_price)
            ranked = self._rank_candidates_by_spread(
                items, agg_prices, max_price_usd=max_price_cap
            )
            top_titles = [
                t for t, _ in ranked[: Config.ORACLE_TOP_K_VALIDATE]
            ]

            if self.multi_source_oracle is not None and top_titles:
                # Get fair prices from MultiSource oracle
                fair_prices = await self.multi_source_oracle.get_fair_prices_batch(top_titles)
                for t in top_titles:
                    fp = fair_prices.get(t)
                    if fp and fp.fair_price > 0:
                        cs_snapshots[t] = fp
                logger.info(
                    f"[MultiSource] top_titles={len(top_titles)} "
                    f"priced={len(cs_snapshots)}"
                )

            # v15.0: MultiSource batch for cross-market buy targets.
            # Get fair prices for all traded titles from Market.CSGO + Waxpeer.
            cs_target_snapshots: dict[str, Any] = {}
            if (
                Config.CROSS_MARKET_TARGET_ENABLED
                and self.multi_source_oracle is not None
            ):
                try:
                    target_titles = list(agg_prices.keys())[:100]
                    cs_target_snapshots = await self.multi_source_oracle.get_fair_prices_batch(target_titles)
                    logger.info(
                        f"[MultiSource] fetched {len(cs_target_snapshots)} "
                        f"cross-market reference prices"
                    )
                except Exception as e:
                    logger.debug(f"[MultiSource] batch failed: {e}")

            # v14.1: Pre-fetch DMarket last-sales for CVD/VPIN/VWAP analysis
            # Only for top candidates, uses DMarket API.
            self._sales_cache: dict[str, list[dict[str, Any]]] = {}
            if Config.CVD_ENABLED or Config.VWAP_FILTER_ENABLED or Config.VPIN_ENABLED:
                sales_titles: list[str] = []
                if 'ranked' in dir():
                    sales_titles = list({t for t, _ in ranked[: Config.CVD_WINDOW_ITEMS]})
                elif top_titles:
                    sales_titles = top_titles[: Config.CVD_WINDOW_ITEMS]
                if sales_titles:
                    try:
                        for t in sales_titles:
                            try:
                                sales = await self.client.get_last_sales(
                                    game_id, t, days=7, limit=30
                                )
                                if sales:
                                    self._sales_cache[t] = sales
                                    # v14.1: Accumulate into trade_history for CVD/VPIN
                                    try:
                                        price_db.save_trades_batch(t, sales)
                                    except Exception as e:
                                        # DB write failure → next cycle's CVD/VPIN/VWAP filters
                                        # operate on stale data → potential mispricing
                                        logger.warning(f"[TRADES] save_trades_batch failed for {t}: {e}")
                            except Exception as e:
                                logger.debug(f"[SALES] Sales cache fetch failed: {e}")
                        if self._sales_cache:
                            logger.debug(
                                f"[v14.1 SALES] Fetched last-sales for "
                                f"{len(self._sales_cache)} items for CVD/VPIN/VWAP"
                            )
                    except Exception as e:
                        logger.debug(f"[v14.1 SALES] Pre-fetch failed: {e}")

            # v12.6: Pump detection sweep — we just observed fresh prices
            # for ~100 items. Run the spike check on each so that any
            # item with >PUMP_THRESHOLD_PCT move in the last hour gets
            # blacklisted and alerted. Cheap (in-memory DB read); runs
            # BEFORE the filter loop so the filter can skip blacklisted
            # items automatically (via risk.pre_trade_check below).
            if self.pump_detector is not None:
                pd_count = 0
                for title, agg in agg_prices.items():
                    best_ask = agg.get("best_ask", 0.0) or 0.0
                    if best_ask > 0:
                        # Use ask price as the "current price" proxy
                        # (best_ask is what we'd actually pay to buy).
                        self.pump_detector.check_price(title, best_ask)
                        pd_count += 1
                if self.deep_scan_counter % 10 == 0:
                    pd_stats = self.pump_detector.stats()
                    logger.info(
                        f"[PumpDetector] checked {pd_count} items; "
                        f"blacklist={pd_stats['active_blacklist_size']} "
                        f"detections={pd_stats['total_detections']}"
                    )

            # v12.7: Parallel candidate evaluation (P0-2).
            # _evaluate_candidate is mostly read-only (SQLite + dict lookups).
            # HTTP fallback path (oracle.get_item_price) is rare when cache is warm.
            # Semaphore caps concurrent fallback HTTP calls to prevent rate-limit storm.

            # v12.8: Pre-compute saturation counts ONCE before parallel loop (P-1).
            # Was O(N²): each candidate called get_virtual_inventory (N table scans).
            # Now: 1 table scan → dict lookup per candidate (O(1)).
            raw_inv = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
            saturation_counts: dict[str, int] = {}
            for inv_item in raw_inv:
                hn = inv_item["hash_name"]
                saturation_counts[hn] = saturation_counts.get(hn, 0) + 1

            candidates_to_eval = [
                item for item in items
                if item.get("title") and item.get("itemId")
            ]
            if candidates_to_eval:
                _eval_sem = asyncio.Semaphore(10)

                # v14.9: Dual-signal evaluation with value detection scanner.
                # First, try the new evaluate_combined_signal for rarity-based buys.
                # If that returns None, fall back to legacy _evaluate_candidate.
                async def _eval_with_sem(item):
                    async with _eval_sem:
                        title = item.get("title", "")
                        # Get aggregated price data
                        agg = agg_prices.get(title, {})
                        best_bid = agg.get("best_bid", 0.0)
                        best_ask = agg.get("best_ask", 0.0)
                        # Get reference price from MultiSource oracle
                        cs2cap_ask = 0.0
                        if title in cs_snapshots:
                            fp = cs_snapshots[title]
                            cs2cap_ask = fp.fair_price if hasattr(fp, 'fair_price') else fp

                        # Try VALUE signal first
                        if Config.VALUE_SCAN_ENABLED and cs2cap_ask > 0:
                            from src.core.target_sniping.value_pipelines import (
                                evaluate_combined_signal,
                            )
                            value_result = evaluate_combined_signal(
                                title=title,
                                item=item,
                                cs2cap_ask=cs2cap_ask,
                                best_bid=best_bid,
                                best_ask=best_ask,
                                fee_rate=bulk_fees.get(item.get("itemId"), Config.FEE_RATE),
                                current_margin=current_margin,
                            )
                            if value_result is not None:
                                vs_base_price = value_result["base_price"]

                                # v14.9.1: Safety checks for value scanner path
                                # (previously bypassed LiquidityManager, saturation, lock-aware cap)

                                # Saturation check — prevent over-concentration
                                vs_held = saturation_counts.get(title, 0)
                                if vs_held >= Config.MAX_SAME_ITEM_HOLDINGS:
                                    logger.debug(
                                        f"[VALUE-SCAN] {title}: saturation limit "
                                        f"({vs_held}/{Config.MAX_SAME_ITEM_HOLDINGS}). Skipping."
                                    )
                                else:
                                    # Lock-aware inventory cap
                                    vs_skip = False
                                    if Config.LOCK_AWARE_CAP_ENABLED:
                                        vs_eff_bal = effective_balance or current_balance
                                        vs_locked = price_db.get_virtual_inventory_locked_value()
                                        vs_liquid_remaining = vs_eff_bal * Config.LOCK_AWARE_LIQUID_FRACTION
                                        if vs_locked + vs_base_price > vs_liquid_remaining:
                                            logger.debug(
                                                f"[VALUE-SCAN] {title}: lock-aware cap "
                                                f"(${vs_locked:.2f}+${vs_base_price:.2f} > "
                                                f"${vs_liquid_remaining:.2f}). Skipping."
                                            )
                                            vs_skip = True

                                    # LiquidityManager daily spend gate
                                    if not vs_skip and self.liquidity is not None:
                                        from src.db.price_history.core import get_game_id_from_title
                                        vs_game_id = get_game_id_from_title(title) or game_id
                                        if not self.liquidity.can_spend(
                                            vs_base_price, vs_game_id, current_balance
                                        ):
                                            logger.debug(
                                                f"[VALUE-SCAN] {title}: LiquidityManager "
                                                f"daily spend limit reached. Skipping."
                                            )
                                            vs_skip = True

                                    if not vs_skip:
                                        buy_offer = {
                                            "offerId": item.get("itemId"),
                                            "price": item.get("price", {}),
                                        }
                                        return {
                                            "buy_offer": buy_offer,
                                            "title": title,
                                            "item_id": item.get("itemId"),
                                            "base_price": vs_base_price,
                                            "list_price": value_result["list_price"],
                                            "best_bid": best_bid,
                                            "best_ask": best_ask,
                                            "strategy": "value_scanner",
                                            "target_platform": "dmarket",
                                            "is_rare": True,
                                            "value_signal": value_result,
                                        }

                        # Fallback to legacy spread-based evaluation
                        return await self._evaluate_candidate(
                            item=item,
                            game_id=game_id,
                            oracle=oracle,
                            agg_prices=agg_prices,
                            bulk_fees=bulk_fees,
                            current_balance=current_balance,
                            current_margin=current_margin,
                            cs_snapshots=cs_snapshots,
                            cs_bids=cs_bids,
                            saturation_counts=saturation_counts,
                            effective_balance=effective_balance,
                            dynamic_max_price=dynamic_max_price,
                        )

                results = await asyncio.gather(
                    *[_eval_with_sem(item) for item in candidates_to_eval],
                    return_exceptions=True,
                )
                for r in results:
                    if isinstance(r, dict) and r is not None:
                        instant_buys.append(r)
                    elif isinstance(r, Exception):
                        logger.debug(f"Candidate eval error: {r}")

            # --- Step 5: Execute instant buys (delegated) ---
            if instant_buys:
                # v14.5: Strategy selector — dynamically choose strategy per cycle
                try:
                    from datetime import datetime, timezone

                    from src.core.strategy_selector import strategy_selector
                    now = datetime.now(timezone.utc)
                    is_weekend = now.weekday() >= 5
                    is_night = 3 <= now.hour < 8
                    spreads = [
                        ((b["best_bid"] - b["best_ask"]) / max(b["best_ask"], 0.01)) * 100
                        for b in instant_buys if b.get("best_ask", 0) > 0
                    ]
                    avg_spread = sum(spreads) / max(len(spreads), 1)
                    event_active = event_shield.get_active_events() != []
                    drawdown = getattr(self.risk, '_current_drawdown_pct', 0.0)

                    strategy_selector.select(
                        cycle=self.deep_scan_counter,
                        oracle_ok=len(cs_snapshots) > 0,
                        avg_spread_pct=avg_spread,
                        avg_volatility=0.15,
                        is_weekend=is_weekend,
                        is_night=is_night,
                        event_active=event_active,
                        drawdown_pct=drawdown,
                    )
                except Exception as e:
                    logger.warning(f"[STRATEGY] strategy_selector.select failed: {e}")
                try:
                    from src.core.limit_orders import _LimitOrderMixin
                    limit_mixin = _LimitOrderMixin()
                    limit_mixin.client = self.client
                    limit_targets, instant_targets = limit_mixin._categorize_candidates(instant_buys)
                    if limit_targets:
                        placed = await limit_mixin._execute_limit_orders(
                            candidates=limit_targets,
                            game_id=game_id,
                            current_balance=current_balance,
                        )
                        if placed > 0:
                            logger.info(f"[LIMIT] {placed} buy target(s) placed for wide-spread items")
                    instant_buys = instant_targets  # only instant-buy the rest

                    # v14.9: Cross-market buy targets — when DMarket ask is above
                    # MultiSource oracle: post liquidity at reference prices.
                    cross_placed = await limit_mixin._execute_cross_market_targets(
                        game_id=game_id,
                        agg_prices=agg_prices,
                        cs_snapshots=cs_target_snapshots or cs_snapshots,
                        current_balance=current_balance,
                    )
                    if cross_placed > 0:
                        logger.info(f"[CROSS-MARKET TARGET] {cross_placed} target(s) placed")
                except Exception as e:
                    logger.debug(f"[LIMIT] Limit order flow failed: {e}")

                await self._execute_instant_buys(
                    instant_buys=instant_buys, current_balance=current_balance,
                    game_id=game_id,
                )
                # v13.0: List immediately after purchase (capital velocity fix)
                await self.auto_resale(game_id)

            # v14.7: Position guard — stop-loss + take-profit via composition
            if self.deep_scan_counter % 3 == 0:
                check_stop, check_tp = 0, 0
                try:
                    from src.core.target_sniping.position_guard import _PositionGuardMixin
                    pg = _PositionGuardMixin()
                    pg.client = self.client
                    pg.multi_source_oracle = self.multi_source_oracle
                    check_stop = await pg.check_stop_losses(game_id)
                    check_tp = await pg.check_take_profits(game_id)
                except Exception as e:
                    logger.debug(f"Position guard check failed: {e}")
                if check_stop or check_tp:
                    logger.info(
                        f"[POS-GUARD] stop-loss={check_stop} take-profit={check_tp}"
                    )

            # Periodic repricing
            if self.reprice_counter % 60 == 0:  # Every ~60 cycles
                await self.reprice_unsold_offers(game_id)

            # v12.0 Phase 1.1: Refresh low-fee cache every 100 cycles
            if self.deep_scan_counter % 100 == 0:
                await self._refresh_low_fee_cache(game_id)

            # v14.1: Cleanup old trade_history every 200 cycles (~100 min)
            if self.deep_scan_counter % 200 == 0:
                try:
                    deleted = price_db.cleanup_old_trades(days=90)
                    if deleted > 0:
                        logger.info(f"[v14.1] Pruned {deleted} old trade_history records")
                except Exception as e:
                    logger.warning(f"[v14.1] cleanup_old_trades failed: {e}")

            # v13.1: Release expired TP holds before equity report
            price_db.release_expired_funds()

            # Equity report
            equity = price_db.get_total_equity(current_balance)
            frozen_str = f" Frozen: ${equity['frozen']:.2f} |" if equity.get("frozen", 0) > 0 else ""
            logger.info(
                f"[EQUITY] Available: ${equity['available']:.2f} | "
                f"Cash: ${equity['cash']:.2f} |{frozen_str}"
                f" Assets: ${equity['assets']:.2f} | "
                f"TOTAL: ${equity['total']:.2f} (Items: {equity['count']})"
            )

            self._update_health_metrics(equity)
            self._send_equity_milestone(equity)
            self._log_cycle_diag(game_id, len(candidates_to_eval), len(instant_buys))

            # v14.5: Feed live shadow engine (paper trading alongside real bot)
            try:
                from src.core.live_shadow import live_shadow
                live_shadow.feed_cycle(
                    candidates=instant_buys,
                    agg_prices=agg_prices,
                    cs2cap_ok=len(cs_snapshots) > 0,
                )
            except Exception as e:
                logger.debug(f"[SHADOW] live_shadow.feed_cycle failed: {e}")

            if self.deep_scan_counter % 200 == 0:
                price_db.cleanup_old_targets()

        except Exception as e:
            # v12.6 error policy:
            # - CircuitOpenError / RateLimit → log & continue (DMarket
            #   is throttling; the next sleep will naturally pace us).
            # - Other transient (timeout, network) → log & continue.
            # - FATAL / UNKNOWN (our code bug, db corruption) →
            #   log with structured report, then RE-RAISE so the outer
            #   supervisor exits with a distinct code. The watchdog
            #   will not auto-restart.
            classification = classify(e)
            if classification in ("FATAL", "UNKNOWN"):
                report = ErrorReporter(e, context={
                    "phase": "run_cycle",
                    "game_id": game_id,
                    "cycle": self.deep_scan_counter,
                    "balance": f"${current_balance:.2f}" if "current_balance" in dir() else "?",
                    "items_in_page": len(items) if "items" in dir() else "?",
                })
                logger.error(report.format_log())
                # Re-raise so the outer loop can exit with the right code.
                raise
            # Transient — log a short warning, let the cycle skip.
            logger.warning(
                f"[v12.6] Transient cycle error ({classification}) for "
                f"{game_id}: {type(e).__name__}: {e}",
                exc_info=True,
            )


if __name__ == "__main__":
    pass
