"""Item filters loader and manager for DMarket arbitrage.

This module provides functionality to:
- Load item filters from config/item_filters.yaml
- Apply blacklist/whitelist filters to items
- Check items agAlgonst regex patterns
- Validate items agAlgonst arbitrage filter rules

Usage:
    from src.dmarket.item_filters import ItemFilters

    filters = ItemFilters()
    if filters.is_item_allowed("AK-47 | Redline (Field-Tested)"):
        # Item passes all filters
        pass
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default config path
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "item_filters.yaml"


class ItemFilters:
    """Manager for item filtering rules.

    Loads configuration from item_filters.yaml and provides
    methods to check if items should be included or excluded
    from arbitrage opportunities.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        """Initialize ItemFilters.

        Args:
            config_path: Path to item_filters.yaml (optional)

        """
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config: dict[str, Any] = {}

        # Compiled regex patterns
        self._bad_patterns: list[re.Pattern[str]] = []
        self._good_patterns: list[re.Pattern[str]] = []

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Item filters config not found: {self.config_path}")
                self.config = self._get_default_config()
                return

            with open(self.config_path, encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}

            # Compile regex patterns
            self._compile_patterns()

            logger.info(f"Loaded item filters from {self.config_path}")

        except Exception:
            logger.exception("Failed to load item filters")
            self.config = self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration if file not found.

        Returns:
            Default configuration dictionary

        """
        return {
            "arbitrage_filters": {
                "min_avg_price": 0.50,
                "good_points_percent": 80,
                "boost_percent": 150,
                "min_sales_volume": 10,
                "max_price_deviation_percent": 50,
                "min_liquidity_score": 30,
            },
            "bad_items": [
                "Sticker",
                "Graffiti",
                "Music Kit",
                "Patch",
                "Pin",
                "Souvenir",
                "Case",
                "Capsule",
            ],
            "bad_item_patterns": [],
            "good_categories": [
                "Rifle",
                "Pistol",
                "Knife",
            ],
        }

    def _compile_patterns(self) -> None:
        """Compile regex patterns from configuration."""
        self._bad_patterns = []
        self._good_patterns = []

        # Compile bad item patterns
        for pattern in self.config.get("bad_item_patterns", []):
            try:
                self._bad_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid bad pattern '{pattern}': {e}")

        # Compile good item patterns (if any)
        for pattern in self.config.get("good_item_patterns", []):
            try:
                self._good_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid good pattern '{pattern}': {e}")

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    @property
    def arbitrage_filters(self) -> dict[str, Any]:
        """Get arbitrage filter settings.

        Returns:
            Dictionary with filter settings

        """
        return self.config.get("arbitrage_filters", {})

    @property
    def bad_items(self) -> list[str]:
        """Get list of blacklisted item keywords.

        Returns:
            List of keywords to exclude

        """
        return self.config.get("bad_items", [])

    @property
    def good_categories(self) -> list[str]:
        """Get list of prioritized categories.

        Returns:
            List of good category keywords

        """
        return self.config.get("good_categories", [])

    @property
    def game_settings(self) -> dict[str, Any]:
        """Get game-specific settings.

        Returns:
            Dictionary with game settings

        """
        return self.config.get("game_settings", {})

    @property
    def liquidity_settings(self) -> dict[str, Any]:
        """Get liquidity threshold settings.

        Returns:
            Dictionary with liquidity settings

        """
        return self.config.get("liquidity", {})

    @property
    def risk_settings(self) -> dict[str, Any]:
        """Get risk management settings.

        Returns:
            Dictionary with risk settings

        """
        return self.config.get("risk_management", {})

    def is_item_blacklisted(self, item_name: str) -> bool:
        """Check if item matches any blacklist rule.

        Args:
            item_name: Item name to check

        Returns:
            True if item is blacklisted

        """
        # Check keyword blacklist
        for keyword in self.bad_items:
            if keyword.lower() in item_name.lower():
                return True

        # Check regex patterns
        return any(pattern.search(item_name) for pattern in self._bad_patterns)

    def is_item_in_good_category(self, item_name: str) -> bool:
        """Check if item is in a good category.

        Args:
            item_name: Item name to check

        Returns:
            True if item is in a prioritized category

        """
        for category in self.good_categories:
            if category.lower() in item_name.lower():
                return True

        # Check good patterns
        return any(pattern.search(item_name) for pattern in self._good_patterns)

    def is_item_allowed(self, item_name: str) -> bool:
        """Check if item passes all filters.

        Args:
            item_name: Item name to check

        Returns:
            True if item is allowed for arbitrage

        """
        return not self.is_item_blacklisted(item_name)

    def _get_item_price(self, item: dict[str, Any]) -> float:
        """Extract price from item dictionary.

        Args:
            item: Item dictionary with price data

        Returns:
            Price in USD (converted from cents)

        """
        price_data = item.get("price", {})
        if isinstance(price_data, dict):
            price = float(price_data.get("USD", price_data.get("amount", 0))) / 100
        else:
            price = float(price_data) / 100 if price_data else 0
        return price

    def is_game_enabled(self, game: str) -> bool:
        """Check if game is enabled for arbitrage.

        Args:
            game: Game code (csgo, dota2, etc.)

        Returns:
            True if game is enabled

        """
        game_config = self.game_settings.get(game, {})
        return game_config.get("enabled", True)

    def get_game_price_range(self, game: str) -> tuple[float, float]:
        """Get price range for a specific game.

        Args:
            game: Game code

        Returns:
            Tuple of (min_price, max_price)

        """
        game_config = self.game_settings.get(game, {})
        min_price = game_config.get("min_price", 0.10)
        max_price = game_config.get("max_price", 1000.00)
        return (min_price, max_price)

    def get_priority_categories(self, game: str) -> list[str]:
        """Get priority item categories for a game.

        Args:
            game: Game code

        Returns:
            List of priority category keywords

        """
        game_config = self.game_settings.get(game, {})
        return game_config.get("priority_categories", [])

    def filter_items(
        self,
        items: list[dict[str, Any]],
        game: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter list of items based on all rules.

        Args:
            items: List of item dictionaries
            game: Game code for game-specific filtering

        Returns:
            Filtered list of items

        """
        filtered = []

        for item in items:
            # Get item name from different possible fields
            item_name = (
                item.get("title")
                or item.get("name")
                or item.get("market_hash_name")
                or ""
            )

            # Skip blacklisted items
            if self.is_item_blacklisted(item_name):
                logger.debug(f"Filtered out blacklisted item: {item_name}")
                continue

            # Check game-specific settings
            if game:
                min_price, max_price = self.get_game_price_range(game)

                # Get item price using helper method
                price = self._get_item_price(item)

                # Check price range
                if price < min_price or price > max_price:
                    logger.debug(
                        f"Filtered out item outside price range: {item_name} (${price})"
                    )
                    continue

            filtered.append(item)

        logger.info(f"Filtered {len(items)} items to {len(filtered)}")
        return filtered

    def validate_arbitrage_opportunity(
        self,
        item: dict[str, Any],
        avg_price: float | None = None,
        sales_volume: int | None = None,
        liquidity_score: float | None = None,
    ) -> tuple[bool, str | None]:
        """Validate if an arbitrage opportunity passes all filters.

        Args:
            item: Item dictionary
            avg_price: Average price from sales history
            sales_volume: Number of sales in last 7 days
            liquidity_score: Liquidity score (0-100)

        Returns:
            Tuple of (is_valid, reason_if_invalid)

        """
        item_name = (
            item.get("title") or item.get("name") or item.get("market_hash_name") or ""
        )

        # Check blacklist
        if self.is_item_blacklisted(item_name):
            return False, "Item is blacklisted"

        filters = self.arbitrage_filters

        # Check minimum average price
        if avg_price is not None:
            min_avg = filters.get("min_avg_price", 0.50)
            if avg_price < min_avg:
                return (
                    False,
                    f"Average price ${avg_price:.2f} below minimum ${min_avg:.2f}",
                )

        # Check sales volume
        if sales_volume is not None:
            min_volume = filters.get("min_sales_volume", 10)
            if sales_volume < min_volume:
                return False, f"Sales volume {sales_volume} below minimum {min_volume}"

        # Check liquidity score
        if liquidity_score is not None:
            min_liquidity = filters.get("min_liquidity_score", 30)
            if liquidity_score < min_liquidity:
                return (
                    False,
                    f"Liquidity score {liquidity_score:.1f} below minimum {min_liquidity}",
                )

        # Check price deviation from average
        if avg_price is not None:
            current_price = self._get_item_price(item)

            if current_price > 0 and avg_price > 0:
                boost_percent = filters.get("boost_percent", 150)
                if current_price > avg_price * (boost_percent / 100):
                    return (
                        False,
                        f"Price ${current_price:.2f} is >{boost_percent}% of average ${avg_price:.2f}",
                    )

        return True, None


# Global instance for convenience
_item_filters: ItemFilters | None = None


def get_item_filters() -> ItemFilters:
    """Get global ItemFilters instance.

    Returns:
        ItemFilters instance

    """
    global _item_filters
    if _item_filters is None:
        _item_filters = ItemFilters()
    return _item_filters


def reload_filters() -> None:
    """Reload filters from configuration file."""
    global _item_filters
    if _item_filters is not None:
        _item_filters.reload()
    else:
        _item_filters = ItemFilters()
