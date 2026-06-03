"""
filter.py — Per-item candidate evaluation.

Mixin with the heavy filter loop (originally inline in run_cycle).
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.api.cs2cap_oracle import RateLimitException
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
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single market item and return a buy payload, or None.

        Returns a dict {buy_offer, title, item_id, base_price, list_price,
        best_bid, best_ask} if the item passes all filters; None otherwise.
        """
        from src.config import Config

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

        max_risk_price = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)
        if base_price > max_risk_price:
            return None

        if not self.liquidity.can_spend(base_price, game_id, current_balance):
            return None

        if price_db.is_crashing(title):
            return None

        # v12.2 Phase 2.4: Multi-level liquidity verification
        if Config.USE_LIQUIDITY_FILTER:
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
        if Config.WASH_TRADING_DETECTION and not price_db.detect_wash_trading(
            title,
            days=14,
            boost_pct=Config.TRIMMED_MEAN_BOOST_PCT,
            max_outliers=Config.TRIMMED_MEAN_MAX_OUTLIERS,
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
        try:
            validate_volatility(prices_only)
        except PriceValidationError:
            return None

        # --- Strategy A: bid-ask spread analysis ---
        agg = agg_prices.get(title, {})
        best_bid = agg.get("best_bid", 0.0)
        best_ask = agg.get("best_ask", 0.0)
        ask_count = agg.get("ask_count", 0)
        bid_count = agg.get("bid_count", 0)

        if best_ask <= 0 or best_bid <= 0:
            return None
        if ask_count < 1 or bid_count < 1:
            return None  # No real demand

        # Spread check: best_bid > best_ask * 1.05
        if best_bid <= best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
            return None

        # CS2Cap oracle validation (sanity check)
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
        try:
            cs_price = await oracle.get_item_price(title)
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

        # Calculate profit: list at best_bid - 0.01
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
            net_margin = validate_arbitrage_profit(
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

        if is_sandbox:
            if base_price > current_balance:
                price_db.record_missed_opportunity(
                    title, base_price, list_price, "Insufficient Balance"
                )
            held_count = len(
                [
                    x
                    for x in price_db.get_virtual_inventory(status="idle")
                    if x["hash_name"] == title
                ]
            )
            if held_count >= 5:
                price_db.record_missed_opportunity(
                    title, base_price, list_price, f"Saturation Limit ({held_count})"
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
        }
