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


# ══════════════════════════════════════════════════════════════════════
# DEMA / TEMA — Reduced-Lag Exponential Moving Averages
# ══════════════════════════════════════════════════════════════════════


def dema(prices: list[float], period: int = 14) -> float | None:
    """Double Exponential Moving Average (DEMA).

    Reference: Trotman (1992), Tilmann (1993)

    Formula: DEMA = 2 × EMA(N) - EMA(EMA(N))

    Reduces lag by ~50% compared to standard EMA.
    Reacts faster to price changes while maintaining smoothness.

    Args:
        prices: Price series (oldest first).
        period: EMA period (default 14).

    Returns:
        DEMA value or None if insufficient data.
    """
    if len(prices) < period:
        return None

    alpha = 2.0 / (period + 1)
    ema1 = ewma(prices, alpha)
    # For EMA of EMA, we need a series of EMA values
    # Compute EMA1 for all prices, then EMA2 on those
    ema1_values: list[float] = []
    result = prices[0]
    for p in prices:
        result = alpha * p + (1 - alpha) * result
        ema1_values.append(result)

    ema2 = ewma(ema1_values, alpha)
    return round(2.0 * ema1 - ema2, 4)


def tema(prices: list[float], period: int = 14) -> float | None:
    """Triple Exponential Moving Average (TEMA).

    Reference: Trotman (1992), Tilmann (1993)

    Formula: TEMA = 3 × EMA(N) - 3 × EMA(EMA(N)) + EMA(EMA(EMA(N)))

    Reduces lag by ~70% compared to standard EMA.
    Fastest response while maintaining smoothness.

    Args:
        prices: Price series (oldest first).
        period: EMA period (default 14).

    Returns:
        TEMA value or None if insufficient data.
    """
    if len(prices) < period:
        return None

    alpha = 2.0 / (period + 1)

    # EMA1
    ema1_values: list[float] = []
    result = prices[0]
    for p in prices:
        result = alpha * p + (1 - alpha) * result
        ema1_values.append(result)

    # EMA2 = EMA(EMA1)
    ema2_values: list[float] = []
    result = ema1_values[0]
    for v in ema1_values:
        result = alpha * v + (1 - alpha) * result
        ema2_values.append(result)

    # EMA3 = EMA(EMA2)
    ema3 = ewma(ema2_values, alpha)

    ema1_final = ema1_values[-1]
    ema2_final = ema2_values[-1]

    return round(3.0 * ema1_final - 3.0 * ema2_final + ema3, 4)


def ema_crossover(
    prices: list[float],
    fast_period: int = 9,
    slow_period: int = 21,
) -> str:
    """Detect EMA crossover signal.

    Uses DEMA for faster response.

    Args:
        prices: Price series (oldest first).
        fast_period: Fast DEMA period (default 9).
        slow_period: Slow DEMA period (default 21).

    Returns:
        "bullish"  — fast crossed above slow (buy signal)
        "bearish"  — fast crossed below slow (sell signal)
        "neutral"  — no crossover
    """
    if len(prices) < slow_period + 2:
        return "neutral"

    # Current DEMA values
    fast_now = dema(prices, fast_period)
    slow_now = dema(prices, slow_period)

    # Previous DEMA values (without last price)
    fast_prev = dema(prices[:-1], fast_period)
    slow_prev = dema(prices[:-1], slow_period)

    if any(v is None for v in [fast_now, slow_now, fast_prev, slow_prev]):
        return "neutral"

    # Type guard: all values are float after None check
    assert fast_now is not None and slow_now is not None
    assert fast_prev is not None and slow_prev is not None

    # Bullish crossover: fast was below slow, now above
    if fast_prev <= slow_prev and fast_now > slow_now:
        return "bullish"

    # Bearish crossover: fast was above slow, now below
    if fast_prev >= slow_prev and fast_now < slow_now:
        return "bearish"

    return "neutral"


def macd(
    prices: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float] | None:
    """MACD: Moving Average Convergence/Divergence.

    Reference: Appel (1979)

    Formula:
        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal_period)
        Histogram = MACD Line - Signal Line

    Args:
        prices: Price series (oldest first).
        fast_period: Fast EMA period (default 12).
        slow_period: Slow EMA period (default 26).
        signal_period: Signal EMA period (default 9).

    Returns:
        (macd_line, signal_line, histogram) or None if insufficient data.
    """
    if len(prices) < slow_period:
        return None

    fast_alpha = 2.0 / (fast_period + 1)
    slow_alpha = 2.0 / (slow_period + 1)
    signal_alpha = 2.0 / (signal_period + 1)

    # Compute fast and slow EMA series
    fast_ema = prices[0]
    slow_ema = prices[0]
    macd_series: list[float] = []

    for p in prices:
        fast_ema = fast_alpha * p + (1 - fast_alpha) * fast_ema
        slow_ema = slow_alpha * p + (1 - slow_alpha) * slow_ema
        macd_series.append(fast_ema - slow_ema)

    # Signal line = EMA of MACD series
    if len(macd_series) < signal_period:
        return None

    signal = macd_series[0]
    for v in macd_series:
        signal = signal_alpha * v + (1 - signal_alpha) * signal

    macd_line = macd_series[-1]
    histogram = macd_line - signal

    return round(macd_line, 4), round(signal, 4), round(histogram, 4)


def macd_signal(prices: list[float]) -> str:
    """MACD-based trading signal.

    Returns:
        "bullish"   — histogram > 0 and growing (momentum up)
        "bearish"   — histogram < 0 and shrinking (momentum down)
        "neutral"   — no clear signal
    """
    result = macd(prices)
    if result is None:
        return "neutral"

    macd_line, signal_line, histogram = result

    # Need previous histogram for direction
    prev_result = macd(prices[:-1]) if len(prices) > 27 else None
    if prev_result is None:
        if histogram > 0:
            return "bullish"
        elif histogram < 0:
            return "bearish"
        return "neutral"

    _, _, prev_histogram = prev_result

    # Bullish: histogram positive and growing
    if histogram > 0 and histogram > prev_histogram:
        return "bullish"

    # Bearish: histogram negative and shrinking
    if histogram < 0 and histogram < prev_histogram:
        return "bearish"

    return "neutral"


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
