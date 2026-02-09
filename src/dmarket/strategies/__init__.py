"""Unified Strategy System - modular strategy package.

This package provides a unified strategy system for finding market opportunities.
All strategies implement the IFindingStrategy interface from base.py.

Example usage:
    from src.dmarket.strategies import (
        StrategyType,
        StrategyConfig,
    )
    from src.dmarket.unified_strategy_system import (
        UnifiedStrategyManager,
        CrossPlatformArbitrageStrategy,
    )
"""

# Base types (enums, dataclasses, interface)
from src.dmarket.strategies.base import (
    ActionType,
    IFindingStrategy,
    OpportunityScore,
    OpportunityStatus,
    RiskLevel,
    StrategyConfig,
    StrategyType,
    UnifiedOpportunity,
)

# Note: Strategy implementations are in unified_strategy_system.py
# Import them directly from there to avoid circular imports:
#   from src.dmarket.unified_strategy_system import CrossPlatformArbitrageStrategy

__all__ = [
    # Enums
    "ActionType",
    "OpportunityStatus",
    "RiskLevel",
    "StrategyType",
    # Dataclasses
    "OpportunityScore",
    "StrategyConfig",
    "UnifiedOpportunity",
    # Interface
    "IFindingStrategy",
]
