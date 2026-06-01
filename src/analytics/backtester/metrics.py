"""
metrics.py — Pure functions for backtest performance metrics.

These are stateless, module-level functions, so they can be unit-tested
in isolation and reused outside the Backtester.
"""

from __future__ import annotations

from decimal import Decimal


def calculate_max_drawdown(balance_history: list[Decimal]) -> Decimal:
    """Calculate maximum drawdown.

    Args:
        balance_history: List of balance values over time

    Returns:
        Maximum drawdown as percentage
    """
    if len(balance_history) < 2:
        return Decimal(0)

    peak = balance_history[0]
    max_drawdown = Decimal(0)

    for balance in balance_history[1:]:
        if balance > peak:
            peak = balance
        else:
            drawdown = (peak - balance) / peak if peak > 0 else Decimal(0)
            max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown * 100


def calculate_sharpe_ratio(
    balance_history: list[Decimal],
    risk_free_rate: float = 0.02,  # 2% annual risk-free rate
) -> float:
    """Calculate Sharpe ratio.

    Args:
        balance_history: List of balance values over time
        risk_free_rate: Annual risk-free rate

    Returns:
        Sharpe ratio
    """
    if len(balance_history) < 2:
        return 0.0

    # Calculate daily returns
    returns: list[float] = []
    for i in range(1, len(balance_history)):
        if balance_history[i - 1] > 0:
            daily_return = float(
                (balance_history[i] - balance_history[i - 1])
                / balance_history[i - 1]
            )
            returns.append(daily_return)

    if not returns:
        return 0.0

    # Calculate mean and std dev
    mean_return = sum(returns) / len(returns)
    if len(returns) < 2:
        return 0.0

    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = variance**0.5

    if std_dev == 0:
        return 0.0

    # Annualize (assuming 365 trading days)
    daily_rf = (1 + risk_free_rate) ** (1 / 365) - 1
    excess_return = mean_return - daily_rf

    # Sharpe ratio (annualized)
    sharpe = (excess_return * (365**0.5)) / (std_dev * (365**0.5))

    return float(round(sharpe, 2))
