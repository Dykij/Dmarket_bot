"""Game filters module - compatibility wrapper.

This module provides backward compatibility for tests and code that import
from src.dmarket.game_filters. It re-exports classes from the filters subpackage.
"""

from src.dmarket.filters.game_filters import (
    BaseGameFilter,
    CS2Filter,
    Dota2Filter,
    FilterFactory,
    RustFilter,
    TF2Filter,
    apply_filters_to_items,
)

__all__ = [
    "BaseGameFilter",
    "CS2Filter",
    "Dota2Filter",
    "FilterFactory",
    "RustFilter",
    "TF2Filter",
    "apply_filters_to_items",
]
