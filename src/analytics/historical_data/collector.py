"""
collector.py — Orchestrator: cache + per-source fan-out + batch API.

`HistoricalDataCollector` ties the source collectors together and adds
an in-memory TTL cache keyed by `game:title:days`. It also exposes a
`collect_batch` helper that fans out across titles and a `clear_cache`
+ `get_cache_stats` pair for the admin tooling (Telegram, CLI).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .models import PriceHistory
from .sources import collect_from_aggregated, collect_from_sales_history

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


class HistoricalDataCollector:
    """Collector for historical price data from DMarket.

    Fetches and stores price history for backtesting analysis.

    Attributes:
        api: DMarket API client
        cache: In-memory cache for recent queries
    """

    def __init__(
        self,
        api: "IDMarketAPI",
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

        points: list = []

        try:
            # Collect from sales history
            sales_points = await collect_from_sales_history(
                self.api, game, title, days
            )
            points.extend(sales_points)

            # Collect from aggregated prices
            agg_points = await collect_from_aggregated(self.api, game, title)
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


__all__ = ["HistoricalDataCollector"]
