"""Trading module for automated trading.

This module provides:
- Trading automation (stop-loss, take-profit, DCA)
- Auto-rebalancing
- Scheduled tasks
- Market regime detection
- Backtesting
"""

from src.trading.backtester import (
    BacktestConfig,
    Backtester,
    BacktestResults,
    BreakoutStrategy,
    MeanReversionStrategy,
    SimpleStrategy,
    Strategy,
    Trade,
    TradeAction,
    create_backtester,
    create_simple_strategy,
)
from src.trading.regime_detector import (
    AdaptiveTrader,
    MarketRegime,
    RegimeAnalysis,
    RegimeDetector,
    create_adaptive_trader,
    create_regime_detector,
)
from src.trading.trading_automation import (
    AutoOrder,
    DCAConfig,
    ExecutionResult,
    OrderStatus,
    OrderType,
    RebalanceConfig,
    ScheduledTask,
    TradingAutomation,
    create_trading_automation,
)

__all__ = [
    "AdaptiveTrader",
    "AutoOrder",
    "BacktestConfig",
    "BacktestResults",
    "Backtester",
    "BreakoutStrategy",
    "DCAConfig",
    "ExecutionResult",
    "MarketRegime",
    "MeanReversionStrategy",
    "OrderStatus",
    "OrderType",
    "RebalanceConfig",
    "RegimeAnalysis",
    "RegimeDetector",
    "ScheduledTask",
    "SimpleStrategy",
    "Strategy",
    "Trade",
    "TradeAction",
    "TradingAutomation",
    "create_adaptive_trader",
    "create_backtester",
    "create_regime_detector",
    "create_simple_strategy",
    "create_trading_automation",
]
