"""Historical data collection and storage for backtesting.

Collects price history from DMarket API and stores it for backtesting analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """A single price point in historical data.

    Attributes:
        game: Game code (csgo, dota2, etc.)
        title: Item name
        price: Price in USD
        volume: Number of sales (if available)
        timestamp: When this price was recorded
        source: Data source (market, sales_history, aggregated)
    """

    game: str
    title: str
    price: Decimal
    timestamp: datetime
    volume: int = 0
    source: str = "market"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "game": self.game,
            "title": self.title,
            "price": float(self.price),
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PricePoint:
        """Create from dictionary."""
        return cls(
            game=data["game"],
            title=data["title"],
            price=Decimal(str(data["price"])),
            volume=data.get("volume", 0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "market"),
        )


@dataclass
class PriceHistory:
    """Historical price data for an item.

    Attributes:
        game: Game code
        title: Item name
        points: List of price points sorted by timestamp
        collected_at: When this history was collected
    """

    game: str
    title: str
    points: list[PricePoint] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def average_price(self) -> Decimal:
        """Calculate average price across all points."""
        if not self.points:
            return Decimal(0)
        return Decimal(sum(p.price for p in self.points)) / Decimal(len(self.points))

    @property
    def min_price(self) -> Decimal:
        """Get minimum price."""
        if not self.points:
            return Decimal(0)
        return min(p.price for p in self.points)

    @property
    def max_price(self) -> Decimal:
        """Get maximum price."""
        if not self.points:
            return Decimal(0)
        return max(p.price for p in self.points)

    @property
    def total_volume(self) -> int:
        """Get total volume across all points."""
        return sum(p.volume for p in self.points)

    @property
    def price_volatility(self) -> float:
        """Calculate price volatility (standard deviation / mean)."""
        if len(self.points) < 2:
            return 0.0

        prices = [float(p.price) for p in self.points]
        mean = sum(prices) / len(prices)
        if mean == 0:
            return 0.0

        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5
        return float(std_dev / mean)


class HistoricalDataCollector:
    """Collector for historical price data from DMarket.

    Fetches and stores price history for backtesting analysis.

    Attributes:
        api: DMarket API client
        cache: In-memory cache for recent queries
    """

    def __init__(
        self,
        api: IDMarketAPI,
        cache_ttl_minutes: int = 60,
    ) -> None:
        """Initialize collector.

        Args:
            api: DMarket API client
            cache_ttl_minutes: Cache TTL in minutes
        """
        self.api = api
        self._cache: dict[str, tuple[datetime, PriceHistory]] = {}
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)

    async def collect_price_history(
        self,
        game: str,
        title: str,
        days: int = 30,
        use_cache: bool = True,
    ) -> PriceHistory:
        """Collect price history for an item.

        Args:
            game: Game code (csgo, dota2, tf2, rust)
            title: Item name
            days: Number of days of history to collect
            use_cache: Whether to use cached data

        Returns:
            PriceHistory object with collected data
        """
        cache_key = f"{game}:{title}:{days}"

        # Check cache
        if use_cache and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if datetime.now(UTC) - cached_time < self._cache_ttl:
                logger.debug("cache_hit", extra={"key": cache_key})
                return cached_data

        logger.info(
            "collecting_price_history",
            extra={"game": game, "title": title, "days": days},
        )

        points: list[PricePoint] = []

        try:
            # Collect from sales history
            sales_points = await self._collect_from_sales_history(game, title, days)
            points.extend(sales_points)

            # Collect from aggregated prices
            agg_points = await self._collect_from_aggregated(game, title)
            points.extend(agg_points)

            # Sort by timestamp
            points.sort(key=lambda p: p.timestamp)

        except Exception as e:
            logger.warning(
                "price_history_collection_error",
                extra={"game": game, "title": title, "error": str(e)},
            )

        history = PriceHistory(
            game=game,
            title=title,
            points=points,
        )

        # Update cache
        self._cache[cache_key] = (datetime.now(UTC), history)

        logger.info(
            "price_history_collected",
            extra={
                "game": game,
                "title": title,
                "points_count": len(points),
            },
        )

        return history

    async def _collect_from_sales_history(
        self,
        game: str,
        title: str,
        days: int,
    ) -> list[PricePoint]:
        """Collect price points from sales history.

        Args:
            game: Game code
            title: Item name
            days: Number of days

        Returns:
            List of PricePoints from sales history
        """
        points: list[PricePoint] = []

        try:
            # Get sales history from API
            history = await self.api.get_sales_history(
                game=game,
                title=title,
                period=f"{days}d",
            )

            if "sales" in history:
                for sale in history["sales"]:
                    # Parse timestamp
                    ts_str = sale.get("date") or sale.get("timestamp")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(
                                ts_str.replace("Z", "+00:00")  # noqa: FURB162
                            )
                        except (ValueError, TypeError):
                            ts = datetime.now(UTC)
                    else:
                        ts = datetime.now(UTC)

                    # Parse price (cents to USD)
                    price_raw = sale.get("price", {})
                    if isinstance(price_raw, dict):
                        price_cents = int(
                            price_raw.get("USD", price_raw.get("amount", 0))
                        )
                    else:
                        price_cents = int(price_raw)

                    price_usd = Decimal(price_cents) / 100

                    points.append(
                        PricePoint(
                            game=game,
                            title=title,
                            price=price_usd,
                            timestamp=ts,
                            volume=1,
                            source="sales_history",
                        )
                    )

        except Exception as e:
            logger.debug(
                "sales_history_fetch_error",
                extra={"error": str(e)},
            )

        return points

    async def _collect_from_aggregated(
        self,
        game: str,
        title: str,
    ) -> list[PricePoint]:
        """Collect price points from aggregated prices.

        Args:
            game: Game code
            title: Item name

        Returns:
            List of PricePoints from aggregated data
        """
        points: list[PricePoint] = []

        try:
            # Get aggregated prices
            aggregated = await self.api.get_aggregated_prices_bulk(
                game=game,
                titles=[title],
                limit=1,
            )

            if aggregated and "aggregatedPrices" in aggregated:
                for price_data in aggregated["aggregatedPrices"]:
                    if price_data.get("title") == title:
                        # Best offer price
                        offer_price = int(price_data.get("offerBestPrice", 0))
                        if offer_price > 0:
                            points.append(
                                PricePoint(
                                    game=game,
                                    title=title,
                                    price=Decimal(offer_price) / 100,
                                    timestamp=datetime.now(UTC),
                                    source="aggregated_offer",
                                )
                            )

                        # Best order price (buy orders)
                        order_price = int(price_data.get("orderBestPrice", 0))
                        if order_price > 0:
                            points.append(
                                PricePoint(
                                    game=game,
                                    title=title,
                                    price=Decimal(order_price) / 100,
                                    timestamp=datetime.now(UTC),
                                    source="aggregated_order",
                                )
                            )

        except Exception as e:
            logger.debug(
                "aggregated_prices_fetch_error",
                extra={"error": str(e)},
            )

        return points

    async def collect_batch(
        self,
        game: str,
        titles: list[str],
        days: int = 30,
    ) -> dict[str, PriceHistory]:
        """Collect price history for multiple items.

        Args:
            game: Game code
            titles: List of item names
            days: Number of days

        Returns:
            Dictionary mapping title -> PriceHistory
        """
        results: dict[str, PriceHistory] = {}

        for title in titles:
            try:
                history = await self.collect_price_history(game, title, days)
                results[title] = history
            except Exception as e:
                logger.warning(
                    "batch_collect_error",
                    extra={"title": title, "error": str(e)},
                )

        return results

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.info("cache_cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        now = datetime.now(UTC)
        valid_count = sum(
            1 for ts, _ in self._cache.values() if now - ts < self._cache_ttl
        )

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "ttl_minutes": self._cache_ttl.total_seconds() / 60,
        }


__all__ = [
    "HistoricalDataCollector",
    "PriceHistory",
    "PricePoint",
]
