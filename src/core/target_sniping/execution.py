"""
execution.py — Instant-buy execution pipeline.

Mixin with the buy-execution logic (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from src.config import Config
from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class _ExecutionMixin:
    """Instant-buy execution pipeline."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient
    liquidity: Any  # LiquidityManager

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...  # type: ignore[empty-body]
    def _maybe_inject_error(self, method_name: str) -> None: ...  # type: ignore[empty-body]
    def _simulate_competition(self, margin: float) -> bool: ...  # type: ignore[empty-body]

    async def _execute_instant_buys(
        self,
        *,
        instant_buys: List[Dict[str, Any]],
        current_balance: float,
        game_id: str = "",
    ) -> None:
        """..."""
        if not instant_buys:
            return

        # v13.1: Calculate available balance (excludes frozen TP-held funds)
        available_balance = current_balance
        if hasattr(self, "risk"):
            try:
                price_db.release_expired_funds()
                equity_now = price_db.get_total_equity(current_balance)
                self.risk._update_equity(equity_now["total"])
                available_balance = equity_now["available"]
                if equity_now["frozen"] > 0:
                    logger.info(
                        f"[FUNDS] ${available_balance:.2f} available / "
                        f"${current_balance:.2f} total (${equity_now['frozen']:.2f} frozen in TP holds)"
                    )
            except Exception as e:
                logger.debug(f"Risk equity update failed: {e}")

        logger.info(
            f"Executing INSTANT BUY for {len(instant_buys)} items (Strategy A)..."
        )

        # v12.9: Parallel slippage protection.
        # Re-verify listing prices haven't increased >5% since scan.
        # Uses asyncio.gather for all items instead of sequential loop.
        _MAX_SLIPPAGE_PCT = 5.0

        async def _check_slippage(item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            try:
                title = item_data["title"]
                expected_price = item_data["base_price"]
                resp = await self.client.get_market_items_v2(
                    game_id, limit=5, title=title
                )
                current_listings = resp.get("objects", [])
                if current_listings:
                    matching = [
                        lst for lst in current_listings
                        if lst.get("itemId") == item_data["item_id"]
                    ]
                    if matching:
                        cheapest_cents = min(
                            int(lst.get("price", {}).get("USD", 0))
                            for lst in matching
                        )
                    else:
                        cheapest_cents = int(
                            current_listings[0].get("price", {}).get("USD", 0)
                        )
                    current_price = cheapest_cents / 100.0
                    slippage_pct = (
                        ((current_price - expected_price) / expected_price) * 100
                        if expected_price > 0 else 0
                    )
                    if slippage_pct > _MAX_SLIPPAGE_PCT:
                        logger.warning(
                            f"[SLIPPAGE] {title}: expected ${expected_price:.2f}, "
                            f"now ${current_price:.2f} (+{slippage_pct:.1f}% > {_MAX_SLIPPAGE_PCT}%). Skipping."
                        )
                        return None
                return item_data
            except Exception as e:
                logger.debug(f"Slippage check failed for {item_data.get('title', '?')}: {e}")
                return item_data  # proceed on check failure

        results = await asyncio.gather(*[_check_slippage(d) for d in instant_buys])
        verified_buys = [r for r in results if r is not None]

        if not verified_buys:
            logger.info("[SLIPPAGE] All buys filtered by slippage protection.")
            return

        await self._simulate_network_latency()
        self._maybe_inject_error("buy_items")
        buy_payloads = [item["buy_offer"] for item in verified_buys]
        buy_response = await self.client.buy_items(buy_payloads)

        # v12.3: DMarket returns 200 OK with `status: 'TxFailed'` and
        # `dmOffersFailReason: {code: 'OfferNotFound'}` if the listing was
        # already taken by another bot. We must check the response body
        # before recording the spend locally.
        successful_titles = set()
        bought_items: List[Dict[str, Any]] = []  # v12.5: [{itemId, title}, ...]
        if isinstance(buy_response, dict):
            status = buy_response.get("status", "")
            # v12.5: DMarket's /exchange/v1/market/buy response usually
            # contains an `Items` array with the newly-acquired assets,
            # each with their new itemId. We need those to list them
            # for sale later. Shape (per DMarket API v1.1):
            #   {"Items": [{"itemId": "abc", "title": "...", "price": {...}}]}
            for key in ("Items", "items", "AcquiredItems"):
                raw = buy_response.get(key)
                if isinstance(raw, list):
                    for it in raw:
                        if isinstance(it, dict) and it.get("itemId"):
                            bought_items.append({
                                "itemId": str(it["itemId"]),
                                "title": it.get("title", ""),
                            })
                    if bought_items:
                        break
            if status and status != "TxFailed":
                # All offers succeeded
                successful_titles = {
                    item_data["title"] for item_data in verified_buys
                }
            else:
                # Inspect dmOffersStatus to find successes
                dm_offers_status = buy_response.get("dmOffersStatus", {}) or {}
                for offer_id, info in dm_offers_status.items():
                    if info.get("started") or info.get("success"):
                        # Map offer_id back to title (best effort: any offer that started)
                        for item_data in verified_buys:
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
                f"successful={len(successful_titles)}/{len(verified_buys)} "
                f"bought_items={len(bought_items)}"
            )

        for item_data in verified_buys:
            title = item_data["title"]
            item_id = item_data["item_id"]
            base_price = item_data["base_price"]
            list_price = item_data["list_price"]
            is_rare = item_data.get("is_rare", False)
            # v12.5: pass real per-item margin to the competition model so
            # the simulator actually differentiates between 5% and 60% edge.
            # Hardcoding 0.15 previously meant every buy saw the same 30%
            # fail rate regardless of how fat the spread was.
            best_bid = item_data.get("best_bid", 0.0)
            best_ask = item_data.get("best_ask", 0.0)
            item_margin = (
                (best_bid - best_ask) / best_ask
                if best_ask > 0
                else 0.0
            )

            # v12.5: Find the new dm_item_id for this buy (for sell-side)
            new_dm_item_id = ""
            for bi in bought_items:
                if bi["title"] == title and bi["itemId"]:
                    new_dm_item_id = bi["itemId"]
                    break

            if os.getenv("DRY_RUN", "true").lower() == "true":
                if not self._simulate_competition(item_margin):
                    logger.warning(
                        f"[SIM] COMPETITION! {title} was sniped by another bot first."
                    )
                    continue

                # v12.5: Risk manager pre-trade check (soft/hard halts)
                if hasattr(self, "risk"):
                    risk_check = self.risk.pre_trade_check(
                        proposed_size_usd=base_price,
                        current_equity_usd=available_balance,
                        game_id=game_id,
                        item_title=title,
                    )
                    if not risk_check.allowed:
                        logger.warning(
                            f"[RISK] BLOCKED {title} @ ${base_price:.2f}: {risk_check.reason}"
                        )
                        try:
                            price_db.record_risk_event(
                                "pre_trade_block",
                                "warning",
                                f"{title} @ ${base_price:.2f}: {risk_check.reason}",
                            )
                        except Exception:
                            pass
                        continue
                    if risk_check.adjusted_size_usd is not None and risk_check.adjusted_size_usd < base_price:
                        logger.info(
                            f"[RISK] Soft-adjusted {title}: ${base_price:.2f} → "
                            f"${risk_check.adjusted_size_usd:.2f}"
                        )

                # v13.0: Total inventory cap check
                total_equity = price_db.get_total_equity(0.0)
                current_held_value = total_equity["assets"]
                current_held_count = total_equity["count"]
                if current_held_count >= Config.MAX_TOTAL_INVENTORY_ITEMS:
                    logger.warning(
                        f"[INV-CAP] Already holding {current_held_count}/{Config.MAX_TOTAL_INVENTORY_ITEMS} items. Skipping {title}."
                    )
                    continue
                if current_held_value + base_price > Config.MAX_TOTAL_INVENTORY_VALUE:
                    logger.warning(
                        f"[INV-CAP] Inventory value ${current_held_value:.2f} + ${base_price:.2f} > ${Config.MAX_TOTAL_INVENTORY_VALUE:.2f} cap. Skipping {title}."
                    )
                    continue

                held_count = len(
                    [
                        x
                        for x in price_db.get_virtual_inventory(status="idle")
                        if x["hash_name"] == title
                    ]
                )
                if held_count >= Config.MAX_SAME_ITEM_HOLDINGS:
                    logger.warning(
                        f"[SATURATION] Already holding {held_count}x {title}. Skipping."
                    )
                    continue

                # v12.5: capture the new row_id so we can attach dm_item_id
                # in production (or leave it empty in DRY).
                price_db.add_virtual_item(title, base_price, trade_lock_hours=Config.TRADE_LOCK_HOURS, exclusive=is_rare)
                row = price_db.state_conn.execute(
                    "SELECT id FROM virtual_inventory "
                    "WHERE hash_name = ? AND status = 'idle' "
                    "ORDER BY id DESC LIMIT 1",
                    (title,),
                ).fetchone()
                if row and new_dm_item_id:
                    price_db.attach_dm_item_id(int(row["id"]), new_dm_item_id)
                if is_rare and row:
                    price_db.mark_exclusive(int(row["id"]))

                vwap = price_db.calculate_vwap(title)
                logger.info(
                    f"[SIM] SNIPED! {title} @ ${base_price} → list ${list_price} "
                    f"(spread: {item_data['best_bid']-item_data['best_ask']:.2f}, "
                    f"VWAP: ${vwap:.2f}, rare={is_rare})"
                )
                # v12.2 Phase 2.1: Track asset status (trade_protected for N hours)
                price_db.update_asset_status(
                    item_id,
                    title,
                    "trade_protected",
                    finalization_time=time.time() + Config.TRADE_LOCK_HOURS * 3600,
                )
                # v12.5: Record trade outcome (negative PnL = cost)
                if hasattr(self, "risk"):
                    self.risk.record_trade_outcome(
                        pnl_usd=-base_price,  # spend is a negative PnL event
                        trade_type="buy",
                        item_title=title,
                    )
                # v12.5: Telegram buy notification (throttled to 1/min)
                asyncio.create_task(
                    notifier.buy(
                        title=title,
                        price_usd=base_price,
                        expected_sell_usd=list_price,
                        strategy=item_data.get("strategy", "intra_spread"),
                    )
                )

            # v12.3: Only record local spend/target if the actual buy succeeded.
            # For DRY_RUN, always record (simulated). For production, gate on
            # successful_titles which is populated from the buy response.
            is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
            if is_dry or title in successful_titles:
                # v12.5: Pre-trade risk check (production path)
                if not is_dry and hasattr(self, "risk"):
                    risk_check = self.risk.pre_trade_check(
                        proposed_size_usd=base_price,
                        current_equity_usd=current_balance,
                        game_id=game_id,
                        item_title=title,
                    )
                    if not risk_check.allowed:
                        logger.warning(
                            f"[RISK] BLOCKED buy {title} @ ${base_price:.2f}: "
                            f"{risk_check.reason}"
                        )
                        try:
                            price_db.record_risk_event(
                                "pre_trade_block",
                                "warning",
                                f"{title} @ ${base_price:.2f}: {risk_check.reason}",
                            )
                        except Exception:
                            pass
                        continue
                price_db.record_placed_target(item_id, title, base_price)
                self.liquidity.record_spend(base_price)
                # v12.5: Record trade outcome (negative PnL = spend)
                if hasattr(self, "risk"):
                    self.risk.record_trade_outcome(
                        pnl_usd=-base_price,
                        trade_type="buy",
                        item_title=title,
                    )
                # v12.5: Production-side dm_item_id attach. If we didn't
                # capture it from the buy response above (e.g. the response
                # didn't include Items), the inventory sync will pick it up
                # within the next cycle.
                if not is_dry and new_dm_item_id:
                    # Find the most recent virtual_inventory row for this
                    # title that has no dm_item_id and attach it.
                    row = price_db.state_conn.execute(
                        "SELECT id FROM virtual_inventory "
                        "WHERE hash_name = ? AND status = 'idle' "
                        "AND (dm_item_id IS NULL OR dm_item_id = '') "
                        "ORDER BY id DESC LIMIT 1",
                        (title,),
                    ).fetchone()
                    if row:
                        price_db.attach_dm_item_id(int(row["id"]), new_dm_item_id)
                # v12.5: Production-side buy notification (in addition to the
                # DRY notification above; one will no-op because of the throttle)
                if not is_dry:
                    asyncio.create_task(
                        notifier.buy(
                            title=title,
                            price_usd=base_price,
                            expected_sell_usd=list_price,
                            strategy=item_data.get("strategy", "intra_spread"),
                        )
                    )
            else:
                logger.info(
                    f"Skipping local record for {title!r} — buy did not succeed"
                )
