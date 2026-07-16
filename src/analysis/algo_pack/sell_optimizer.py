"""
sell_optimizer.py — Optimal sell price via ternary search.

Source: CP-Algorithms (ternary search)
Adapted for DMarket: finds discount% that maximizes expected profit.

Expected profit = (sell_price - cost) × P(fill at this price)
where P(fill) is estimated from historical price data.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("SellOptimizer")


def find_optimal_discount(
    fair_price: float,
    cost_price: float,
    fee_rate: float,
    price_history: list[float],
    min_discount: float = 0.01,
    max_discount: float = 0.15,
    iterations: int = 100,
) -> float:
    """Ternary search for optimal sell discount percentage.

    Maximizes: expected_profit(discount) = margin × P(sell at this price)

    Args:
        fair_price: Oracle/aggregated fair price of the item.
        cost_price: What we paid (or will pay) for the item.
        fee_rate: DMarket fee rate (e.g. 0.05 for 5%).
        price_history: Historical selling prices for this item.
        min_discount: Minimum discount (0.01 = 1%).
        max_discount: Maximum discount (0.15 = 15%).
        iterations: Number of ternary search iterations.

    Returns:
        Optimal discount as a float (e.g. 0.035 = 3.5% discount).

    Source: CP-Algorithms ternary_search.html
    """
    if fair_price <= 0 or cost_price <= 0:
        return min_discount

    lo, hi = min_discount, max_discount
    eps = 1e-4

    for _ in range(iterations):
        if hi - lo < eps:
            break

        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3

        f1 = _expected_profit(fair_price, cost_price, m1, fee_rate, price_history)
        f2 = _expected_profit(fair_price, cost_price, m2, fee_rate, price_history)

        if f1 < f2:
            lo = m1
        else:
            hi = m2

    result = round((lo + hi) / 2, 4)

    # Sanity check: never discount below break-even
    break_even_discount = 1.0 - (cost_price * (1 + fee_rate)) / fair_price
    if result < break_even_discount:
        result = max(min_discount, break_even_discount)

    return round(max(min_discount, min(max_discount, result)), 4)


def find_optimal_sell_price(
    fair_price: float,
    cost_price: float,
    fee_rate: float,
    price_history: list[float],
) -> float:
    """Return optimal sell price in USD."""
    discount = find_optimal_discount(
        fair_price, cost_price, fee_rate, price_history
    )
    return round(fair_price * (1 - discount), 2)


def _expected_profit(
    fair_price: float,
    cost_price: float,
    discount: float,
    fee_rate: float,
    price_history: list[float],
) -> float:
    """Expected profit = margin × probability of fill.

    P(fill) = fraction of historical prices >= sell_price.
    """
    sell_price = fair_price * (1 - discount)
    margin = sell_price - cost_price - (sell_price * fee_rate)

    if margin <= 0:
        return -1e9  # never sell at a loss

    if not price_history:
        return margin * 0.5  # default 50% fill probability

    fills = sum(1 for p in price_history if p >= sell_price)
    fill_prob = fills / len(price_history)

    return margin * fill_prob


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for sell optimizer."""
    # Item: fair price $10, cost $8, fee 5%
    # History: prices around $9-11
    history = [9.5, 10.0, 10.2, 10.5, 11.0, 9.8, 10.1]

    discount = find_optimal_discount(
        fair_price=10.0,
        cost_price=8.0,
        fee_rate=0.05,
        price_history=history,
    )
    sell_price = 10.0 * (1 - discount)
    margin = sell_price - 8.0 - sell_price * 0.05

    print(f"[SellOptimizer] Optimal discount: {discount:.1%}")
    print(f"[SellOptimizer] Sell price: ${sell_price:.2f}")
    print(f"[SellOptimizer] Expected margin: ${margin:.2f}")

    assert 0.01 <= discount <= 0.15, f"Discount out of range: {discount}"
    assert margin > 0, f"Negative margin: {margin}"
    print("[SellOptimizer] Self-check PASSED")


if __name__ == "__main__":
    _demo()
