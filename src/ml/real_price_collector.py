"""
Real Price Collector Module.

Async collector for real market prices from DMarket, Waxpeer, and Steam APIs.
Integrates with PriceNormalizer for unified price representation.

Version: 1.0.0
Created: January 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

from src.ml.price_normalizer import (
    NormalizedPrice,
    PriceNormalizer,
    PriceSource,
)

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI

logger = structlog.get_logger(__name__)


class CollectionStatus(Enum):
    """Status of price collection operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NO_DATA = "no_data"


class GameType(Enum):
    """Supported game types for price collection."""

    CSGO = "csgo"
    CS2 = "cs2"
    DOTA2 = "dota2"
    TF2 = "tf2"
    RUST = "rust"

    @property
    def dmarket_id(self) -> str:
        """Get DMarket game ID."""
        mapping = {
            GameType.CSGO: "a8db",
            GameType.CS2: "a8db",
            GameType.DOTA2: "9a92",
            GameType.TF2: "tf2",
            GameType.RUST: "rust",
        }
        return mapping[self]

    @property
    def waxpeer_name(self) -> str:
        """Get Waxpeer game name."""
        mapping = {
            GameType.CSGO: "csgo",
            GameType.CS2: "cs2",
            GameType.DOTA2: "dota2",
            GameType.TF2: "tf2",
            GameType.RUST: "rust",
        }
        return mapping[self]

    @property
    def steam_app_id(self) -> int:
        """Get Steam App ID."""
        mapping = {
            GameType.CSGO: 730,
            GameType.CS2: 730,
            GameType.DOTA2: 570,
            GameType.TF2: 440,
            GameType.RUST: 252490,
        }
        return mapping[self]


@dataclass
class CollectedPrice:
    """A collected price from a specific platform."""

    item_name: str
    normalized_price: NormalizedPrice
    game: GameType
    additional_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionResult:
    """Result of a price collection operation."""

    status: CollectionStatus
    source: PriceSource
    game: GameType
    prices: list[CollectedPrice] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    items_requested: int = 0
    items_collected: int = 0
    error_message: str | None = None
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate collection success rate."""
        if self.items_requested == 0:
            return 0.0
        return self.items_collected / self.items_requested

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "source": self.source.value,
            "game": self.game.value,
            "collected_at": self.collected_at.isoformat(),
            "items_requested": self.items_requested,
            "items_collected": self.items_collected,
            "success_rate": self.success_rate,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class MultiSourceResult:
    """Result of collecting prices from multiple sources."""

    results: list[CollectionResult] = field(default_factory=list)
    all_prices: list[CollectedPrice] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def total_items(self) -> int:
        """Get total number of collected items."""
        return len(self.all_prices)

    @property
    def total_duration(self) -> float:
        """Get total collection duration in seconds."""
        if self.completed_at is None:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success_count(self) -> int:
        """Count successful collections."""
        return sum(1 for r in self.results if r.status == CollectionStatus.SUCCESS)

    def get_prices_by_source(self, source: PriceSource) -> list[CollectedPrice]:
        """Get prices from a specific source."""
        return [p for p in self.all_prices if p.normalized_price.source == source]

    def get_prices_by_item(self, item_name: str) -> list[CollectedPrice]:
        """Get all prices for a specific item across sources."""
        return [p for p in self.all_prices if p.item_name.lower() == item_name.lower()]


class RealPriceCollector:
    """
    Async collector for real market prices from multiple platforms.

    Integrates with DMarket, Waxpeer, and Steam APIs to collect
    real-time price data for ML training.

    Features:
        - Async price collection from multiple sources
        - Automatic price normalization via PriceNormalizer
        - Rate limiting awareness
        - Error handling and retries
        - Batch collection support

    Example:
        ```python
        collector = RealPriceCollector(
            dmarket_api=dmarket_client,
            waxpeer_api=waxpeer_client,
        )

        # Collect prices for specific items
        result = await collector.collect_all(
            item_names=["AK-47 | Redline (Field-Tested)"],
            game=GameType.CSGO,
        )

        # Access normalized prices
        for price in result.all_prices:
            print(f"{price.item_name}: ${price.normalized_price.price_usd}")
        ```
    """

    # Default timeout for API calls (seconds)
    DEFAULT_TIMEOUT: float = 30.0

    # Maximum items per batch request
    MAX_BATCH_SIZE: int = 100

    # Retry configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    def __init__(
        self,
        dmarket_api: DMarketAPI | None = None,
        waxpeer_api: WaxpeerAPI | None = None,
        normalizer: PriceNormalizer | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize RealPriceCollector.

        Args:
            dmarket_api: DMarket API client instance
            waxpeer_api: Waxpeer API client instance
            normalizer: Price normalizer (created if not provided)
            timeout: Timeout for API calls in seconds
        """
        self.dmarket_api = dmarket_api
        self.waxpeer_api = waxpeer_api
        self.normalizer = normalizer or PriceNormalizer()
        self.timeout = timeout

        self._collection_stats: dict[str, int] = {
            "dmarket_calls": 0,
            "waxpeer_calls": 0,
            "steam_calls": 0,
            "total_items_collected": 0,
            "total_errors": 0,
        }

        logger.info(
            "real_price_collector_initialized",
            has_dmarket=dmarket_api is not None,
            has_waxpeer=waxpeer_api is not None,
            timeout=timeout,
        )

    async def collect_from_dmarket(
        self,
        item_names: list[str],
        game: GameType,
    ) -> CollectionResult:
        """
        Collect prices from DMarket API.

        Args:
            item_names: List of item names to collect prices for
            game: Game type

        Returns:
            CollectionResult with collected prices
        """
        start_time = datetime.now(UTC)
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.DMARKET,
            game=game,
            items_requested=len(item_names),
        )

        if not self.dmarket_api:
            result.status = CollectionStatus.FAILED
            result.error_message = "DMarket API client not configured"
            logger.warning("dmarket_collection_skipped", reason="no_api_client")
            return result

        try:
            prices: list[CollectedPrice] = []

            # Use aggregated prices endpoint for efficiency
            if hasattr(self.dmarket_api, "get_aggregated_prices"):
                response = await asyncio.wait_for(
                    self.dmarket_api.get_aggregated_prices(
                        game=game.dmarket_id,
                        titles=item_names,
                    ),
                    timeout=self.timeout,
                )

                aggregated = response.get("aggregatedPrices", [])
                for item_data in aggregated:
                    title = item_data.get("title", "")
                    offer_price = item_data.get("offerBestPrice")

                    if offer_price is not None:
                        # DMarket returns prices in cents
                        price_cents = int(offer_price)
                        normalized = self.normalizer.normalize(
                            price=Decimal(price_cents),
                            source=PriceSource.DMARKET,
                            item_name=title,
                            game=game.value,
                        )

                        prices.append(
                            CollectedPrice(
                                item_name=title,
                                normalized_price=normalized,
                                game=game,
                                additional_data={
                                    "order_best_price": item_data.get("orderBestPrice"),
                                    "order_count": item_data.get("orderCount", 0),
                                    "offer_count": item_data.get("offerCount", 0),
                                },
                            )
                        )

            # Fallback: collect individual prices
            else:
                for name in item_names:
                    try:
                        item_response = await asyncio.wait_for(
                            self.dmarket_api.get_market_items(
                                game=game.dmarket_id,
                                title=name,
                                limit=1,
                            ),
                            timeout=self.timeout,
                        )

                        items = item_response.get("objects", [])
                        if items:
                            item = items[0]
                            price_data = item.get("price", {})
                            price_cents = int(price_data.get("USD", 0))

                            if price_cents > 0:
                                normalized = self.normalizer.normalize(
                                    price=Decimal(price_cents),
                                    source=PriceSource.DMARKET,
                                    item_name=name,
                                    game=game.value,
                                )

                                prices.append(
                                    CollectedPrice(
                                        item_name=name,
                                        normalized_price=normalized,
                                        game=game,
                                        additional_data={
                                            "item_id": item.get("itemId"),
                                            "suggested_price": item.get(
                                                "suggestedPrice", {}
                                            ).get("USD"),
                                        },
                                    )
                                )
                    except TimeoutError:
                        logger.warning(
                            "dmarket_item_timeout",
                            item_name=name,
                        )
                    except Exception as e:
                        logger.warning(
                            "dmarket_item_error",
                            item_name=name,
                            error=str(e),
                        )

            result.prices = prices
            result.items_collected = len(prices)
            result.status = (
                CollectionStatus.SUCCESS
                if prices
                else CollectionStatus.NO_DATA
            )

            self._collection_stats["dmarket_calls"] += 1
            self._collection_stats["total_items_collected"] += len(prices)

            logger.info(
                "dmarket_collection_complete",
                game=game.value,
                items_requested=len(item_names),
                items_collected=len(prices),
            )

        except TimeoutError:
            result.status = CollectionStatus.TIMEOUT
            result.error_message = f"Request timed out after {self.timeout}s"
            self._collection_stats["total_errors"] += 1
            logger.error("dmarket_collection_timeout", game=game.value)

        except Exception as e:
            result.status = CollectionStatus.FAILED
            result.error_message = str(e)
            self._collection_stats["total_errors"] += 1
            logger.error(
                "dmarket_collection_error",
                game=game.value,
                error=str(e),
            )

        result.duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()
        return result

    async def collect_from_waxpeer(
        self,
        item_names: list[str],
        game: GameType,
    ) -> CollectionResult:
        """
        Collect prices from Waxpeer API.

        Args:
            item_names: List of item names to collect prices for
            game: Game type

        Returns:
            CollectionResult with collected prices
        """
        start_time = datetime.now(UTC)
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.WAXPEER,
            game=game,
            items_requested=len(item_names),
        )

        if not self.waxpeer_api:
            result.status = CollectionStatus.FAILED
            result.error_message = "Waxpeer API client not configured"
            logger.warning("waxpeer_collection_skipped", reason="no_api_client")
            return result

        try:
            prices: list[CollectedPrice] = []

            # Use bulk prices for efficiency if available
            if hasattr(self.waxpeer_api, "get_market_prices"):
                response = await asyncio.wait_for(
                    self.waxpeer_api.get_market_prices(
                        item_names=item_names,
                        game=game.waxpeer_name,
                    ),
                    timeout=self.timeout,
                )

                for name, price_info in response.items():
                    if price_info and price_info.get("price"):
                        # Waxpeer returns prices in mils (1 USD = 1000 mils)
                        price_mils = int(price_info["price"])
                        normalized = self.normalizer.normalize(
                            price=Decimal(price_mils),
                            source=PriceSource.WAXPEER,
                            item_name=name,
                            game=game.value,
                        )

                        prices.append(
                            CollectedPrice(
                                item_name=name,
                                normalized_price=normalized,
                                game=game,
                                additional_data={
                                    "count": price_info.get("count", 0),
                                    "avg_price": price_info.get("avg"),
                                    "min_price": price_info.get("min"),
                                    "max_price": price_info.get("max"),
                                },
                            )
                        )

            # Fallback: use get_item_price for individual items
            elif hasattr(self.waxpeer_api, "get_item_price"):
                for name in item_names:
                    try:
                        price_usd = await asyncio.wait_for(
                            self.waxpeer_api.get_item_price(name),
                            timeout=self.timeout,
                        )

                        if price_usd and price_usd > 0:
                            # Convert USD back to mils for normalization
                            price_mils = int(price_usd * 1000)
                            normalized = self.normalizer.normalize(
                                price=Decimal(price_mils),
                                source=PriceSource.WAXPEER,
                                item_name=name,
                                game=game.value,
                            )

                            prices.append(
                                CollectedPrice(
                                    item_name=name,
                                    normalized_price=normalized,
                                    game=game,
                                )
                            )
                    except TimeoutError:
                        logger.warning("waxpeer_item_timeout", item_name=name)
                    except Exception as e:
                        logger.warning(
                            "waxpeer_item_error",
                            item_name=name,
                            error=str(e),
                        )

            result.prices = prices
            result.items_collected = len(prices)
            result.status = (
                CollectionStatus.SUCCESS
                if prices
                else CollectionStatus.NO_DATA
            )

            self._collection_stats["waxpeer_calls"] += 1
            self._collection_stats["total_items_collected"] += len(prices)

            logger.info(
                "waxpeer_collection_complete",
                game=game.value,
                items_requested=len(item_names),
                items_collected=len(prices),
            )

        except TimeoutError:
            result.status = CollectionStatus.TIMEOUT
            result.error_message = f"Request timed out after {self.timeout}s"
            self._collection_stats["total_errors"] += 1
            logger.error("waxpeer_collection_timeout", game=game.value)

        except Exception as e:
            result.status = CollectionStatus.FAILED
            result.error_message = str(e)
            self._collection_stats["total_errors"] += 1
            logger.error(
                "waxpeer_collection_error",
                game=game.value,
                error=str(e),
            )

        result.duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()
        return result

    async def collect_from_steam(
        self,
        item_names: list[str],
        game: GameType,
    ) -> CollectionResult:
        """
        Collect prices from Steam Market API.

        Note: Steam API requires slower rate limiting (3 req/min recommended).

        Args:
            item_names: List of item names to collect prices for
            game: Game type

        Returns:
            CollectionResult with collected prices
        """
        start_time = datetime.now(UTC)
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.STEAM,
            game=game,
            items_requested=len(item_names),
        )

        try:
            # Import Steam API if available
            try:
                from src.dmarket.steam_api import SteamMarketAPI
            except ImportError:
                result.status = CollectionStatus.FAILED
                result.error_message = "Steam API module not available"
                logger.warning("steam_collection_skipped", reason="module_not_found")
                return result

            prices: list[CollectedPrice] = []
            steam_api = SteamMarketAPI()

            for name in item_names:
                try:
                    # Steam API rate limit: ~20 requests/minute
                    price_info = await asyncio.wait_for(
                        steam_api.get_item_price(
                            app_id=game.steam_app_id,
                            market_hash_name=name,
                        ),
                        timeout=self.timeout,
                    )

                    if price_info and price_info.get("lowest_price"):
                        # Steam returns prices in USD as strings like "$12.34"
                        price_str = price_info["lowest_price"]
                        # Parse price string
                        price_usd = self._parse_steam_price(price_str)

                        if price_usd > 0:
                            normalized = self.normalizer.normalize(
                                price=Decimal(str(price_usd)),
                                source=PriceSource.STEAM,
                                item_name=name,
                                game=game.value,
                            )

                            prices.append(
                                CollectedPrice(
                                    item_name=name,
                                    normalized_price=normalized,
                                    game=game,
                                    additional_data={
                                        "median_price": price_info.get("median_price"),
                                        "volume": price_info.get("volume"),
                                    },
                                )
                            )

                    # Rate limiting for Steam
                    await asyncio.sleep(3.0)

                except TimeoutError:
                    logger.warning("steam_item_timeout", item_name=name)
                except Exception as e:
                    logger.warning(
                        "steam_item_error",
                        item_name=name,
                        error=str(e),
                    )

            result.prices = prices
            result.items_collected = len(prices)
            result.status = (
                CollectionStatus.SUCCESS
                if prices
                else CollectionStatus.NO_DATA
            )

            self._collection_stats["steam_calls"] += 1
            self._collection_stats["total_items_collected"] += len(prices)

            logger.info(
                "steam_collection_complete",
                game=game.value,
                items_requested=len(item_names),
                items_collected=len(prices),
            )

        except Exception as e:
            result.status = CollectionStatus.FAILED
            result.error_message = str(e)
            self._collection_stats["total_errors"] += 1
            logger.error(
                "steam_collection_error",
                game=game.value,
                error=str(e),
            )

        result.duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()
        return result

    def _parse_steam_price(self, price_str: str) -> float:
        """
        Parse Steam price string to float.

        Handles formats like "$12.34", "€10,50", "12,34 USD", etc.

        Args:
            price_str: Price string from Steam API

        Returns:
            Price as float in USD
        """
        import re

        if not price_str:
            return 0.0

        # Remove currency symbols and normalize
        cleaned = re.sub(r"[^\d.,]", "", price_str)

        # Handle European format (comma as decimal separator)
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned and "." in cleaned:
            # Remove thousand separator
            cleaned = cleaned.replace(",", "")

        try:
            return float(cleaned)
        except ValueError:
            logger.warning("steam_price_parse_error", price_str=price_str)
            return 0.0

    async def collect_all(
        self,
        item_names: list[str],
        game: GameType,
        sources: list[PriceSource] | None = None,
        parallel: bool = True,
    ) -> MultiSourceResult:
        """
        Collect prices from all configured sources.

        Args:
            item_names: List of item names to collect prices for
            game: Game type
            sources: Specific sources to collect from (default: all available)
            parallel: Whether to collect from sources in parallel

        Returns:
            MultiSourceResult with all collected prices
        """
        result = MultiSourceResult()

        # Determine which sources to use
        if sources is None:
            sources = []
            if self.dmarket_api:
                sources.append(PriceSource.DMARKET)
            if self.waxpeer_api:
                sources.append(PriceSource.WAXPEER)
            # Steam is always available (no API key required for market prices)
            sources.append(PriceSource.STEAM)

        if not sources:
            logger.warning("no_sources_available")
            return result

        logger.info(
            "collecting_prices",
            items_count=len(item_names),
            game=game.value,
            sources=[s.value for s in sources],
            parallel=parallel,
        )

        # Collect from each source
        if parallel:
            tasks = []
            for source in sources:
                if source == PriceSource.DMARKET:
                    tasks.append(self.collect_from_dmarket(item_names, game))
                elif source == PriceSource.WAXPEER:
                    tasks.append(self.collect_from_waxpeer(item_names, game))
                elif source == PriceSource.STEAM:
                    tasks.append(self.collect_from_steam(item_names, game))

            collection_results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in collection_results:
                if isinstance(res, Exception):
                    logger.error("collection_task_error", error=str(res))
                elif isinstance(res, CollectionResult):
                    result.results.append(res)
                    result.all_prices.extend(res.prices)

        else:
            # Sequential collection
            for source in sources:
                try:
                    if source == PriceSource.DMARKET:
                        res = await self.collect_from_dmarket(item_names, game)
                    elif source == PriceSource.WAXPEER:
                        res = await self.collect_from_waxpeer(item_names, game)
                    elif source == PriceSource.STEAM:
                        res = await self.collect_from_steam(item_names, game)
                    else:
                        continue

                    result.results.append(res)
                    result.all_prices.extend(res.prices)

                except Exception as e:
                    logger.error(
                        "collection_error",
                        source=source.value,
                        error=str(e),
                    )

        result.completed_at = datetime.now(UTC)

        logger.info(
            "collection_complete",
            total_items=result.total_items,
            sources_succeeded=result.success_count,
            duration=result.total_duration,
        )

        return result

    async def collect_bulk_prices(
        self,
        game: GameType,
        limit: int = 1000,
    ) -> MultiSourceResult:
        """
        Collect bulk prices for a game without specifying item names.

        Uses platform-specific bulk endpoints for efficiency.

        Args:
            game: Game type
            limit: Maximum number of items to collect

        Returns:
            MultiSourceResult with collected prices
        """
        result = MultiSourceResult()

        # Collect from DMarket bulk
        if self.dmarket_api:
            try:
                dm_result = await self._collect_dmarket_bulk(game, limit)
                result.results.append(dm_result)
                result.all_prices.extend(dm_result.prices)
            except Exception as e:
                logger.error("dmarket_bulk_error", error=str(e))

        # Collect from Waxpeer bulk
        if self.waxpeer_api and hasattr(self.waxpeer_api, "get_bulk_prices"):
            try:
                wp_result = await self._collect_waxpeer_bulk(game, limit)
                result.results.append(wp_result)
                result.all_prices.extend(wp_result.prices)
            except Exception as e:
                logger.error("waxpeer_bulk_error", error=str(e))

        result.completed_at = datetime.now(UTC)
        return result

    async def _collect_dmarket_bulk(
        self,
        game: GameType,
        limit: int,
    ) -> CollectionResult:
        """Collect bulk prices from DMarket."""
        start_time = datetime.now(UTC)
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.DMARKET,
            game=game,
            items_requested=limit,
        )

        try:
            response = await asyncio.wait_for(
                self.dmarket_api.get_market_items(
                    game=game.dmarket_id,
                    limit=min(limit, 100),  # DMarket max is 100
                ),
                timeout=self.timeout,
            )

            prices: list[CollectedPrice] = []
            for item in response.get("objects", []):
                title = item.get("title", "")
                price_data = item.get("price", {})
                price_cents = int(price_data.get("USD", 0))

                if price_cents > 0:
                    normalized = self.normalizer.normalize(
                        price=Decimal(price_cents),
                        source=PriceSource.DMARKET,
                        item_name=title,
                        game=game.value,
                    )

                    prices.append(
                        CollectedPrice(
                            item_name=title,
                            normalized_price=normalized,
                            game=game,
                            additional_data={
                                "item_id": item.get("itemId"),
                            },
                        )
                    )

            result.prices = prices
            result.items_collected = len(prices)
            result.status = CollectionStatus.SUCCESS if prices else CollectionStatus.NO_DATA

        except Exception as e:
            result.status = CollectionStatus.FAILED
            result.error_message = str(e)

        result.duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()
        return result

    async def _collect_waxpeer_bulk(
        self,
        game: GameType,
        limit: int,
    ) -> CollectionResult:
        """Collect bulk prices from Waxpeer."""
        start_time = datetime.now(UTC)
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.WAXPEER,
            game=game,
            items_requested=limit,
        )

        try:
            response = await asyncio.wait_for(
                self.waxpeer_api.get_bulk_prices(game=game.waxpeer_name),
                timeout=self.timeout,
            )

            prices: list[CollectedPrice] = []
            count = 0

            for name, price_mils in response.items():
                if count >= limit:
                    break

                if price_mils and price_mils > 0:
                    normalized = self.normalizer.normalize(
                        price=Decimal(price_mils),
                        source=PriceSource.WAXPEER,
                        item_name=name,
                        game=game.value,
                    )

                    prices.append(
                        CollectedPrice(
                            item_name=name,
                            normalized_price=normalized,
                            game=game,
                        )
                    )
                    count += 1

            result.prices = prices
            result.items_collected = len(prices)
            result.status = CollectionStatus.SUCCESS if prices else CollectionStatus.NO_DATA

        except Exception as e:
            result.status = CollectionStatus.FAILED
            result.error_message = str(e)

        result.duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()
        return result

    def get_statistics(self) -> dict[str, Any]:
        """
        Get collection statistics.

        Returns:
            Dictionary with collection stats
        """
        return {
            **self._collection_stats,
            "normalizer_stats": self.normalizer.get_statistics(),
        }

    def reset_statistics(self) -> None:
        """Reset collection statistics."""
        self._collection_stats = {
            "dmarket_calls": 0,
            "waxpeer_calls": 0,
            "steam_calls": 0,
            "total_items_collected": 0,
            "total_errors": 0,
        }
        self.normalizer.reset_statistics()


# Convenience function for one-off collection
async def collect_prices(
    item_names: list[str],
    game: str | GameType,
    dmarket_api: DMarketAPI | None = None,
    waxpeer_api: WaxpeerAPI | None = None,
) -> MultiSourceResult:
    """
    Convenience function to collect prices from all available sources.

    Args:
        item_names: List of item names
        game: Game type (string or GameType enum)
        dmarket_api: Optional DMarket API client
        waxpeer_api: Optional Waxpeer API client

    Returns:
        MultiSourceResult with collected prices
    """
    if isinstance(game, str):
        game = GameType(game.lower())

    collector = RealPriceCollector(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
    )

    return await collector.collect_all(item_names, game)
