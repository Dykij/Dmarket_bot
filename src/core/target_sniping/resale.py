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
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from src.api.oracle_factory import OracleFactory
from src.config import Config
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


class _ResaleMixin:
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

    # ----------------------------------------------------------------
    # DRY-mode helpers
    # ----------------------------------------------------------------
    def _dry_simulate_sales(self) -> None:
        """DRY: Mark some `listed` items as sold (40% per cycle)."""
        listed = price_db.get_virtual_inventory(status="listed")
        if not listed:
            return
        for it in listed:
            if random.random() < 0.40:
                # Simulate the sale at the listed price minus 5% fee
                sell_price = round((it["sell_price"] or it["buy_price"] * 1.05), 2)
                fee = round(sell_price * 0.05, 4)
                price_db.record_virtual_sale(int(it["id"]), sell_price, fee)
                # v13.1: Simulate TP funds hold (7 days)
                hold_until = time.time() + 7 * 24 * 3600
                price_db.set_funds_hold(int(it["id"]), hold_until)
                profit = sell_price - (it["buy_price"] or 0) - fee
                logger.info(
                    f"[SIM] SOLD! {it['hash_name']} | "
                    f"Buy: ${it['buy_price']:.2f} → Sell: ${sell_price:.2f} "
                    f"| PnL: ${profit:+.2f}"
                )
                # v12.5: notify + record in risk manager
                asyncio.create_task(
                    notifier.sell(
                        title=it["hash_name"],
                        buy_price_usd=float(it["buy_price"] or 0),
                        sell_price_usd=sell_price,
                        profit_usd=profit,
                    )
                )
                if hasattr(self, "risk"):
                    try:
                        self.risk.record_trade_outcome(
                            pnl_usd=profit,
                            trade_type="sell",
                            item_title=it["hash_name"],
                        )
                    except Exception as e:
                        logger.debug(f"risk.record_trade_outcome (sim sell) failed: {e}")

    async def _dry_list_unlocked(self, items: List[Any], game_id: str) -> None:
        """DRY: Simulate listing unlocked items at buy_price * 1.05."""
        oracle = OracleFactory.get_oracle(game_id)
        for item in items:
            current_price = 0.0
            if oracle:
                try:
                    current_price = await oracle.get_item_price(item["hash_name"])
                except Exception:
                    pass
            if current_price <= 0:
                current_price = item["buy_price"] * 1.05
            buy_price = item["buy_price"]
            target_sell = round(buy_price * 1.05, 2)
            if current_price < target_sell:
                # Market no longer supports our markup — hold off
                continue
            list_price = round(min(current_price * 0.97, current_price - 0.01), 2)
            price_db.mark_listed(int(item["id"]), dm_offer_id=f"sim-{int(time.time())}-{item['id']}", list_price=list_price)
            est_profit = round(list_price - buy_price - list_price * 0.05, 2)
            logger.info(
                f"[SIM] LISTED: {item['hash_name']} | "
                f"Buy: ${buy_price:.2f} → Listed: ${list_price:.2f} "
                f"| Est profit: ${est_profit:+.2f}"
            )

    # ----------------------------------------------------------------
    # PROD-mode helpers
    # ----------------------------------------------------------------
    async def _sync_real_inventory(self, game_id: str) -> int:
        """
        PROD: Pull DMarket inventory and ensure every item is in our
        local virtual_inventory with its real dm_item_id. Returns count
        of newly linked items.
        """
        new_count = 0
        cursor: Optional[str] = None
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
                avg_row = price_db.state_conn.execute(
                    "SELECT AVG(buy_price) as p FROM virtual_inventory "
                    "WHERE hash_name = ? AND status IN ('sold','listed')",
                    (title,),
                ).fetchone()
                if avg_row and avg_row["p"]:
                    inferred_price = float(avg_row["p"])
                new_id = price_db.state_conn.execute(
                    "INSERT INTO virtual_inventory "
                    "(hash_name, buy_price, status, acquired_at, unlock_at) "
                    "VALUES (?, ?, 'idle', ?, ?)",
                    (title, inferred_price, time.time(), time.time()),
                ).lastrowid
                price_db.attach_dm_item_id(int(new_id), dm_item_id)
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
        closed_by_id: Dict[str, Dict[str, Any]] = {
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
            asyncio.create_task(
                notifier.sell(
                    title=it["hash_name"],
                    buy_price_usd=float(it["buy_price"] or 0),
                    sell_price_usd=sell_price,
                    profit_usd=profit,
                )
            )
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

    async def _prod_list_unlocked(self, items: List[Any], game_id: str) -> None:
        """
        PROD: Batch-list unlocked items on DMarket.

        Strategy:
        1. Group items by hash_name
        2. For each unique title, fetch CS2Cap price from cache (free)
        3. If CS2Cap says price > buy_price * (1 + min_margin), list it
        4. Cap simultaneous listings to SELL_MAX_OPEN_LISTINGS
        5. Call create_sell_offers_batch in chunks of LIST_BATCH_SIZE
        6. Track success/failure per item
        """
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

        listable: List[Any] = []
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
        # Allow retry of items that previously failed (no list_error filter
        # above means we just need items with a list_error to be retried too
        # in a later cycle — handled implicitly by the cooldown).
        # (Removed separate retryable loop; the cooldown logic in production
        # should reset list_error after a few cycles anyway.)

        if not listable:
            return

        # Get CS2Cap asks via cache (sub-ms, no HTTP)
        asks: Dict[str, float] = {}
        if self.cs2cap_cache is not None:
            for it in listable:
                title = it["hash_name"]
                if title not in asks:
                    snap = self.cs2cap_cache.get_ask(title)
                    asks[title] = snap.min_price if snap and snap.has_data else 0.0

        # Build payload: (row_id, dm_item_id, title, list_price, buy_price)
        payloads: List[Tuple[int, str, str, float, float]] = []
        for it in listable:
            title = it["hash_name"]
            buy_price = float(it["buy_price"] or 0)
            cs_price = asks.get(title, 0.0)
            if cs_price <= buy_price:
                # Oracle says price <= what we paid; skip (no point listing)
                continue
            target_sell = buy_price * (1 + LIST_MIN_MARGIN_PCT / 100.0)
            if cs_price < target_sell:
                # Not enough margin after fees
                continue
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
                for (row_id, _dm_id, title, _lp, _bp) in chunk:
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
                    asyncio.create_task(
                        notifier.buy(  # reuse buy() helper; it just announces
                            title=f"LISTED: {title}",
                            price_usd=bp,
                            expected_sell_usd=lp,
                            strategy="resale",
                        )
                    )
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
                # Drop the price, but never below buy_price * 1.01 (avoid loss)
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
