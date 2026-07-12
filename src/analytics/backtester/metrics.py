"""
metrics.py — Pure functions for backtest performance metrics.

These are stateless, module-level functions, so they can be unit-tested
in isolation and reused outside the Backtester.

v15.2: Uses numpy for vectorized math. Fixed Sharpe ratio annualization bug.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np


def calculate_max_drawdown(balance_history: list[Decimal]) -> Decimal:
    """Calculate maximum drawdown.

    Args:
        balance_history: List of balance values over time

    Returns:
        Maximum drawdown as percentage
    
    v15.2: Uses numpy for vectorized peak tracking.
    """
    if len(balance_history) < 2:
        return Decimal(0)

    arr = np.array([float(b) for b in balance_history], dtype=np.float64)
    peak = np.maximum.accumulate(arr)
    drawdown = np.where(peak > 0, (peak - arr) / peak, 0.0)
    max_dd = float(np.max(drawdown))

    return Decimal(str(round(max_dd * 100, 2)))


def calculate_sharpe_ratio(
    balance_history: list[Decimal],
    risk_free_rate: float = 0.02,  # 2% annual risk-free rate
) -> float:
    """Calculate Sharpe ratio.

    Args:
        balance_history: List of balance values over time
        risk_free_rate: Annual risk-free rate

    Returns:
        Sharpe ratio (annualized)
    
    v15.2: Uses numpy. Fixed annualization bug (sqrt(365) was canceling out).
    """
    if len(balance_history) < 2:
        return 0.0

    arr = np.array([float(b) for b in balance_history], dtype=np.float64)
    # Daily returns
    returns = np.diff(arr) / arr[:-1]
    returns = returns[np.isfinite(returns)]

    if len(returns) < 2:
        return 0.0

    mean_return = np.mean(returns)
    std_dev = np.std(returns, ddof=1)

    if std_dev == 0:
        return 0.0

    # Annualize (assuming 365 trading days)
    daily_rf = (1 + risk_free_rate) ** (1 / 365) - 1
    excess_return = mean_return - daily_rf

    # v15.2 FIX: Sharpe = (mean - rf) / std * sqrt(365)
    # Previous code had (excess * sqrt(365)) / (std * sqrt(365)) which simplifies to excess/std
    sharpe = excess_return / std_dev * (365 ** 0.5)

    return float(round(sharpe, 2))
