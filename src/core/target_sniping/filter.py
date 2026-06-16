"""
filter.py — Per-item candidate evaluation.

Mixin with the heavy filter loop (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from src.api.cs2cap_oracle import RateLimitException
from src.config import Config
from src.core.sandbox_scenarios import scenario_engine
from src.db.price_history import price_db
from src.risk.price_validator import (
    PriceValidationError,
    validate_arbitrage_profit,
    validate_volatility,
)

logger = logging.getLogger("SnipingBot")


class _FilterMixin:
    """Per-item candidate evaluation (filter loop)."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient
    buy_budget: float
    liquidity: Any  # LiquidityManager
    _diag_cycle_id: int

    def _skip_if_locked(self, item_id: str, title: str) -> bool: ...  # type: ignore[empty-body]
    def _calculate_float_premium(self, attrs: Dict[str, Any]) -> float: ...  # type: ignore[empty-body]

    # v12.7: Per-cycle oracle price cache (P1-5).
    # Avoids duplicate HTTP calls for the same title within a single cycle.
    # Cleared at the start of each run_cycle via _clear_oracle_cache().
    _oracle_price_cache: Dict[str, float] = {}

    def _clear_oracle_cache(self) -> None:
        """Clear the per-cycle oracle price cache. Called at start of run_cycle."""
        self._oracle_price_cache.clear()

    @staticmethod
    def _rank_candidates_by_spread(
        items: List[Dict[str, Any]],
        agg_prices: Dict[str, Dict[str, Any]],
        max_price_usd: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """
        v12.7: Rank items by volume-weighted spread score (P2-3).

        Formula: score = spread_usd * sqrt(ask_count + bid_count)
        This prioritizes items with both good spread AND reasonable volume,
        avoiding low-liquidity items that are hard to sell.

        Returns: [(title, score), ...] sorted best-score first.
        Items with no agg_prices entry or zero bid/ask are filtered out.

        max_price_usd: optional cap to exclude items too expensive for our
        balance (avoids wasting CS2Cap quota on $1000 Karambits when balance
        is $43.91).
        """
        import math

        ranked: List[Tuple[str, float]] = []
        for it in items:
            title = it.get("title", "")
            if not title:
                continue
            # Exclude items too expensive for our budget (avoid wasting
            # CS2Cap quota on items we can't actually buy)
            if max_price_usd is not None:
                base_price_cents = int(it.get("price", {}).get("USD", 0))
                base_price = base_price_cents / 100.0
                if base_price > max_price_usd:
                    continue
            agg = agg_prices.get(title, {})
            best_bid = agg.get("best_bid", 0.0) or 0.0
            best_ask = agg.get("best_ask", 0.0) or 0.0
            ask_count = agg.get("ask_count", 0) or 0
            bid_count = agg.get("bid_count", 0) or 0
            if best_bid <= 0 or best_ask <= 0:
                continue
            # Apply the same minimum-spread gate the per-item filter uses
            if best_bid <= best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
                continue
            # v12.7: Volume-weighted spread score
            # spread * sqrt(volume) — rewards both spread width and liquidity
            spread = best_bid - best_ask
            volume = ask_count + bid_count
            if spread > 0 and volume > 0:
                score = spread * math.sqrt(volume)
                ranked.append((title, score))
            elif spread > 0:
                # No volume data — use spread only (fallback)
                ranked.append((title, spread))
        # Sort by score descending — best opportunities first
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    async def _evaluate_candidate(
        self,
        *,
        item: Dict[str, Any],
        game_id: str,
        oracle: Any,
        agg_prices: Dict[str, Dict[str, Any]],
        bulk_fees: Dict[str, float],
        current_balance: float,
        current_margin: float,
        cs_snapshots: Optional[Dict[str, Any]] = None,
        cs_bids: Optional[Dict[str, Any]] = None,
        saturation_counts: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single market item and return a buy payload, or None.

        Returns a dict {buy_offer, title, item_id, base_price, list_price,
        best_bid, best_ask} if the item passes all filters; None otherwise.

        cs_snapshots: optional dict {title: PriceSnapshot} pre-populated by the
        caller via a single CS2Cap /prices/batch call. When supplied, the
        CS2Cap validation step here is a dict lookup (free) instead of a
        per-item HTTP call. Falls back to per-item oracle.get_item_price
        only if the title is missing from the snapshots (selective mode miss).
        """

        title = item.get("title", "")
        item_id = item.get("itemId")
        base_price_cents = int(item.get("price", {}).get("USD", 0))
        base_price = base_price_cents / 100.0

        if not title or not item_id or base_price <= 0:
            return None

        if price_db.has_target_been_placed(item_id):
            return None

        # v12.2 Phase 2.1: Skip if asset is reverted or trade_protected
        if self._skip_if_locked(item_id, title):
            return None

        if base_price < Config.MIN_PRICE_USD:
            return None
        if base_price > self.buy_budget or base_price > current_balance:
            return None

        # v12.4 P0-C: Hard cap on instant-buy price (balance protection).
        # 7-day trade-lock means each snipe freezes the spend for a week.
        # With balance <$100, instant-buy only items < MAX_SNIPING_PRICE_USD
        # to ensure continued turnover after the lock expires.
        # Items > cap are left for the buy-order (target) path, which does
        # not freeze cash until the order fills.
        if base_price > Config.MAX_SNIPING_PRICE_USD:
            if os.getenv("DRY_RUN", "true").lower() == "true":
                price_db.log_decision(
                    title,
                    "skip",
                    "Above instant-buy cap",
                    f"${base_price:.2f} > ${Config.MAX_SNIPING_PRICE_USD:.2f}",
                )
            return None

        max_risk_price = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)
        if base_price > max_risk_price:
            return None

        # Per-cycle diag (one log per cycle)
        if not hasattr(self, "_diag_cycle_id") or self._diag_cycle_id != getattr(self, "_cur_cycle", -1):
            self._diag_cycle_id = getattr(self, "_cur_cycle", -1)
            agg_keys = list(agg_prices.keys())[:3] if agg_prices else []
            cs_keys = list((cs_snapshots or {}).keys())[:3]
            cs_bid_keys = list((cs_bids or {}).keys())[:3]
            logger.info(
                f"[DIAG] item={title!r} base=${base_price:.2f} | "
                f"agg_titles={len(agg_prices)} (sample={agg_keys}) | "
                f"cs_snap_titles={len(cs_snapshots or {})} (sample={cs_keys}) | "
                f"cs_bid_titles={len(cs_bids or {})} (sample={cs_bid_keys})"
            )
        # Per-item diag for top-5 candidates (those in cs_snapshots)
        if cs_snapshots and title in cs_snapshots:
            agg_for_this = agg_prices.get(title, {})
            logger.info(
                f"[DIAG-TOP5] {title!r} base=${base_price:.2f} | "
                f"DM_bid=${agg_for_this.get('best_bid', 0):.2f} "
                f"DM_ask=${agg_for_this.get('best_ask', 0):.2f}"
            )

        # --- Strategy A: bid-ask spread analysis (needed by cross-market threshold) ---
        agg = agg_prices.get(title, {})
        best_bid = agg.get("best_bid", 0.0)
        best_ask = agg.get("best_ask", 0.0)
        ask_count = agg.get("ask_count", 0)
        bid_count = agg.get("bid_count", 0)

        # --- Strategy C: cross-market arb (CS2Cap provider bids) ---
        # Run BEFORE liquidity/wash-trading checks: a strong cross-market
        # signal (provider bid >> DMarket ask) is sufficient evidence of
        # mispricing even for items with no DMarket sales history.
        cross_market_provider = None
        cross_market_bid = 0.0
        if Config.CROSS_MARKET_ENABLED and cs_bids:
            bid_snap = cs_bids.get(title)
            if bid_snap is not None and getattr(bid_snap, "has_data", False):
                # Find provider with highest bid (best cross-market target)
                provider_bids = getattr(bid_snap, "provider_bids", {}) or {}
                if provider_bids:
                    cross_market_provider, cross_market_bid = max(
                        provider_bids.items(), key=lambda kv: kv[1]
                    )
                    # Cross-market must beat: DMarket ask * (1 + min_spread)
                    cm_threshold = best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0)
                    if best_ask > 0 and cross_market_bid > cm_threshold:
                        # Cross-market viable! Override intra-spread requirements.
                        logger.info(
                            f"Cross-market arb HIT: {title} "
                            f"DM_ask=${best_ask:.2f} < "
                            f"{cross_market_provider}_bid=${cross_market_bid:.2f} "
                            f"(+{((cross_market_bid/best_ask)-1)*100:.1f}%)"
                        )
                    else:
                        if best_ask > 0:
                            logger.debug(
                                f"Cross-market miss: {title} "
                                f"DM_ask=${best_ask:.2f} >= "
                                f"{cross_market_provider}_bid=${cross_market_bid:.2f} "
                                f"(threshold=${cm_threshold:.2f})"
                            )
                        cross_market_provider = None
                        cross_market_bid = 0.0
            elif cs_bids:
                logger.debug(
                    f"Cross-market: {title} not in cs_bids "
                    f"(has_data={getattr(bid_snap, 'has_data', 'N/A')})"
                )

        if not self.liquidity.can_spend(base_price, game_id, current_balance):
            return None

        if price_db.is_crashing(title):
            return None

        # v12.2 Phase 2.4: Multi-level liquidity verification
        if Config.USE_LIQUIDITY_FILTER and cross_market_provider is None:
            liquidity = price_db.get_liquidity_metrics(title)
            if not liquidity["is_liquid"]:
                is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
                if is_sandbox:
                    price_db.log_decision(
                        title,
                        "skip",
                        "Low liquidity",
                        f"{liquidity['reason']} (sales={liquidity['total_sales']})",
                    )
                return None

        # v12.2 Phase 2.3: Wash trading detection (trimmed mean)
        if (
            Config.WASH_TRADING_DETECTION
            and cross_market_provider is None
            and not price_db.detect_wash_trading(
                title,
                days=14,
                boost_pct=Config.TRIMMED_MEAN_BOOST_PCT,
                max_outliers=Config.TRIMMED_MEAN_MAX_OUTLIERS,
            )
        ):
            is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "Wash trading detected",
                    "Raw mean >> trimmed mean — price inflated by anomalies",
                )
            return None

        history = price_db.get_recent_prices(title, days=14)
        prices_only = [p for p, _ in history]
        # Skip volatility validation if we have a strong cross-market signal.
        if not prices_only and cross_market_provider is None:
            try:
                validate_volatility(prices_only)
            except PriceValidationError:
                return None

        # --- Strategy C: cross-market arb (CS2Cap provider bids) ---
        # (Now runs BEFORE liquidity/wash-trading checks — see above.)

        if best_ask <= 0 or best_bid <= 0:
            return None
        if ask_count < 1 or bid_count < 1:
            return None  # No real demand

        # Spread check: best_bid > best_ask * (1 + threshold)
        # Skip if NO cross-market arb available either
        if (
            best_bid <= best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0)
            and cross_market_provider is None
        ):
            return None

        # CS2Cap oracle validation (Phase 1: selective, top-K via batch).
        # In selective mode the caller pre-fetches CS2Cap snapshots for the
        # top-K candidates and passes them in cs_snapshots. We do a dict
        # lookup here (free) instead of a per-item HTTP call.
        # v12.7: Also check per-cycle cache to avoid duplicate HTTP calls (P1-5).
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
        cs_price = 0.0
        cs_snap = (cs_snapshots or {}).get(title)
        if cs_snap is not None and getattr(cs_snap, "has_data", False):
            cs_price = cs_snap.min_price
            if is_sandbox:
                cs_price *= scenario_engine.get_price_modifier()
        elif title in self._oracle_price_cache:
            # v12.7: Per-cycle cache hit — avoid HTTP call (P1-5).
            cs_price = self._oracle_price_cache[title]
            if is_sandbox:
                cs_price *= scenario_engine.get_price_modifier()
        else:
            # Title not in the pre-fetched snapshots (not in top-K) or
            # selective mode is off — fall back to per-item call.
            try:
                cs_price = await oracle.get_item_price(title)
                # v12.7: Cache the result for this cycle (P1-5).
                if cs_price > 0:
                    self._oracle_price_cache[title] = cs_price
                if is_sandbox:
                    cs_price *= scenario_engine.get_price_modifier()
            except (RateLimitException, Exception) as e:
                if isinstance(e, RateLimitException) or "429" in str(e):
                    logger.error(f"Oracle rate limited during {game_id} scan.")
                    self.empty_page_count = 5
                    return None
                raise e

        # CS2Cap reference: ensure oracle price is not way below our buy
        # (this would mean the item is genuinely overvalued on DMarket)
        if cs_price > 0 and base_price > cs_price * 1.5:
            # DMarket price is 50%+ above BUFF163 — likely overpriced, skip
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "DMarket overpriced vs BUFF163",
                    f"DM=${base_price} BUFF=${cs_price}",
                )
            return None

        # Calculate profit: list at best_bid - 0.01, but use cross-market bid
        # as upper bound (don't list above what other platforms pay)
        if cross_market_provider and cross_market_bid > best_bid:
            # Cross-market reference is higher than DMarket bid — use it as
            # list price (DMarket bid may rise to meet it, or our listing
            # will be competitive enough for Steam-originated buyers)
            list_price = round(
                min(cross_market_bid * 0.97, cross_market_bid - Config.INTRA_LIST_DISCOUNT),
                2,
            )
        else:
            list_price = round(best_bid - Config.INTRA_LIST_DISCOUNT, 2)

        # v12.0 Phase 1.2: Float Premium (FN-0, FT-0, FN)
        attrs_list = item.get("attributes", [])
        attrs = {a.get("name"): a.get("value") for a in attrs_list}
        float_premium = self._calculate_float_premium(attrs)
        if float_premium > 1.0:
            list_price = round(list_price * float_premium, 2)
            if is_sandbox:
                logger.debug(f"Float premium {float_premium:.2f}x applied to {title}")

        if list_price < base_price * 1.02:
            # Less than 2% gross — too thin after fees
            return None

        # v12.0 Phase 1.1: Low-Fee Filter (prefer low-fee items)
        # v12.2 Phase 2.2: Use bulk fee instead of per-item API call
        fee_rate = bulk_fees.get(item_id, 0.05)
        if fee_rate == 0.05:
            # Fall back to per-item call only if bulk missed this item
            fee_rate = await self.client.get_item_fee(game_id, item_id, base_price_cents)
        cached_low_fee = price_db.get_low_fee_rate(title)
        if cached_low_fee is not None and cached_low_fee < fee_rate:
            # Use the lower cached rate (it might differ slightly from dynamic)
            fee_rate = min(fee_rate, cached_low_fee)

        try:
            validate_arbitrage_profit(
                buy_price=base_price,
                expected_sell_price=list_price,
                fee_markup=fee_rate,
                min_profit_margin=current_margin,
                lock_days=7,
            )
        except PriceValidationError as e:
            if is_sandbox:
                price_db.log_decision(title, "skip", "Low profit", str(e))
            return None

        # v12.7: Inventory saturation check (P2-4).
        # Limits concentration risk: max N units of same hash_name.
        # Uses Config.MAX_SAME_ITEM_HOLDINGS (env-configurable, default 3).
        # v12.8: Uses pre-computed saturation_counts (O(1) lookup) when available,
        # avoiding N separate DB calls for each candidate in the parallel loop.
        if saturation_counts is not None:
            held_count = saturation_counts.get(title, 0)
        else:
            held_count = len(
                [
                    x
                    for x in price_db.get_virtual_inventory(status="idle", only_unlocked=False)
                    if x["hash_name"] == title
                ]
            )
        if held_count >= Config.MAX_SAME_ITEM_HOLDINGS:
            if is_sandbox:
                price_db.record_missed_opportunity(
                    title, base_price, list_price, f"Saturation Limit ({held_count})"
                )
            else:
                logger.debug(
                    f"[SATURATION] {title}: already holding {held_count} units, "
                    f"max={Config.MAX_SAME_ITEM_HOLDINGS}. Skipping."
                )
            return None

        if is_sandbox and base_price > current_balance:
            price_db.record_missed_opportunity(
                title, base_price, list_price, "Insufficient Balance"
            )

        # --- Decide: instant buy vs target ---
        # For intra-spread strategy, we typically instant-buy
        # (the spread exists right now, may not in 5 minutes)
        buy_offer = {
            "offerId": item_id,
            "price": {"amount": str(int(base_price * 100)), "currency": "USD"},
        }
        return {
            "buy_offer": buy_offer,
            "title": title,
            "item_id": item_id,
            "base_price": base_price,
            "list_price": list_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "strategy": "cross_market" if cross_market_provider else "intra_spread",
            "target_platform": cross_market_provider or "dmarket",
        }
