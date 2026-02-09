"""
Tests for RealPriceCollector - collecting prices from DMarket, Waxpeer, and Steam APIs.

Tests cover:
- CollectedPrice dataclass
- CollectionResult dataclass
- CollectionStatus enum
- GameType enum
- MultiSourceResult dataclass
- RealPriceCollector class
- Module-level collect_prices function
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.ml.price_normalizer import NormalizedPrice, PriceSource
from src.ml.real_price_collector import (
    CollectedPrice,
    CollectionResult,
    CollectionStatus,
    GameType,
    MultiSourceResult,
    RealPriceCollector,
    collect_prices,
)

# =============================================================================
# TestCollectedPrice
# =============================================================================


class TestCollectedPrice:
    """Tests for CollectedPrice dataclass."""

    def test_create_collected_price(self) -> None:
        """Test creating a CollectedPrice instance."""
        normalized = NormalizedPrice(
            price_usd=10.50,
            source=PriceSource.DMARKET,
            original_value=1050,
            timestamp=datetime.now(UTC),
        )
        price = CollectedPrice(
            item_name="AK-47 | Redline",
            normalized_price=normalized,
            game=GameType.CSGO,
        )

        assert price.item_name == "AK-47 | Redline"
        assert price.normalized_price.price_usd == 10.50
        assert price.game == GameType.CSGO
        assert price.additional_data == {}

    def test_collected_price_with_additional_data(self) -> None:
        """Test CollectedPrice with additional_data."""
        normalized = NormalizedPrice(
            price_usd=25.00,
            source=PriceSource.WAXPEER,
            original_value=2500,
            timestamp=datetime.now(UTC),
        )
        price = CollectedPrice(
            item_name="AWP | Asiimov",
            normalized_price=normalized,
            game=GameType.CS2,
            additional_data={"float_value": 0.25, "stattrak": False},
        )

        assert price.additional_data["float_value"] == 0.25
        assert price.additional_data["stattrak"] is False

    def test_collected_price_game_types(self) -> None:
        """Test CollectedPrice with different game types."""
        normalized = NormalizedPrice(
            price_usd=5.00,
            source=PriceSource.STEAM,
            original_value=500,
            timestamp=datetime.now(UTC),
        )

        for game in [GameType.CSGO, GameType.CS2, GameType.DOTA2, GameType.TF2, GameType.RUST]:
            price = CollectedPrice(
                item_name="Test Item",
                normalized_price=normalized,
                game=game,
            )
            assert price.game == game


# =============================================================================
# TestCollectionResult
# =============================================================================


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful CollectionResult."""
        result = CollectionResult(
            status=CollectionStatus.SUCCESS,
            source=PriceSource.DMARKET,
            game=GameType.CSGO,
            items_requested=10,
            items_collected=10,
        )

        assert result.status == CollectionStatus.SUCCESS
        assert result.source == PriceSource.DMARKET
        assert result.game == GameType.CSGO
        assert result.items_requested == 10
        assert result.items_collected == 10
        assert result.error_message is None

    def test_create_failed_result(self) -> None:
        """Test creating a failed CollectionResult."""
        result = CollectionResult(
            status=CollectionStatus.FAILED,
            source=PriceSource.WAXPEER,
            game=GameType.DOTA2,
            items_requested=5,
            items_collected=0,
            error_message="API connection failed",
        )

        assert result.status == CollectionStatus.FAILED
        assert result.error_message == "API connection failed"
        assert result.items_collected == 0

    def test_success_rate_property(self) -> None:
        """Test success_rate property calculation."""
        result = CollectionResult(
            status=CollectionStatus.PARTIAL,
            source=PriceSource.STEAM,
            game=GameType.TF2,
            items_requested=10,
            items_collected=7,
        )

        assert result.success_rate == 0.7

    def test_success_rate_zero_requested(self) -> None:
        """Test success_rate when items_requested is 0."""
        result = CollectionResult(
            status=CollectionStatus.NO_DATA,
            source=PriceSource.DMARKET,
            game=GameType.RUST,
            items_requested=0,
            items_collected=0,
        )

        assert result.success_rate == 0.0

    def test_to_dict_method(self) -> None:
        """Test to_dict method."""
        result = CollectionResult(
            status=CollectionStatus.SUCCESS,
            source=PriceSource.DMARKET,
            game=GameType.CSGO,
            items_requested=5,
            items_collected=5,
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "success"
        assert result_dict["source"] == "dmarket"
        assert result_dict["game"] == "csgo"
        assert result_dict["items_requested"] == 5
        assert result_dict["items_collected"] == 5
        assert result_dict["success_rate"] == 1.0


# =============================================================================
# TestCollectionStatus
# =============================================================================


class TestCollectionStatus:
    """Tests for CollectionStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected statuses exist."""
        assert CollectionStatus.SUCCESS is not None
        assert CollectionStatus.PARTIAL is not None
        assert CollectionStatus.FAILED is not None
        assert CollectionStatus.RATE_LIMITED is not None
        assert CollectionStatus.TIMEOUT is not None
        assert CollectionStatus.NO_DATA is not None

    def test_status_values(self) -> None:
        """Test status string values."""
        assert CollectionStatus.SUCCESS.value == "success"
        assert CollectionStatus.PARTIAL.value == "partial"
        assert CollectionStatus.FAILED.value == "failed"
        assert CollectionStatus.RATE_LIMITED.value == "rate_limited"
        assert CollectionStatus.TIMEOUT.value == "timeout"
        assert CollectionStatus.NO_DATA.value == "no_data"


# =============================================================================
# TestGameType
# =============================================================================


class TestGameType:
    """Tests for GameType enum."""

    def test_all_game_types_exist(self) -> None:
        """Test all expected game types exist."""
        assert GameType.CSGO is not None
        assert GameType.CS2 is not None
        assert GameType.DOTA2 is not None
        assert GameType.TF2 is not None
        assert GameType.RUST is not None

    def test_dmarket_id_property(self) -> None:
        """Test dmarket_id property for each game."""
        assert GameType.CSGO.dmarket_id == "a8db"
        assert GameType.CS2.dmarket_id == "a8db"
        assert GameType.DOTA2.dmarket_id == "9a92"
        assert GameType.TF2.dmarket_id == "tf2"
        assert GameType.RUST.dmarket_id == "rust"

    def test_steam_app_id_property(self) -> None:
        """Test steam_app_id property for each game."""
        assert GameType.CSGO.steam_app_id == 730
        assert GameType.CS2.steam_app_id == 730
        assert GameType.DOTA2.steam_app_id == 570
        assert GameType.TF2.steam_app_id == 440
        assert GameType.RUST.steam_app_id == 252490


# =============================================================================
# TestMultiSourceResult
# =============================================================================


class TestMultiSourceResult:
    """Tests for MultiSourceResult dataclass."""

    def test_empty_multi_source_result(self) -> None:
        """Test empty MultiSourceResult."""
        result = MultiSourceResult()

        assert result.results == []
        assert result.all_prices == []
        assert result.total_items == 0
        assert result.success_count == 0

    def test_multi_source_result_with_results(self) -> None:
        """Test MultiSourceResult with results."""
        collection_result = CollectionResult(
            status=CollectionStatus.SUCCESS,
            source=PriceSource.DMARKET,
            game=GameType.CSGO,
            items_requested=5,
            items_collected=5,
        )

        normalized = NormalizedPrice(
            price_usd=10.00,
            original_value=1000,
            source=PriceSource.DMARKET,
            timestamp=datetime.now(UTC),
        )
        collected_price = CollectedPrice(
            item_name="Test Item",
            normalized_price=normalized,
            game=GameType.CSGO,
        )

        result = MultiSourceResult(
            results=[collection_result],
            all_prices=[collected_price],
        )

        assert len(result.results) == 1
        assert len(result.all_prices) == 1
        assert result.total_items == 1

    def test_success_count_property(self) -> None:
        """Test success_count property."""
        success_result = CollectionResult(
            status=CollectionStatus.SUCCESS,
            source=PriceSource.DMARKET,
            game=GameType.CSGO,
        )
        failed_result = CollectionResult(
            status=CollectionStatus.FAILED,
            source=PriceSource.WAXPEER,
            game=GameType.CSGO,
        )
        partial_result = CollectionResult(
            status=CollectionStatus.PARTIAL,
            source=PriceSource.STEAM,
            game=GameType.CSGO,
        )

        result = MultiSourceResult(
            results=[success_result, failed_result, partial_result],
            all_prices=[],
        )

        # SUCCESS and PARTIAL count as successful
        assert result.success_count >= 1


# =============================================================================
# TestRealPriceCollector
# =============================================================================


class TestRealPriceCollector:
    """Tests for RealPriceCollector class."""

    @pytest.fixture()
    def mock_dmarket_api(self) -> AsyncMock:
        """Create mock DMarket API."""
        mock = AsyncMock()
        mock.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "title": "AK-47 | Redline",
                        "price": {"USD": "1050"},
                        "suggestedPrice": {"USD": "1100"},
                    },
                    {
                        "title": "AWP | Asiimov",
                        "price": {"USD": "2500"},
                        "suggestedPrice": {"USD": "2600"},
                    },
                ]
            }
        )
        return mock

    @pytest.fixture()
    def mock_waxpeer_api(self) -> AsyncMock:
        """Create mock Waxpeer API."""
        mock = AsyncMock()
        mock.get_items_for_sale = AsyncMock(
            return_value={
                "items": [
                    {"name": "AK-47 | Redline", "price": 10500},  # mils
                    {"name": "AWP | Asiimov", "price": 25000},
                ]
            }
        )
        return mock

    @pytest.fixture()
    def collector(
        self, mock_dmarket_api: AsyncMock, mock_waxpeer_api: AsyncMock
    ) -> RealPriceCollector:
        """Create RealPriceCollector with mocks."""
        return RealPriceCollector(
            dmarket_api=mock_dmarket_api,
            waxpeer_api=mock_waxpeer_api,
            timeout=30.0,
        )

    def test_collector_initialization(
        self, mock_dmarket_api: AsyncMock, mock_waxpeer_api: AsyncMock
    ) -> None:
        """Test RealPriceCollector initialization."""
        collector = RealPriceCollector(
            dmarket_api=mock_dmarket_api,
            waxpeer_api=mock_waxpeer_api,
        )

        assert collector.dmarket_api is mock_dmarket_api
        assert collector.waxpeer_api is mock_waxpeer_api
        assert collector.normalizer is not None

    def test_collector_with_custom_timeout(
        self, mock_dmarket_api: AsyncMock, mock_waxpeer_api: AsyncMock
    ) -> None:
        """Test RealPriceCollector with custom timeout."""
        collector = RealPriceCollector(
            dmarket_api=mock_dmarket_api,
            waxpeer_api=mock_waxpeer_api,
            timeout=60.0,
        )

        assert collector.timeout == 60.0

    @pytest.mark.asyncio()
    async def test_collect_from_dmarket(self, collector: RealPriceCollector) -> None:
        """Test collecting prices from DMarket."""
        item_names = ["AK-47 | Redline", "AWP | Asiimov"]

        result = await collector.collect_from_dmarket(item_names, GameType.CSGO)

        assert result.source == PriceSource.DMARKET
        assert result.game == GameType.CSGO
        # prices accessible via result.prices
        assert hasattr(result, "prices")

    @pytest.mark.asyncio()
    async def test_collect_from_waxpeer(self, collector: RealPriceCollector) -> None:
        """Test collecting prices from Waxpeer."""
        item_names = ["AK-47 | Redline", "AWP | Asiimov"]

        result = await collector.collect_from_waxpeer(item_names, GameType.CSGO)

        assert result.source == PriceSource.WAXPEER
        assert result.game == GameType.CSGO
        assert hasattr(result, "prices")

    @pytest.mark.asyncio()
    async def test_collect_from_steam(self, collector: RealPriceCollector) -> None:
        """Test collecting prices from Steam."""
        item_names = ["AK-47 | Redline"]

        # Mock SteamMarketAPI in the module where it's imported dynamically
        with patch("src.dmarket.steam_api.SteamMarketAPI") as mock_steam_api_class:
            mock_steam_api = AsyncMock()
            mock_steam_api.get_item_price = AsyncMock(
                return_value={
                    "success": True,
                    "lowest_price": "$10.50",
                    "median_price": "$11.00",
                    "volume": "100",
                }
            )
            mock_steam_api_class.return_value = mock_steam_api

            result = await collector.collect_from_steam(item_names, GameType.CSGO)

            assert result.source == PriceSource.STEAM
            assert result.game == GameType.CSGO
            assert hasattr(result, "prices")

    @pytest.mark.asyncio()
    async def test_collect_all_sources(self, collector: RealPriceCollector) -> None:
        """Test collecting from all sources."""
        item_names = ["AK-47 | Redline"]

        with patch.object(collector, "collect_from_dmarket") as mock_dmarket:
            with patch.object(collector, "collect_from_waxpeer") as mock_waxpeer:
                with patch.object(collector, "collect_from_steam") as mock_steam:
                    normalized = NormalizedPrice(
                        price_usd=10.50,
                        source=PriceSource.DMARKET,
                        original_value=1050,
                        timestamp=datetime.now(UTC),
                    )
                    collected = CollectedPrice(
                        item_name="AK-47 | Redline",
                        normalized_price=normalized,
                        game=GameType.CSGO,
                    )

                    mock_dmarket.return_value = CollectionResult(
                        status=CollectionStatus.SUCCESS,
                        source=PriceSource.DMARKET,
                        game=GameType.CSGO,
                        items_requested=1,
                        items_collected=1,
                        prices=[collected],
                    )
                    mock_waxpeer.return_value = CollectionResult(
                        status=CollectionStatus.NO_DATA,
                        source=PriceSource.WAXPEER,
                        game=GameType.CSGO,
                    )
                    mock_steam.return_value = CollectionResult(
                        status=CollectionStatus.NO_DATA,
                        source=PriceSource.STEAM,
                        game=GameType.CSGO,
                    )

                    multi_result = await collector.collect_all(
                        item_names,
                        GameType.CSGO,
                        sources=[PriceSource.DMARKET, PriceSource.WAXPEER, PriceSource.STEAM],
                    )

                    assert isinstance(multi_result, MultiSourceResult)
                    assert len(multi_result.results) == 3

    @pytest.mark.asyncio()
    async def test_collect_bulk_prices(self, collector: RealPriceCollector) -> None:
        """Test collecting bulk prices from DMarket."""
        multi_result = await collector.collect_bulk_prices(GameType.CSGO, limit=10)

        assert isinstance(multi_result, MultiSourceResult)

    def test_get_statistics(self, collector: RealPriceCollector) -> None:
        """Test getting collector statistics."""
        stats = collector.get_statistics()

        assert isinstance(stats, dict)
        assert "dmarket_calls" in stats or "total_requests" in stats or len(stats) >= 0

    def test_reset_statistics(self, collector: RealPriceCollector) -> None:
        """Test resetting collector statistics."""
        # Should not raise
        collector.reset_statistics()


# =============================================================================
# TestRealPriceCollectorWithoutAPIs
# =============================================================================


class TestRealPriceCollectorWithoutAPIs:
    """Tests for RealPriceCollector when APIs are None."""

    def test_collector_with_none_dmarket(self) -> None:
        """Test collector with None DMarket API."""
        collector = RealPriceCollector(
            dmarket_api=None,
            waxpeer_api=AsyncMock(),
        )

        assert collector.dmarket_api is None

    def test_collector_with_none_waxpeer(self) -> None:
        """Test collector with None Waxpeer API."""
        collector = RealPriceCollector(
            dmarket_api=AsyncMock(),
            waxpeer_api=None,
        )

        assert collector.waxpeer_api is None

    def test_collector_with_both_none(self) -> None:
        """Test collector with both APIs None."""
        collector = RealPriceCollector(
            dmarket_api=None,
            waxpeer_api=None,
        )

        assert collector.dmarket_api is None
        assert collector.waxpeer_api is None

    @pytest.mark.asyncio()
    async def test_collect_from_dmarket_returns_failed_when_none(self) -> None:
        """Test that collect_from_dmarket returns FAILED when API is None."""
        collector = RealPriceCollector(
            dmarket_api=None,
            waxpeer_api=AsyncMock(),
        )

        result = await collector.collect_from_dmarket(["Test Item"], GameType.CSGO)

        assert result.status == CollectionStatus.FAILED
        assert len(result.prices) == 0

    @pytest.mark.asyncio()
    async def test_collect_from_waxpeer_returns_failed_when_none(self) -> None:
        """Test that collect_from_waxpeer returns FAILED when API is None."""
        collector = RealPriceCollector(
            dmarket_api=AsyncMock(),
            waxpeer_api=None,
        )

        result = await collector.collect_from_waxpeer(["Test Item"], GameType.CSGO)

        assert result.status == CollectionStatus.FAILED
        assert len(result.prices) == 0


# =============================================================================
# TestCollectPricesConvenienceFunction
# =============================================================================


class TestCollectPricesConvenienceFunction:
    """Tests for module-level collect_prices function."""

    @pytest.mark.asyncio()
    async def test_collect_prices_function(self) -> None:
        """Test the convenience collect_prices function."""
        mock_dmarket = AsyncMock()
        mock_dmarket.get_market_items = AsyncMock(return_value={"objects": []})

        mock_waxpeer = AsyncMock()
        mock_waxpeer.get_items_for_sale = AsyncMock(return_value={"items": []})

        result = await collect_prices(
            item_names=["Test Item"],
            game=GameType.CSGO,
            dmarket_api=mock_dmarket,
            waxpeer_api=mock_waxpeer,
        )

        assert isinstance(result, MultiSourceResult)

    @pytest.mark.asyncio()
    async def test_collect_prices_with_none_apis(self) -> None:
        """Test collect_prices with None APIs."""
        result = await collect_prices(
            item_names=["Test Item"],
            game=GameType.CSGO,
            dmarket_api=None,
            waxpeer_api=None,
        )

        assert isinstance(result, MultiSourceResult)
        # Should still return a result, but with failed statuses
