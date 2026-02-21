"""Refactored rare items pricing analyzer.

This module identifies mispriced rare items with:
- Early returns pattern for validation
- Smaller focused functions (<50 lines each)
- Clear data structures for rare traits
- Better separation of concerns

Phase 2 Refactoring (January 1, 2026)
"""

import logging
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)

__all__ = [
    "RarePricingAnalyzer",
    "RarityTraits",
    "ScoredItem",
]


class RarityTraits:
    """Rare traits configuration for different games."""

    TRAITS = {
        "csgo": {
            "Knife": 100,
            "Gloves": 90,
            "Covert": 70,
            "StatTrak™": 50,
            "Souvenir": 60,
            "Factory New": 40,
            "Case Hardened": 50,
            "Fade": 60,
            "Doppler": 60,
            "Crimson Web": 50,
            "★": 100,
        },
        "dota2": {
            "Arcana": 100,
            "Immortal": 80,
            "Unusual": 90,
            "Inscribed": 30,
            "Genuine": 40,
            "Corrupted": 60,
            "Exalted": 50,
            "Autographed": 40,
        },
        "tf2": {
            "Unusual": 100,
            "Vintage": 50,
            "Genuine": 40,
            "Strange": 30,
            "Haunted": 60,
            "Australium": 80,
            "Collector's": 70,
            "Professional Killstreak": 50,
            "Golden Frying Pan": 100,
            "Burning Flames": 95,
            "Sunbeams": 90,
            "Team Captain": 70,
        },
        "rust": {
            "Glowing": 70,
            "Limited": 80,
            "Unique": 50,
            "Complete Set": 60,
            "Sign": 65,
            "Trophy": 75,
            "Relic": 70,
            "Hazmat Suit": 60,
            "Metal": 55,
            "Blackout": 60,
            "Tempered": 65,
            "Punishment": 70,
        },
    }

    @classmethod
    def get_traits(cls, game: str) -> dict[str, int]:
        """Get rare traits for specific game.

        Args:
            game: Game code

        Returns:
            Dictionary of trait -> weight
        """
        return cls.TRAITS.get(game, {})


class ScoredItem:
    """Scored item with rarity analysis."""

    def __init__(
        self,
        item: dict[str, Any],
        rarity_score: int,
        rare_traits: list[str],
        current_price: float,
        estimated_value: float,
    ):
        """Initialize scored item.

        Args:
            item: Original item data
            rarity_score: Calculated rarity score
            rare_traits: Detected rare traits
            current_price: Current market price
            estimated_value: Estimated true value
        """
        self.item = item
        self.rarity_score = rarity_score
        self.rare_traits = rare_traits
        self.current_price = current_price
        self.estimated_value = estimated_value
        self.price_difference = estimated_value - current_price
        self.price_difference_percent = (self.price_difference / current_price) * 100

    def is_undervalued(
        self,
        min_difference: float = 2.0,
        min_percent: float = 10.0,
    ) -> bool:
        """Check if item is undervalued.

        Args:
            min_difference: Minimum price difference in USD
            min_percent: Minimum percentage difference

        Returns:
            True if item appears undervalued
        """
        return (
            self.price_difference > min_difference
            and self.price_difference_percent > min_percent
        )

    def to_dict(self, game: str) -> dict[str, Any]:
        """Convert to dictionary format.

        Args:
            game: Game code

        Returns:
            Dictionary with all item data
        """
        return {
            "item": self.item,
            "rarity_score": self.rarity_score,
            "rare_traits": self.rare_traits,
            "current_price": self.current_price,
            "estimated_value": self.estimated_value,
            "price_difference": self.price_difference,
            "price_difference_percent": self.price_difference_percent,
            "game": game,
        }


class RarePricingAnalyzer:
    """Analyzer for finding mispriced rare items."""

    def __init__(self, api_client: DMarketAPI | None = None):
        """Initialize analyzer.

        Args:
            api_client: DMarket API client (optional)
        """
        self.api_client = api_client
        self._close_api = False

    async def __aenter__(self):
        """Async context manager entry."""
        if self.api_client is None:
            from src.telegram_bot.utils.api_helper import create_dmarket_api_client

            self.api_client = create_dmarket_api_client(None)
            self._close_api = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._close_api and hasattr(self.api_client, "_close_client"):
            await self.api_client._close_client()

    async def find_mispriced_rare_items(
        self,
        game: str,
        min_price: float = 10.0,
        max_price: float = 1000.0,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Find rare items that appear mispriced.

        Args:
            game: Game code (csgo, dota2, tf2, rust)
            min_price: Minimum item price
            max_price: Maximum item price
            max_results: Maximum results to return

        Returns:
            List of mispriced rare items
        """
        logger.info(f"Searching for mispriced rare items in {game}")

        try:
            # Fetch market items
            items = await self._fetch_market_items(
                game=game,
                min_price=min_price,
                max_price=max_price,
            )

            if not items:
                return []

            # Analyze items for rare traits
            scored_items = self._analyze_items(
                items=items,
                game=game,
                min_price=min_price,
                max_price=max_price,
            )

            # Return top results
            return self._get_top_results(scored_items, max_results, game)

        except Exception as e:
            logger.exception(f"Error in find_mispriced_rare_items: {e!s}")
            return []

    async def _fetch_market_items(
        self,
        game: str,
        min_price: float,
        max_price: float,
    ) -> list[dict[str, Any]]:
        """Fetch market items from API.

        Args:
            game: Game code
            min_price: Minimum price
            max_price: Maximum price

        Returns:
            List of market items
        """
        items_response = await self.api_client.get_market_items(
            game=game,
            limit=500,
            offset=0,
            price_from=min_price,
            price_to=max_price,
        )

        return items_response.get("items", [])

    def _analyze_items(
        self,
        items: list[dict[str, Any]],
        game: str,
        min_price: float,
        max_price: float,
    ) -> list[ScoredItem]:
        """Analyze items for rare traits and pricing.

        Args:
            items: List of items to analyze
            game: Game code
            min_price: Minimum price filter
            max_price: Maximum price filter

        Returns:
            List of scored items
        """
        scored_items = []

        for item in items:
            scored_item = self._analyze_single_item(
                item=item,
                game=game,
                min_price=min_price,
                max_price=max_price,
            )

            if scored_item and scored_item.is_undervalued():
                scored_items.append(scored_item)

        return scored_items

    def _analyze_single_item(
        self,
        item: dict[str, Any],
        game: str,
        min_price: float,
        max_price: float,
    ) -> ScoredItem | None:
        """Analyze single item for rarity and pricing.

        Args:
            item: Item data
            game: Game code
            min_price: Minimum price
            max_price: Maximum price

        Returns:
            ScoredItem or None if item doesn't qualify
        """
        title = item.get("title", "")
        if not title:
            return None

        # Extract and validate price
        price = self._extract_price(item)
        if not self._is_price_valid(price, min_price, max_price):
            return None

        # Calculate rarity score
        rarity_score, detected_traits = self._calculate_rarity_score(
            item=item,
            title=title,
            game=game,
        )

        # Check minimum rarity threshold
        if rarity_score <= 30:
            return None

        # Estimate value
        suggested_price = self._extract_suggested_price(item)
        estimated_value = self._estimate_value(
            price=price,
            suggested_price=suggested_price,
            rarity_score=rarity_score,
        )

        return ScoredItem(
            item=item,
            rarity_score=rarity_score,
            rare_traits=detected_traits,
            current_price=price,
            estimated_value=estimated_value,
        )

    def _extract_price(self, item: dict[str, Any]) -> float | None:
        """Extract price from item data.

        Args:
            item: Item data

        Returns:
            Price in USD or None
        """
        if "price" not in item:
            return None

        price_data = item["price"]

        if isinstance(price_data, dict) and "amount" in price_data:
            return int(price_data["amount"]) / 100

        if isinstance(price_data, (int, float)):
            return float(price_data)

        return None

    def _is_price_valid(
        self,
        price: float | None,
        min_price: float,
        max_price: float,
    ) -> bool:
        """Check if price is within valid range.

        Args:
            price: Price to check
            min_price: Minimum price
            max_price: Maximum price

        Returns:
            True if price is valid
        """
        if price is None:
            return False

        return not (price < min_price or price > max_price)

    def _calculate_rarity_score(
        self,
        item: dict[str, Any],
        title: str,
        game: str,
    ) -> tuple[int, list[str]]:
        """Calculate rarity score based on traits.

        Args:
            item: Item data
            title: Item title
            game: Game code

        Returns:
            Tuple of (rarity_score, detected_traits)
        """
        rarity_score = 0
        detected_traits = []

        # Check title for rare traits
        traits = RarityTraits.get_traits(game)
        for trait, weight in traits.items():
            if trait in title:
                rarity_score += weight
                detected_traits.append(trait)

        # Add CS:GO float value bonus
        if game == "csgo":
            float_bonus, float_trait = self._get_float_bonus(item)
            rarity_score += float_bonus
            if float_trait:
                detected_traits.append(float_trait)

        return rarity_score, detected_traits

    def _get_float_bonus(self, item: dict[str, Any]) -> tuple[int, str | None]:
        """Calculate bonus score for CS:GO float value.

        Args:
            item: Item data

        Returns:
            Tuple of (bonus_score, trait_description)
        """
        if "float" not in item:
            return 0, None

        float_value = float(item.get("float", 1.0))

        if float_value < 0.01:  # Extremely low float
            return 70, f"Float: {float_value:.4f}"

        if float_value < 0.07:  # Very low float
            return 40, f"Float: {float_value:.4f}"

        return 0, None

    def _extract_suggested_price(self, item: dict[str, Any]) -> float:
        """Extract suggested price from item data.

        Args:
            item: Item data

        Returns:
            Suggested price in USD or 0
        """
        if "suggestedPrice" not in item:
            return 0.0

        suggested_data = item["suggestedPrice"]

        if isinstance(suggested_data, dict) and "amount" in suggested_data:
            return int(suggested_data["amount"]) / 100

        if isinstance(suggested_data, (int, float)):
            return float(suggested_data)

        return 0.0

    def _estimate_value(
        self,
        price: float,
        suggested_price: float,
        rarity_score: int,
    ) -> float:
        """Estimate true value of item.

        Args:
            price: Current market price
            suggested_price: Suggested price (if available)
            rarity_score: Calculated rarity score

        Returns:
            Estimated value in USD
        """
        # If no suggested price, estimate based on rarity
        if suggested_price == 0:
            suggested_price = price * (1 + (rarity_score / 200))

        # Calculate estimated value
        return max(
            suggested_price,
            price * (1 + (rarity_score / 300)),
        )

    def _get_top_results(
        self,
        scored_items: list[ScoredItem],
        max_results: int,
        game: str,
    ) -> list[dict[str, Any]]:
        """Get top results sorted by price difference.

        Args:
            scored_items: List of scored items
            max_results: Maximum results to return
            game: Game code

        Returns:
            List of top results as dictionaries
        """
        # Sort by price difference percentage (highest first)
        sorted_items = sorted(
            scored_items,
            key=lambda x: x.price_difference_percent,
            reverse=True,
        )

        # Convert to dictionaries
        return [item.to_dict(game) for item in sorted_items[:max_results]]


# Backward compatibility function
async def find_mispriced_rare_items(
    game: str,
    min_price: float = 10.0,
    max_price: float = 1000.0,
    max_results: int = 5,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Find rare items that appear mispriced (legacy interface).

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        min_price: Minimum item price
        max_price: Maximum item price
        max_results: Maximum results to return
        dmarket_api: DMarket API instance (optional)

    Returns:
        List of mispriced rare items
    """
    async with RarePricingAnalyzer(api_client=dmarket_api) as analyzer:
        return await analyzer.find_mispriced_rare_items(
            game=game,
            min_price=min_price,
            max_price=max_price,
            max_results=max_results,
        )
