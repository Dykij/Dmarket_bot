"""Analytics module for DMarket trading.

Provides:
- Historical data collection and storage
- Backtesting engine for trading strategies
- Performance analysis and reporting
"""

from .backtester import (
    Backtester,
    BacktestResult,
    SimpleArbitrageStrategy,
    TradingStrategy,
)
from .historical_data import HistoricalDataCollector, PricePoint

__all__ = [
    "BacktestResult",
    "Backtester",
    "HistoricalDataCollector",
    "PricePoint",
    "SimpleArbitrageStrategy",
    "TradingStrategy",
]
