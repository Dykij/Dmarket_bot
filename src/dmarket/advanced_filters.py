"""Advanced filters for arbitrage trading on DMarket.

Provides comprehensive filtering capabilities including:
- Sales history analysis (average price, median, outliers)
- Liquidity assessment (time to sell, market depth)
- Category blacklist/whitelist
- Statistical outlier detection

Based on best practices from:
- timagr615/dmarket_bot
- louisa-uno/dmarket_bot

Usage:
    ```python
    from src.dmarket.advanced_filters import AdvancedArbitrageFilter

    filter = AdvancedArbitrageFilter()

    # Check if item passes all filters
    is_good, reasons = await filter.evaluate_item(item_data, api_client)

    # Get filter statistics
    stats = filter.get_statistics()
    ```
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class FilterResult(StrEnum):
    """Result of filter evaluation."""

    PASS = "pass"  # noqa: S105 - not a password, filter result
    FAIL = "fail"
    SKIP = "skip"  # Not enough data


@dataclass
class FilterConfig:
    """Configuration for advanced filters.

    Attributes:
        min_avg_price: Minimum average price over sales history (USD)
        good_points_percent: Required % of sales with profit > min margin
        boost_percent: Max price as % of average (reject if > this)
        min_sales_volume: Minimum sales in period for liquidity
        min_profit_margin: Minimum required profit margin (%)
        outlier_threshold: Standard deviations for outlier detection
        min_liquidity_score: Minimum liquidity score (0-100)
        max_time_to_sell_days: Maximum acceptable time to sell
        enable_category_filter: Enable category blacklist/whitelist
        enable_outlier_filter: Enable statistical outlier detection
        enable_liquidity_filter: Enable liquidity requirements
        enable_sales_history_filter: Enable sales history analysis
    """

    min_avg_price: float = 0.50
    good_points_percent: float = 80.0
    boost_percent: float = 150.0
    min_sales_volume: int = 10
    min_profit_margin: float = 5.0
    outlier_threshold: float = 2.0
    min_liquidity_score: float = 60.0
    max_time_to_sell_days: int = 7
    enable_category_filter: bool = True
    enable_outlier_filter: bool = True
    enable_liquidity_filter: bool = True
    enable_sales_history_filter: bool = True


@dataclass
class FilterStatistics:
    """Statistics for filter performance tracking."""

    total_evaluated: int = 0
    passed: int = 0
    failed_category: int = 0
    failed_liquidity: int = 0
    failed_sales_history: int = 0
    failed_outlier: int = 0
    failed_price: int = 0
    skipped_no_data: int = 0


# Default category filters
DEFAULT_BAD_CATEGORIES: set[str] = {
    "Sticker",
    "Graffiti",
    "Music Kit",
    "Patch",
    "Pin",
    "Sealed Graffiti",
    "Charm",
    "Package",
    "Pass",
    "Key",
    "Capsule",
    "Container",
}

DEFAULT_GOOD_CATEGORIES: set[str] = {
    "Rifle",
    "Pistol",
    "Knife",
    "SMG",
    "Shotgun",
    "Sniper Rifle",
    "Machine Gun",
    "Gloves",
}


class AdvancedArbitrageFilter:
    """Advanced filtering system for arbitrage items.

    Evaluates items against multiple criteria to reduce risk
    and improve arbitrage success rate.
    """

    def __init__(
        self,
        config: FilterConfig | None = None,
        bad_categories: set[str] | None = None,
        good_categories: set[str] | None = None,
    ) -> None:
        """Initialize the filter.

        Args:
            config: Filter configuration
            bad_categories: Categories to exclude
            good_categories: Preferred categories (items get bonus)
        """
        self.config = config or FilterConfig()
        self.bad_categories = bad_categories or DEFAULT_BAD_CATEGORIES
        self.good_categories = good_categories or DEFAULT_GOOD_CATEGORIES
        self.statistics = FilterStatistics()
        self._sales_cache: dict[str, dict[str, Any]] = {}

    async def evaluate_item(
        self,
        item: dict[str, Any],
        api_client: DMarketAPI | None = None,
        game: str = "csgo",
    ) -> tuple[bool, list[str]]:
        """Evaluate item against all filters.

        Args:
            item: Item data from DMarket API
            api_client: DMarket API client for additional data
            game: Game ID (csgo, dota2, etc.)

        Returns:
            Tuple of (passed, list of reasons)
        """
        self.statistics.total_evaluated += 1
        reasons: list[str] = []
        item_name = item.get("title", "") or item.get("market_hash_name", "")

        # 1. Category filter
        if self.config.enable_category_filter:
            result, reason = self._check_category(item_name, item)
            if result == FilterResult.FAIL:
                self.statistics.failed_category += 1
                reasons.append(reason)
                return False, reasons

        # 2. Basic price check
        price = self._extract_price(item)
        if price < self.config.min_avg_price:
            self.statistics.failed_price += 1
            reasons.append(f"Price ${price:.2f} below minimum ${self.config.min_avg_price:.2f}")
            return False, reasons

        # 3. Sales history analysis (requires API client)
        if self.config.enable_sales_history_filter and api_client:
            result, reason = await self._check_sales_history(item_name, price, api_client, game)
            if result == FilterResult.FAIL:
                self.statistics.failed_sales_history += 1
                reasons.append(reason)
                return False, reasons
            if result == FilterResult.SKIP:
                self.statistics.skipped_no_data += 1
                # Continue with other checks

        # 4. Liquidity filter
        if self.config.enable_liquidity_filter:
            result, reason = self._check_liquidity(item)
            if result == FilterResult.FAIL:
                self.statistics.failed_liquidity += 1
                reasons.append(reason)
                return False, reasons

        # 5. Outlier detection
        if self.config.enable_outlier_filter:
            result, reason = await self._check_outlier(item_name, price, api_client, game)
            if result == FilterResult.FAIL:
                self.statistics.failed_outlier += 1
                reasons.append(reason)
                return False, reasons

        self.statistics.passed += 1
        return True, ["Passed all filters"]

    def _check_category(self, item_name: str, item: dict[str, Any]) -> tuple[FilterResult, str]:
        """Check if item category is allowed.

        Args:
            item_name: Item name
            item: Item data

        Returns:
            Filter result and reason
        """
        # Check against bad categories
        item_name_lower = item_name.lower()
        for bad_cat in self.bad_categories:
            if bad_cat.lower() in item_name_lower:
                return FilterResult.FAIL, f"Item in excluded category: {bad_cat}"

        # Check item type from API data
        item_type = item.get("type", "") or item.get("itemType", "")
        if item_type:
            for bad_cat in self.bad_categories:
                if bad_cat.lower() in item_type.lower():
                    return FilterResult.FAIL, f"Item type excluded: {item_type}"

        return FilterResult.PASS, ""

    def _extract_price(self, item: dict[str, Any]) -> float:
        """Extract price from item data.

        Args:
            item: Item data

        Returns:
            Price in USD
        """
        try:
            # Try different price fields
            if "price" in item:
                price_data = item["price"]
                if isinstance(price_data, dict):
                    # Price in cents
                    return float(price_data.get("USD", 0)) / 100
                return float(price_data) / 100

            if "salesPrice" in item:
                return float(item["salesPrice"]) / 100

            if "suggestedPrice" in item:
                price_data = item["suggestedPrice"]
                if isinstance(price_data, dict):
                    return float(price_data.get("USD", 0)) / 100
                return float(price_data) / 100

            return 0.0
        except (KeyError, ValueError, TypeError):
            return 0.0

    async def _check_sales_history(
        self,
        item_name: str,
        current_price: float,
        api_client: DMarketAPI,
        game: str,
    ) -> tuple[FilterResult, str]:
        """Analyze sales history for item.

        Args:
            item_name: Item name
            current_price: Current item price
            api_client: DMarket API client
            game: Game ID

        Returns:
            Filter result and reason
        """
        try:
            # Get cached or fetch new data
            cache_key = f"{game}:{item_name}"
            if cache_key in self._sales_cache:
                sales_data = self._sales_cache[cache_key]
            else:
                sales_data = await self._fetch_sales_history(item_name, api_client, game)
                self._sales_cache[cache_key] = sales_data

            if not sales_data or sales_data.get("num_sales", 0) < 3:
                return FilterResult.SKIP, "Insufficient sales data"

            # Check minimum sales volume
            if sales_data["num_sales"] < self.config.min_sales_volume:
                return (
                    FilterResult.FAIL,
                    f"Sales volume {sales_data['num_sales']} below minimum {self.config.min_sales_volume}",
                )

            # Check if price is within reasonable range (boost check)
            avg_price = sales_data.get("average_price", 0)
            if avg_price > 0:
                price_ratio = (current_price / avg_price) * 100
                if price_ratio > self.config.boost_percent:
                    return (
                        FilterResult.FAIL,
                        f"Price {price_ratio:.0f}% of average exceeds {self.config.boost_percent}%",
                    )

            # Check average price minimum
            if avg_price < self.config.min_avg_price:
                return (
                    FilterResult.FAIL,
                    f"Average price ${avg_price:.2f} below minimum ${self.config.min_avg_price:.2f}",
                )

            # Check good points percentage (profitable transactions)
            good_points = sales_data.get("good_points_percent", 0)
            if good_points < self.config.good_points_percent:
                return (
                    FilterResult.FAIL,
                    f"Only {good_points:.0f}% profitable sales (min {self.config.good_points_percent}%)",
                )

            return FilterResult.PASS, ""

        except Exception as e:
            logger.warning("Error checking sales history for %s: %s", item_name, e)
            return FilterResult.SKIP, f"Error: {e}"

    async def _fetch_sales_history(
        self,
        item_name: str,
        api_client: DMarketAPI,
        game: str,
    ) -> dict[str, Any]:
        """Fetch and analyze sales history from API.

        Args:
            item_name: Item name
            api_client: DMarket API client
            game: Game ID

        Returns:
            Analyzed sales data
        """
        try:
            # Get price history from API
            history = await api_client.get_item_price_history(
                title=item_name,
                game=game,
                period="7d",
            )

            if not history or not isinstance(history, list):
                return {}

            # Extract prices
            prices = []
            for sale in history:
                if "price" in sale:
                    price = float(sale["price"]) / 100  # Convert from cents
                    prices.append(price)

            if not prices:
                return {}

            # Calculate statistics
            avg_price = sum(prices) / len(prices)
            median_price = self._calculate_median(prices)
            std_dev = self._calculate_std_dev(prices, avg_price)

            # Calculate good points (sales with profit potential)
            min_margin = self.config.min_profit_margin / 100
            good_count = sum(1 for p in prices if p >= avg_price * (1 - min_margin))
            good_points_percent = (good_count / len(prices)) * 100

            return {
                "num_sales": len(prices),
                "average_price": avg_price,
                "median_price": median_price,
                "std_dev": std_dev,
                "min_price": min(prices),
                "max_price": max(prices),
                "good_points_percent": good_points_percent,
            }

        except Exception as e:
            logger.warning("Error fetching sales history: %s", e)
            return {}

    def _check_liquidity(self, item: dict[str, Any]) -> tuple[FilterResult, str]:
        """Check item liquidity metrics.

        Args:
            item: Item data

        Returns:
            Filter result and reason
        """
        # Check available offers count (market depth)
        offers_count = item.get("offersCount", 0) or item.get("inMarket", 0)
        if offers_count == 0:
            return FilterResult.FAIL, "No active market offers"

        # If item has explicit liquidity score
        liquidity_score = item.get("liquidityScore", -1)
        if 0 <= liquidity_score < self.config.min_liquidity_score:
            return (
                FilterResult.FAIL,
                f"Liquidity score {liquidity_score} below minimum {self.config.min_liquidity_score}",
            )

        return FilterResult.PASS, ""

    async def _check_outlier(
        self,
        item_name: str,
        current_price: float,
        api_client: DMarketAPI | None,
        game: str,
    ) -> tuple[FilterResult, str]:
        """Check if current price is an outlier.

        Uses statistical analysis (Z-score) to detect
        prices that deviate significantly from historical data.

        Args:
            item_name: Item name
            current_price: Current price
            api_client: DMarket API client
            game: Game ID

        Returns:
            Filter result and reason
        """
        if not api_client:
            return FilterResult.SKIP, "No API client for outlier check"

        try:
            # Get cached sales data
            cache_key = f"{game}:{item_name}"
            if cache_key not in self._sales_cache:
                return FilterResult.SKIP, "No sales data for outlier check"

            sales_data = self._sales_cache[cache_key]
            avg_price = sales_data.get("average_price", 0)
            std_dev = sales_data.get("std_dev", 0)

            if avg_price == 0 or std_dev == 0:
                return FilterResult.SKIP, "Insufficient data for outlier detection"

            # Calculate Z-score
            z_score = abs(current_price - avg_price) / std_dev

            if z_score > self.config.outlier_threshold:
                direction = "above" if current_price > avg_price else "below"
                return (
                    FilterResult.FAIL,
                    f"Price is outlier ({z_score:.1f}σ {direction} average)",
                )

            return FilterResult.PASS, ""

        except Exception as e:
            logger.warning("Error in outlier check: %s", e)
            return FilterResult.SKIP, f"Outlier check error: {e}"

    def _calculate_median(self, numbers: list[float]) -> float:
        """Calculate median of a list."""
        if not numbers:
            return 0.0
        sorted_nums = sorted(numbers)
        n = len(sorted_nums)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
        return sorted_nums[mid]

    def _calculate_std_dev(self, numbers: list[float], mean: float) -> float:
        """Calculate standard deviation."""
        if len(numbers) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in numbers) / (len(numbers) - 1)
        return math.sqrt(variance)

    def is_in_good_category(self, item_name: str) -> bool:
        """Check if item is in a preferred category.

        Args:
            item_name: Item name

        Returns:
            True if item is in good category
        """
        item_name_lower = item_name.lower()
        return any(cat.lower() in item_name_lower for cat in self.good_categories)

    def get_statistics(self) -> dict[str, Any]:
        """Get filter performance statistics.

        Returns:
            Dictionary with filter statistics
        """
        total = self.statistics.total_evaluated
        return {
            "total_evaluated": total,
            "passed": self.statistics.passed,
            "pass_rate": (self.statistics.passed / total * 100) if total > 0 else 0,
            "failed_category": self.statistics.failed_category,
            "failed_liquidity": self.statistics.failed_liquidity,
            "failed_sales_history": self.statistics.failed_sales_history,
            "failed_outlier": self.statistics.failed_outlier,
            "failed_price": self.statistics.failed_price,
            "skipped_no_data": self.statistics.skipped_no_data,
        }

    def reset_statistics(self) -> None:
        """Reset filter statistics."""
        self.statistics = FilterStatistics()

    def clear_cache(self) -> None:
        """Clear sales history cache."""
        self._sales_cache.clear()


def load_filter_config_from_yaml(config_path: str) -> FilterConfig:
    """Load filter configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        FilterConfig instance
    """
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        filters_config = data.get("arbitrage_filters", {})

        return FilterConfig(
            min_avg_price=filters_config.get("MIN_AVG_PRICE", 0.50),
            good_points_percent=filters_config.get("GOOD_POINTS_PERCENT", 80.0),
            boost_percent=filters_config.get("BOOST_PERCENT", 150.0),
            min_sales_volume=filters_config.get("MIN_SALES_VOLUME", 10),
            min_profit_margin=filters_config.get("MIN_PROFIT_MARGIN", 5.0),
            outlier_threshold=filters_config.get("OUTLIER_THRESHOLD", 2.0),
            min_liquidity_score=filters_config.get("MIN_LIQUIDITY_SCORE", 60.0),
            max_time_to_sell_days=filters_config.get("MAX_TIME_TO_SELL_DAYS", 7),
            enable_category_filter=filters_config.get("ENABLE_CATEGORY_FILTER", True),
            enable_outlier_filter=filters_config.get("ENABLE_OUTLIER_FILTER", True),
            enable_liquidity_filter=filters_config.get("ENABLE_LIQUIDITY_FILTER", True),
            enable_sales_history_filter=filters_config.get("ENABLE_SALES_HISTORY_FILTER", True),
        )

    except Exception as e:
        logger.warning("Error loading filter config: %s, using defaults", e)
        return FilterConfig()


def load_category_filters_from_yaml(
    config_path: str,
) -> tuple[set[str], set[str]]:
    """Load category filters from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Tuple of (bad_categories, good_categories)
    """
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        bad_items = set(data.get("bad_items", []))
        good_categories = set(data.get("good_categories", []))

        return bad_items, good_categories

    except Exception as e:
        logger.warning("Error loading category filters: %s, using defaults", e)
        return DEFAULT_BAD_CATEGORIES, DEFAULT_GOOD_CATEGORIES
