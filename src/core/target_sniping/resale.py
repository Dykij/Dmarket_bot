"""
resale.py — Auto-resale + repricing pipeline (v12.5 production-ready).

Mixed into `SnipingLoop` (see `core.py`).

Two operating modes:

  DRY_RUN=true   — pure simulation. Items are added to the SQLite virtual
                   inventory at buy time; this module randomly marks some
                   as sold and the rest as "listed" at a small markup
                   over buy price. The PnL is paper-tracked.

  DRY_RUN=false  — real production. The bot fetches the user's real
                   DMarket inventory, prices each item using the CS2Cap
                   cache, and calls the batch create_sell_offers API.
                   Periodically checks for items that have sold (via
                   /user-offers/closed) and records the realized PnL.
                   Stale listings (>REPRICE_AFTER_HOURS) are auto-edited
                   with a 5% lower price.

Both modes share the same SQLite schema (virtual_inventory with
dm_item_id, dm_offer_id, listed_at, list_error) so a future mode flip
doesn't lose state.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.config import Config
from src.core.target_sniping.position_guard import _PositionGuardMixin
from src.core.target_sniping.resale_constants import (
    REPRICE_DROP_PCT,
)
from src.core.target_sniping.resale_dry import _ResaleDryMixin
from src.core.target_sniping.resale_prod import _ResaleProdMixin
from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


class _ResaleMixin(_ResaleDryMixin, _ResaleProdMixin, _PositionGuardMixin):
    """Post-buy pipeline (list, sell, reprice)."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient
    cs2cap_cache: Any  # CS2CapCache (or None)

    # ----------------------------------------------------------------
    # auto_resale — DRY + PROD paths
    # ----------------------------------------------------------------
    async def auto_resale(self, game_id: str) -> None:
        """
        v12.5: Unified auto-resale. Routes to DRY simulation or real DMarket API.

        Flow (both modes):
        1. List all `idle` items past their 7-day trade lock.
        2. If DRY: simulate listing + random sales.
        3. If PROD: price via CS2Cap cache + batch list on DMarket.

        Skips if no items. Errors are logged but never crash the loop.
        """
        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"

        # Report on trade-lock status
        all_idle = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
        unlocked_idle = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
        locked_count = len(all_idle) - len(unlocked_idle)

        if locked_count > 0:
            logger.info(f"[RESALE] Trade Lock: {locked_count} item(s) frozen, "
                        f"{len(unlocked_idle)} ready to list")

        # First: detect any real-world sells (PROD) so we record them
        # before we try to list new items. This keeps the sold count
        # accurate for daily PnL.
        if not is_dry:
            try:
                sold_count = await self._sync_sold_offers(game_id)
                if sold_count > 0:
                    logger.info(f"[RESALE] Recorded {sold_count} new sale(s) since last sync")
            except Exception as e:
                logger.warning(f"[RESALE] _sync_sold_offers failed: {e}", exc_info=True)

            # Reconcile DMarket inventory with local DB (picks up new items
            # the bot bought since last sync, with their real itemId).
            try:
                synced = await self._sync_real_inventory(game_id)
                if synced > 0:
                    logger.info(f"[RESALE] Inventory sync: {synced} new item(s) linked")
            except Exception as e:
                logger.warning(f"[RESALE] _sync_real_inventory failed: {e}", exc_info=True)

        # DRY: simulate sales of `selling` items
        if is_dry:
            self._dry_simulate_sales()
        else:
            try:
                await self._check_external_sales(game_id)
            except Exception as e:
                logger.warning(f"[RESALE] _check_external_sales failed: {e}", exc_info=True)

        if not unlocked_idle:
            return

        # v13.0: Skip exclusive (keep-forever) items — they shouldn't be auto-listed
        unlocked_non_exclusive = [
            item for item in unlocked_idle
            if not dict(item).get("exclusive")
        ]
        exclusive_count = len(unlocked_idle) - len(unlocked_non_exclusive)
        if exclusive_count > 0:
            logger.info(f"[RESALE] Skipping {exclusive_count} exclusive item(s) — kept for rarity")

        if not unlocked_non_exclusive:
            return

        logger.info(f"[RESALE] Scanning {len(unlocked_non_exclusive)} unlocked item(s) for listing")

        # v14.5: Stop-loss & take-profit checks (before listing new items)
        if is_dry:
            try:
                stopped = await self.check_stop_losses(game_id)
                if stopped > 0:
                    logger.info(f"[STOP-LOSS] Simulated liquidation of {stopped} item(s)")
                profited = await self.check_take_profits(game_id)
                if profited > 0:
                    logger.info(f"[TAKE-PROFIT] Simulated profit-taking on {profited} item(s)")
            except Exception as e:
                logger.warning(f"[POSITION-GUARD] Stop/take check failed: {e}", exc_info=True)
        else:
            try:
                stopped = await self.check_stop_losses(game_id)
                if stopped > 0:
                    logger.warning(f"[STOP-LOSS] Liquidated {stopped} item(s) at loss")
                profited = await self.check_take_profits(game_id)
                if profited > 0:
                    logger.info(f"[TAKE-PROFIT] Took profit on {profited} item(s)")
            except Exception as e:
                logger.warning(f"[POSITION-GUARD] Stop/take check failed: {e}", exc_info=True)

        if is_dry:
            await self._dry_list_unlocked(unlocked_non_exclusive, game_id)
        else:
            await self._prod_list_unlocked(unlocked_non_exclusive, game_id)

    # DRY-mode helpers → src.core.target_sniping.resale_dry._ResaleDryMixin
    # PROD-mode helpers → src.core.target_sniping.resale_prod._ResaleProdMixin

    # ----------------------------------------------------------------
    # reprice
    # ----------------------------------------------------------------
    async def reprice_unsold_offers(self, game_id: str) -> None:
        """
        v12.7: Auto-reprice items listed for >REPRICE_AFTER_HOURS that haven't sold.

        Uses batch_edit_offers_v2 (up to 100 per request) instead of per-offer edit.
        DRY: just log.
        PROD: batch edit with a 5% lower price (configurable via SELL_REPRICE_DROP_PCT).
        """

        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        stale = price_db.get_stale_listings(int(Config.REPRICE_AFTER_HOURS * 3600))
        if not stale:
            return

        if is_dry:
            logger.info(
                f"[REPRICE] {len(stale)} items would be repriced (DRY simulation)"
            )
            return

        logger.info(
            f"[REPRICE] {len(stale)} item(s) listed >{Config.REPRICE_AFTER_HOURS}h, "
            f"dropping {REPRICE_DROP_PCT}%"
        )

        # v12.7: Batch repricing (up to 100 per request) instead of per-offer edit.
        edits_batch = []
        skipped = 0
        for it in stale:
            try:
                offer_id = it["dm_offer_id"] or ""
                if not offer_id:
                    skipped += 1
                    continue
                old_price = float(it["sell_price"] or 0)
                if old_price <= 0:
                    skipped += 1
                    continue
                # v14.3 Smart Reprice — order-book-aware price adjustment
                new_price = old_price   # default: no change yet
                floor = round(float(it["buy_price"] or 0) * 1.01, 2)
                if Config.SMART_REPRICE_ENABLED and hasattr(self, '_prev_agg_prices'):
                    from src.analysis.microstructure import smart_reprice_signal
                    agg_now = getattr(self, '_prev_agg_prices', {}).get(it["hash_name"], {})
                    prev_agg = getattr(self, '_prev_agg_prices_prior', {}).get(it["hash_name"], {})
                    if agg_now:
                        signal, suggested = smart_reprice_signal(
                            current_bid_count=agg_now.get("bid_count", 0) or 0,
                            current_ask_count=agg_now.get("ask_count", 0) or 0,
                            prev_bid_count=prev_agg.get("bid_count", 0) or 0,
                            prev_ask_count=prev_agg.get("ask_count", 0) or 0,
                            listed_price=old_price,
                            best_bid=agg_now.get("best_bid", 0.0) or 0.0,
                            best_ask=agg_now.get("best_ask", 0.0) or 0.0,
                        )
                        if signal == "drop" and suggested:
                            new_price = max(floor, round(suggested, 2))
                        elif signal == "boost" and suggested:
                            new_price = suggested  # demand rising, ask more
                        elif signal == "cancel":
                            # Withdraw stale listing entirely
                            _withdraw_id = int(it["id"])
                            price_db.update_virtual_status(_withdraw_id, "idle")
                            logger.info(
                                f"[SMART-REPRICE] Cancelled {it['hash_name']} "
                                f"@ ${old_price:.2f} — market deteriorated"
                            )
                            skipped += 1
                            continue

                # Drop the price, but never below buy_price * 1.01 (avoid loss)
                if not (Config.SMART_REPRICE_ENABLED and new_price != old_price):
                    new_price = round(old_price * (1 - REPRICE_DROP_PCT / 100.0), 2)
                floor = round(float(it["buy_price"] or 0) * 1.01, 2)
                if new_price < floor:
                    logger.debug(
                        f"[REPRICE] {it['hash_name']} at floor (${floor:.2f}), skipping"
                    )
                    skipped += 1
                    continue
                edits_batch.append({
                    "offer_id": offer_id,
                    "new_price_usd": new_price,
                    "db_id": int(it["id"]),
                    "title": it["hash_name"],
                    "old_price": old_price,
                })
            except (KeyError, IndexError) as e:
                logger.debug(f"[REPRICE] Row access error (skip): {e}")
                skipped += 1

        # Send in chunks of 100 (DMarket batch limit)
        repriced = 0
        for chunk_start in range(0, len(edits_batch), 100):
            chunk = edits_batch[chunk_start:chunk_start + 100]
            try:
                await self.client.batch_edit_offers_v2(chunk)
                # Mark all as repriced in DB
                for edit in chunk:
                    price_db.mark_listed(edit["db_id"], edit["offer_id"], edit["new_price_usd"])
                    repriced += 1
                    logger.info(
                        f"[REPRICE] {edit['title']} ${edit['old_price']:.2f} → "
                        f"${edit['new_price_usd']:.2f}"
                    )
            except Exception as e:
                logger.warning(
                    f"[REPRICE] Batch edit failed (chunk {chunk_start}-{chunk_start+len(chunk)}): {e}",
                    exc_info=True,
                )

        if repriced > 0:
            logger.info(f"[REPRICE] Repriced {repriced} item(s) successfully")
        if skipped > 0:
            logger.debug(f"[REPRICE] Skipped {skipped} item(s)")
