"""
cycle_orchestrator.py — Pipeline stage extraction from SnipingLoop.run_cycle().

Decomposes the monolithic run_cycle() into discrete, testable stages:
    1. _stage_prepare       — counters, balance, oracle init
    2. _stage_scan          — aggregated prices + secondary scans
    3. _stage_prefetch      — bulk fees, sales cache, pump detection
    4. _stage_evaluate      — parallel candidate evaluation
    5. _stage_execute       — instant buys + limit orders
    6. _stage_postprocess   — resale, repricing, telemetry

Each stage receives a CycleContext and returns an updated one.
This file is a mixin — mixed into SnipingLoop.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

from src.config import Config
from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


@dataclass
class CycleContext:
    """Shared state passed between pipeline stages."""
    game_id: str = ""
    current_balance: float = 0.0
    effective_balance: float = 0.0
    dynamic_max_price: float = 0.0
    oracle: Any = None
    agg_prices: dict[str, Any] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    bulk_fees: dict[str, float] = field(default_factory=dict)
    cs_snapshots: dict[str, Any] = field(default_factory=dict)
    cs_target_snapshots: dict[str, Any] = field(default_factory=dict)
    current_margin: float = 0.0
    instant_buys: list[dict[str, Any]] = field(default_factory=list)
    is_fresh_cycle: bool = False
    cursor_key: str = ""
    # v15.2: Triple balance tracking
    balance_before: float = 0.0      # Balance before cycle starts
    balance_during: float = 0.0      # Balance before each buy (re-checked)
    balance_after: float = 0.0       # Balance after all sells complete
    total_spent: float = 0.0         # Total USD spent this cycle
    total_earned: float = 0.0        # Total USD earned this cycle (from sells)


class CycleOrchestrator:
    """Pipeline stage extraction mixin for SnipingLoop."""

    # Type stubs for attributes from SnipingLoop
    client: Any
    deep_scan_counter: int
    reprice_counter: int
    empty_page_count: int
    multi_source_oracle: Any
    pump_detector: Any
    risk: Any
    self_reflection: Any
    _prev_agg_prices: dict[str, Any]
    _sales_cache: dict[str, Any]

    async def _stage_prepare(self, ctx: CycleContext) -> CycleContext:
        """Stage 1: Prepare cycle — counters, balance, oracle."""
        from src.api.oracle_factory import OracleFactory
        from src.utils.health_server import health_state

        try:
            health_state.mark_cycle(0.0, 0.0, 0.0)
        except Exception as e:
            logger.debug(f"[HEALTH] mark_cycle failed: {e}")

        self._clear_oracle_cache()
        self.deep_scan_counter += 1
        self.reprice_counter += 1
        ctx.is_fresh_cycle = self.deep_scan_counter % 5 == 0
        ctx.cursor_key = f"dmarket_cursor_{ctx.game_id}"

        if self.deep_scan_counter % 20 == 0:
            await self._sync_inventory_statuses(ctx.game_id)

        ctx.current_balance = await self.client.get_real_balance()
        ctx.balance_before = ctx.current_balance
        ctx.effective_balance = max(0.0, ctx.current_balance - Config.BALANCE_RESERVE_USD)
        ctx.dynamic_max_price = max(
            Config.MAX_SNIPING_PRICE_FLOOR,
            ctx.effective_balance * Config.MAX_SNIPING_PRICE_BALANCE_FRACTION,
        )
        import os
        if os.getenv("MAX_SNIPING_PRICE_USD"):
            ctx.dynamic_max_price = Config.MAX_SNIPING_PRICE_USD
        ctx.dynamic_max_price = min(ctx.dynamic_max_price, ctx.effective_balance)

        ctx.oracle = OracleFactory.get_oracle(ctx.game_id)
        self.oracle = ctx.oracle
        return ctx

    async def _stage_scan(self, ctx: CycleContext) -> CycleContext:
        """Stage 2: Market scan — aggregated prices + secondary scans."""

        cursor = "" if ctx.is_fresh_cycle else (price_db.get_state(ctx.cursor_key) or "")

        # Capital velocity check
        if Config.CAPITAL_VELOCITY_ENABLED and ctx.effective_balance > 0:
            try:
                weekly_sales = price_db.get_virtual_inventory_weekly_sales()
                locked_value = price_db.get_virtual_inventory_locked_value()
                if weekly_sales > 0 or locked_value > 0:
                    avg_balance = float(price_db.get_state("avg_balance") or str(ctx.effective_balance))
                    velocity = weekly_sales / max(avg_balance, 0.01)
                    if velocity < Config.CAPITAL_VELOCITY_MIN:
                        logger.info(f"[VELOCITY] {velocity:.2f}x < {Config.CAPITAL_VELOCITY_MIN}x. Skipping.")
                        return ctx
            except Exception as e:
                logger.debug(f"[VELOCITY] check failed: {e}")

        # Aggregated prices
        try:
            ctx.agg_prices = await self.client.get_aggregated_prices(
                ctx.game_id, titles=list(ctx.agg_prices.keys())[:100] if ctx.agg_prices else []
            )
        except Exception:
            ctx.agg_prices = {}

        if not ctx.agg_prices:
            return ctx

        # Cheapest listings
        top_titles = sorted(
            ctx.agg_prices.keys(),
            key=lambda t: (ctx.agg_prices[t].get("best_ask", 0) or 0),
        )[:20]  # Top 20 by lowest ask

        ctx.items = await self._fetch_cheapest_listings(ctx.game_id, top_titles)

        # Secondary scans (float, price-range, low-fee)
        ctx.items = await self._run_secondary_scans(ctx, cursor)
        return ctx

    async def _run_secondary_scans(self, ctx: CycleContext, cursor: str) -> list[dict[str, Any]]:
        """Run float/phase, price-range, and low-fee secondary scans."""
        items = list(ctx.items)
        # v2 uses "offerId", v1 uses "itemId"
        seen = {
            it.get("offerId", "") or it.get("itemId", "")
            for it in items
            if it.get("offerId") or it.get("itemId")
        }

        # Float/phase scan (every 5 cycles)
        if self.deep_scan_counter % 5 == 0:
            try:
                top_titles = [it.get("title", "") for it in items[:50]]
                fp_items = await self._fetch_float_filtered_listings(ctx.game_id, top_titles)
                for cand in fp_items:
                    cid = cand.get("offerId", "") or cand.get("itemId", "")
                    if cid and cid not in seen:
                        seen.add(cid)
                        items.append(cand)
            except Exception as e:
                logger.debug(f"[FLOAT] scan failed: {e}")

        # Price-range scan
        if Config.PRICE_RANGE_SCAN_ENABLED and self.deep_scan_counter % Config.PRICE_RANGE_CYCLE_INTERVAL == 0:
            try:
                pr_items = await self._fetch_price_range_listings(
                    game_id=ctx.game_id,
                    min_usd=Config.PRICE_RANGE_MIN_USD,
                    max_usd=min(Config.PRICE_RANGE_MAX_USD, ctx.dynamic_max_price),
                )
                for cand in pr_items:
                    cid = cand.get("offerId", "") or cand.get("itemId", "")
                    if cid and cid not in seen:
                        seen.add(cid)
                        items.append(cand)
            except Exception as e:
                logger.debug(f"[PRICE-RANGE] scan failed: {e}")

        # Low-fee scan
        try:
            lf_items = await self._fetch_low_fee_listings(ctx.game_id, max_titles=Config.LOW_FEE_ITEMS_SCAN_LIMIT)
            for cand in lf_items:
                cid = cand.get("offerId", "") or cand.get("itemId", "")
                if cid and cid not in seen:
                    seen.add(cid)
                    items.append(cand)
        except Exception as e:
            logger.debug(f"[LOW-FEE] scan failed: {e}")

        return items

    async def _stage_prefetch(self, ctx: CycleContext) -> CycleContext:
        """Stage 3: Pre-fetch bulk fees, sales cache, pump detection."""
        # Bulk fees
        candidate_ids = [
            (it.get("offerId", "") or it.get("itemId", ""))
            for it in ctx.items
            if (it.get("offerId") or it.get("itemId"))
            and int(it.get("priceCents", 0) or it.get("price", {}).get("USD", 0)) > 0
        ]
        if candidate_ids:
            try:
                ctx.bulk_fees = await self.client.get_item_fee_bulk(ctx.game_id, candidate_ids)
            except Exception:
                ctx.bulk_fees = {}

        # MultiSource oracle
        if self.multi_source_oracle is not None:
            try:
                top_titles = list(ctx.agg_prices.keys())[:Config.ORACLE_TOP_K_VALIDATE]
                fair_prices = await self.multi_source_oracle.get_fair_prices_batch(top_titles)
                for t, fp in fair_prices.items():
                    if fp and fp.fair_price > 0:
                        ctx.cs_snapshots[t] = fp
            except Exception as e:
                logger.debug(f"[MultiSource] batch failed: {e}")

        # Pump detection
        if self.pump_detector is not None:
            for title, agg in ctx.agg_prices.items():
                best_ask = agg.get("best_ask", 0.0) or 0.0
                if best_ask > 0:
                    self.pump_detector.check_price(title, best_ask)

        # Sales cache for CVD/VPIN
        if Config.CVD_ENABLED or Config.VWAP_FILTER_ENABLED or Config.VPIN_ENABLED:
            self._sales_cache = {}
            for t in list(ctx.agg_prices.keys())[:Config.CVD_WINDOW_ITEMS]:
                try:
                    sales = await self.client.get_last_sales(ctx.game_id, t, days=7, limit=30)
                    if sales:
                        self._sales_cache[t] = sales
                        price_db.save_trades_batch(t, sales)
                except Exception:
                    pass

        ctx.current_margin = await self.get_min_profit_margin()
        return ctx

    async def _stage_evaluate(self, ctx: CycleContext) -> CycleContext:
        """Stage 4: Parallel candidate evaluation."""
        from src.core.target_sniping.ranking import rank_candidates_by_spread

        max_price_cap = min(ctx.effective_balance, ctx.dynamic_max_price)
        ranked = rank_candidates_by_spread(ctx.items, ctx.agg_prices, max_price_usd=max_price_cap)
        if ranked:
            try:
                ranked_titles = {t for t, _ in ranked}
                ctx.items.sort(key=lambda it: next(
                    (i for i, (t, _) in enumerate(ranked) if t == it.get("title", "")),
                    len(ranked)
                ))
            except (ValueError, TypeError):
                pass  # ranked format unexpected, skip sorting

        raw_inv = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
        sat_counts: dict[str, int] = {}
        for inv in raw_inv:
            hn = inv["hash_name"]
            sat_counts[hn] = sat_counts.get(hn, 0) + 1

        candidates = [
            it for it in ctx.items
            if it.get("title") and (it.get("offerId") or it.get("itemId"))
        ]
        if not candidates:
            return ctx

        sem = asyncio.Semaphore(10)

        async def _eval(item):
            async with sem:
                return await self._evaluate_candidate(
                    item=item, game_id=ctx.game_id,
                    oracle=ctx.oracle,
                    agg_prices=ctx.agg_prices, bulk_fees=ctx.bulk_fees,
                    cs_snapshots=ctx.cs_snapshots, current_margin=ctx.current_margin,
                    effective_balance=ctx.effective_balance,
                    dynamic_max_price=ctx.dynamic_max_price,
                    saturation_counts=sat_counts,
                )

        results = await asyncio.gather(*[_eval(it) for it in candidates], return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r.get("buy_offer"):
                ctx.instant_buys.append(r)
            elif isinstance(r, Exception):
                logger.debug(f"[EVAL] candidate failed: {r}")

        return ctx

    async def _stage_execute(self, ctx: CycleContext) -> CycleContext:
        """Stage 5: Execute instant buys with balance re-check before each."""
        if not ctx.instant_buys:
            return ctx

        logger.info(f"[EXECUTE] {len(ctx.instant_buys)} candidates to buy")
        # v15.2: Re-check balance before execution batch
        ctx.balance_during = await self.client.get_real_balance()
        effective_now = max(0.0, ctx.balance_during - Config.BALANCE_RESERVE_USD)

        try:
            await self._execute_instant_buys(
                instant_buys=ctx.instant_buys,
                current_balance=effective_now,
                game_id=ctx.game_id,
            )
            ctx.total_spent += sum(b.get("base_price", 0.0) for b in ctx.instant_buys)
        except Exception as e:
            logger.warning(f"[EXECUTE] instant buys failed: {e}")

        return ctx

    async def _stage_postprocess(self, ctx: CycleContext) -> None:
        """Stage 6: Post-cycle — resale, repricing, balance check, telemetry."""
        # Resale
        if self.deep_scan_counter % self.resale_cycle_limit == 0:
            try:
                await self.auto_resale(ctx.game_id)
            except Exception as e:
                logger.debug(f"[RESALE] failed: {e}")

        # Repricing
        if self.reprice_counter % 60 == 0:
            try:
                await self.reprice_unsold_offers(ctx.game_id)
            except Exception as e:
                logger.debug(f"[REPRICE] failed: {e}")

        # v15.2: Balance check AFTER sells
        try:
            ctx.balance_after = await self.client.get_real_balance()
            ctx.total_earned = max(0.0, ctx.balance_after - ctx.balance_before + ctx.total_spent)

            if ctx.total_spent > 0 or ctx.total_earned > 0:
                logger.info(
                    f"[BALANCE] Before: ${ctx.balance_before:.2f} | "
                    f"Spent: ${ctx.total_spent:.2f} | "
                    f"Earned: ${ctx.total_earned:.2f} | "
                    f"After: ${ctx.balance_after:.2f} | "
                    f"Net: ${ctx.total_earned - ctx.total_spent:+.2f}"
                )
        except Exception as e:
            logger.debug(f"[BALANCE] post-sell check failed: {e}")

        # Telemetry
        try:
            risk_state = self.risk.get_state()
            logger.info(
                f"[CYCLE] balance=${ctx.current_balance:.2f} "
                f"effective=${ctx.effective_balance:.2f} "
                f"items={len(ctx.items)} "
                f"buys={len(ctx.instant_buys)} "
                f"drawdown={risk_state.current_drawdown_pct:.1f}%"
            )
        except Exception:
            pass

        # Persist risk state to SQLite (survives restarts for 24/7 operation)
        try:
            self.risk.save_state_to_db()
        except Exception:
            pass

        # Periodic SQLite maintenance (every 1000 cycles / ~8 hours at 30s/cycle)
        if self.deep_scan_counter % 1000 == 0:
            try:
                price_db.wal_checkpoint()
                price_db.optimize()
                price_db.cleanup_old_prices(days=30)
                price_db.cleanup_old_trades(days=90)
                logger.info(f"[DB] WAL checkpoint + optimize + cleanup at cycle {self.deep_scan_counter}")
            except Exception:
                pass
            # Fallback: commit state to orphan branch (independent of GH Actions cache)
            try:
                await self._commit_state_to_branch()
            except Exception as e:
                logger.debug(f"[STATE-BACKUP] Failed: {e}")

    async def _commit_state_to_branch(self) -> None:
        """Fallback: commit SQLite state to orphan branch 'dryrun-state'.
        
        Independent of GitHub Actions cache — provides a second recovery
        path if cache is evicted. Runs in a thread to avoid blocking the
        event loop.
        """
        from pathlib import Path

        def _do_commit() -> None:
            try:
                branch = "dryrun-state"
                db_files = ["data/dmarket_state.db", "data/dmarket_history.db",
                            "data/dmarket_trading.db"]
                existing = [f for f in db_files if Path(f).exists()]
                if not existing:
                    return

                # Ensure branch exists
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", branch],
                    capture_output=True, timeout=10
                )
                if result.returncode != 0:
                    # Create orphan branch
                    subprocess.run(
                        ["git", "checkout", "--orphan", branch],
                        capture_output=True, timeout=10
                    )
                    subprocess.run(
                        ["git", "rm", "-rf", "."],
                        capture_output=True, timeout=10
                    )
                else:
                    subprocess.run(
                        ["git", "checkout", branch],
                        capture_output=True, timeout=10
                    )

                # Copy DB files to staging
                for f in existing:
                    subprocess.run(
                        ["git", "add", f, f"{f}-wal", f"{f}-shm"],
                        capture_output=True, timeout=10
                    )

                # Commit
                import time
                msg = f"state-backup cycle={self.deep_scan_counter} ts={int(time.time())}"
                result = subprocess.run(
                    ["git", "commit", "-m", msg, "--allow-empty"],
                    capture_output=True, timeout=10, text=True
                )
                if result.returncode != 0 and "nothing to commit" not in result.stderr.lower():
                    logger.warning(f"[STATE-BACKUP] git commit failed: {result.stderr[:200]}")

                # Push to remote (for GitHub Actions persistence)
                push_result = subprocess.run(
                    ["git", "push", "origin", branch, "--force"],
                    capture_output=True, timeout=30, text=True
                )
                if push_result.returncode != 0:
                    logger.warning(
                        f"[STATE-BACKUP] git push failed: {push_result.stderr[:200]}"
                    )

                # Return to previous branch
                subprocess.run(
                    ["git", "checkout", "-"],
                    capture_output=True, timeout=10
                )
                logger.info(
                    f"[STATE-BACKUP] Committed to '{branch}' at cycle {self.deep_scan_counter}"
                )
            except Exception as e:
                logger.debug(f"[STATE-BACKUP] Git commit failed: {e}")
                # Try to return to a valid branch
                try:
                    subprocess.run(
                        ["git", "checkout", "master"],
                        capture_output=True, timeout=10
                    )
                except Exception:
                    pass

        await asyncio.get_event_loop().run_in_executor(None, _do_commit)
