"""
orderbook.py — DOM / Order Book analysis utilities (v14.0).

Provides:
  - find_gap_price():      Place listing into largest price gap
  - compute_depth_profile(): Build DOM profile with gaps, median, weighted avg
"""

from __future__ import annotations

from typing import Any, Dict, List


def find_gap_price(listings: List[Dict[str, Any]], min_price: float) -> float:
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


def compute_depth_profile(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    weighted = sum(prices) / len(prices)

    return {
        "levels": dict(levels),
        "gaps": gaps,
        "median_price": round(median, 2),
        "weighted_avg": round(weighted, 2),
    }
