"""
ranking.py — Volume-weighted spread ranking (standalone, extracted from filter.py).

v14.6: Commission optimizer — boosts score for low-fee items.
"""

from __future__ import annotations

import math
from typing import Any

from src.config import Config


def rank_candidates_by_spread(
    items: list[dict[str, Any]],
    agg_prices: dict[str, dict[str, Any]],
    max_price_usd: float | None = None,
    low_fee_titles: set | None = None,
) -> list[tuple[str, float]]:
    """
    v12.7: Rank items by volume-weighted spread score (P2-3).

    Formula: score = spread_usd * sqrt(ask_count + bid_count)
    This prioritizes items with both good spread AND reasonable volume,
    avoiding low-liquidity items that are hard to sell.

    v14.6: Commission optimizer — items with 2% fee get +15% score boost
    (higher effective profit margin due to lower fees).

    Returns: [(title, score), ...] sorted best-score first.
    Items with no agg_prices entry or zero bid/ask are filtered out.

    max_price_usd: optional cap to exclude items too expensive for our
    balance (avoids wasting oracle quota on $1000 Karambits when balance
    is $43.91).

    low_fee_titles: optional set of titles known to have 2% commission.
    """
    ranked: list[tuple[str, float]] = []
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

        # v14.8: Fee-aware ranking. Prefer high margin% * liquidity rather than
        # absolute spread, so a 10% margin on a $2 item ranks above a 2% margin
        # on a $20 item with the same volume.
        effective_min_spread = Config.INTRA_MIN_SPREAD_PCT
        if Config.SEASONAL_TIMING_ENABLED:
            try:
                from src.analysis.seasonal import get_timing_multiplier
                effective_min_spread *= get_timing_multiplier()
            except Exception:
                pass

        spread = best_bid - best_ask
        spread_pct = spread / best_ask if best_ask > 0 else 0.0
        if spread_pct < float(effective_min_spread) / 100.0:
            continue

        # Estimated cost to buy + sell + cash out. Low-fee items get a lower
        # effective cost and therefore a higher score.
        fee_estimate = float(Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE)
        if Config.COMMISSION_OPTIMIZER_ENABLED and low_fee_titles is not None and title in low_fee_titles:
            fee_estimate *= 0.70  # ~30% cheaper fee stack (e.g. 2% vs 4.5%)

        net_margin = spread_pct - fee_estimate
        if net_margin <= 0:
            continue

        volume = ask_count + bid_count
        liquidity = math.sqrt(max(volume, 1))
        # Score = expected net margin × liquidity. Items with no volume still
        # score margin × 1, but liquidity is strongly preferred.
        score = net_margin * liquidity

        # v14.6: Filler skin boost — higher demand = faster resale
        if Config.FILLER_TRACKING_ENABLED:
            try:
                from src.analytics.filler_tracker import is_filler
                if is_filler(title):
                    score *= 1.08  # +8% for filler skins (faster turnover)
            except Exception:
                pass

        ranked.append((title, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
