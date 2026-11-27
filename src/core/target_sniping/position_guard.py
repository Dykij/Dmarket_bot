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
import os  # noqa: F401
import time
from typing import Any

import src.db.price_history as _price_history_mod
from src.analysis.algo_pack.ewma import ewma_volatility
from src.config import Config  # noqa: F401
from src.db.price_history import price_db
from src.utils.fee_utils import get_total_fee_rate

logger = logging.getLogger("PositionGuard")
_DEFAULT_PRICE_DB = price_db
_DEFAULT_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def _get_price_db() -> Any:
    """Resolve price_db honoring patches on either position_guard or price_history."""
    if price_db is not _DEFAULT_PRICE_DB:
        return price_db
    return _price_history_mod.price_db


async def _run_db(db: Any, fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a DB callable via db.run_in_thread when available, else inline (for mocks)."""
    runner = getattr(db, "run_in_thread", None)
    if asyncio.iscoroutinefunction(runner):
        return await runner(fn, *args, **kwargs)
    return fn(*args, **kwargs)


def liquidation_candidates() -> list[dict[str, Any]]:
    """Return all inventory items eligible for emergency liquidation in order:
    idle+only_unlocked, then selling, then listed."""
    db = _get_price_db()
    items = list(db.get_virtual_inventory(status="idle", only_unlocked=True))
    items.extend(db.get_virtual_inventory(status="selling"))  # sel3:cand-selling
    items.extend(db.get_virtual_inventory(status="listed"))
    return items


def _get_notifier():
    """P1-1: Lazy import notifier to avoid core->telegram coupling at import time."""
    from src.telegram.notifier import notifier
    return notifier

# BUG-9 FIX: Use Config fields instead of os.getenv (validated, typed, centralized)
STOP_LOSS_PCT = Config.STOP_LOSS_PCT
TAKE_PROFIT_PCT = Config.TAKE_PROFIT_PCT
STOP_LOSS_ENABLED = Config.STOP_LOSS_ENABLED
TAKE_PROFIT_ENABLED = Config.TAKE_PROFIT_ENABLED
STOP_LOSS_MIN_AGE_HOURS = Config.STOP_LOSS_MIN_AGE_HOURS


class _PositionGuardMixin:
    """Stop-loss, take-profit, and liquidation logic."""

    client: Any  # DMarketAPIClient

    async def check_stop_losses(self, game_id: str) -> int:
        """
        Scan all idle (unlocked) items. If current price has dropped
        below the stop-loss threshold relative to buy price, force-sell.
        Returns number of items liquidated.
        """
        if not STOP_LOSS_ENABLED:
            return 0

        db = _get_price_db()
        items = await _run_db(db, db.get_virtual_inventory, status="idle", only_unlocked=True)
        if not items:
            return 0

        now = time.time()
        items_to_liquidate: list[tuple[Any, float, str]] = []  # (item, sell_price, reason)

        for it in items:
            if it.get("exclusive"):
                continue  # keep-forever item (sticker rarity): never auto-sold
            buy_price = float(it["buy_price"] or 0)
            if buy_price <= 0:
                continue

            acquired = float(it["acquired_at"] or 0)
            age_hours = (now - acquired) / 3600.0 if acquired > 0 else 0
            if age_hours < STOP_LOSS_MIN_AGE_HOURS:
                continue

            current_price = await self._get_current_price(it["hash_name"], use_bid=True)
            if current_price <= 0:
                continue

            loss_pct = ((buy_price - current_price) / buy_price) * 100.0
            # Include sell-side fees in loss calculation for accurate trigger
            fee_pct = get_total_fee_rate() * 100.0
            realized_loss_pct = loss_pct + fee_pct
            if realized_loss_pct >= STOP_LOSS_PCT:
                logger.warning(
                    f"[STOP-LOSS] {it['hash_name']}: "
                    f"bought ${buy_price:.2f}, now ${current_price:.2f} "
                    f"({loss_pct:.1f}% loss >= {STOP_LOSS_PCT:.1f}% threshold)"
                )
                items_to_liquidate.append((it, current_price, f"stop-loss {-loss_pct:.1f}%"))
                continue  # sel3:one-reason-per-item

            # v17.2: Dynamic stop-loss for demand strategy items
            if Config.DEMAND_STRATEGY_ENABLED and it.get("strategy") == "demand":
                age_days = age_hours / 24.0

                # Instant stop: if price dropped >5% since purchase, sell immediately
                if buy_price > 0 and current_price < buy_price * 0.95 and age_days >= 1.0:
                    loss_pct = (buy_price - current_price) / buy_price * 100
                    logger.warning(
                        f"[DEMAND-INSTANT-STOP] {it['hash_name']}: "
                        f"price dropped {loss_pct:.1f}% in {age_days:.1f}d"
                    )
                    items_to_liquidate.append((it, current_price, f"demand-instant-stop {loss_pct:.1f}%"))
                    continue  # Skip time-based check for this item

                # Dynamic time-based stop: EWMA volatility → hold days
                try:
                    history = await _run_db(db, db.get_recent_prices, it["hash_name"], days=14)
                    prices = [p for p, _ in history if p > 0]

                    if len(prices) >= 10:
                        vol = ewma_volatility(prices, alpha=0.06)
                        # High vol (>3%) → shorter hold (2 days)
                        # Low vol (<1%) → longer hold (5 days)
                        dynamic_hold = max(2.0, min(6.0, 5.0 - (vol / 0.01) * 0.5))
                    else:
                        dynamic_hold = Config.DEMAND_MAX_HOLD_DAYS
                except Exception:
                    dynamic_hold = Config.DEMAND_MAX_HOLD_DAYS

                if age_days > dynamic_hold:
                    logger.warning(
                        f"[DEMAND-TIMEOUT] {it['hash_name']}: "
                        f"{age_days:.1f}d > {dynamic_hold:.1f}d"
                    )
                    items_to_liquidate.append((it, current_price, f"demand-timeout {age_days:.1f}d"))

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

        db = _get_price_db()
        items = await _run_db(db, db.get_virtual_inventory, status="idle", only_unlocked=True)
        if not items:
            return 0

        items_to_sell: list[tuple[Any, float, str]] = []

        for it in items:
            if it.get("exclusive"):
                continue  # keep-forever item (sticker rarity): never auto-sold
            buy_price = float(it["buy_price"] or 0)
            if buy_price <= 0:
                continue

            current_price = await self._get_current_price(it["hash_name"], use_bid=True)
            if current_price <= 0:
                continue

            profit_pct = ((current_price - buy_price) / buy_price) * 100.0
            # Include sell-side fees in profit calculation for accurate trigger
            fee_pct = get_total_fee_rate() * 100.0
            realized_profit_pct = profit_pct - fee_pct
            if realized_profit_pct >= TAKE_PROFIT_PCT:
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
        Force-sell ALL unlocked/selling/listed inventory at current best bid.
        Used for emergency exit or /liquidate Telegram command.

        Returns {"liquidated": int, "total_value": float, "errors": int,
                 "skipped_no_price": int, "exclusive": int}
        """
        db = _get_price_db()
        all_items = await _run_db(db, liquidation_candidates)

        if not all_items:
            return {
                "liquidated": 0,
                "total_value": 0.0,
                "errors": 0,
                "skipped_no_price": 0,
                "exclusive": 0,
            }

        unique_titles = list({it["hash_name"] for it in all_items if it.get("hash_name")})
        bids: dict[str, dict[str, Any]] = {}
        if unique_titles:
            try:
                bids = await self.client.get_aggregated_prices(game_id, titles=unique_titles)  # sel3:liq-fetch-bids
            except Exception as e:
                logger.warning(f"[EMERGENCY-LIQ] Aggregated prices fetch failed: {e}")

        liquidate_list: list[tuple[Any, float, str]] = []
        skipped_no_price = 0
        for it in all_items:
            price = float((bids.get(it["hash_name"]) or {}).get("best_bid") or 0)
            if price <= 0:
                skipped_no_price += 1
                logger.warning(f"[EMERGENCY-LIQ] No bid for {it['hash_name']}, skipping")
                continue  # sel3:liq-no-price-skip
            liquidate_list.append((it, price, "emergency-liquidation"))

        if not liquidate_list:
            return {
                "liquidated": 0,
                "total_value": 0.0,
                "errors": 0,
                "skipped_no_price": skipped_no_price,
                "exclusive": 0,
            }

        self._last_liquidated_ids: set[int] = set()
        count = await self._execute_liquidation(liquidate_list, game_id, "EMERGENCY-LIQ")
        succeeded_ids = getattr(self, "_last_liquidated_ids", set())
        executable = [
            (dict(it) if not isinstance(it, dict) else it, sell_price)
            for it, sell_price, _ in liquidate_list
            if (dict(it) if not isinstance(it, dict) else it).get("dm_item_id")
            or (dict(it) if not isinstance(it, dict) else it).get("asset_id")
        ]
        if count <= 0:
            sold_rows: list[tuple[dict[str, Any], float]] = []
        elif succeeded_ids:
            sold_rows = [
                (row, sell_price)
                for row, sell_price in executable
                if int(row["id"]) in succeeded_ids
            ]
        else:
            sold_rows = executable if count >= len(executable) else []
        total_value = sum(sell_price for _, sell_price in sold_rows)
        exclusive_count = sum(1 for row, _ in sold_rows if row.get("exclusive"))
        return {
            "liquidated": count,
            "total_value": round(total_value, 2),
            "errors": len(liquidate_list) - count,
            "skipped_no_price": skipped_no_price,
            "exclusive": exclusive_count,
        }

    async def _get_current_price(self, hash_name: str, use_bid: bool = False) -> float:
        """Get current market price from DMarket aggregated prices."""
        agg = getattr(self, '_current_agg_prices', {})
        data = agg.get(hash_name, {})
        if use_bid:
            return float(data.get("best_bid", 0) or 0)
        return float(data.get("best_ask", 0) or 0)

    @staticmethod
    def _is_definite_rejection(exc: BaseException) -> bool:
        """True only if the server certainly rejected the request (HTTP 4xx
        other than 429). Timeouts, disconnects, 5xx, 429 and exhausted retries
        leave the outcome unknown or merely rate-limited."""
        import aiohttp

        return (
            isinstance(exc, aiohttp.ClientResponseError)
            and 400 <= exc.status < 500
            and exc.status != 429
        )

    @staticmethod
    def _failed_asset_ids(result: Any, tag: str) -> set[str]:
        """assetIds listed in `failed[]` of a batchCreate answer (logged)."""
        failed = result.get("failed") if isinstance(result, dict) else None
        ids: set[str] = set()
        for f in failed or []:
            if not isinstance(f, dict):
                continue
            aid = f.get("assetId") or f.get("asset_id") or ""
            ids.add(aid)
            logger.warning(
                f"[{tag}] Listing refused for {aid}: code={f.get('code')} "
                f"reason={f.get('reasonCode')} {f.get('message') or ''}".rstrip()
            )
        return ids

    def _spawn_sell_notification(
        self, title: str, buy_price: float, sell_price: float, profit: float
    ) -> None:
        """Spawn notifier.sell task and keep a strong reference until completion."""
        task = asyncio.create_task(
            _get_notifier().sell(
                title=title,
                buy_price_usd=buy_price,
                sell_price_usd=sell_price,
                profit_usd=round(profit, 4),
            )
        )
        tasks_set = getattr(self, "_background_tasks", None)
        if tasks_set is None:
            tasks_set = _DEFAULT_BACKGROUND_TASKS
        tasks_set.add(task)
        task.add_done_callback(tasks_set.discard)

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
        is_dry = Config.DRY_RUN
        db = _get_price_db()
        self._last_liquidated_ids = set()
        liquidated = 0

        batch: list[dict[str, Any]] = []
        # Map virtual_inventory ids to plan entries
        id_to_plan: dict[int, tuple[Any, float, str]] = {}
        for item, sell_price, reason in items:
            row = dict(item) if not isinstance(item, dict) else item
            dm_id = row.get("dm_item_id") or row.get("asset_id") or ""
            if not dm_id:
                logger.warning(f"[{tag}] No dm_item_id for {row['hash_name']}, skipping")
                continue
            batch.append({"asset_id": dm_id, "price_usd": round(sell_price, 2)})
            id_to_plan[row["id"]] = (row, sell_price, reason)

        if not batch:
            return 0

        if is_dry:
            for _it_id, (item, sell_price, reason) in id_to_plan.items():
                buy_price = float(item["buy_price"] or 0)
                fee = round(sell_price * get_total_fee_rate(), 4)
                profit = sell_price - buy_price - fee
                await _run_db(db, db.update_virtual_status, item["id"], "sold")
                await _run_db(db, db.record_virtual_sale, int(item["id"]), sell_price, fee)
                logger.info(
                    f"[{tag}-SIM] {item['hash_name']}: "
                    f"${buy_price:.2f} → ${sell_price:.2f} "
                    f"(P&L ${profit:+.2f}, {reason})"
                )
                # BUG-10 FIX: Store task reference to prevent GC before completion
                self._spawn_sell_notification(item["hash_name"], buy_price, sell_price, profit)
                self._last_liquidated_ids.add(int(item["id"]))
                liquidated += 1
            return liquidated

        try:
            result = await self.client.batch_create_offers_v2(batch)
            failed_ids = self._failed_asset_ids(result, tag)
            offer_entries = result.get("offers") or result.get("items") or []
            for entry in offer_entries:
                aid = entry.get("assetId") or entry.get("asset_id") or ""
                if aid in failed_ids:
                    continue
                for _it_id, (item, sell_price, reason) in id_to_plan.items():
                    if item.get("dm_item_id") == aid or item.get("asset_id") == aid:
                        buy_price = float(item["buy_price"] or 0)
                        fee = round(sell_price * get_total_fee_rate(), 4)
                        profit = sell_price - buy_price - fee
                        await _run_db(db, db.update_virtual_status, item["id"], "selling")
                        logger.info(
                            f"[{tag}] {item['hash_name']}: "
                            f"${buy_price:.2f} → ${sell_price:.2f} "
                            f"(P&L ${profit:+.2f}, {reason})"
                        )
                        # BUG-10 FIX: Store task reference to prevent GC
                        self._spawn_sell_notification(item["hash_name"], buy_price, sell_price, profit)
                        self._last_liquidated_ids.add(int(item["id"]))
                        liquidated += 1
                        break
        except Exception as e:
            logger.error(f"[{tag}] Batch liquidation failed: {e}", exc_info=True)
            if not self._is_definite_rejection(e):
                # Timeout / dropped connection / 5xx / exhausted retries / 429:
                # the batch may have been processed. Re-listing item by item
                # now would double-handle assets; inventory sync reconciles.
                logger.warning(
                    f"[{tag}] Outcome of the batch is unknown ({type(e).__name__}); "
                    f"no individual fallback for {len(batch)} items"
                )
                return liquidated
            logger.info(f"[{tag}] Falling back to individual offers for {len(batch)} items")
            for entry in batch:
                try:
                    single = [{"asset_id": entry["asset_id"], "price_usd": entry["price_usd"]}]
                    res = await self.client.batch_create_offers_v2(single)
                    failed_ids = self._failed_asset_ids(res, tag)
                    listed = {
                        o.get("assetId") or o.get("asset_id") or ""
                        for o in (res.get("offers") or res.get("items") or [])
                    }
                    if entry["asset_id"] in listed and entry["asset_id"] not in failed_ids:
                        aid = entry["asset_id"]
                        for _it_id, (item, sell_price, reason) in id_to_plan.items():
                            if item.get("dm_item_id") == aid or item.get("asset_id") == aid:
                                buy_price = float(item["buy_price"] or 0)
                                fee = round(sell_price * get_total_fee_rate(), 4)
                                profit = sell_price - buy_price - fee
                                await _run_db(db, db.update_virtual_status, item["id"], "selling")
                                logger.info(
                                    f"[{tag}-FALLBACK] {item['hash_name']}: "
                                    f"${buy_price:.2f} → ${sell_price:.2f} "
                                    f"(P&L ${profit:+.2f}, {reason})"
                                )
                                self._spawn_sell_notification(item["hash_name"], buy_price, sell_price, profit)
                                self._last_liquidated_ids.add(int(item["id"]))
                                liquidated += 1
                                break
                except Exception as e2:
                    logger.error(f"[{tag}] Individual sell fallback failed: {e2}")
            if liquidated > 0:
                logger.info(f"[{tag}] Fallback recovered {liquidated}/{len(batch)} items")

        return liquidated
