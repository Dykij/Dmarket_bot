"""Модуль для управления таргетами (buy orders) на DMarket (Facade).

DEPRECATED: Этот модуль служит фасадом для обратной совместимости.
Все реализации перемещены в пакет targets/.

Для нового кода используйте:
    from src.dmarket.targets import TargetManager, ...

Рефакторинг выполнен 14.12.2025 в рамках задачи R-8.
"""

import warnings

# Re-export everything from targets package
from src.dmarket.targets import (
    GAME_IDS,
    TargetManager,
    analyze_target_competition,
    assess_competition,
    extract_attributes_from_title,
    filter_low_competition_items,
    validate_attributes,
)

# Emit deprecation warning
warnings.warn(
    "targets.py is deprecated. Import from src.dmarket.targets instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "GAME_IDS",
    "TargetManager",
    "analyze_target_competition",
    "assess_competition",
    "extract_attributes_from_title",
    "filter_low_competition_items",
    "validate_attributes",
]
