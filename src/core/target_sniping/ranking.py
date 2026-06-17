"""
ranking.py — Volume-weighted spread ranking (standalone, extracted from filter.py).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from src.config import Config


def rank_candidates_by_spread(
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
    ranked: List[Tuple[str, float]] = []
    for it in items:
        title = it.get("title", "")
        if not title:
            continue
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
        if best_bid <= best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
            continue
        spread = best_bid - best_ask
        volume = ask_count + bid_count
        if spread > 0 and volume > 0:
            score = spread * math.sqrt(volume)
            ranked.append((title, score))
        elif spread > 0:
            ranked.append((title, spread))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
