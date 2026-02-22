"""Game scanner module for arbitrage scanning.

This module provides a refactored version of scan_game() with:
- Early returns pattern
- Helper methods (<50 lines each)
- Reduced nesting (max 2 levels)
- Better separation of concerns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.dmarket.arbitrage import arbitrage_boost, arbitrage_mid, arbitrage_pro
from src.dmarket.arbitrage.trader import ArbitrageTrader

try:
    from src.utils.rate_limiter import RateLimiter

    rate_limiter = RateLimiter()
except ImportError:
    # Fallback for testing
    rate_limiter = None

try:
    from src.utils.sentry_breadcrumbs import add_trading_breadcrumb
except ImportError:
    # Fallback for testing
    def add_trading_breadcrumb(**kwargs):
        pass


logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """Configuration for game scanning."""

    game: str
    mode: str = "medium"
    max_items: int = 20
    price_from: float | None = None
    price_to: float | None = None

    def get_cache_key(self) -> tuple:
        """Generate cache key."""
        return (
            self.game,
            self.mode,
            self.price_from or 0,
            self.price_to or float("inf"),
        )


@dataclass
class ProfitRange:
    """Profit range configuration."""

    min_profit: float
    max_profit: float


class GameScanner:
    """Scanner for finding arbitrage opportunities in a game."""

    def __init__(
        self,
        cache_manager: Any,
        liquidity_analyzer: Any | None = None,
        enable_liquidity_filter: bool = True,
    ):
        """Initialize scanner.

        Args:
            cache_manager: Cache manager instance
            liquidity_analyzer: Optional liquidity analyzer
            enable_liquidity_filter: Whether to enable liquidity filtering
        """
        self.cache_manager = cache_manager
        self.liquidity_analyzer = liquidity_analyzer
        self.enable_liquidity_filter = enable_liquidity_filter
        self.total_scans = 0
        self.total_items_found = 0

    async def scan(self, config: ScanConfig) -> list[dict[str, Any]]:
        """Scan game for arbitrage opportunities.

        Args:
            config: Scan configuration

        Returns:
            List of arbitrage opportunities
        """
        self._log_scan_start(config)

        # Check cache first
        cached_results = self._check_cache(config)
        if cached_results is not None:
            return cached_results[: config.max_items]

        # Perform scan
        try:
            return await self._perform_scan(config)
        except Exception as e:
            self._log_scan_error(config, e)
            return []

    def _log_scan_start(self, config: ScanConfig) -> None:
        """Log scan start breadcrumb."""
        add_trading_breadcrumb(
            action="scan_game_started",
            game=config.game,
            level=config.mode,
            max_items=config.max_items,
            price_from=config.price_from,
            price_to=config.price_to,
        )

    def _check_cache(self, config: ScanConfig) -> list[dict[str, Any]] | None:
        """Check cache for results."""
        cache_key = config.get_cache_key()
        cached_results = self.cache_manager._get_cached_results(cache_key)

        if not cached_results:
            return None

        logger.debug(f"Using cached data for {config.game} in mode {config.mode}")
        add_trading_breadcrumb(
            action="scan_game_cache_hit",
            game=config.game,
            level=config.mode,
            cached_items=len(cached_results),
        )
        return cached_results

    async def _perform_scan(self, config: ScanConfig) -> list[dict[str, Any]]:
        """Perform actual scanning."""
        self.total_scans += 1

        # WAlgot for rate limiter if avAlgolable
        if rate_limiter is not None:
            await rate_limiter.wait_if_needed("market")

        # Find items using both methods
        items = await self._find_items(config)

        # Sort by profitability
        items.sort(key=lambda x: x.get("profit", 0), reverse=True)

        # Apply liquidity filter if enabled
        results = await self._apply_liquidity_filter(items, config)

        # Limit results
        results = results[: config.max_items]

        # Log and cache results
        self._log_scan_complete(config, results)
        self._save_results(config, results)

        return results

    async def _find_items(self, config: ScanConfig) -> list[dict[str, Any]]:
        """Find items using built-in and trader methods."""
        items: list[dict[str, Any]] = []

        # Method 1: Built-in functions (if no price range specified)
        if config.price_from is None and config.price_to is None:
            builtin_items = self._find_items_builtin(config)
            items.extend(builtin_items)

        # Method 2: ArbitrageTrader (more detailed)
        trader_items = await self._find_items_with_trader(config)
        items.extend(trader_items)

        return items

    def _find_items_builtin(self, config: ScanConfig) -> list[dict[str, Any]]:
        """Find items using built-in arbitrage functions."""
        try:
            if config.mode == "low":
                return arbitrage_boost(config.game)
            if config.mode == "high":
                return arbitrage_pro(config.game)
            # Default to medium
            return arbitrage_mid(config.game)
        except Exception as e:
            logger.warning(f"Error using built-in arbitrage functions: {e}")
            return []

    async def _find_items_with_trader(self, config: ScanConfig) -> list[dict[str, Any]]:
        """Find items using ArbitrageTrader."""
        try:
            profit_range = self._get_profit_range(config.mode)
            price_range = self._get_price_range(config)

            trader = ArbitrageTrader()
            items = await trader.find_profitable_items(
                game=config.game,
                min_profit_percentage=profit_range.min_profit,
                max_items=100,
                min_price=price_range[0],
                max_price=price_range[1],
            )

            return self._standardize_items(
                items,
                config.game,
                profit_range.min_profit,
                profit_range.max_profit,
            )
        except Exception as e:
            logger.warning(f"Error using ArbitrageTrader: {e}")
            return []

    def _get_profit_range(self, mode: str) -> ProfitRange:
        """Get profit range for mode."""
        if mode == "low":
            return ProfitRange(min_profit=1.0, max_profit=5.0)
        if mode == "medium":
            return ProfitRange(min_profit=5.0, max_profit=20.0)
        if mode == "high":
            return ProfitRange(min_profit=20.0, max_profit=100.0)
        # Default to medium
        return ProfitRange(min_profit=5.0, max_profit=20.0)

    def _get_price_range(self, config: ScanConfig) -> tuple[float, float]:
        """Get price range for scan.

        Returns:
            Tuple of (min_price, max_price)
        """
        # Use explicit price range if provided
        if config.price_from is not None or config.price_to is not None:
            return (config.price_from or 1.0, config.price_to or 100.0)

        # Determine range based on mode
        if config.mode == "low":
            return (1.0, 20.0)  # Up to $20
        if config.mode == "medium":
            return (20.0, 100.0)  # $20-$100
        if config.mode == "high":
            return (100.0, 1000.0)  # $100+
        # Default to medium
        return (20.0, 100.0)

    def _standardize_items(
        self,
        items: list[Any],
        game: str,
        min_profit: float,
        max_profit: float,
    ) -> list[dict[str, Any]]:
        """Standardize item format.

        Args:
            items: Raw items from trader
            game: Game code
            min_profit: Minimum profit
            max_profit: Maximum profit

        Returns:
            Standardized items
        """
        standardized = []

        for item in items:
            # Skip items outside profit range
            profit = item.get("profit", 0)
            if profit < min_profit or profit > max_profit:
                continue

            # Ensure required fields
            standardized_item = {
                "game": game,
                "title": item.get("title", "Unknown"),
                "price": item.get("price", 0),
                "profit": profit,
                "profit_percentage": item.get("profit_percentage", 0),
                **item,  # Keep all other fields
            }
            standardized.append(standardized_item)

        return standardized

    async def _apply_liquidity_filter(
        self, items: list[dict[str, Any]], config: ScanConfig
    ) -> list[dict[str, Any]]:
        """Apply liquidity filter to items."""
        if not self.enable_liquidity_filter or not self.liquidity_analyzer:
            return items

        # Take more candidates for filtering
        candidates = items[: config.max_items * 2]

        # Filter through liquidity analyzer
        return await self.liquidity_analyzer.filter_liquid_items(
            candidates, game=config.game
        )

    def _log_scan_complete(
        self, config: ScanConfig, results: list[dict[str, Any]]
    ) -> None:
        """Log scan completion breadcrumb."""
        add_trading_breadcrumb(
            action="scan_game_completed",
            game=config.game,
            level=config.mode,
            items_found=len(results),
            liquidity_filter=self.enable_liquidity_filter,
        )

    def _log_scan_error(self, config: ScanConfig, error: Exception) -> None:
        """Log scan error."""
        logger.error(f"Error scanning game {config.game}: {error}")
        add_trading_breadcrumb(
            action="scan_game_error",
            game=config.game,
            level=config.mode,
            error=str(error),
        )

    def _save_results(self, config: ScanConfig, results: list[dict[str, Any]]) -> None:
        """Save results to cache and update stats."""
        cache_key = config.get_cache_key()
        self.cache_manager._save_to_cache(cache_key, results)
        self.total_items_found += len(results)


# Backward-compatible wrapper function
async def scan_game(
    scanner_instance: Any,
    game: str,
    mode: str = "medium",
    max_items: int = 20,
    price_from: float | None = None,
    price_to: float | None = None,
) -> list[dict[str, Any]]:
    """Scan game for arbitrage opportunities.

    This is a backward-compatible wrapper around GameScanner class.

    Args:
        scanner_instance: ArbitrageScanner instance (for cache and liquidity)
        game: Game code
        mode: Scan mode (low/medium/high)
        max_items: Maximum items to return
        price_from: Minimum price
        price_to: Maximum price

    Returns:
        List of arbitrage opportunities
    """
    config = ScanConfig(
        game=game,
        mode=mode,
        max_items=max_items,
        price_from=price_from,
        price_to=price_to,
    )

    scanner = GameScanner(
        cache_manager=scanner_instance,
        liquidity_analyzer=scanner_instance.liquidity_analyzer,
        enable_liquidity_filter=scanner_instance.enable_liquidity_filter,
    )

    return await scanner.scan(config)
