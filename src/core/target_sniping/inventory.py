"""
inventory.py — v12.2 inventory status sync (trade_protected, reverted).

Mixin with the inventory-status helpers. Mixed into `SnipingLoop`
(see `core.py`).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


class _InventoryMixin:
    """v12.2 inventory status sync (trade_protected, reverted)."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient

    # ------------------------------------------------------------------
    # v12.2 Phase 2.1: Inventory Status Sync (trade_protected, reverted)
    # ------------------------------------------------------------------
    async def _sync_inventory_statuses(self, game_id: str) -> None:
        """
        Synchronize asset statuses with DMarket's authoritative state.
        Updates asset_status table with:
        - status='trade_protected' if item is locked
        - status='reverted' if DMarket rolled back the transaction
        - status='active' if item is now tradable

        Also detects rollbacks via transaction history.
        """
        if os.getenv("DRY_RUN", "true").lower() == "true":
            # In sandbox we just simulate; status changes happen rarely
            return

        try:
            # 1. Fetch detailed inventory from DMarket
            inv_items = await self.client.get_user_inventory_detailed(game_id, limit=100)
            if not inv_items:
                return

            updated_count = 0
            for item in inv_items:
                item_id = item.get("itemId", "")
                if not item_id:
                    continue
                status = item.get("status", "active")
                finalization_time = item.get("FinalizationTime", 0.0)
                title = item.get("title", "")

                # Update local status from DMarket's authoritative state
                old_status = price_db.get_asset_status(item_id)
                if not old_status or old_status["status"] != status:
                    price_db.update_asset_status(item_id, title, status, finalization_time)
                    updated_count += 1
                    if status == "reverted":
                        logger.warning(
                            f"[STATUS] Asset {title} ({item_id}) was REVERTED by DMarket"
                        )
                    elif status == "trade_protected":
                        logger.info(
                            f"[STATUS] Asset {title} ({item_id}) is trade_protected "
                            f"until {finalization_time}"
                        )

            if updated_count > 0:
                logger.info(f"[STATUS-SYNC] Updated {updated_count} asset statuses")

            # 2. Cross-check with transaction history for rollbacks
            txs = await self.client.get_transaction_history(days=7, limit=50)
            reverted_count = 0
            for tx in txs:
                if tx.get("type") == "reverted" or tx.get("status") == "reverted":
                    item_id = tx.get("itemId", "")
                    # Only mark if we previously knew the item
                    if item_id and price_db.is_known_item(item_id):
                        if price_db.get_asset_status(item_id):
                            price_db.mark_reverted(item_id)
                            reverted_count += 1
            if reverted_count > 0:
                logger.warning(
                    f"[STATUS-SYNC] {reverted_count} newly-reverted items detected"
                )

        except Exception as e:
            logger.debug(f"Inventory status sync failed: {e}")

    def _skip_if_locked(self, item_id: str, title: str) -> bool:
        """
        Returns True if the item should be SKIPPED due to:
        - We already own it (would double-buy)
        - It's currently trade_protected
        - It's been reverted
        """
        if price_db.is_known_item(item_id):
            asset = price_db.get_asset_status(item_id)
            if asset:
                if asset["status"] == "reverted":
                    logger.debug(f"[SKIP] {title} was reverted, skipping")
                    return True
                if asset["status"] == "trade_protected":
                    fin = asset["finalization_time"]
                    if fin <= 0 or fin > time.time():
                        logger.debug(f"[SKIP] {title} is trade_protected")
                        return True
        return False
