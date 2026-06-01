"""
resale.py — Auto-resale + repricing pipeline.

Mixin with the post-buy pipeline: lists items for sale, sells them, and
reprices stale listings. Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from src.api.oracle_factory import OracleFactory
from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


class _ResaleMixin:
    """Post-buy pipeline (list, sell, reprice)."""

    async def auto_resale(self, game_id: str) -> None:
        """
        v12.0: Scans virtual inventory and lists items at best_bid - 0.01.
        """
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
        locked_count = (
            len(price_db.get_virtual_inventory(status="idle", only_unlocked=False))
            - len(items)
        )
        selling_items = price_db.get_virtual_inventory(status="selling")

        if locked_count > 0:
            logger.info(f"Trade Lock: {locked_count} items are currently frozen.")

        for item in selling_items:
            if random.random() < 0.4:
                price_db.update_virtual_status(item["id"], "sold")
                logger.info(f"[SIM] ITEM SOLD! {item['hash_name']} | Exit Profit logged.")

        if not items:
            return
        logger.info(f"Scanning Virtual Inventory for resale ({len(items)} items)...")
        for item in items:
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                continue
            try:
                current_price = await oracle.get_item_price(item["hash_name"])
                if current_price <= 0:
                    continue
                buy_price = item["buy_price"]
                target_sell = round(buy_price * 1.05, 2)
                market_profit = round(current_price * 0.95 - buy_price, 2)
                if current_price >= target_sell:
                    price_db.update_virtual_status(item["id"], "selling")
                    logger.info(
                        f"[SIM] LISTING: {item['hash_name']} | "
                        f"Buy: ${buy_price} | Market: ${current_price} | "
                        f"Est. Net Profit: ${market_profit}"
                    )
            except Exception as e:
                logger.debug(f"Resale check failed for {item['hash_name']}: {e}")

    async def reprice_unsold_offers(self, game_id: str) -> None:
        """
        v12.0: Reprice items that have been listed > REPRICE_AFTER_HOURS.
        In production: call client.edit_offer(); in DRY_RUN: log only.
        """
        from src.config import Config

        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        selling_items = price_db.get_virtual_inventory(status="selling")
        if not selling_items:
            return
        cutoff = time.time() - (Config.REPRICE_AFTER_HOURS * 3600)
        stale = [it for it in selling_items if it["acquired_at"] < cutoff]
        if stale:
            logger.info(
                f"[REPRICE] {len(stale)} items pending repricing "
                f"(>{Config.REPRICE_AFTER_HOURS}h listed)"
            )
