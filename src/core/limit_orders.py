"""
limit_orders.py — Buy-target (limit order) integration (v14.5).

The DMarket API client has batch_create_targets() but it was never used.
This module integrates limit orders into the execution pipeline so the bot
can place buy orders below market ask and wait for sellers to hit them —
instead of always being a taker (instant-buy).

Strategy:
  - For items with high spread (>10%) → place target at best_bid, wait
  - For items with moderate spread (5-10%) → instant-buy at best_ask
  - For items with low spread (<5%) → skip

Mixed into `_ExecutionMixin` (see `execution.py`).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.config import Config

logger = logging.getLogger("LimitOrders")

LIMIT_ORDER_ENABLED = os.getenv("LIMIT_ORDER_ENABLED", "true").lower() == "true"
LIMIT_ORDER_MIN_SPREAD_PCT = float(os.getenv("LIMIT_ORDER_MIN_SPREAD_PCT", "10.0"))
LIMIT_ORDER_MAX_PER_CYCLE = int(os.getenv("LIMIT_ORDER_MAX_PER_CYCLE", "5"))
LIMIT_ORDER_TARGET_DISCOUNT = float(os.getenv("LIMIT_ORDER_TARGET_DISCOUNT", "0.03"))  # 3% below bid

# Cross-market buy targets: place orders on DMarket at CS2Cap ask minus costs.
# This lets the bot provide liquidity and catch sellers who hit our price,
# even when DMarket's best ask is above CS2Cap (the normal state).
CROSS_MARKET_TARGET_ENABLED = os.getenv("CROSS_MARKET_TARGET_ENABLED", "true").lower() == "true"
CROSS_MARKET_TARGET_MARGIN = float(os.getenv("CROSS_MARKET_TARGET_MARGIN", "0.03"))  # 3% target profit
CROSS_MARKET_TARGET_MAX_PER_CYCLE = int(os.getenv("CROSS_MARKET_TARGET_MAX_PER_CYCLE", "10"))


class _LimitOrderMixin:
    """Buy-target (limit order) execution."""

    client: Any  # DMarketAPIClient

    async def _execute_limit_orders(
        self,
        *,
        candidates: List[Dict[str, Any]],
        game_id: str,
        current_balance: float,
    ) -> int:
        """
        Place buy targets (limit orders) for items with wide spreads.
        These sit on the order book and fill when a seller hits our price.

        Returns number of targets placed.
        """
        if not LIMIT_ORDER_ENABLED:
            return 0

        targets_to_place: List[Dict[str, Any]] = []
        for cand in candidates[:LIMIT_ORDER_MAX_PER_CYCLE]:
            title = cand.get("title", "")
            best_bid = cand.get("best_bid", 0.0)
            best_ask = cand.get("best_ask", 0.0)
            base_price = cand.get("base_price", 0.0)

            if best_ask <= 0 or best_bid <= 0:
                continue

            spread_pct = ((best_bid - best_ask) / best_ask) * 100.0
            if spread_pct < LIMIT_ORDER_MIN_SPREAD_PCT:
                continue

            # Target slightly below best bid — we want to be the highest bidder
            # but still get a discount vs instant-buy at best_ask
            target_price = round(best_bid * (1 - LIMIT_ORDER_TARGET_DISCOUNT), 2)
            if target_price >= best_ask:
                continue  # target would be at or above ask — just instant-buy instead
            if target_price > current_balance:
                continue

            targets_to_place.append({
                "title": title,
                "price": {"amount": str(int(target_price * 100)), "currency": "USD"},
                "game_id": game_id,
            })

        if not targets_to_place:
            return 0

        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        if is_dry:
            logger.info(
                f"[LIMIT] Would place {len(targets_to_place)} buy target(s): "
                f"{', '.join(t['title'][:20] for t in targets_to_place[:3])}"
            )
            return len(targets_to_place)

        try:
            result = await self.client.batch_create_targets(targets_to_place)
            placed = len(result.get("targets", result.get("items", [])))
            logger.info(f"[LIMIT] Placed {placed}/{len(targets_to_place)} buy target(s)")
            return placed
        except Exception as e:
            logger.warning(f"[LIMIT] batch_create_targets failed: {e}")
            return 0

    def _categorize_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Split candidates into:
          - limit_order: wide spread → place target
          - instant_buy: moderate spread → instant-buy at ask
        Narrow spread items (<5%) are dropped.
        """
        limit_targets: List[Dict[str, Any]] = []
        instant_targets: List[Dict[str, Any]] = []

        for cand in candidates:
            best_ask = cand.get("best_ask", 0.0)
            best_bid = cand.get("best_bid", 0.0)
            if best_ask <= 0:
                continue
            spread_pct = ((best_bid - best_ask) / best_ask) * 100.0 if best_bid > 0 else 0

            if spread_pct >= LIMIT_ORDER_MIN_SPREAD_PCT:
                limit_targets.append(cand)
            elif spread_pct >= 3.0:
                instant_targets.append(cand)

        return limit_targets, instant_targets

    async def _execute_cross_market_targets(
        self,
        *,
        game_id: str,
        agg_prices: Dict[str, Any],
        cs_snapshots: Dict[str, Any],
        current_balance: float,
    ) -> int:
        """
        Place DMarket buy targets priced from CS2Cap lowest ask minus costs.

        When DMarket best ask is above CS2Cap (the usual case), we cannot
        instant-buy profitably. Instead we post buy orders slightly below
        CS2Cap ask. If a DMarket seller hits our price, we buy cheap and can
        resell at/near CS2Cap reference.

        Returns number of targets placed.
        """
        from src.config import Config

        if not (LIMIT_ORDER_ENABLED and Config.CROSS_MARKET_TARGET_ENABLED):
            return 0

        # Track titles we already targeted this session to avoid duplicates.
        if not hasattr(self, "_placed_cross_targets"):
            self._placed_cross_targets: set[str] = set()

        total_cost = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE
        required_margin = total_cost + Config.CROSS_MARKET_TARGET_MARGIN

        candidates: List[Dict[str, Any]] = []
        for title, agg in agg_prices.items():
            if title in self._placed_cross_targets:
                continue

            cs_snap = cs_snapshots.get(title)
            if cs_snap is None or not getattr(cs_snap, "has_data", False):
                continue

            cs_ask = cs_snap.min_price
            if cs_ask <= 0:
                continue

            best_ask = agg.get("best_ask", 0.0) or 0.0
            if best_ask <= 0:
                continue

            # Target: CS2Cap ask minus fees and target profit.
            target_price = round(cs_ask * (1 - required_margin), 2)

            # Only place if our target is below current DMarket ask
            # (otherwise we'd just instant-buy instead).
            if target_price >= best_ask * 0.99:
                continue

            if target_price > current_balance:
                continue

            if target_price < Config.MIN_PRICE_USD:
                continue

            # Potential margin if filled and sold at CS2Cap ask.
            margin = (cs_ask - target_price) / target_price if target_price > 0 else 0.0
            candidates.append({
                "title": title,
                "price": {"amount": str(int(target_price * 100)), "currency": "USD"},
                "game_id": game_id,
                "target_price": target_price,
                "margin": margin,
            })

        # Sort by best margin and cap at max per cycle.
        candidates.sort(key=lambda x: x["margin"], reverse=True)
        targets_to_place = candidates[:Config.CROSS_MARKET_TARGET_MAX_PER_CYCLE]

        if not targets_to_place:
            return 0

        # Remember titles so we don't re-target them in the next cycle.
        for t in targets_to_place:
            self._placed_cross_targets.add(t["title"])

        is_dry = os.getenv("DRY_RUN", "true").lower() == "true"
        if is_dry:
            logger.info(
                f"[CROSS-MARKET TARGET] Would place {len(targets_to_place)} buy target(s): "
                f"{', '.join(t['title'][:20] for t in targets_to_place[:3])}"
            )
            return len(targets_to_place)

        try:
            result = await self.client.batch_create_targets(targets_to_place)
            placed = len(result.get("targets", result.get("items", [])))
            logger.info(f"[CROSS-MARKET TARGET] Placed {placed}/{len(targets_to_place)} buy target(s)")
            return placed
        except Exception as e:
            logger.warning(f"[CROSS-MARKET TARGET] batch_create_targets failed: {e}")
            return 0
