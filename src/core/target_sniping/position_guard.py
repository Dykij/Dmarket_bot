"""
position_guard.py — Stop-loss, take-profit, emergency liquidation (v14.5).

Protects held inventory from losses and locks in gains automatically.

Features:
  1. Stop-loss: auto-sell if current price drops below buy_price * (1 - threshold)
  2. Take-profit: auto-sell if current price rises above buy_price * (1 + threshold)
  3. Emergency liquidation: sell ALL unlocked items at best bid immediately

Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from src.config import Config
from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("PositionGuard")

# Tunables
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "20.0"))       # sell if price drops 20% below buy
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "15.0"))    # sell if profit reaches 15%
STOP_LOSS_ENABLED = os.getenv("STOP_LOSS_ENABLED", "true").lower() == "true"
TAKE_PROFIT_ENABLED = os.getenv("TAKE_PROFIT_ENABLED", "true").lower() == "true"
STOP_LOSS_MIN_AGE_HOURS = int(os.getenv("STOP_LOSS_MIN_AGE_HOURS", "1"))  # don't trigger on very fresh items
LIQUIDATE_AT_BID_DISCOUNT = float(os.getenv("LIQUIDATE_AT_BID_DISCOUNT", "0.01"))  # $0.01 below bid for fast exit

# v15.5: Time-stop — cancel buy targets sitting too long without fill
# Source: Reddit r/algotrading "90-minute time-stop for dead positions"
TIME_STOP_ENABLED = os.getenv("TIME_STOP_ENABLED", "true").lower() == "true"
TIME_STOP_MINUTES = int(os.getenv("TIME_STOP_MINUTES", "90"))  # cancel after 90min


class _PositionGuardMixin:
    """Stop-loss, take-profit, and liquidation logic."""

    client: Any  # DMarketAPIClient
    oracle: Any  # Oracle cache (or None)

    async def check_stop_losses(self, game_id: str) -> int:
        """
        Scan all idle (unlocked) items. If current oracle price has dropped
        below the stop-loss threshold relative to buy price, force-sell.
        Returns number of items liquidated.
        """
        if not STOP_LOSS_ENABLED:
            return 0

        items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
        if not items:
            return 0

        now = __import__("time").time()
        items_to_liquidate: list[tuple[Any, float, str]] = []  # (item, sell_price, reason)

        for it in items:
            buy_price = float(it["buy_price"] or 0)
            if buy_price <= 0:
                continue

            acquired = float(it["acquired_at"] or 0)
            age_hours = (now - acquired) / 3600.0 if acquired > 0 else 0
            if age_hours < STOP_LOSS_MIN_AGE_HOURS:
                continue

            current_price = await self._get_current_price(it["hash_name"])
            if current_price <= 0:
                continue

            loss_pct = ((buy_price - current_price) / buy_price) * 100.0
            if loss_pct >= STOP_LOSS_PCT:
                logger.warning(
                    f"[STOP-LOSS] {it['hash_name']}: "
                    f"bought ${buy_price:.2f}, now ${current_price:.2f} "
                    f"({loss_pct:.1f}% loss >= {STOP_LOSS_PCT:.1f}% threshold)"
                )
                items_to_liquidate.append((it, current_price, f"stop-loss {-loss_pct:.1f}%"))

        if not items_to_liquidate:
            return 0

        return await self._execute_liquidation(items_to_liquidate, game_id, "STOP-LOSS")

    async def check_take_profits(self, game_id: str) -> int:
        """
        Scan all idle (unlocked) items. If current price has risen
        above the take-profit threshold relative to buy price, sell.
        Returns number of items sold.
        """
        if not TAKE_PROFIT_ENABLED:
            return 0

        items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
        if not items:
            return 0

        items_to_sell: list[tuple[Any, float, str]] = []

        for it in items:
            buy_price = float(it["buy_price"] or 0)
            if buy_price <= 0:
                continue

            current_price = await self._get_current_price(it["hash_name"])
            if current_price <= 0:
                continue

            profit_pct = ((current_price - buy_price) / buy_price) * 100.0
            if profit_pct >= TAKE_PROFIT_PCT:
                logger.info(
                    f"[TAKE-PROFIT] {it['hash_name']}: "
                    f"bought ${buy_price:.2f}, now ${current_price:.2f} "
                    f"(+{profit_pct:.1f}% >= {TAKE_PROFIT_PCT:.1f}% target)"
                )
                items_to_sell.append((it, current_price, f"take-profit +{profit_pct:.1f}%"))

        if not items_to_sell:
            return 0

        return await self._execute_liquidation(items_to_sell, game_id, "TAKE-PROFIT")

    async def emergency_liquidate_all(self, game_id: str) -> dict[str, Any]:
        """
        Force-sell ALL unlocked inventory at current best bid.
        Used for emergency exit or /liquidate Telegram command.

        Returns {"liquidated": int, "total_value": float, "errors": int}
        """
        all_items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
        items_also = price_db.get_virtual_inventory(status="selling")
        all_items.extend(items_also)
        items_also = price_db.get_virtual_inventory(status="listed")
        all_items.extend(items_also)

        if not all_items:
            return {"liquidated": 0, "total_value": 0.0, "errors": 0}

        liquidate_list: list[tuple[Any, float, str]] = []
        for it in all_items:
            try:
                price = await self._get_current_price(it["hash_name"], use_bid=True)
            except Exception as e:
                logger.warning(f"[EMERGENCY-LIQ] Price fetch failed for {it['hash_name']}: {e}")
                price = 0.0
            if price <= 0:
                buy_px = float(it.get("buy_price") or 0)
                if buy_px <= 0:
                    logger.warning(f"[EMERGENCY-LIQ] No price for {it['hash_name']}, skipping (would sell at $0)")
                    continue
                price = round(buy_px * 0.95, 2)
                logger.warning(f"[EMERGENCY-LIQ] Fallback price ${price:.2f} for {it['hash_name']}")
            liquidate_list.append((it, price, "emergency-liquidation"))

        count = await self._execute_liquidation(liquidate_list, game_id, "EMERGENCY-LIQ")
        total_value = sum(sell_price for _, sell_price, _ in liquidate_list)
        return {"liquidated": count, "total_value": round(total_value, 2), "errors": len(liquidate_list) - count}

    async def _get_current_price(self, hash_name: str, use_bid: bool = False) -> float:
        """Get current market price from oracle cache or oracle."""
        if self.oracle is not None:
            if use_bid:
                bid = self.oracle.get_bid(hash_name)
                if bid is not None and bid > 0:
                    return bid
            ask = self.oracle.get_ask(hash_name)
            if ask is not None and ask > 0:
                return ask

        from src.api.oracle_factory import OracleFactory
        oracle = OracleFactory.get_oracle("a8db")
        if oracle:
            try:
                price = await oracle.get_item_price(hash_name)
                if price > 0:
                    return price
            except Exception as e:
                logger.debug(f"[POSITION-GUARD] Oracle price fetch failed for {hash_name}: {e}")
        return 0.0

    async def check_stale_targets(self, game_id: str) -> int:
        """v15.5: Cancel buy targets sitting too long without fill (time-stop).

        Source: Reddit r/algotrading — "90-minute time-stop for dead positions"
        Prevents capital lockup in unfilled orders.
        """
        if not TIME_STOP_ENABLED:
            return 0

        now = __import__("time").time()
        cutoff = now - (TIME_STOP_MINUTES * 60)

        targets = price_db.get_active_targets()
        if not targets:
            return 0

        stale: list[dict] = []
        for t in targets:
            created = float(t.get("created_at", 0))
            if created > 0 and created < cutoff:
                stale.append(t)

        if not stale:
            return 0

        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        cancelled = 0

        if is_dry:
            for t in stale:
                age_min = (now - float(t.get("created_at", 0))) / 60
                logger.info(
                    f"[TIME-STOP-SIM] Would cancel stale target: "
                    f"{t.get('hash_name', '?')} (age {age_min:.0f}min > {TIME_STOP_MINUTES}min)"
                )
                cancelled += 1
            return cancelled

        try:
            target_ids = [t["item_id"] for t in stale if t.get("item_id")]
            if target_ids:
                await self.client.batch_delete_targets(
                    [{"targetId": tid} for tid in target_ids]
                )
                for t in stale:
                    age_min = (now - float(t.get("created_at", 0))) / 60
                    logger.info(
                        f"[TIME-STOP] Cancelled stale target: "
                        f"{t.get('hash_name', '?')} (age {age_min:.0f}min)"
                    )
                    cancelled += 1
        except Exception as e:
            logger.warning(f"[TIME-STOP] Batch cancel failed: {e}")

        return cancelled

    async def _execute_liquidation(
        self,
        items: list[tuple[Any, float, str]],
        game_id: str,
        tag: str,
    ) -> int:
        """
        Batch-sell items at the given prices.
        In DRY_RUN, simulates the sales. In PROD, calls DMarket API.
        Returns count of successfully liquidated items.
        """
        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        liquidated = 0

        batch: list[dict[str, Any]] = []
        # Map virtual_inventory ids to plan entries
        id_to_plan: dict[int, tuple[Any, float, str]] = {}
        for item, sell_price, reason in items:
            row = dict(item)
            dm_id = row.get("dm_item_id") or row.get("asset_id") or ""
            if not dm_id:
                logger.warning(f"[{tag}] No dm_item_id for {row['hash_name']}, skipping")
                continue
            batch.append({"asset_id": dm_id, "price_usd": round(sell_price, 2)})
            id_to_plan[row["id"]] = (item, sell_price, reason)

        if not batch:
            return 0

        if is_dry:
            for _it_id, (item, sell_price, reason) in id_to_plan.items():
                buy_price = float(item["buy_price"] or 0)
                fee = round(sell_price * Config.FEE_RATE, 4)
                profit = sell_price - buy_price - fee
                price_db.update_virtual_status(item["id"], "sold")
                price_db.record_virtual_sale(
                    int(item["id"]), sell_price, fee,
                )
                logger.info(
                    f"[{tag}-SIM] {item['hash_name']}: "
                    f"${buy_price:.2f} → ${sell_price:.2f} "
                    f"(P&L ${profit:+.2f}, {reason})"
                )
                asyncio.create_task(
                    notifier.sell(
                        title=item["hash_name"],
                        buy_price_usd=buy_price,
                        sell_price_usd=sell_price,
                        profit_usd=round(profit, 4),
                    )
                )
                liquidated += 1
            return liquidated

        try:
            import asyncio as _asyncio
            result = await self.client.batch_create_offers_v2(batch)
            offer_entries = result.get("offers") or result.get("items") or []
            for entry in offer_entries:
                aid = entry.get("assetId") or entry.get("asset_id") or ""
                for _it_id, (item, sell_price, reason) in id_to_plan.items():
                    if item.get("dm_item_id") == aid or item.get("asset_id") == aid:
                        buy_price = float(item["buy_price"] or 0)
                        fee = round(sell_price * Config.FEE_RATE, 4)
                        profit = sell_price - buy_price - fee
                        price_db.update_virtual_status(item["id"], "selling")
                        logger.info(
                            f"[{tag}] {item['hash_name']}: "
                            f"${buy_price:.2f} → ${sell_price:.2f} "
                            f"(P&L ${profit:+.2f}, {reason})"
                        )
                        _asyncio.create_task(
                            notifier.sell(
                                title=item["hash_name"],
                                buy_price_usd=buy_price,
                                sell_price_usd=sell_price,
                                profit_usd=round(profit, 4),
                            )
                        )
                        liquidated += 1
                        break
        except Exception as e:
            logger.error(f"[{tag}] Batch liquidation failed: {e}", exc_info=True)
            logger.info(f"[{tag}] Falling back to individual offers for {len(batch)} items")
            import asyncio as _asyncio
            for entry in batch:
                try:
                    await self.client.create_offer(entry["asset_id"], entry["price_usd"])
                    liquidated += 1
                except Exception as e2:
                    logger.error(f"[{tag}] Individual sell fallback failed: {e2}")
            if liquidated > 0:
                logger.info(f"[{tag}] Fallback recovered {liquidated}/{len(batch)} items")

        return liquidated
