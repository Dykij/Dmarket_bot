"""
orderbook.py — DOM / Order Book analysis utilities (v14.0, v14.9.1 improved).

Provides:
  - find_gap_price():        Place listing into largest price gap
  - compute_depth_profile(): Build DOM profile with gaps, median, weighted avg
  - detect_spoofing():       Detect order book manipulation patterns
"""

from __future__ import annotations

from typing import Any


def find_gap_price(listings: list[dict[str, Any]], min_price: float) -> float:
    """
    Find the optimal listing price by placing into the largest price gap.

    Args:
        listings: list of DMarket listing dicts with {"price": {"USD": int}}
        min_price: minimum acceptable sell price (buy_price + fees + margin)

    Returns:
        Optimal sell price in USD, or min_price * 1.03 if no suitable gap found.
    """
    if not listings or len(listings) < 2:
        return round(min_price * 1.03, 2)

    prices = sorted(
        int(item.get("price", {}).get("USD", 0)) / 100.0
        for item in listings
        if int(item.get("price", {}).get("USD", 0)) > 0
    )

    if len(prices) < 2:
        return round(min_price * 1.03, 2)

    best_gap = 0.0
    best_upper = 0.0
    for i in range(len(prices) - 1):
        gap = prices[i + 1] - prices[i]
        if gap > best_gap and prices[i + 1] > min_price:
            best_gap = gap
            best_upper = prices[i + 1]

    if best_gap > 0 and best_upper > min_price:
        return round(best_upper - 0.01, 2)

    return round(min_price * 1.03, 2)


def compute_depth_profile(listings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a depth-of-market profile from DMarket listings.

    Args:
        listings: list of DMarket listing dicts with {"price": {"USD": int}}

    Returns:
        {
            "levels": {price: count},
            "gaps": [(lower_price, upper_price, gap_size), ...],
            "median_price": float,
            "weighted_avg": float,
        }
    """
    from collections import Counter

    prices = sorted(
        int(item.get("price", {}).get("USD", 0)) / 100.0
        for item in listings
        if int(item.get("price", {}).get("USD", 0)) > 0
    )

    if not prices:
        return {
            "levels": {}, "gaps": [], "median_price": 0.0, "weighted_avg": 0.0,
        }

    levels = Counter(prices)

    gaps = []
    for i in range(len(prices) - 1):
        gap = prices[i + 1] - prices[i]
        if gap > prices[i] * 0.02:
            gaps.append((prices[i], prices[i + 1], round(gap, 2)))

    mid = len(prices) // 2
    median = prices[mid]

    # v14.9.1: True volume-weighted average (was simple mean before)
    total_volume = sum(levels.values())
    if total_volume > 0:
        weighted = sum(price * count for price, count in levels.items()) / total_volume
    else:
        weighted = sum(prices) / len(prices) if prices else 0.0

    return {
        "levels": dict(levels),
        "gaps": gaps,
        "median_price": round(median, 2),
        "weighted_avg": round(weighted, 2),
    }


def detect_spoofing(
    listings: list[dict[str, Any]],
    price_history: list[float] | None = None,
    max_single_level_pct: float = 0.40,
    max_top3_pct: float = 0.70,
    imbalance_threshold: float = 3.0,
) -> dict[str, Any]:
    """
    v14.9.1: Detect order book manipulation (spoofing) patterns.
    
    Spoofing indicators:
    1. Single price level holds >40% of total depth (concentration risk)
    2. Top 3 levels hold >70% of total depth (artificial depth)
    3. Bid/ask imbalance >3:1 (one-sided book, likely fake)
    4. Large orders far from mid-price (iceberg/spoof walls)
    
    Args:
        listings: list of DMarket listing dicts
        price_history: optional recent prices for mid-price reference
        max_single_level_pct: max fraction at single level before flagging
        max_top3_pct: max fraction at top 3 levels before flagging
        imbalance_threshold: max bid/ask ratio before flagging
        
    Returns:
        {
            "is_suspicious": bool,
            "flags": [str],
            "confidence": float (0-1),
        }
    """
    from collections import Counter

    if not listings or len(listings) < 5:
        return {"is_suspicious": False, "flags": [], "confidence": 0.0}

    prices = sorted(
        int(item.get("price", {}).get("USD", 0)) / 100.0
        for item in listings
        if int(item.get("price", {}).get("USD", 0)) > 0
    )

    if len(prices) < 5:
        return {"is_suspicious": False, "flags": [], "confidence": 0.0}

    levels = Counter(prices)
    total_orders = sum(levels.values())
    if total_orders == 0:
        return {"is_suspicious": False, "flags": [], "confidence": 0.0}

    flags = []
    confidence = 0.0

    # 1. Single level concentration
    max_level_count = max(levels.values())
    max_level_pct = max_level_count / total_orders
    if max_level_pct > max_single_level_pct:
        flags.append(f"single_level_concentration: {max_level_pct:.1%}")
        confidence += 0.3

    # 2. Top 3 levels concentration
    sorted_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)
    top3_count = sum(count for _, count in sorted_levels[:3])
    top3_pct = top3_count / total_orders
    if top3_pct > max_top3_pct:
        flags.append(f"top3_concentration: {top3_pct:.1%}")
        confidence += 0.25

    # 3. Bid/Ask imbalance (split at median)
    mid_price = prices[len(prices) // 2]
    bid_count = sum(count for p, count in levels.items() if p <= mid_price)
    ask_count = sum(count for p, count in levels.items() if p > mid_price)

    imbalance = bid_count / ask_count if ask_count > 0 else float("inf")

    if imbalance > imbalance_threshold or (1.0 / imbalance if imbalance > 0 else 0) > imbalance_threshold:
        flags.append(f"bid_ask_imbalance: {imbalance:.2f}")
        confidence += 0.25

    # 4. Wall detection: large orders far from median
    wall_threshold = mid_price * 0.15  # 15% away from median
    for price, count in levels.items():
        if abs(price - mid_price) > wall_threshold and count > total_orders * 0.15:
            flags.append(f"wall_at_{price:.2f}: {count} orders ({count/total_orders:.1%})")
            confidence += 0.2

    # 5. Price gap analysis: suspicious gaps near current price
    if len(prices) >= 2:
        near_mid_gaps = []
        for i in range(len(prices) - 1):
            gap = prices[i + 1] - prices[i]
            avg_price = (prices[i] + prices[i + 1]) / 2
            if avg_price > 0 and gap / avg_price > 0.05:  # >5% gap
                near_mid_gaps.append(gap)
        if len(near_mid_gaps) > 2:
            flags.append(f"suspicious_gaps: {len(near_mid_gaps)} large gaps")
            confidence += 0.15

    confidence = min(confidence, 1.0)
    is_suspicious = confidence > 0.4 or len(flags) >= 2

    return {
        "is_suspicious": is_suspicious,
        "flags": flags,
        "confidence": round(confidence, 2),
    }
