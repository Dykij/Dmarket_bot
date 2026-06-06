"""
execution.py — Instant-buy execution pipeline.

Mixin with the buy-execution logic (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List

from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


class _ExecutionMixin:
    """Instant-buy execution pipeline."""

    async def _execute_instant_buys(
        self,
        *,
        instant_buys: List[Dict[str, Any]],
        current_balance: float,
    ) -> None:
        """
        Execute a batch of instant buys produced by the filter loop.

        In DRY_RUN: simulates the buy and updates virtual inventory.
        In production: calls the real buy_items endpoint.
        """
        if not instant_buys:
            return

        logger.info(
            f"Executing INSTANT BUY for {len(instant_buys)} items (Strategy A)..."
        )
        await self._simulate_network_latency()
        self._maybe_inject_error("buy_items")
        buy_payloads = [item["buy_offer"] for item in instant_buys]
        buy_response = await self.client.buy_items(buy_payloads)

        # v12.3: DMarket returns 200 OK with `status: 'TxFailed'` and
        # `dmOffersFailReason: {code: 'OfferNotFound'}` if the listing was
        # already taken by another bot. We must check the response body
        # before recording the spend locally.
        successful_titles = set()
        if isinstance(buy_response, dict):
            status = buy_response.get("status", "")
            if status and status != "TxFailed":
                # All offers succeeded
                successful_titles = {
                    item_data["title"] for item_data in instant_buys
                }
            else:
                # Inspect dmOffersStatus to find successes
                dm_offers_status = buy_response.get("dmOffersStatus", {}) or {}
                for offer_id, info in dm_offers_status.items():
                    if info.get("started") or info.get("success"):
                        # Map offer_id back to title (best effort: any offer that started)
                        for item_data in instant_buys:
                            if (
                                item_data["buy_offer"].get("offerId")
                                == offer_id
                            ):
                                successful_titles.add(item_data["title"])
                                break
                fail_reason = buy_response.get("dmOffersFailReason", {}) or {}
                if fail_reason:
                    logger.warning(
                        f"Buy failed: {fail_reason.get('code', 'unknown')} "
                        f"for {fail_reason.get('offerId', '?')[:12]}..."
                    )
                elif status == "TxFailed":
                    logger.warning(f"Buy TxFailed: {buy_response}")
            logger.info(
                f"Buy response: status={status} "
                f"successful={len(successful_titles)}/{len(instant_buys)}"
            )

        for item_data in instant_buys:
            title = item_data["title"]
            item_id = item_data["item_id"]
            base_price = item_data["base_price"]
            list_price = item_data["list_price"]

            if os.getenv("DRY_RUN", "true").lower() == "true":
                if not self._simulate_competition(0.15):
                    logger.warning(
                        f"[SIM] COMPETITION! {title} was sniped by another bot first."
                    )
                    continue

                held_count = len(
                    [
                        x
                        for x in price_db.get_virtual_inventory(status="idle")
                        if x["hash_name"] == title
                    ]
                )
                if held_count >= 5:
                    logger.warning(
                        f"[SATURATION] Already holding {held_count}x {title}. Skipping."
                    )
                    continue

                price_db.add_virtual_item(title, base_price, trade_lock_hours=168)
                vwap = price_db.calculate_vwap(title)
                logger.info(
                    f"[SIM] SNIPED! {title} @ ${base_price} → list ${list_price} "
                    f"(spread: {item_data['best_bid']-item_data['best_ask']:.2f}, "
                    f"VWAP: ${vwap:.2f})"
                )
                # v12.2 Phase 2.1: Track asset status (trade_protected for 7 days)
                price_db.update_asset_status(
                    item_id,
                    title,
                    "trade_protected",
                    finalization_time=time.time() + 168 * 3600,
                )

            # v12.3: Only record local spend/target if the actual buy succeeded.
            # For DRY_RUN, always record (simulated). For production, gate on
            # successful_titles which is populated from the buy response.
            is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
            if is_dry or title in successful_titles:
                price_db.record_placed_target(item_id, title, base_price)
                self.liquidity.record_spend(base_price)
            else:
                logger.info(
                    f"Skipping local record for {title!r} — buy did not succeed"
                )
