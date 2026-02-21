"""Пакет арбитража для DMarket.

Содержит модули для поиска арбитражных возможностей,
управления торговлей и анализа рынка.

Modules:
    constants: Константы и конфигурации
    cache: Кэширование результатов
    calculations: Расчеты прибыли и комиссий
    core: Основные функции арбитража
    trader: Класс ArbitrageTrader для автоматической торговли
    search: Функции поиска арбитражных возможностей
"""

from __future__ import annotations

# =============================================================================
# Cache functions
# =============================================================================
from .cache import (
    _arbitrage_cache,  # Backward compatibility for tests
    _get_cached_results,  # Backward compatibility for tests
    _save_arbitrage_cache,  # Backward compatibility for tests
    _save_to_cache,  # Backward compatibility for tests
    clear_cache,
    get_arbitrage_cache,
    get_cache_statistics,
    get_cached_results,
    save_arbitrage_cache,
    save_to_cache,
    set_cache_ttl,
)

# =============================================================================
# Calculation functions
# =============================================================================
from .calculations import (
    _calculate_commission,  # Backward compatibility alias
    calculate_commission,
    calculate_net_profit,
    calculate_profit,
    calculate_profit_percent,
    cents_to_usd,
    get_fee_for_liquidity,
    is_profitable_opportunity,
    usd_to_cents,
)

# =============================================================================
# Constants - все константы из constants.py
# =============================================================================
from .constants import (  # Автоторговля; Кэш; Комиссии; Лимиты API; Торговля; Комиссии по играм; Игры; Популярность; Редкости; Типы; Ошибки; Режимы
    AUTO_TRADING_INTERVAL,
    BASE_COMMISSION_PERCENT,
    CACHE_CLEANUP_COUNT,
    CACHE_TTL,
    CENTS_TO_USD,
    DAlgoLY_LIMIT_RESET_SECONDS,
    DEFAULT_DAlgoLY_LIMIT,
    DEFAULT_FEE,
    DEFAULT_LIMIT,
    DEFAULT_MAX_TRADE_VALUE,
    DEFAULT_MIN_BALANCE,
    DEFAULT_MIN_PROFIT_PERCENTAGE,
    ERROR_PAUSE_LONG,
    ERROR_PAUSE_SHORT,
    ERROR_THRESHOLD_LONG,
    ERROR_THRESHOLD_SHORT,
    GAME_COMMISSION_FACTORS,
    GAMES,
    HIGH_FEE,
    HIGH_POPULARITY_THRESHOLD,
    HIGH_RARITY_ITEMS,
    HIGH_VALUE_ITEM_TYPES,
    LOW_FEE,
    LOW_POPULARITY_THRESHOLD,
    LOW_RARITY_ITEMS,
    LOW_VALUE_ITEM_TYPES,
    MAX_CACHE_SIZE,
    MAX_COMMISSION_PERCENT,
    MAX_CONSECUTIVE_ERRORS,
    MAX_RETRIES,
    MAX_RETURN_OPPORTUNITIES,
    MIN_COMMISSION_PERCENT,
    MIN_PROFIT_PERCENT,
    PRICE_RANGES,
    USD_TO_CENTS,
)

# =============================================================================
# Core arbitrage functions
# =============================================================================
from .core import (
    _find_arbitrage_async,
    arbitrage_boost,
    arbitrage_boost_async,
    arbitrage_mid,
    arbitrage_mid_async,
    arbitrage_pro,
    arbitrage_pro_async,
    fetch_market_items,
    find_arbitrage_opportunities,
    find_arbitrage_opportunities_async,
)

# =============================================================================
# Search functions
# =============================================================================
from .search import (
    _group_items_by_name,  # Backward compatibility for tests
    find_arbitrage_items,
    find_arbitrage_opportunities_advanced,
)

# =============================================================================
# Trader class
# =============================================================================
from .trader import ArbitrageTrader

# =============================================================================
# Public API
# =============================================================================
__all__ = [
    "AUTO_TRADING_INTERVAL",
    "BASE_COMMISSION_PERCENT",
    "CACHE_CLEANUP_COUNT",
    "CACHE_TTL",
    "CENTS_TO_USD",
    "DAlgoLY_LIMIT_RESET_SECONDS",
    "DEFAULT_DAlgoLY_LIMIT",
    "DEFAULT_FEE",
    "DEFAULT_LIMIT",
    "DEFAULT_MAX_TRADE_VALUE",
    "DEFAULT_MIN_BALANCE",
    "DEFAULT_MIN_PROFIT_PERCENTAGE",
    "ERROR_PAUSE_LONG",
    "ERROR_PAUSE_SHORT",
    "ERROR_THRESHOLD_LONG",
    "ERROR_THRESHOLD_SHORT",
    "GAMES",
    "GAME_COMMISSION_FACTORS",
    "HIGH_FEE",
    "HIGH_POPULARITY_THRESHOLD",
    "HIGH_RARITY_ITEMS",
    "HIGH_VALUE_ITEM_TYPES",
    "LOW_FEE",
    "LOW_POPULARITY_THRESHOLD",
    "LOW_RARITY_ITEMS",
    "LOW_VALUE_ITEM_TYPES",
    "MAX_CACHE_SIZE",
    "MAX_COMMISSION_PERCENT",
    "MAX_CONSECUTIVE_ERRORS",
    "MAX_RETRIES",
    "MAX_RETURN_OPPORTUNITIES",
    "MIN_COMMISSION_PERCENT",
    "MIN_PROFIT_PERCENT",
    "PRICE_RANGES",
    "USD_TO_CENTS",
    "ArbitrageTrader",
    "_arbitrage_cache",
    "_calculate_commission",
    "_find_arbitrage_async",
    "_get_cached_results",
    "_group_items_by_name",
    "_save_arbitrage_cache",
    "_save_to_cache",
    "arbitrage_boost",
    "arbitrage_boost_async",
    "arbitrage_mid",
    "arbitrage_mid_async",
    "arbitrage_pro",
    "arbitrage_pro_async",
    "calculate_commission",
    "calculate_net_profit",
    "calculate_profit",
    "calculate_profit_percent",
    "cents_to_usd",
    "clear_cache",
    "fetch_market_items",
    "find_arbitrage_items",
    "find_arbitrage_opportunities",
    "find_arbitrage_opportunities_advanced",
    "find_arbitrage_opportunities_async",
    "get_arbitrage_cache",
    "get_cache_statistics",
    "get_cached_results",
    "get_fee_for_liquidity",
    "is_profitable_opportunity",
    "save_arbitrage_cache",
    "save_to_cache",
    "set_cache_ttl",
    "usd_to_cents",
]
