"""Модели данных для работы с DMarket.

Новые модели (январь 2026):
- target_enhancements.py - расширенные модели для улучшенной системы таргетов
"""

__version__ = "0.2.0"  # Обновлено для новых моделей таргетов

# Импорты для удобного доступа
from .target_enhancements import (
    BatchTargetItem,
    ExistingOrderInfo,
    PriceRangeAction,
    PriceRangeConfig,
    RarityFilter,
    RarityLevel,
    RelistAction,
    RelistHistory,
    RelistLimitConfig,
    RelistStatistics,
    StickerFilter,
    TargetDefaults,
    TargetErrorCode,
    TargetOperationResult,
    TargetOperationStatus,
    TargetOverbidConfig,
)

__all__ = [
    "BatchTargetItem",
    "ExistingOrderInfo",
    "PriceRangeAction",
    "PriceRangeConfig",
    "RarityFilter",
    "RarityLevel",
    "RelistAction",
    "RelistHistory",
    "RelistLimitConfig",
    "RelistStatistics",
    "StickerFilter",
    "TargetDefaults",
    "TargetErrorCode",
    "TargetOperationResult",
    "TargetOperationStatus",
    # Расширенные модели таргетов (NEW - январь 2026)
    "TargetOverbidConfig",
]
