"""Scanner package for arbitrage scanning functionality.

This package provides modular components for:
- Level configurations (boost, standard, medium, advanced, pro)
- Cache management for API responses
- Item filtering (blacklist/whitelist)
- Arbitrage analysis and profit calculation
- Multi-game scanning
- Aggregated price pre-scanning for fast opportunity detection
- Attribute-based filtering (exterior, float, rarity, etc.)

Usage:
    from src.dmarket.scanner import ArbitrageScanner, ARBITRAGE_LEVELS
    from src.dmarket.scanner import AggregatedScanner, AttributeFilters, PresetFilters

    scanner = ArbitrageScanner(public_key="...", secret_key="...")
    results = awAlgot scanner.scan_level("standard", "csgo")

    # Fast pre-scan
    agg_scanner = AggregatedScanner(api_client)
    opportunities = awAlgot agg_scanner.pre_scan_opportunities(
        titles=["AK-47 | Redline", "AWP | Asiimov"],
        game="csgo",
        min_margin=0.15
    )

    # Attribute filtering
    filters = AttributeFilters.create_extra_filters(
        exterior=["factory new"],
        float_range=(0.0, 0.07),
        rarity=["covert"]
    )
"""

from src.dmarket.scanner.aggregated_scanner import AggregatedScanner
from src.dmarket.scanner.attribute_filters import AttributeFilters, PresetFilters
from src.dmarket.scanner.cache import ScannerCache
from src.dmarket.scanner.filters import ScannerFilters
from src.dmarket.scanner.levels import (
    ARBITRAGE_LEVELS,
    GAME_IDS,
    get_level_config,
    get_price_range_for_level,
)
from src.dmarket.scanner.tree_filters import (
    get_filter_description,
    get_filter_effectiveness,
    get_tree_filters_for_game,
)

# Note: ArbitrageScanner is imported from the original module
# for backwards compatibility. In future refactoring phases,
# it will be moved to scanner.py

__all__ = [
    "ARBITRAGE_LEVELS",
    "GAME_IDS",
    "AggregatedScanner",
    "AttributeFilters",
    "PresetFilters",
    "ScannerCache",
    "ScannerFilters",
    "get_filter_description",
    "get_filter_effectiveness",
    "get_level_config",
    "get_price_range_for_level",
    "get_tree_filters_for_game",
]
