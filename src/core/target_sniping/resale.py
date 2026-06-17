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

import asyncio
import logging
import math
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.core.target_sniping.resale_dry import _ResaleDryMixin
from src.core.target_sniping.resale_prod import _ResaleProdMixin
from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")

# Tunables (env-overridable for fine-tuning without code changes)
LIST_BATCH_SIZE = int(os.getenv("SELL_BATCH_SIZE", "10"))  # max items per /user-offers/create call
LIST_MIN_MARGIN_PCT = float(os.getenv("SELL_MIN_MARGIN_PCT", "3.0"))  # min gross margin to list
LIST_PRICE_DISCOUNT = float(os.getenv("SELL_LIST_DISCOUNT", "0.01"))  # undercut vs oracle by $0.01
REPRICE_DROP_PCT = float(os.getenv("SELL_REPRICE_DROP_PCT", "5.0"))  # drop price by 5% on reprice
SELL_MAX_OPEN_LISTINGS = int(os.getenv("SELL_MAX_OPEN_LISTINGS", "50"))  # cap on simultaneous listed items
SELL_FEE_RATE = float(os.getenv("SELL_FEE_RATE", str(Config.FEE_RATE)))  # 5% DMarket fee (with subscription)
INVENTORY_SYNC_MAX_PAGES = int(os.getenv("INVENTORY_SYNC_MAX_PAGES", "5"))  # pagination cap
CLOSED_OFFERS_LOOKBACK_DAYS = int(os.getenv("CLOSED_OFFERS_LOOKBACK_DAYS", "7"))  # how far back to scan for sales


class _ResaleMixin(_ResaleDryMixin, _ResaleProdMixin):
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
            if not item.get("exclusive")
        ]
        exclusive_count = len(unlocked_idle) - len(unlocked_non_exclusive)
        if exclusive_count > 0:
            logger.info(f"[RESALE] Skipping {exclusive_count} exclusive item(s) — kept for rarity")

        if not unlocked_non_exclusive:
            return

        logger.info(f"[RESALE] Scanning {len(unlocked_non_exclusive)} unlocked item(s) for listing")

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
        from src.config import Config

        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        time.time() - (Config.REPRICE_AFTER_HOURS * 3600)
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
        smart_edits = []   # v14.3: smart OFI-aware repricing
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
                if Config.SMART_REPRICE_ENABLED and hasattr(self, '_prev_agg_prices'):
                    from src.analysis.microstructure import smart_reprice_signal
                    agg_now = getattr(self, '_prev_agg_prices', {}).get(it["hash_name"], {})
                    if agg_now:
                        signal, suggested = smart_reprice_signal(
                            current_bid_count=agg_now.get("bid_count", 0) or 0,
                            current_ask_count=agg_now.get("ask_count", 0) or 0,
                            prev_bid_count=agg_now.get("bid_count", 0) or 0,
                            prev_ask_count=agg_now.get("ask_count", 0) or 0,
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
