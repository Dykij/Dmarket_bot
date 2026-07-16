"""
trend_strength.py — Trend detection via LIS (Longest Increasing Subsequence).

Source: CP-Algorithms (LIS O(n log n))
Adapted for DMarket: measures trend strength from price history.

trend_strength = LIS_length / window_length
  1.0 = perfect uptrend
  0.5 = random walk
  0.0 = perfect downtrend

Use: skip buys during sustained downtrend (trend_strength < threshold).
"""

from __future__ import annotations

import bisect
import logging

logger = logging.getLogger("TrendStrength")


def lis_length(prices: list[float]) -> int:
    """Length of longest strictly increasing subsequence.

    O(n log n) via patience sorting / binary search on tails.

    Source: CP-Algorithms longest_increasing_subsequence.html

    Args:
        prices: Sequence of numeric values.

    Returns:
        Length of the LIS.
    """
    if not prices:
        return 0

    tails: list[float] = []
    for price in prices:
        pos = bisect.bisect_left(tails, price)
        if pos == len(tails):
            tails.append(price)
        else:
            tails[pos] = price

    return len(tails)


def trend_strength(
    prices: list[float],
    window: int = 50,
) -> float:
    """Trend strength from LIS ratio.

    Args:
        prices: Historical prices (oldest first).
        window: Lookback window size.

    Returns:
        Float in [0.0, 1.0]. >0.5 = uptrend, <0.5 = downtrend.
    """
    if len(prices) < 3:
        return 0.5  # neutral — not enough data

    recent = prices[-window:]
    lis_len = lis_length(recent)

    return lis_len / len(recent)


def should_buy_by_trend(
    prices: list[float],
    threshold: float = 0.40,
    window: int = 50,
) -> bool:
    """Gate: should we buy this item based on trend?

    Returns True if trend_strength >= threshold (uptrend or neutral).
    Returns False during sustained downtrend.
    """
    strength = trend_strength(prices, window)
    return strength >= threshold


def trend_direction(prices: list[float], window: int = 50) -> str:
    """Human-readable trend direction."""
    s = trend_strength(prices, window)
    if s >= 0.6:
        return "STRONG_UPTREND"
    elif s >= 0.5:
        return "WEAK_UPTREND"
    elif s >= 0.4:
        return "RANGING"
    else:
        return "DOWNTREND"


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for trend strength."""
    uptrend = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9]
    downtrend = [1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0]
    random_walk = [1.0, 1.2, 0.9, 1.3, 0.8, 1.4, 0.7, 1.5, 0.6, 1.6]

    u = trend_strength(uptrend)
    d = trend_strength(downtrend)
    r = trend_strength(random_walk)

    print(f"[TrendStrength] Uptrend:   {u:.2f} ({trend_direction(uptrend)})")
    print(f"[TrendStrength] Downtrend: {d:.2f} ({trend_direction(downtrend)})")
    print(f"[TrendStrength] Random:    {r:.2f} ({trend_direction(random_walk)})")

    assert u > 0.8, f"Uptrend should be high: {u}"
    assert d < 0.3, f"Downtrend should be low: {d}"
    assert should_buy_by_trend(uptrend)
    assert not should_buy_by_trend(downtrend)
    print("[TrendStrength] Self-check PASSED")


if __name__ == "__main__":
    _demo()
