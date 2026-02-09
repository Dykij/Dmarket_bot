"""Arbitrage level configurations.

This module contains all level definitions for arbitrage scanning:
- boost: Quick, low-risk arbitrage (1-5% profit)
- standard: Balanced arbitrage (5-10% profit)
- medium: Medium-risk arbitrage (5-20% profit)
- advanced: Higher-risk arbitrage (10-30% profit)
- pro: High-risk, high-reward arbitrage (20-100% profit)

Also contains game ID mappings for DMarket API.
"""

from __future__ import annotations

from typing import Any

# Маппинг кодов игр к ID DMarket API
GAME_IDS: dict[str, str] = {
    "csgo": "a8db",
    "dota2": "9a92",
    "tf2": "tf2",
    "rust": "rust",
}

# Определение уровней арбитража
ARBITRAGE_LEVELS: dict[str, dict[str, Any]] = {
    "boost": {
        "name": "🚀 Разгон баланса",
        "min_profit_percent": 1.0,
        "max_profit_percent": 5.0,
        "price_range": (0.5, 3.0),
        "max_price": 20.0,
        "description": "Low-risk, quick arbitrage (1-5% profit)",
    },
    "standard": {
        "name": "⚡ Стандарт",
        "min_profit_percent": 5.0,
        "max_profit_percent": 10.0,
        "price_range": (3.0, 10.0),
        "min_price": 20.0,
        "max_price": 50.0,
        "description": "Balanced arbitrage (5-10% profit)",
    },
    "medium": {
        "name": "💰 Средний",
        "min_profit_percent": 5.0,
        "max_profit_percent": 20.0,
        "price_range": (10.0, 30.0),
        "min_price": 20.0,
        "max_price": 100.0,
        "description": "Medium-risk arbitrage (5-20% profit)",
    },
    "advanced": {
        "name": "🎯 Продвинутый",
        "min_profit_percent": 10.0,
        "max_profit_percent": 30.0,
        "price_range": (30.0, 100.0),
        "min_price": 50.0,
        "max_price": 200.0,
        "description": "Higher-risk arbitrage (10-30% profit)",
    },
    "pro": {
        "name": "💎 Профи",
        "min_profit_percent": 20.0,
        "max_profit_percent": 100.0,
        "price_range": (100.0, 1000.0),
        "min_price": 100.0,
        "description": "High-risk, high-reward arbitrage (20-100% profit)",
    },
}


def get_level_config(level: str) -> dict[str, Any]:
    """Get configuration for a specific arbitrage level.

    Args:
        level: Level name (boost, standard, medium, advanced, pro)

    Returns:
        Dictionary with level configuration including:
        - name: Display name with emoji
        - min_profit_percent: Minimum profit percentage
        - max_profit_percent: Maximum profit percentage
        - price_range: Tuple of (min_price, max_price)
        - description: Level description

    Raises:
        KeyError: If level name is not found
    """
    if level not in ARBITRAGE_LEVELS:
        available = ", ".join(ARBITRAGE_LEVELS.keys())
        raise KeyError(f"Unknown level '{level}'. Available levels: {available}")
    return ARBITRAGE_LEVELS[level].copy()


def get_price_range_for_level(level: str) -> tuple[float, float]:
    """Get price range for a specific arbitrage level.

    Args:
        level: Level name (boost, standard, medium, advanced, pro)

    Returns:
        Tuple of (min_price, max_price) in USD

    Raises:
        KeyError: If level name is not found
    """
    config = get_level_config(level)
    return config.get("price_range", (0.0, float("inf")))


def get_all_levels() -> list[str]:
    """Get list of all available arbitrage levels.

    Returns:
        List of level names in order of risk (low to high)
    """
    return list(ARBITRAGE_LEVELS.keys())


def get_level_description(level: str) -> str:
    """Get human-readable description for a level.

    Args:
        level: Level name

    Returns:
        Description string
    """
    config = get_level_config(level)
    return config.get("description", "No description available")


def get_profit_range_for_level(level: str) -> tuple[float, float]:
    """Get profit percentage range for a specific level.

    Args:
        level: Level name

    Returns:
        Tuple of (min_profit_percent, max_profit_percent)
    """
    config = get_level_config(level)
    return (
        config.get("min_profit_percent", 0.0),
        config.get("max_profit_percent", 100.0),
    )
