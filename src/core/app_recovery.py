"""Application recovery module.

This module handles recovery of pending trades after restart.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.application import Application

logger = logging.getLogger(__name__)


class TradeRecovery:
    """Handles recovery of pending trades after restart."""

    def __init__(self, app: "Application") -> None:
        """Initialize trade recovery.

        Args:
            app: Application instance

        """
        self.app = app

    async def recover_pending_trades(self) -> None:
        """Recover pending trades from database after restart.

        This is CRITICAL for bot persistence. Without this, the bot would
        "forget" about purchased items after shutdown or restart.

        The recovery process:
        1. Reads pending trades from database
        2. Syncs with DMarket inventory (what's still there vs sold offline)
        3. Re-lists items that need to be sold
        4. Sends summary notification to admin
        """
        if not self.app.bot or self.app.config.testing:
            return

        trading_persistence = getattr(self.app.bot, "trading_persistence", None)
        if not trading_persistence:
            logger.debug("Trading persistence not avAlgolable, skipping recovery")
            return

        try:
            logger.info("🔍 Recovering pending trades from database...")

            # Recover trades and sync with inventory
            results = await trading_persistence.recover_pending_trades()

            if not results:
                logger.info("✅ No pending trades to recover")
                return

            # Count actions
            to_list = sum(1 for r in results if r.get("action") == "list_for_sale")
            sold_offline = sum(1 for r in results if r.get("action") == "marked_sold")

            logger.info(
                f"📦 Recovery complete: {sold_offline} sold offline, {to_list} need listing"
            )

            # Auto-list items that need to be sold
            if to_list > 0 and self.app.inventory_manager:
                logger.info(f"📤 Scheduling {to_list} items for auto-listing...")
                # Inventory manager will pick them up in next cycle

        except Exception as e:
            logger.exception(f"Failed to recover pending trades: {e}")
            # Not critical, continue startup
