"""
ewma.py — Exponentially Weighted Moving Average & Volatility.

Source: Habr quantitative trading, RiskMetrics methodology, arXiv:2508.16598

EWMA gives exponentially more weight to recent observations.
Better than SMA for price forecasting and volatility estimation.

Use cases:
- Price forecasting: ewma_forecast(prices) → predicted next price
- Volatility estimation: ewma_volatility(prices) → risk measure
- Adaptive Kelly: ewma_adjusted_kelly(win_rate, prices) → position size
"""

from __future__ import annotations

import math
import logging

logger = logging.getLogger("EWMA")


def ewma(prices: list[float], alpha: float = 0.3) -> float:
    """Exponentially Weighted Moving Average.

    Args:
        prices: Price series (oldest first).
        alpha: Smoothing factor (0 < alpha <= 1).
            0.1 = slow (long memory), 0.3 = moderate, 0.5 = fast.

    Returns:
        EWMA value (last smoothed estimate).
    """
    if not prices:
        return 0.0

    result = prices[0]
    for price in prices[1:]:
        result = alpha * price + (1 - alpha) * result

    return result


def ewma_forecast(prices: list[float], alpha: float = 0.3) -> float:
    """Forecast next price using EWMA.

    The EWMA itself is the best forecast for the next observation
    under the assumption of mean-reverting prices.
    """
    return ewma(prices, alpha)


def ewma_volatility(prices: list[float], alpha: float = 0.06) -> float:
    """EWMA volatility estimator (RiskMetrics method).

    alpha = 0.06 is the RiskMetrics default for daily data.
    More responsive to recent volatility shocks than simple std.

    Args:
        prices: Price series (oldest first).
        alpha: Smoothing factor.

    Returns:
        Annualized (or per-period) volatility as a float.
    """
    if len(prices) < 2:
        return 0.0

    # Compute returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            r = (prices[i] - prices[i - 1]) / prices[i - 1]
            returns.append(r)

    if not returns:
        return 0.0

    # EWMA variance
    var = returns[0] ** 2
    for r in returns[1:]:
        var = alpha * r ** 2 + (1 - alpha) * var

    return math.sqrt(var)


def ewma_volatility_regime(
    prices: list[float],
    fast_alpha: float = 0.15,
    slow_alpha: float = 0.03,
) -> str:
    """Detect volatility regime via dual EWMA.

    Fast EWMA reacts quickly, slow EWMA is stable.
    If fast > slow → volatility expanding (dangerous).
    If fast < slow → volatility contracting (safe).

    Returns: 'EXPANDING', 'CONTRACTING', or 'NEUTRAL'.
    """
    vol_fast = ewma_volatility(prices, fast_alpha)
    vol_slow = ewma_volatility(prices, slow_alpha)

    ratio = vol_fast / max(vol_slow, 1e-8)

    if ratio > 1.3:
        return "EXPANDING"
    elif ratio < 0.7:
        return "CONTRACTING"
    return "NEUTRAL"


def adaptive_kelly_fraction(
    win_rate: float,
    win_loss_ratio: float,
    prices: list[float],
    base_fraction: float = 0.5,
) -> float:
    """Kelly criterion with EWMA volatility adjustment.

    High volatility → reduce position size.
    Low volatility → increase position size.

    Source: arXiv:2508.16598 (Hybrid Kelly+Volatility).

    Args:
        win_rate: Historical win rate [0, 1].
        win_loss_ratio: Average win / average loss.
        prices: Recent price history for volatility estimation.
        base_fraction: Base Kelly fraction (0.5 = Half Kelly).

    Returns:
        Adjusted Kelly fraction [0, 1].
    """
    # Standard Kelly
    wlr = max(win_loss_ratio, 1.0)
    kelly_f = win_rate - (1 - win_rate) / wlr

    # Volatility scaling
    vol = ewma_volatility(prices)
    # Map vol to [0.3, 1.0] scale: high vol → reduce, low vol → increase
    vol_factor = max(0.3, min(1.0, 1.0 - vol * 10))

    return max(0.0, kelly_f * base_fraction * vol_factor)


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for EWMA."""
    # Simulated uptrend
    prices = [10.0 + i * 0.1 for i in range(20)]

    f = ewma_forecast(prices)
    v = ewma_volatility(prices)
    regime = ewma_volatility_regime(prices)
    kelly = adaptive_kelly_fraction(0.6, 1.5, prices)

    print(f"[EWMA] Forecast: ${f:.2f}")
    print(f"[EWMA] Volatility: {v:.4f}")
    print(f"[EWMA] Vol regime: {regime}")
    print(f"[EWMA] Adaptive Kelly: {kelly:.3f}")

    assert 10.0 < f < 13.0, f"Forecast out of range: {f}"
    assert 0.0 <= v < 0.1, f"Volatility out of range: {v}"
    assert 0.0 <= kelly <= 1.0, f"Kelly out of range: {kelly}"
    print("[EWMA] Self-check PASSED")


if __name__ == "__main__":
    _demo()
