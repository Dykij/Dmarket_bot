"""
backtester.py — DEPRECATED monolith.
Python resolves `src.analytics.backtester` to the `backtester/` package directory.
Re-exports kept for backward compatibility — use the package directly.
"""
from src.analytics.backtester import (
    Backtester,
    BacktestResult,
    Position,
    SimpleArbitrageStrategy,
    Trade,
    TradeType,
    TradingStrategy,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)

__all__ = [
    "BacktestResult", "Backtester", "Position",
    "SimpleArbitrageStrategy", "Trade", "TradeType", "TradingStrategy",
    "calculate_max_drawdown", "calculate_sharpe_ratio",
]
