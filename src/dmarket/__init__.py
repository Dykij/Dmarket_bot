"""Scanner package for arbitrage scanning functionality.

This package provides modular components for:
- Level configurations (boost, standard, medium, advanced, pro)
- Cache management for API responses
- Item filtering (blacklist/whitelist)
- Arbitrage analysis and profit calculation
- Multi-game scanning

Usage:
    from src.dmarket.scanner import ArbitrageScanner, ARBITRAGE_LEVELS

    scanner = ArbitrageScanner(public_key="...", secret_key="...")
    results = await scanner.scan_level("standard", "csgo")
"""

from src.dmarket.scanner.cache import ScannerCache
from src.dmarket.scanner.filters import ScannerFilters
from src.dmarket.scanner.levels import (
    ARBITRAGE_LEVELS,
    GAME_IDS,
    get_level_config,
    get_price_range_for_level,
)

# Note: ArbitrageScanner is imported from the original module
# for backwards compatibility. In future refactoring phases,
# it will be moved to scanner.py

__all__ = [
    "ARBITRAGE_LEVELS",
    "GAME_IDS",
    "ScannerCache",
    "ScannerFilters",
    "get_level_config",
    "get_price_range_for_level",
]
