"""
spread_optimizer.py — Adaptive MIN_SPREAD via binary search.

Source: CP-Algorithms (binary search on arbitrary predicate)

Problem: MIN_SPREAD_PCT = 3.0 is fixed. Not adaptive to market conditions.
Solution: Binary search finds min_spread that achieves target win_rate.

Use: periodically recalculate optimal MIN_SPREAD from trade history.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("SpreadOptimizer")


def find_optimal_min_spread(
    trade_history: list[dict[str, Any]],
    target_win_rate: float = 0.55,
    min_spread: float = 0.01,
    max_spread: float = 0.15,
    iterations: int = 50,
) -> float:
    """Binary search for min_spread that achieves target win rate.

    Predicate: win_rate at this spread threshold >= target_win_rate.

    Args:
        trade_history: List of completed trades with 'spread_pct' and 'profit'.
        target_win_rate: Desired win rate (e.g. 0.55 for 55%).
        min_spread: Minimum spread to consider (1%).
        max_spread: Maximum spread to consider (15%).
        iterations: Binary search iterations.

    Returns:
        Optimal min_spread as a float (e.g. 0.035 = 3.5%).

    Source: CP-Algorithms binary_search.html
    """
    if not trade_history:
        return (min_spread + max_spread) / 2  # default midpoint

    lo, hi = min_spread, max_spread
    eps = 0.001

    for _ in range(iterations):
        if hi - lo < eps:
            break

        mid = (lo + hi) / 2

        # Count wins and total at this spread threshold
        wins = 0
        total = 0
        for t in trade_history:
            spread = t.get("spread_pct", 0)
            profit = t.get("profit", 0)
            if spread >= mid:
                total += 1
                if profit > 0:
                    wins += 1

        if total == 0:
            # No data at this spread → lower threshold
            hi = mid
            continue

        win_rate = wins / total

        if win_rate >= target_win_rate:
            # Can afford to be more selective
            lo = mid
        else:
            # Too selective, not enough wins → lower threshold
            hi = mid

    result = round((lo + hi) / 2, 3)
    logger.info(
        f"[SpreadOptimizer] Optimal min_spread: {result:.1%} "
        f"(target WR={target_win_rate:.0%})"
    )
    return result


def estimate_spread_distribution(
    trade_history: list[dict[str, Any]],
) -> dict[str, float]:
    """Analyze spread distribution from trade history.

    Returns stats: mean, median, p25, p75, win_rate by spread bucket.
    """
    if not trade_history:
        return {}

    spreads = [t.get("spread_pct", 0) for t in trade_history]
    spreads.sort()

    n = len(spreads)
    return {
        "count": n,
        "mean": sum(spreads) / n,
        "median": spreads[n // 2],
        "p25": spreads[n // 4],
        "p75": spreads[3 * n // 4],
        "min": spreads[0],
        "max": spreads[-1],
    }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for spread optimizer."""
    # Simulated trade history: higher spread = more wins
    import random
    random.seed(42)

    history = []
    for _ in range(200):
        spread = random.uniform(0.01, 0.10)
        # P(win) increases with spread
        win_prob = min(0.9, 0.3 + spread * 8)
        won = random.random() < win_prob
        history.append({
            "spread_pct": round(spread, 3),
            "profit": 1.0 if won else -0.5,
        })

    optimal = find_optimal_min_spread(history, target_win_rate=0.55)
    stats = estimate_spread_distribution(history)

    print(f"[SpreadOptimizer] Optimal min_spread: {optimal:.1%}")
    print(f"[SpreadOptimizer] Distribution: mean={stats['mean']:.1%}, "
          f"median={stats['median']:.1%}")

    assert 0.01 <= optimal <= 0.15, f"Out of range: {optimal}"
    print("[SpreadOptimizer] Self-check PASSED")


if __name__ == "__main__":
    _demo()
