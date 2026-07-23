"""
execution.py — Instant-buy execution pipeline.

Mixin with the buy-execution logic (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any

from src.config import Config
from src.db.price_history import price_db
from src.strategies.twap import TWAPExecutor
from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class _ExecutionMixin:
    """Instant-buy execution pipeline."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient
    liquidity: Any  # LiquidityManager

    # v15.10: TWAP executor for anti-slippage on large orders
    _twap_executor: TWAPExecutor | None = None

    def _get_twap_executor(self) -> TWAPExecutor:
        """Lazy-init TWAP executor."""
        if self._twap_executor is None:
            self._twap_executor = TWAPExecutor(
                client=self.client,
                max_slices=int(os.getenv("TWAP_MAX_SLICES", "5")),
                min_interval_seconds=float(os.getenv("TWAP_MIN_INTERVAL_S", "30")),
                max_slippage_pct=float(os.getenv("TWAP_MAX_SLIPPAGE_PCT", "5.0")),
            )
        return self._twap_executor

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...  # type: ignore[empty-body]
    def _maybe_inject_error(self, method_name: str) -> None: ...  # type: ignore[empty-body]
    def _simulate_competition(self, margin: float) -> bool: ...  # type: ignore[empty-body]

    async def _execute_instant_buys(
        self,
        *,
        instant_buys: list[dict[str, Any]],
        current_balance: float,
        game_id: str = "",
    ) -> None:
        """..."""
        if not instant_buys:
            return

        # v13.1: Calculate available balance (excludes frozen TP-held funds)
        available_balance = current_balance
        _cached_equity = None  # BUG-15 FIX: Cache equity to avoid redundant DB calls
        if hasattr(self, "risk"):
            try:
                await price_db.run_in_thread(price_db.release_expired_funds)
                equity_now = await price_db.run_in_thread(price_db.get_total_equity, current_balance)
                if isinstance(equity_now, dict):
                    _cached_equity = equity_now  # Cache for pre-buy cap check below
                    self.risk._update_equity(equity_now["total"])
                    available_balance = equity_now["available"]
                    if equity_now["frozen"] > 0:
                        logger.info(
                            f"[FUNDS] ${available_balance:.2f} available / "
                            f"${current_balance:.2f} total (${equity_now['frozen']:.2f} frozen in TP holds)"
                        )
            except Exception as e:
                logger.warning(f"Risk equity update failed (using raw balance): {e}")

        logger.info(
            f"Executing INSTANT BUY for {len(instant_buys)} items (Strategy A)..."
        )

        # v12.9: Parallel slippage protection.
        # Re-verify listing prices haven't increased >5% since scan.
        # Uses asyncio.gather for all items instead of sequential loop.
        _MAX_SLIPPAGE_PCT = 5.0
        # NOV-3: Oracle price drift threshold — if oracle fair price dropped
        # more than this since evaluation, cancel the trade.  Accounts for
        # the gap between scan (oracle fetch) and execution (now).
        _MAX_ORACLE_DRIFT_PCT = 10.0

        async def _check_slippage(item_data: dict[str, Any]) -> dict[str, Any] | None:
            try:
                title = item_data["title"]
                expected_price = item_data["base_price"]
                resp = await self.client.get_market_items_v2(
                    game_id, limit=5, title=title
                )
                current_listings = resp.get("objects", [])
                if not current_listings:
                    # Listing disappeared — item was already sold or removed.
                    # Don't proceed with a stale price.
                    logger.warning(
                        f"[SLIPPAGE] {title}: listing no longer available. Skipping."
                    )
                    return None
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
                if current_price <= 0:
                    logger.warning(f"[SLIPPAGE] {title}: price is 0. Skipping.")
                    return None
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

                # NOV-3 FIX: Re-check oracle fair price before buy.
                # If oracle price dropped significantly since evaluation,
                # the trade may no longer be profitable after fees.
                original_list_price = item_data.get("list_price", 0.0)
                if original_list_price > 0 and hasattr(self, "oracle") and self.oracle is not None:
                    try:
                        fresh_result = await self.oracle.get_fair_price(title)
                        if fresh_result and fresh_result.source_count > 0 and fresh_result.fair_price > 0:
                            fresh_fair = fresh_result.fair_price
                            # Check if oracle price dropped below profitability threshold
                            required_sell = expected_price * (1 + Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE + 0.02)
                            if fresh_fair < required_sell:
                                logger.warning(
                                    f"[ORACLE-DRIFT] {title}: oracle fair price dropped "
                                    f"${original_list_price:.2f} → ${fresh_fair:.2f}, "
                                    f"below required ${required_sell:.2f}. Skipping."
                                )
                                return None
                            drift_pct = abs(fresh_fair - original_list_price) / original_list_price * 100
                            if drift_pct > _MAX_ORACLE_DRIFT_PCT:
                                logger.warning(
                                    f"[ORACLE-DRIFT] {title}: oracle price drifted {drift_pct:.1f}% "
                                    f"(${original_list_price:.2f} → ${fresh_fair:.2f}). Skipping."
                                )
                                return None
                    except Exception as e:
                        # Oracle re-check failed — proceed with caution
                        logger.debug(f"[ORACLE-DRIFT] Re-check failed for {title}: {e}")

                return item_data
            except Exception as e:
                logger.warning(f"Slippage check failed for {item_data.get('title', '?')}: {e}")
                return None  # fail-closed: block buy when verification fails

        results = await asyncio.gather(
            *[_check_slippage(d) for d in instant_buys], return_exceptions=True
        )
        verified_buys: list[dict[str, Any]] = [
            r for r in results
            if r is not None and isinstance(r, dict)
        ]

        if not verified_buys:
            logger.info("[SLIPPAGE] All buys filtered by slippage protection.")
            return

        # v14.9: Pre-trade risk check (PROD path, runs before purchase)
        is_dry = Config.DRY_RUN
        if not is_dry:
            pre_checked = []
            for item_data in verified_buys:
                if hasattr(self, "risk"):
                    risk_check = self.risk.pre_trade_check(
                        proposed_size_usd=item_data["base_price"],
                        current_equity_usd=available_balance,
                        game_id=game_id,
                        item_title=item_data["title"],
                    )
                    if not risk_check.allowed:
                        logger.warning(
                            f"[RISK] BLOCKED {item_data['title']} @ ${item_data['base_price']:.2f}: "
                            f"{risk_check.reason}"
                        )
                        with contextlib.suppress(Exception):
                            await price_db.run_in_thread(
                                price_db.record_risk_event,
                                "pre_trade_block", "warning",
                                f"{item_data['title']} @ ${item_data['base_price']:.2f}: {risk_check.reason}",
                            )
                        continue
                pre_checked.append(item_data)
            verified_buys = pre_checked
            if not verified_buys:
                logger.info("[RISK] All buys blocked by pre-trade check.")
                return

        # FIX: Inventory cap checks BEFORE buy API call with cumulative tracking
        # Query equity ONCE, then track cumulative spend to prevent TOCTOU
        _pre_buy_filtered = []
        # BUG-15 FIX: Use cached equity from risk update above (avoid redundant DB call)
        if isinstance(_cached_equity, dict):
            _total_equity = _cached_equity
        else:
            _total_equity = await price_db.run_in_thread(price_db.get_total_equity, 0.0)
            if not isinstance(_total_equity, dict):
                _total_equity = {"count": 0, "assets": 0.0}
        _cumulative_count = _total_equity["count"]
        _cumulative_value = _total_equity["assets"]
        # FIX: Fetch existing inventory ONCE before loop (eliminates N+1 DB query)
        _existing_held_all = await price_db.run_in_thread(price_db.get_virtual_inventory, "idle")
        for item_data in verified_buys:
            if _cumulative_count >= Config.MAX_TOTAL_INVENTORY_ITEMS:
                logger.warning(
                    f"[INV-CAP] Already holding {_cumulative_count}/{Config.MAX_TOTAL_INVENTORY_ITEMS} items. "
                    f"Skipping {item_data['title']}."
                )
                continue
            if _cumulative_value + item_data["base_price"] > Config.MAX_TOTAL_INVENTORY_VALUE:
                logger.warning(
                    f"[INV-CAP] Inventory value ${_cumulative_value:.2f} + "
                    f"${item_data['base_price']:.2f} > ${Config.MAX_TOTAL_INVENTORY_VALUE:.2f} cap. "
                    f"Skipping {item_data['title']}."
                )
                continue
            # Saturation check: limit same-item holdings
            _held_count = len([x for x in _pre_buy_filtered if x["title"] == item_data["title"]])
            # Also count existing holdings from DB (uses pre-fetched inventory)
            _existing_count = len([x for x in _existing_held_all if x["hash_name"] == item_data["title"]])
            if _held_count + _existing_count >= Config.MAX_SAME_ITEM_HOLDINGS:
                logger.warning(
                    f"[SATURATION] Already holding {_existing_count}x {item_data['title']} "
                    f"(cap: {Config.MAX_SAME_ITEM_HOLDINGS}). Skipping."
                )
                continue
            _cumulative_count += 1
            _cumulative_value += item_data["base_price"]
            _pre_buy_filtered.append(item_data)
        verified_buys = _pre_buy_filtered
        if not verified_buys:
            logger.info("[INV-CAP] All buys filtered by inventory cap.")
            return

        await self._simulate_network_latency()
        self._maybe_inject_error("buy_items")
        buy_payloads = [item["buy_offer"] for item in verified_buys]
        # BUG-12 FIX: Catch CircuitOpenError — circuit breaker blocked the request
        try:
            buy_response = await self.client.buy_items(buy_payloads)
        except Exception as e:
            if "CircuitOpen" in type(e).__name__ or "circuit" in str(e).lower():
                logger.warning("[CB] Buy blocked by circuit breaker — skipping cycle")
                return
            raise

        # v12.3: DMarket returns 200 OK with `status: 'TxFailed'` and
        # `dmOffersFailReason: {code: 'OfferNotFound'}` if the listing was
        # already taken by another bot. We must check the response body
        # before recording the spend locally.
        successful_titles = set()
        bought_items: list[dict[str, Any]] = []  # v12.5: [{itemId, title}, ...]
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
                                # BUG-3 FIX: Store offerId from response if available
                                "offerId": it.get("offerId", ""),
                            })
                    if bought_items:
                        break
            if status and status != "TxFailed":
                # v15.10: Always check per-offer status, not just top-level.
                # DMarket can return partial success with non-TxFailed status.
                dm_offers_status = buy_response.get("dmOffersStatus", {}) or {}
                if dm_offers_status:
                    # Per-offer granularity available — use it
                    for offer_id, info in dm_offers_status.items():
                        if info.get("started") or info.get("success"):
                            for item_data in verified_buys:
                                if item_data["buy_offer"].get("offerId") == offer_id:
                                    successful_titles.add(item_data["title"])
                                    break
                else:
                    # No per-offer status — only assume success if status is not TxFailed
                    if status != "TxFailed":
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

        is_dry = Config.DRY_RUN

        for item_data in verified_buys:
            title = item_data["title"]
            item_id = item_data["item_id"]
            base_price = item_data["base_price"]
            list_price = item_data["list_price"]
            is_rare = item_data.get("is_rare", False)
            best_bid = item_data.get("best_bid", 0.0)
            best_ask = item_data.get("best_ask", 0.0)
            # v15.10: Use actual buy→sell spread, not bid-ask (which is negative)
            item_margin = (
                (list_price - base_price) / base_price
                if base_price > 0
                else 0.0
            )

            new_dm_item_id = ""
            # FIX: Match by offerId (unique) instead of title (can have duplicates)
            for bi in bought_items:
                if bi.get("offerId") == item_data.get("buy_offer", {}).get("offerId") and bi.get("itemId"):
                    new_dm_item_id = bi["itemId"]
                    break
            # Fallback: match by title if offerId not available
            if not new_dm_item_id:
                for bi in bought_items:
                    if bi["title"] == title and bi.get("itemId"):
                        new_dm_item_id = bi["itemId"]
                        break

            # BUG-11 FIX: Post-buy inventory check — WARNING ONLY (items already bought).
            # Pre-buy cap check (lines 167-188) already enforced. Skipping local
            # recording here would create phantom inventory (bought on DMarket but untracked).
            try:
                total_equity = await price_db.run_in_thread(price_db.get_total_equity, 0.0)
                if isinstance(total_equity, dict):
                    current_held_value = total_equity.get("assets", 0.0)
                    current_held_count = total_equity.get("count", 0)
                    if current_held_count >= Config.MAX_TOTAL_INVENTORY_ITEMS:
                        logger.warning(
                            f"[INV-CAP] Post-buy: holding {current_held_count}/{Config.MAX_TOTAL_INVENTORY_ITEMS} items. "
                            f"Item {title} already bought — recording anyway."
                        )
                    if current_held_value + base_price > Config.MAX_TOTAL_INVENTORY_VALUE:
                        logger.warning(
                            f"[INV-CAP] Post-buy: inventory value ${current_held_value:.2f} + ${base_price:.2f} > "
                            f"${Config.MAX_TOTAL_INVENTORY_VALUE:.2f} cap. Item {title} already bought — recording anyway."
                        )
            except Exception:
                pass  # Post-buy check is advisory only

            # Reuse pre-fetched inventory (already loaded at line 182)
            held_count = len([x for x in _existing_held_all if x["hash_name"] == title])
            if held_count >= Config.MAX_SAME_ITEM_HOLDINGS:
                logger.warning(
                    f"[SATURATION] Post-buy: already holding {held_count}x {title}. Already bought — recording anyway."
                )

            if is_dry:
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
                        with contextlib.suppress(Exception):
                            await price_db.run_in_thread(
                                price_db.record_risk_event,
                                "pre_trade_block",
                                "warning",
                                f"{title} @ ${base_price:.2f}: {risk_check.reason}",
                            )
                        continue
                    if risk_check.adjusted_size_usd is not None and risk_check.adjusted_size_usd < base_price:
                        logger.info(
                            f"[RISK] Soft-adjusted {title}: ${base_price:.2f} → "
                            f"${risk_check.adjusted_size_usd:.2f}"
                        )
                        # BUG-1 FIX: Actually apply the adjusted size to the item data
                        item_data["base_price"] = risk_check.adjusted_size_usd
                        item_data["buy_offer"] = {
                            "offerId": item_id,
                            "price": {"amount": str(round(risk_check.adjusted_size_usd * 100)), "currency": "USD"},
                        }
                        base_price = risk_check.adjusted_size_usd  # Update local variable

                # v12.5: capture the new row_id so we can attach dm_item_id
                # in production (or leave it empty in DRY).
                await price_db.run_in_thread(price_db.add_virtual_item, title, base_price, Config.TRADE_LOCK_HOURS, is_rare)
                row = await price_db.run_in_thread(
                    price_db.state_conn.execute,
                    "SELECT id FROM virtual_inventory "
                    "WHERE hash_name = ? AND status = 'idle' "
                    "ORDER BY id DESC LIMIT 1",
                    (title,),
                )
                row = await price_db.run_in_thread(row.fetchone)
                if row and new_dm_item_id:
                    await price_db.run_in_thread(price_db.attach_dm_item_id, int(row["id"]), new_dm_item_id)
                if is_rare and row:
                    await price_db.run_in_thread(price_db.mark_exclusive, int(row["id"]))

                vwap_raw = await price_db.run_in_thread(price_db.calculate_vwap, title)
                vwap = float(vwap_raw) if isinstance(vwap_raw, (int, float)) else 0.0
                logger.info(
                    f"[SIM] SNIPED! {title} @ ${base_price} → list ${list_price} "
                    f"(spread: {item_data.get('best_bid', 0)-item_data.get('best_ask', 0):.2f}, "
                    f"VWAP: ${vwap:.2f}, rare={is_rare})"
                )
                # v12.2 Phase 2.1: Track asset status (trade_protected for N hours)
                await price_db.run_in_thread(
                    price_db.update_asset_status,
                    item_id,
                    title,
                    "trade_protected",
                    time.time() + Config.TRADE_LOCK_HOURS * 3600,
                )
                # v12.5: Record trade outcome (negative PnL = cost)
                if hasattr(self, "risk"):
                    self.risk.record_trade_outcome(
                        pnl_usd=-base_price,  # spend is a negative PnL event
                        trade_type="buy",
                        item_title=title,
                    )
                # v12.5: Telegram buy notification (throttled to 1/min)
                # v15.7 FIX: Hold task reference to prevent GC before completion
                task = asyncio.create_task(
                    notifier.buy(
                        title=title,
                        price_usd=base_price,
                        expected_sell_usd=list_price,
                        strategy=item_data.get("strategy", "intra_spread"),
                    )
                )
                self._background_tasks = getattr(self, '_background_tasks', set())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                # FIX: Decrement available_balance in DRY mode too (prevents
                # RiskManager from seeing stale balance for subsequent buys)
                available_balance -= base_price

            # v12.3: Only record local spend/target if the actual buy succeeded.
            # For DRY_RUN, always record (simulated). For production, gate on
            # successful_titles which is populated from the buy response.
            if is_dry or title in successful_titles:
                await price_db.run_in_thread(price_db.record_placed_target, item_id, title, base_price)
                # v14.5: Ensure virtual_inventory row exists in PROD (DRY creates it earlier)
                if not is_dry and not new_dm_item_id:
                    await price_db.run_in_thread(price_db.add_virtual_item, title, base_price, Config.TRADE_LOCK_HOURS, is_rare)
                # BUG-2 FIX: Use atomic can_spend_and_record to prevent TOCTOU
                # (filter.py can_spend() is advisory; this is the real gate)
                try:
                    if not await self.liquidity.can_spend_and_record(base_price, game_id, available_balance):
                        logger.warning(f"[LIQUIDITY] Spend rejected at execution for {title} ${base_price:.2f}")
                        continue
                except (TypeError, AttributeError):
                    # Fallback for mocks or missing method
                    self.liquidity.record_spend(base_price)
                # v14.5: record_trade_outcome already called in DRY block above
                if not is_dry and hasattr(self, "risk"):
                    self.risk.record_trade_outcome(
                        pnl_usd=-base_price,
                        trade_type="buy",
                        item_title=title,
                    )
                # FIX: Decrement available balance after each successful buy
                # to prevent overspending within a batch
                available_balance -= base_price
                # v12.5: Production-side dm_item_id attach. If we didn't
                # capture it from the buy response above (e.g. the response
                # didn't include Items), the inventory sync will pick it up
                # within the next cycle.
                if not is_dry and new_dm_item_id:
                    # Find the most recent virtual_inventory row for this
                    # title that has no dm_item_id and attach it.
                    row = await price_db.run_in_thread(
                        price_db.state_conn.execute,
                        "SELECT id FROM virtual_inventory "
                        "WHERE hash_name = ? AND status = 'idle' "
                        "AND (dm_item_id IS NULL OR dm_item_id = '') "
                        "ORDER BY id DESC LIMIT 1",
                        (title,),
                    )
                    row = await price_db.run_in_thread(row.fetchone)
                    if row:
                        await price_db.run_in_thread(price_db.attach_dm_item_id, int(row["id"]), new_dm_item_id)
                # v14.5: Track trade protection status immediately in PROD
                if not is_dry:
                    await price_db.run_in_thread(
                        price_db.update_asset_status,
                        item_id, title, "trade_protected",
                        time.time() + Config.TRADE_LOCK_HOURS * 3600,
                    )
                # v12.5: Production-side buy notification (in addition to the
                # DRY notification above; one will no-op because of the throttle)
                if not is_dry:
                    task = asyncio.create_task(
                        notifier.buy(
                            title=title,
                            price_usd=base_price,
                            expected_sell_usd=list_price,
                            strategy=item_data.get("strategy", "intra_spread"),
                        )
                    )
                    self._background_tasks = getattr(self, '_background_tasks', set())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            else:
                logger.info(
                    f"Skipping local record for {title!r} — buy did not succeed"
                )
