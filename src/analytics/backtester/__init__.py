"""
backtester — Backtesting engine for trading strategies.

Composed from focused modules:
    models.py     — TradeType, Trade, Position, BacktestResult
    strategies.py — TradingStrategy ABC + SimpleArbitrageStrategy
    metrics.py    — Pure functions: max_drawdown, sharpe_ratio
    engine.py     — Backtester (the orchestrator)
"""

from __future__ import annotations

from .engine import Backtester
from .metrics import calculate_max_drawdown, calculate_sharpe_ratio
from .models import (
    BacktestResult,
    Position,
    Trade,
    TradeType,
)
from .strategies import SimpleArbitrageStrategy, TradingStrategy

__all__ = [
    # Enums / dataclasses
    "TradeType",
    "Trade",
    "Position",
    "BacktestResult",
    # Strategies
    "TradingStrategy",
    "SimpleArbitrageStrategy",
    # Engine
    "Backtester",
    # Pure metric functions
    "calculate_max_drawdown",
    "calculate_sharpe_ratio",
]
