"""
collector.py — Orchestrator: cache + per-source fan-out.

`HistoricalDataCollector` ties the source collectors together and adds
an in-memory TTL cache keyed by `game:title:days`.

v15.2: Uses cachetools.TTLCache for O(1) eviction instead of manual dict.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from cachetools import TTLCache

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
        api: IDMarketAPI,
        cache_ttl_minutes: int = 60,
    ) -> None:
        """Initialize collector.

        Args:
            api: DMarket API client
            cache_ttl_minutes: Cache TTL in minutes
        """
        self.api = api
        # v15.2: cachetools.TTLCache — automatic TTL expiration, O(1) eviction
        self._cache: TTLCache[str, PriceHistory] = TTLCache(
            maxsize=1000, ttl=cache_ttl_minutes * 60
        )

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

        # v15.2: cachetools handles TTL automatically
        if use_cache and cache_key in self._cache:
            logger.debug("cache_hit", extra={"key": cache_key})
            return self._cache[cache_key]

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

        # v15.2: cachetools handles TTL automatically
        self._cache[cache_key] = history

        logger.info(
            "price_history_collected",
            extra={
                "game": game,
                "title": title,
                "points_count": len(points),
            },
        )

        return history


__all__ = ["HistoricalDataCollector"]
