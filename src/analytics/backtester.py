"""Backtesting engine for trading strategies.

Provides a framework for testing trading strategies on historical data.

This module is a thin facade. The actual implementation lives in the
`backtester` sub-package:

    models.py     — TradeType, Trade, Position, BacktestResult
    strategies.py — TradingStrategy ABC + SimpleArbitrageStrategy
    metrics.py    — Pure functions: max_drawdown, sharpe_ratio
    engine.py     — Backtester (the orchestrator)

Usage:
    ```python
    from src.analytics.backtester import Backtester, SimpleArbitrageStrategy

    strategy = SimpleArbitrageStrategy()
    backtester = Backtester(fee_rate=0.07)
    result = await backtester.run(strategy, histories, start, end, Decimal("100"))
    print(f"Profit: {result.total_profit}, Win rate: {result.win_rate}%")
    ```
"""

from __future__ import annotations

from .backtester import (
    BacktestResult,
    Backtester,
    Position,
    SimpleArbitrageStrategy,
    Trade,
    TradeType,
    TradingStrategy,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)

__all__ = [
    "BacktestResult",
    "Backtester",
    "Position",
    "SimpleArbitrageStrategy",
    "Trade",
    "TradeType",
    "TradingStrategy",
    "calculate_max_drawdown",
    "calculate_sharpe_ratio",
]
