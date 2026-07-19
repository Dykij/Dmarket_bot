"""
resale_prod.py — PROD-mode helpers for the resale pipeline (real DMarket API).

Mixed into SnipingLoop via _ResaleMixin (see resale.py).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from src.config import Config
from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class _ResaleProdMixin:
    """Production resale — real DMarket API calls."""

    client: Any
    oracle: Any

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
                # Skip if already tracked
                if price_db.find_by_dm_item_id(dm_item_id) is not None:
                    continue
                # Infer buy price from item's history (best effort):
                # DMarket inventory items don't include buy price. Use the
                # avg price from the most recent buy cycle as a proxy, or
                # fall back to 0.0 (PnL will be wrong but listing still works).
                inferred_price = 0.0
                avg_row = await price_db.run_in_thread(
                    price_db.state_conn.execute,
                    "SELECT AVG(buy_price) as p FROM virtual_inventory "
                    "WHERE hash_name = ? AND status IN ('sold','listed')",
                    (title,),
                )
                avg_row = await price_db.run_in_thread(avg_row.fetchone)
                if avg_row and avg_row["p"]:
                    inferred_price = float(avg_row["p"])
                # v15.10: Single INSERT with dm_item_id to avoid phantom rows on crash
                cursor_obj = await price_db.run_in_thread(
                    price_db.state_conn.execute,
                    "INSERT INTO virtual_inventory "
                    "(hash_name, buy_price, status, acquired_at, unlock_at, dm_item_id) "
                    "VALUES (?, ?, 'idle', ?, ?, ?)",
                    (title, inferred_price, time.time(), time.time(), dm_item_id),
                )
                new_id = await price_db.run_in_thread(
                    lambda c: c.lastrowid, cursor_obj
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
        from src.core.target_sniping.resale_constants import SELL_FEE_RATE

        listed = price_db.get_virtual_inventory(status="listed")
        if not listed:
            return 0
        detected = 0
        try:
            closed_resp = await self.client.get_user_closed_offers(
                game_id=game_id, limit=50
            )
        except Exception as e:
            logger.debug(f"get_user_closed_offers failed: {e}")
            return 0
        closed_list = closed_resp.get("objects", [])
        # v13.1: Keep full closed record dicts keyed by offerId
        closed_by_id: dict[str, dict[str, Any]] = {
            o.get("offerId", ""): o for o in closed_list
        }
        for it in listed:
            offer_id = it["dm_offer_id"] or ""
            if not offer_id or offer_id not in closed_by_id:
                continue
            match = closed_by_id[offer_id]
            # v13.1: Handle rollbacks — item reverted, DMarket refunded 100%
            closed_status = match.get("status", "")
            if closed_status == "reverted":
                price_db.set_rollback_refund(offer_id)
                logger.info(
                    f"[ROLLBACK] {it['hash_name']} was reverted on DMarket — "
                    f"100% refund applied, PnL neutral."
                )
                # Mark as sold with zero PnL
                price_db.update_virtual_status(int(it["id"]), "sold")
                price_db.record_virtual_sale(int(it["id"]), float(it["buy_price"] or 0), 0.0)
                detected += 1
                continue
            sell_price = 0.0
            fee = 0.0
            sp = int(match.get("price", {}).get("USD", 0))
            sell_price = sp / 100.0
            fee = round(sell_price * SELL_FEE_RATE, 4)
            # Fall back to our last known listed price if closed records
            # are paginated away.
            if sell_price <= 0:
                sell_price = float(it["sell_price"] or 0)
                fee = round(sell_price * SELL_FEE_RATE, 4)
            if sell_price <= 0:
                continue
            price_db.record_virtual_sale(int(it["id"]), sell_price, fee)
            # v13.1: Track funds hold from Trade Protection
            finalization_time = match.get("FinalizationTime", 0.0)
            if finalization_time > time.time():
                price_db.set_funds_hold(int(it["id"]), finalization_time)
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
                notifier.sell(
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
            LIST_PRICE_DISCOUNT,
            SELL_MAX_OPEN_LISTINGS,
        )

        # Cap on already-listed count
        listed_count = len(price_db.get_virtual_inventory(status="listed"))
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

        # Get oracle asks via cache (sub-ms, no HTTP)
        asks: dict[str, float] = {}
        if self.oracle is not None:
            for it in listable:
                title = it["hash_name"]
                if title not in asks:
                    snap = self.oracle.get_ask(title)
                    if not snap or not snap.has_data:
                        asks[title] = 0.0
                        continue
                    # v14.0 Micro-Price: volume-weighted fair price instead of raw min_price
                    if Config.MICRO_PRICE_ENABLED:
                        bid_snap = self.oracle.get_bid(title)
                        if bid_snap and bid_snap.has_data and snap.provider_prices and bid_snap.provider_bids:
                            ask_total = sum(snap.provider_prices.values())
                            bid_total = sum(bid_snap.provider_bids.values())
                            ask_count = len(snap.provider_prices)
                            bid_count = len(bid_snap.provider_bids)
                            if ask_total > 0 and bid_total > 0:
                                mid_price = (snap.min_price * bid_total + bid_snap.max_bid * ask_total) / (bid_total + ask_total)
                                # v14.3 Stoikov Micro-Price — OBI-adjusted
                                if Config.STOIKOV_MICRO_PRICE_ENABLED:
                                    from src.analysis.microstructure import (
                                        simple_obi,
                                        stoikov_micro_price,
                                    )
                                    spread = bid_snap.max_bid - snap.min_price
                                    if spread > 0:
                                        obi_est = simple_obi(
                                            bid_snap.max_bid, snap.min_price,
                                            bid_count=bid_count, ask_count=ask_count,
                                        )
                                        mid_price = stoikov_micro_price(
                                            mid_price, spread, obi_est,
                                            calibration=Config.STOIKOV_CALIBRATION,
                                        )
                                asks[title] = mid_price
                                continue
                    asks[title] = snap.min_price

        # Build payload: (row_id, dm_item_id, title, list_price, buy_price)
        payloads: list[tuple[int, str, str, float, float]] = []
        for it in listable:
            title = it["hash_name"]
            buy_price = float(it["buy_price"] or 0)
            cs_price = asks.get(title, 0.0)
            if cs_price <= buy_price:
                # Oracle says price <= what we paid; skip (no point listing)
                continue
            target_sell = buy_price * (1 + LIST_MIN_MARGIN_PCT / 100.0 + Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE)
            if cs_price < target_sell:
                # Not enough margin after fees
                continue

            # v14.1 A-S (Avellaneda-Stoikov) — inventory-aware reservation price
            if Config.AS_ENABLED and self.oracle is not None:
                bid_snap = self.oracle.get_bid(title)
                ask_snap = self.oracle.get_ask(title)
                if ask_snap and ask_snap.has_data:
                    mid_price = cs_price
                    if bid_snap and bid_snap.has_data:
                        mid_price = (ask_snap.min_price + bid_snap.max_bid) / 2.0
                    same_item = len([
                        x for x in price_db.get_virtual_inventory(
                            status="idle", only_unlocked=False,
                        ) if x["hash_name"] == title
                    ])
                    vol_est = 0.40  # default CS2 skin annualized vol
                    try:
                        hist = price_db.get_recent_prices(title, days=14)
                        if hist and len(hist) >= 3:
                            log_returns = []
                            for i in range(1, len(hist)):
                                prev_p = hist[i - 1][0]
                                curr_p = hist[i][0]
                                if prev_p > 0:
                                    log_returns.append(abs(math.log(curr_p / prev_p)))
                            if log_returns:
                                daily_vol = sum(log_returns) / len(log_returns)
                                vol_est = daily_vol * math.sqrt(365)
                    except Exception:
                        pass
                    from src.analysis.microstructure import reservation_price
                    reserv = reservation_price(
                        mid_price=mid_price,
                        inventory_qty=same_item,
                        target_qty=0,
                        max_qty=max(1, Config.MAX_SAME_ITEM_HOLDINGS),
                        volatility=vol_est,
                        gamma=Config.AS_RISK_AVERSION,
                        T_days=Config.AS_TIME_HORIZON_DAYS,
                    )
                    cs_price = max(target_sell * 1.01, reserv)

            # v14.3: VWAP Bands — list near upper band for mean-reversion target
            if Config.VWAP_BANDS_ENABLED and self.oracle is not None:
                from src.analysis.microstructure import vwap_bands
                item_sales_vwap = price_db.get_trade_history(title, days=30, limit=200)
                if item_sales_vwap and len(item_sales_vwap) >= 5:
                    _, lower, upper = vwap_bands(item_sales_vwap, num_std=2.0)
                    if upper > cs_price and lower < cs_price:
                        cs_price = max(cs_price, upper * 0.98)  # list near upper band

            # v14.0: DOM Gap-aware listing price
            if Config.DOM_GAP_ENABLED and hasattr(self, '_dom_cache'):
                dom_listings = self._dom_cache.get(title, [])
                if dom_listings and len(dom_listings) > 1:
                    from src.analysis.orderbook import find_gap_price
                    gap_price = find_gap_price(dom_listings, target_sell)
                    if gap_price > target_sell:
                        list_price = gap_price
                    else:
                        list_price = round(min(cs_price * 0.97, cs_price - LIST_PRICE_DISCOUNT), 2)
                else:
                    list_price = round(min(cs_price * 0.97, cs_price - LIST_PRICE_DISCOUNT), 2)
            else:
                list_price = round(min(cs_price * 0.97, cs_price - LIST_PRICE_DISCOUNT), 2)
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
                logger.warning(f"[RESALE] create_sell_offers_batch failed: {e}", exc_info=True)
                for (row_id, _dm_id, _title, _lp, _bp) in chunk:
                    price_db.mark_list_failed(row_id, str(e)[:200])
                continue

            # DMarket returns 200 with `status: 'success'` or partial errors.
            # Map each item back by index and update local DB.
            # v2 endpoint format: {"offers": [{"id": "...", "assetId": "..."}], "failed": [...]}
            success_count = 0
            for idx, (row_id, dm_id, title, lp, bp) in enumerate(chunk):
                offer_id = None
                err = None
                if isinstance(resp, dict):
                    # v2 format: "offers" array with "id" and "assetId"
                    v2_offers = resp.get("offers", [])
                    if idx < len(v2_offers):
                        item_info = v2_offers[idx]
                        if isinstance(item_info, dict):
                            offer_id = item_info.get("id") or item_info.get("offerId") or item_info.get("OfferID")
                    # Fallback to old format: "Items" or "items" array
                    if not offer_id:
                        item_status = resp.get("Items", []) or resp.get("items", [])
                        if idx < len(item_status):
                            item_info = item_status[idx]
                            if isinstance(item_info, dict):
                                offer_id = item_info.get("offerId") or item_info.get("OfferID")
                                err = item_info.get("error") or item_info.get("Error")
                    # Check failed array (v2 format)
                    if not offer_id:
                        v2_failed = resp.get("failed", [])
                        for fail in v2_failed:
                            if fail.get("assetId") == dm_id:
                                err = fail.get("message") or fail.get("code")
                                break
                    # Top-level error check
                    if not offer_id and resp.get("status") == "error":
                        err = resp.get("message", "unknown error")
                if offer_id:
                    price_db.mark_listed(row_id, offer_id, lp)
                    success_count += 1
                    listed_ok += 1
                    logger.info(
                        f"[LIST] {title} @ ${lp:.2f} (offerId={offer_id[:12]}...)"
                    )
                    # v15.10 FIX: Store task reference to prevent GC before completion
                    _task = asyncio.create_task(
                        notifier.buy(  # reuse buy() helper; it just announces
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
                    err_msg = (err or "no offerId in response")[:200]
                    price_db.mark_list_failed(row_id, err_msg)
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
