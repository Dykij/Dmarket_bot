"""
resale_prod.py — PROD-mode helpers for the resale pipeline (real DMarket API).

Mixed into SnipingLoop via _ResaleMixin (see resale.py).
"""

from __future__ import annotations

from src.core.target_sniping.resale_pricing import calculate_list_price

import asyncio
import logging
import time
from typing import Any

import aiohttp
from tenacity import RetryError

from src.api.dmarket_api_client.backoff import CircuitOpenError
from src.config import Config  # noqa: F401
from src.db.price_history import price_db
from src.utils.fee_utils import get_total_fee_rate
# P1-1: Lazy import

logger = logging.getLogger("SnipingBot")

def _get_notifier():
    """P1-1: Lazy import notifier to avoid core->telegram coupling at import time."""
    from src.telegram.notifier import notifier
    return notifier

def _min_list_price(buy_price: float, margin_pct: float, fee_rate: float) -> float:
    """Lowest list price that still nets ``margin_pct`` on ``buy_price`` AFTER the sell fee.

    The fee is charged on the sale price, so the price must be divided by
    (1 - fee), not multiplied by (1 + margin + fee):
        net = price * (1 - fee) >= buy_price * (1 + margin)
    Same formula as resale_pipeline.py (min_sell_for_profit).
    A fee outside [0, 1) is invalid: return +inf so the caller skips the item.
    """
    if not (0.0 <= fee_rate < 1.0):
        return float("inf")
    return buy_price * (1.0 + margin_pct / 100.0) / (1.0 - fee_rate)


def _parse_batch_create_results(resp: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Parse DMarket v2 offers:batchCreate response by assetId.

    Returns:
        (success_map, failed_map)
        success_map: {assetId: offerId}
        failed_map: {assetId: error_message}
    """
    success_map: dict[str, str] = {}
    failed_map: dict[str, str] = {}
    if not isinstance(resp, dict):
        return success_map, failed_map

    # 1. Parse failed[] reasons first (mandatory handling per П.7)
    failed_items = resp.get("failed")
    if isinstance(failed_items, list):
        for fail in failed_items:
            if isinstance(fail, dict):
                raw_aid = fail.get("assetId") or fail.get("asset_id")
                if raw_aid is not None and str(raw_aid).strip():
                    aid = str(raw_aid).strip()
                    err = fail.get("message") or fail.get("code") or fail.get("reasonCode") or "listing failed"
                    failed_map[aid] = str(err)

    # 2. Parse successful offers[] by assetId
    raw_offers = resp.get("offers") or resp.get("Items") or resp.get("items")
    if isinstance(raw_offers, list):
        for item in raw_offers:
            if isinstance(item, dict):
                raw_aid = item.get("assetId") or item.get("asset_id")
                raw_oid = item.get("id") or item.get("offerId") or item.get("OfferID")
                if raw_aid is not None and raw_oid is not None:
                    aid = str(raw_aid).strip()
                    oid = str(raw_oid).strip()
                    if aid and oid and aid not in failed_map:
                        success_map[aid] = oid

    return success_map, failed_map


# Specification: DMarket v2.0.0 batchCreate response {offers: [...], failed: [...]}
# reasonCode: "UNAVAILABLE — временный сбой, единственный, который стоит повторить
# как есть (code = Internal); любое другое значение снова даст отказ, пока что-то не изменится."
_TRANSIENT_FAIL_CODES: frozenset[str] = frozenset({"internal", "unavailable"})


def _transient_failed_ids(resp: dict) -> set[str]:
    """Return assetIds from failed[] with transient/retryable codes (Internal / UNAVAILABLE)."""
    if not isinstance(resp, dict):
        return set()
    failed = resp.get("failed")
    if not isinstance(failed, list):
        return set()
    transient_ids: set[str] = set()
    for item in failed:
        if isinstance(item, dict):
            raw_aid = item.get("assetId") or item.get("asset_id")
            if raw_aid is not None and str(raw_aid).strip():
                code = str(item.get("code") or "").strip().lower()
                reason = str(item.get("reasonCode") or "").strip().lower()
                if code in _TRANSIENT_FAIL_CODES or reason in _TRANSIENT_FAIL_CODES:
                    transient_ids.add(str(raw_aid).strip())
    return transient_ids


def _is_unknown_outcome(exc: BaseException) -> bool:
    """True if the mutating request failed transiently or left the outcome unknown.

    (Timeout, connection error, 5xx, 429 rate limit, tenacity retry exhausted;
    CircuitOpenError: запрос не отправлен (breaker открыт), предметы остаются idle для следующего цикла).
    HTTP 4xx (except 429) or other errors mean definite rejection or invalid input.
    """
    if isinstance(
        exc,
        (
            asyncio.TimeoutError,
            TimeoutError,
            aiohttp.ClientConnectionError,
            RetryError,
            CircuitOpenError,
        ),
    ):
        return True
    if isinstance(exc, aiohttp.ClientResponseError):
        return exc.status >= 500 or exc.status == 429
    return False


class _ResaleProdMixin:
    """Production resale — real DMarket API calls."""

    client: Any

    async def _sync_real_inventory(self, game_id: str) -> int:
        """
        PROD: Pull DMarket inventory and ensure every item is in our
        local virtual_inventory with its real dm_item_id. Returns count
        of newly linked items.
        """
        from src.core.target_sniping.resale_constants import INVENTORY_SYNC_MAX_PAGES

        new_count = 0
        cursor: str | None = None
        for _ in range(INVENTORY_SYNC_MAX_PAGES):
            try:
                resp = await self.client.get_user_inventory(
                    game_id=game_id, limit=50, cursor=cursor
                )
            except Exception as e:
                logger.debug(f"get_user_inventory failed: {e}")
                break
            items = resp.get("objects", [])
            if not items:
                break
            for it in items:
                dm_item_id = it.get("itemId", "")
                title = it.get("title", "")
                if not dm_item_id or not title:
                    continue
                # v2 inventory: inMarket=False means the item is still in the
                # Steam inventory; its id is composite and a dmarket listing
                # with it answers 400. None (flag absent) keeps old behaviour.
                if it.get("inMarket") is False:
                    continue
                # Skip if already tracked
                if await price_db.run_in_thread(price_db.find_by_dm_item_id, dm_item_id) is not None:  # P2-17: async
                    continue
                # Bought rows are recorded WITHOUT dm_item_id (the offers-buy
                # response carries no item ids). Link the oldest such idle row
                # of the same title instead of inserting a duplicate.
                unlinked = await price_db.run_in_thread(
                    price_db.execute_and_fetchone,
                    "SELECT id FROM virtual_inventory "
                    "WHERE hash_name = ? AND status = 'idle' "
                    "AND (dm_item_id IS NULL OR dm_item_id = '') "
                    "ORDER BY id ASC LIMIT 1",
                    (title,),
                )
                if unlinked:
                    await price_db.run_in_thread(
                        price_db.attach_dm_item_id, int(unlinked["id"]), dm_item_id
                    )
                    new_count += 1
                    continue
                # Infer buy price from item's history (best effort):
                # DMarket inventory items don't include buy price. Use the
                # avg price from the most recent buy cycle as a proxy, or
                # fall back to 0.0 (PnL will be wrong but listing still works).
                inferred_price = 0.0
                avg_row = await price_db.run_in_thread(
                    price_db.execute_and_fetchone,
                    "SELECT AVG(buy_price) as p FROM virtual_inventory "
                    "WHERE hash_name = ? AND status IN ('sold','listed')",
                    (title,),
                )
                if avg_row and avg_row["p"]:
                    inferred_price = float(avg_row["p"])
                # v15.10: Single INSERT with dm_item_id to avoid phantom rows on crash
                await price_db.run_in_thread(
                    price_db.execute_and_get_lastrowid,
                    "INSERT INTO virtual_inventory "
                    "(hash_name, buy_price, status, acquired_at, unlock_at, dm_item_id) "
                    "VALUES (?, ?, 'idle', ?, ?, ?)",
                    (title, inferred_price, time.time(), time.time(), dm_item_id),
                )
                new_count += 1
            cursor = resp.get("cursor")
            if not cursor or len(items) < 50:
                break
        return new_count

    async def _check_external_sales(self, game_id: str) -> int:
        """
        PROD: For every `listed` local item, check if its dm_offer_id
        has been closed in DMarket's user-offers/closed. If so, mark
        it sold locally and notify. Returns count of newly-detected sells.

        v13.1: Handles Trade Protection funds hold and rollback refunds.
        """
        listed = await price_db.run_in_thread(price_db.get_virtual_inventory, "listed")  # P2-17: async
        if not listed:
            return 0
        detected = 0
        # Follow the cursor until every listed offer is found, the pages end,
        # the server repeats a cursor (ignores it) or a page adds nothing new.
        wanted = {it["dm_offer_id"] for it in listed if it["dm_offer_id"]}
        closed_by_id: dict[str, dict[str, Any]] = {}
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _page in range(10):
            try:
                closed_resp = await self.client.get_user_closed_offers(
                    game_id=game_id, limit=50, cursor=cursor
                )
            except Exception as e:
                logger.debug(f"get_user_closed_offers failed: {e}")
                if not closed_by_id:
                    return 0
                break
            added = 0
            for o in closed_resp.get("objects", []):
                oid = o.get("offerId", "")
                if oid and oid not in closed_by_id:
                    closed_by_id[oid] = o  # v13.1: full record keyed by offerId
                    added += 1
            cursor = closed_resp.get("cursor")
            if (
                not cursor
                or cursor in seen_cursors
                or added == 0
                or wanted.issubset(closed_by_id)
            ):
                break
            seen_cursors.add(cursor)
        for it in listed:
            offer_id = it["dm_offer_id"] or ""
            if not offer_id or offer_id not in closed_by_id:
                continue
            match = closed_by_id[offer_id]
            # v13.1: Handle rollbacks — item reverted, DMarket refunded 100%
            closed_status = match.get("status", "")
            if closed_status not in ("successful", "trade_protected", "reverted"):
                logger.warning(
                    f"[SELL-CHECK] unknown closed status {closed_status!r} for "
                    f"offer {offer_id}; not treated as a sale"
                )
                continue
            if closed_status == "reverted":
                await price_db.run_in_thread(price_db.set_rollback_refund, offer_id)  # P2-17: async
                logger.info(
                    f"[ROLLBACK] {it['hash_name']} was reverted on DMarket — "
                    f"100% refund applied, PnL neutral."
                )
                # Mark as sold with zero PnL
                await price_db.run_in_thread(price_db.update_virtual_status, int(it["id"]), "sold")  # P2-17: async
                await price_db.run_in_thread(price_db.record_virtual_sale, int(it["id"]), float(it["buy_price"] or 0), 0.0)  # P2-17: async
                detected += 1
                continue
            sell_price = 0.0
            fee = 0.0
            # closed offers report the price in DOLLARS (client normalizes to
            # price_usd); fee_usd is DMarket's actual fee when present.
            sell_price = float(match.get("price_usd") or 0.0)
            fee_usd = match.get("fee_usd")
            if sell_price > 0 and fee_usd is not None and 0 <= fee_usd < sell_price:
                fee = round(float(fee_usd), 4)
            else:
                fee = round(sell_price * get_total_fee_rate(), 4)
            # Fall back to our last known listed price if closed records
            # are paginated away.
            if sell_price <= 0:
                sell_price = float(it["sell_price"] or 0)
                fee = round(sell_price * get_total_fee_rate(), 4)
            if sell_price <= 0:
                continue
            await price_db.run_in_thread(price_db.record_virtual_sale, int(it["id"]), sell_price, fee)  # P2-17: async
            # v13.1: Track funds hold from Trade Protection
            finalization_time = float(match.get("finalization_time") or 0.0)
            if finalization_time > time.time():
                await price_db.run_in_thread(price_db.set_funds_hold, int(it["id"]), finalization_time)  # P2-17: async
                logger.info(
                    f"[FUNDS-HOLD] {it['hash_name']}: ${sell_price:.2f} frozen "
                    f"until {time.ctime(finalization_time)} (Trade Protection)"
                )
            profit = sell_price - float(it["buy_price"] or 0) - fee
            logger.info(
                f"[SELL] {it['hash_name']} | "
                f"Buy: ${it['buy_price']:.2f} → Sell: ${sell_price:.2f} "
                f"| PnL: ${profit:+.2f}"
            )
            # v15.10 FIX: Store task reference to prevent GC before completion
            _task = asyncio.create_task(
                _get_notifier().sell(
                    title=it["hash_name"],
                    buy_price_usd=float(it["buy_price"] or 0),
                    sell_price_usd=sell_price,
                    profit_usd=profit,
                )
            )
            self._background_tasks = getattr(self, '_background_tasks', set())
            self._background_tasks.add(_task)
            _task.add_done_callback(self._background_tasks.discard)
            # v12.5: record sell outcome in risk manager (positive PnL)
            if hasattr(self, "risk"):
                try:
                    self.risk.record_trade_outcome(
                        pnl_usd=profit,
                        trade_type="sell",
                        item_title=it["hash_name"],
                    )
                except Exception as e:
                    logger.debug(f"risk.record_trade_outcome (sell) failed: {e}")
            # v18.3: Record trade outcome for DynamicRiskManager Kelly statistics
            if not hasattr(self, '_dynamic_risk'):
                from src.risk.dynamic_manager import DynamicRiskManager
                self._dynamic_risk = DynamicRiskManager()
            try:
                self._dynamic_risk.record_trade(
                    won=profit > 0,
                    profit_usd=profit if profit > 0 else 0.0,
                    loss_usd=abs(profit) if profit < 0 else 0.0,
                )
            except Exception as e:
                logger.debug(f"dynamic_risk.record_trade failed: {e}")
            # v18.2: Record sell in persistent trade history
            try:
                from src.db.profit_tracker import db as profit_db
                result = profit_db.record_sell(it["hash_name"], float(sell_price))
                if "error" not in result:
                    logger.info(
                        f"[TRADE-HISTORY] {it['hash_name']}: "
                        f"bought ${result['buy_price']:.2f} -> sold ${result['sell_price']:.2f} "
                        f"in {result['hold_days']:.1f}d (profit ${result['net_profit']:.2f})"
                    )
            except Exception as e:
                logger.debug(f"profit_tracker.record_sell failed: {e}")
            detected += 1
        return detected

    async def _sync_sold_offers(self, game_id: str) -> int:
        """
        PROD: Look for items we DON'T have in local DB that recently
        sold on DMarket. This is for cases where the user manually
        sold something and the bot should still record it.
        Currently a no-op (we only track items the bot itself bought).
        Returns 0; kept for future extension.
        """
        return 0

    async def _prod_list_unlocked(self, items: list[Any], game_id: str) -> None:
        """
        PROD: Batch-list unlocked items on DMarket.

        Strategy:
        1. Group items by hash_name
        2. For each unique title, fetch oracle price from cache (free)
        3. If oracle says price > buy_price * (1 + min_margin), list it
        4. Cap simultaneous listings to SELL_MAX_OPEN_LISTINGS
        5. Call create_sell_offers_batch in chunks of LIST_BATCH_SIZE
        6. Track success/failure per item
        """
        from src.core.target_sniping.resale_constants import (
            LIST_BATCH_SIZE,
            LIST_MIN_MARGIN_PCT,
            SELL_MAX_OPEN_LISTINGS,
        )

        # Cap on already-listed count
        listed_count = len(await price_db.run_in_thread(price_db.get_virtual_inventory, "listed"))  # P2-17: async
        if listed_count >= SELL_MAX_OPEN_LISTINGS:
            logger.info(
                f"[RESALE] {listed_count} items already listed (cap {SELL_MAX_OPEN_LISTINGS}). "
                f"Skipping new listings this cycle."
            )
            return

        # Filter to items we can actually list (need dm_item_id).
        # sqlite3.Row doesn't have a .get() method, so we use dict-style
        # access with a None default via try/except for optional cols.
        def _row_get(row, col, default=None):
            try:
                val = row[col]
                return val if val is not None else default
            except (IndexError, KeyError):
                return default

        listable: list[Any] = []
        for it in items:
            dm_id = _row_get(it, "dm_item_id", "")
            if not dm_id:
                continue
            buy_price = _row_get(it, "buy_price", 0.0) or 0.0
            if buy_price <= 0:
                continue
            err = _row_get(it, "list_error", None)
            if err:
                continue  # recently failed; let it cool down before retry
            listable.append(it)

        if not listable:
            return

        # Get reference prices from DMarket aggregated data (oracle removed)
        asks: dict[str, float] = {}
        agg = getattr(self, '_current_agg_prices', {})
        for it in listable:
            title = it["hash_name"]
            if title not in asks:
                asks[title] = (agg.get(title, {}) or {}).get("best_bid", 0.0)

        # Build payload: (row_id, dm_item_id, title, list_price, buy_price)
        payloads: list[tuple[int, str, str, float, float]] = []
        for it in listable:
            title = it["hash_name"]
            buy_price = float(it["buy_price"] or 0)
            cs_price = asks.get(title, 0.0)
            if cs_price <= buy_price:
                # Oracle says price <= what we paid; skip (no point listing)
                continue
            target_sell = _min_list_price(buy_price, LIST_MIN_MARGIN_PCT, get_total_fee_rate())
            if cs_price < target_sell:
                # Not enough margin after fees
                continue
            list_price = await calculate_list_price(title, buy_price, cs_price, target_sell, dom_cache=getattr(self, '_dom_cache', None))
            payloads.append((int(it["id"]), it["dm_item_id"], title, list_price, buy_price))

        if not payloads:
            return

        # Respect the open-listings cap
        room = SELL_MAX_OPEN_LISTINGS - listed_count
        if len(payloads) > room:
            logger.info(
                f"[RESALE] Capping listings: {len(payloads)} candidates, "
                f"{room} room under cap"
            )
            payloads = payloads[:room]

        # Batch API call
        listed_ok = 0
        for chunk_start in range(0, len(payloads), LIST_BATCH_SIZE):
            chunk = payloads[chunk_start:chunk_start + LIST_BATCH_SIZE]
            batch_payload = [
                {"item_id": dm_id, "price_usd": lp}
                for (_row_id, dm_id, _title, lp, _bp) in chunk
            ]
            try:
                resp = await self.client.create_sell_offers_batch(game_id, batch_payload)
            except Exception as e:
                if _is_unknown_outcome(e):
                    dm_ids = [dm_id for (_row_id, dm_id, _title, _lp, _bp) in chunk]
                    logger.warning(
                        f"[RESALE] create_sell_offers_batch transient/unknown outcome ({type(e).__name__}: {e}): "
                        f"{len(chunk)} items ({dm_ids}) remain idle for next cycle retry",
                        exc_info=True,
                    )
                else:
                    logger.warning(f"[RESALE] create_sell_offers_batch failed: {e}", exc_info=True)
                    for row_id, _dm_id, _title, _lp, _bp in chunk:
                        await price_db.run_in_thread(
                            price_db.mark_list_failed, row_id, str(e)[:200]
                        )  # P2-17: async
                continue

            # DMarket returns 200 with `status: 'success'` or partial errors.
            # Map each item back by assetId (П.7) and update local DB.
            success_map, failed_map = _parse_batch_create_results(resp)
            transient_ids = _transient_failed_ids(resp)
            success_count = 0
            for row_id, dm_id, title, lp, bp in chunk:
                dm_id_key = str(dm_id).strip()
                if dm_id_key in failed_map:
                    err_msg = failed_map[dm_id_key][:200]
                    if dm_id_key in transient_ids:
                        logger.warning(
                            f"[LIST RETRY] {title}: transient failure ({err_msg}); will retry next cycle"
                        )
                    else:
                        await price_db.run_in_thread(
                            price_db.mark_list_failed, row_id, err_msg
                        )  # P2-17: async
                        logger.warning(f"[LIST FAIL] {title} @ ${lp:.2f}: {err_msg}")
                elif dm_id_key in success_map:
                    offer_id = success_map[dm_id_key]
                    await price_db.run_in_thread(price_db.mark_listed, row_id, offer_id, lp)  # P2-17: async
                    success_count += 1
                    listed_ok += 1
                    logger.info(
                        f"[LIST] {title} @ ${lp:.2f} (offerId={offer_id[:12]}...)"
                    )
                    # v15.10 FIX: Store task reference to prevent GC before completion
                    _task = asyncio.create_task(
                        _get_notifier().buy(  # reuse buy() helper; it just announces
                            title=f"LISTED: {title}",
                            price_usd=bp,
                            expected_sell_usd=lp,
                            strategy="resale",
                        )
                    )
                    self._background_tasks = getattr(self, '_background_tasks', set())
                    self._background_tasks.add(_task)
                    _task.add_done_callback(self._background_tasks.discard)
                else:
                    if isinstance(resp, dict) and resp.get("status") == "error":
                        err_msg = str(resp.get("message") or "error in API response")[:200]
                    else:
                        err_msg = "no offerId in response"
                    await price_db.run_in_thread(price_db.mark_list_failed, row_id, err_msg)  # P2-17: async
                    logger.warning(
                        f"[LIST FAIL] {title} @ ${lp:.2f}: {err_msg}"
                    )
            if success_count > 0:
                logger.info(
                    f"[RESALE] Batch listed {success_count}/{len(chunk)} item(s) "
                    f"(chunk {chunk_start // LIST_BATCH_SIZE + 1})"
                )

        if listed_ok > 0:
            logger.info(f"[RESALE] Total new listings this cycle: {listed_ok}")
