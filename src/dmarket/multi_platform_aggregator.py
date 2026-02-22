"""Multi-Platform Price Aggregator - aggregate prices from multiple marketplaces.

This module provides real-time price aggregation from:
- DMarket
- Waxpeer
- Steam Market
- Buff163 (China market)

Helps find the best buy/sell opportunities across platforms.

Usage:
    ```python
    from src.dmarket.multi_platform_aggregator import MultiPlatformAggregator

    aggregator = MultiPlatformAggregator(
        dmarket_api=dmarket_client,
        waxpeer_api=waxpeer_client,
    )

    prices = await aggregator.get_best_prices("AK-47 | Redline (Field-Tested)")

    if prices.best_buy.platform != prices.best_sell.platform:
        # Cross-platform arbitrage opportunity!
        profit = prices.potential_profit
    ```

Created: January 6, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI


logger = structlog.get_logger(__name__)


class Platform(StrEnum):
    """Trading platforms."""

    DMARKET = "dmarket"
    WAXPEER = "waxpeer"
    STEAM = "steam"
    BUFF163 = "buff163"


# Platform commission rates
COMMISSIONS: dict[Platform, float] = {
    Platform.DMARKET: 0.07,  # 7%
    Platform.WAXPEER: 0.06,  # 6%
    Platform.STEAM: 0.13,  # 13%
    Platform.BUFF163: 0.025,  # 2.5%
}

# Minimum prices for each platform (in USD)
MIN_PRICES: dict[Platform, float] = {
    Platform.DMARKET: 0.03,  # $0.03
    Platform.WAXPEER: 0.10,  # $0.10
    Platform.STEAM: 0.03,  # $0.03
    Platform.BUFF163: 0.10,  # $0.10
}


@dataclass
class PlatformPrice:
    """Price information from a single platform."""

    platform: Platform
    price: float
    quantity: int = 1
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Additional info
    offers_count: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None

    @property
    def net_price_after_sell(self) -> float:
        """Calculate price after platform commission (for selling)."""
        commission = COMMISSIONS.get(self.platform, 0.07)
        return self.price * (1 - commission)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "platform": self.platform,
            "price": self.price,
            "quantity": self.quantity,
            "net_after_commission": round(self.net_price_after_sell, 2),
            "offers_count": self.offers_count,
        }


@dataclass
class AggregatedPrices:
    """Aggregated prices from multiple platforms."""

    item_name: str
    game: str
    prices: dict[Platform, PlatformPrice] = field(default_factory=dict)
    aggregated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def best_buy(self) -> PlatformPrice | None:
        """Get best (lowest) buy price."""
        if not self.prices:
            return None
        return min(self.prices.values(), key=lambda p: p.price)

    @property
    def best_sell(self) -> PlatformPrice | None:
        """Get best (highest) sell price after commission."""
        if not self.prices:
            return None
        return max(self.prices.values(), key=lambda p: p.net_price_after_sell)

    @property
    def price_spread(self) -> float:
        """Calculate price spread between min and max."""
        if len(self.prices) < 2:
            return 0.0

        prices = [p.price for p in self.prices.values()]
        return max(prices) - min(prices)

    @property
    def price_spread_percent(self) -> float:
        """Calculate price spread as percentage."""
        best_buy = self.best_buy
        if not best_buy or best_buy.price <= 0:
            return 0.0

        return (self.price_spread / best_buy.price) * 100

    @property
    def potential_profit(self) -> float:
        """Calculate potential arbitrage profit."""
        best_buy = self.best_buy
        best_sell = self.best_sell

        if not best_buy or not best_sell:
            return 0.0

        return best_sell.net_price_after_sell - best_buy.price

    @property
    def potential_roi(self) -> float:
        """Calculate potential ROI percentage."""
        best_buy = self.best_buy
        if not best_buy or best_buy.price <= 0:
            return 0.0

        return (self.potential_profit / best_buy.price) * 100

    @property
    def has_arbitrage_opportunity(self) -> bool:
        """Check if cross-platform arbitrage is possible."""
        return (
            self.potential_profit > 0
            and self.best_buy is not None
            and self.best_sell is not None
            and self.best_buy.platform != self.best_sell.platform
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "game": self.game,
            "prices": {p: info.to_dict() for p, info in self.prices.items()},
            "best_buy": self.best_buy.to_dict() if self.best_buy else None,
            "best_sell": self.best_sell.to_dict() if self.best_sell else None,
            "price_spread": round(self.price_spread, 2),
            "price_spread_percent": round(self.price_spread_percent, 2),
            "potential_profit": round(self.potential_profit, 2),
            "potential_roi": round(self.potential_roi, 2),
            "has_arbitrage": self.has_arbitrage_opportunity,
        }


class MultiPlatformAggregator:
    """Aggregate prices from multiple trading platforms."""

    def __init__(
        self,
        dmarket_api: DMarketAPI | None = None,
        waxpeer_api: WaxpeerAPI | None = None,
        enabled_platforms: list[Platform] | None = None,
    ) -> None:
        """Initialize aggregator.

        Args:
            dmarket_api: DMarket API client
            waxpeer_api: Waxpeer API client
            enabled_platforms: List of platforms to query

        """
        self.dmarket_api = dmarket_api
        self.waxpeer_api = waxpeer_api
        self.enabled_platforms = enabled_platforms or [
            Platform.DMARKET,
            Platform.WAXPEER,
        ]

    async def get_prices(
        self,
        item_name: str,
        game: str = "csgo",
    ) -> AggregatedPrices:
        """Get prices from all enabled platforms.

        Args:
            item_name: Item name to search
            game: Game ID

        Returns:
            AggregatedPrices with all platform prices

        """
        result = AggregatedPrices(item_name=item_name, game=game)

        # Fetch from each platform
        for platform in self.enabled_platforms:
            try:
                price = await self._fetch_platform_price(platform, item_name, game)
                if price:
                    result.prices[platform] = price
            except Exception as e:
                logger.warning(
                    "platform_fetch_failed",
                    platform=platform,
                    item=item_name,
                    error=str(e),
                )

        logger.info(
            "prices_aggregated",
            item=item_name,
            platforms=len(result.prices),
            has_arbitrage=result.has_arbitrage_opportunity,
            potential_roi=round(result.potential_roi, 2) if result.potential_roi else 0,
        )

        return result

    async def find_arbitrage_opportunities(
        self,
        items: list[str],
        game: str = "csgo",
        min_profit: float = 0.50,
        min_roi_percent: float = 5.0,
    ) -> list[AggregatedPrices]:
        """Find arbitrage opportunities across platforms.

        Args:
            items: List of item names to check
            game: Game ID
            min_profit: Minimum profit in USD
            min_roi_percent: Minimum ROI percentage

        Returns:
            List of items with arbitrage opportunities

        """
        opportunities = []

        for item_name in items:
            prices = await self.get_prices(item_name, game)

            if not prices.has_arbitrage_opportunity:
                continue

            if prices.potential_profit < min_profit:
                continue

            if prices.potential_roi < min_roi_percent:
                continue

            opportunities.append(prices)

        # Sort by ROI (highest first)
        opportunities.sort(key=lambda p: p.potential_roi, reverse=True)

        logger.info(
            "arbitrage_scan_complete",
            items_checked=len(items),
            opportunities_found=len(opportunities),
        )

        return opportunities

    async def _fetch_platform_price(
        self,
        platform: Platform,
        item_name: str,
        game: str,
    ) -> PlatformPrice | None:
        """Fetch price from a specific platform."""
        if platform == Platform.DMARKET:
            return await self._fetch_dmarket_price(item_name, game)
        if platform == Platform.WAXPEER:
            return await self._fetch_waxpeer_price(item_name, game)
        if platform == Platform.STEAM:
            return await self._fetch_steam_price(item_name, game)
        return None

    async def _fetch_dmarket_price(
        self,
        item_name: str,
        game: str,
    ) -> PlatformPrice | None:
        """Fetch price from DMarket."""
        if not self.dmarket_api:
            return None

        try:
            response = await self.dmarket_api.get_market_items(
                game=game,
                title=item_name,
                limit=10,
            )

            items = response.get("objects", [])
            if not items:
                return None

            # Get lowest price
            prices = []
            for item in items:
                price_data = item.get("price", {})
                price_str = price_data.get("USD", "0")
                price = float(price_str) / 100  # Cents to dollars
                if price > 0:
                    prices.append(price)

            if not prices:
                return None

            min_price = min(prices)
            avg_price = sum(prices) / len(prices)

            return PlatformPrice(
                platform=Platform.DMARKET,
                price=min_price,
                quantity=len(items),
                offers_count=len(items),
                min_price=min_price,
                max_price=max(prices),
                avg_price=avg_price,
            )

        except Exception as e:
            logger.exception("dmarket_fetch_error", item=item_name, error=str(e))
            return None

    async def _fetch_waxpeer_price(
        self,
        item_name: str,
        game: str,
    ) -> PlatformPrice | None:
        """Fetch price from Waxpeer."""
        if not self.waxpeer_api:
            return None

        try:
            # Waxpeer uses different game identifiers
            waxpeer_game = "csgo" if game == "csgo" else game

            response = await self.waxpeer_api.get_items(
                game=waxpeer_game,
                search=item_name,
                limit=10,
            )

            items = response.get("items", [])
            if not items:
                return None

            # Waxpeer prices in mils (1/1000 USD)
            prices = []
            for item in items:
                price = item.get("price", 0) / 1000  # Mils to dollars
                if price > 0:
                    prices.append(price)

            if not prices:
                return None

            min_price = min(prices)

            return PlatformPrice(
                platform=Platform.WAXPEER,
                price=min_price,
                quantity=len(items),
                offers_count=len(items),
                min_price=min_price,
                max_price=max(prices),
                avg_price=sum(prices) / len(prices),
            )

        except Exception as e:
            logger.exception("waxpeer_fetch_error", item=item_name, error=str(e))
            return None

    async def _fetch_steam_price(
        self,
        item_name: str,
        game: str,
    ) -> PlatformPrice | None:
        """Fetch price from Steam Market (for reference only)."""
        # Steam prices are fetched via steam_api.py
        # This is a placeholder - implement based on your steam_api
        try:
            from src.dmarket.steam_api import get_steam_price

            price = await get_steam_price(item_name)

            if price and price > 0:
                return PlatformPrice(
                    platform=Platform.STEAM,
                    price=price,
                    quantity=1,
                )

            return None

        except Exception as e:
            logger.exception("steam_fetch_error", item=item_name, error=str(e))
            return None

    async def get_best_buy_platform(
        self,
        item_name: str,
        game: str = "csgo",
    ) -> tuple[Platform, float] | None:
        """Find the platform with the lowest price.

        Args:
            item_name: Item name
            game: Game ID

        Returns:
            Tuple of (platform, price) or None

        """
        prices = await self.get_prices(item_name, game)
        best = prices.best_buy

        if best:
            return (best.platform, best.price)
        return None

    async def get_best_sell_platform(
        self,
        item_name: str,
        game: str = "csgo",
    ) -> tuple[Platform, float] | None:
        """Find the platform with the highest net sell price.

        Args:
            item_name: Item name
            game: Game ID

        Returns:
            Tuple of (platform, net_price) or None

        """
        prices = await self.get_prices(item_name, game)
        best = prices.best_sell

        if best:
            return (best.platform, best.net_price_after_sell)
        return None


# Factory function
def create_aggregator(
    dmarket_api: DMarketAPI | None = None,
    waxpeer_api: WaxpeerAPI | None = None,
) -> MultiPlatformAggregator:
    """Create a multi-platform aggregator instance."""
    return MultiPlatformAggregator(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
    )
