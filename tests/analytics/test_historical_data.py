"""Tests for historical_data.py - Historical data collection and storage.

Phase 3 tests for achieving 80% coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analytics.historical_data import (
    HistoricalDataCollector,
    PriceHistory,
    PricePoint,
)

# ============================================================================
# PricePoint Tests
# ============================================================================


class TestPricePoint:
    """Tests for PricePoint dataclass."""

    def test_price_point_creation_basic(self):
        """Test basic PricePoint creation."""
        now = datetime.now(UTC)
        pp = PricePoint(
            game="csgo",
            title="AK-47 | Redline",
            price=Decimal("15.50"),
            timestamp=now,
        )
        assert pp.game == "csgo"
        assert pp.title == "AK-47 | Redline"
        assert pp.price == Decimal("15.50")
        assert pp.timestamp == now
        assert pp.volume == 0  # default
        assert pp.source == "market"  # default

    def test_price_point_creation_with_all_fields(self):
        """Test PricePoint creation with all fields."""
        now = datetime.now(UTC)
        pp = PricePoint(
            game="dota2",
            title="Dragonclaw Hook",
            price=Decimal("500.00"),
            timestamp=now,
            volume=10,
            source="sales_history",
        )
        assert pp.game == "dota2"
        assert pp.volume == 10
        assert pp.source == "sales_history"

    def test_price_point_to_dict(self):
        """Test PricePoint to_dict conversion."""
        now = datetime.now(UTC)
        pp = PricePoint(
            game="csgo",
            title="AWP | Asiimov",
            price=Decimal("45.99"),
            timestamp=now,
            volume=5,
            source="aggregated",
        )
        result = pp.to_dict()

        assert result["game"] == "csgo"
        assert result["title"] == "AWP | Asiimov"
        assert result["price"] == 45.99  # float conversion
        assert result["volume"] == 5
        assert result["timestamp"] == now.isoformat()
        assert result["source"] == "aggregated"

    def test_price_point_from_dict(self):
        """Test PricePoint from_dict creation."""
        now = datetime.now(UTC)
        data = {
            "game": "rust",
            "title": "AK47",
            "price": 25.50,
            "volume": 3,
            "timestamp": now.isoformat(),
            "source": "market",
        }
        pp = PricePoint.from_dict(data)

        assert pp.game == "rust"
        assert pp.title == "AK47"
        assert pp.price == Decimal("25.5")
        assert pp.volume == 3
        assert pp.source == "market"

    def test_price_point_from_dict_with_defaults(self):
        """Test PricePoint from_dict with missing optional fields."""
        now = datetime.now(UTC)
        data = {
            "game": "tf2",
            "title": "Mann Co. Supply Crate Key",
            "price": 2.50,
            "timestamp": now.isoformat(),
        }
        pp = PricePoint.from_dict(data)

        assert pp.volume == 0  # default
        assert pp.source == "market"  # default

    def test_price_point_roundtrip(self):
        """Test PricePoint to_dict and from_dict roundtrip."""
        now = datetime.now(UTC)
        original = PricePoint(
            game="csgo",
            title="Test Item",
            price=Decimal("99.99"),
            timestamp=now,
            volume=7,
            source="sales_history",
        )

        # Roundtrip
        data = original.to_dict()
        restored = PricePoint.from_dict(data)

        assert restored.game == original.game
        assert restored.title == original.title
        # Price comparison with float precision
        assert abs(float(restored.price) - float(original.price)) < 0.01
        assert restored.volume == original.volume
        assert restored.source == original.source


# ============================================================================
# PriceHistory Tests
# ============================================================================


class TestPriceHistory:
    """Tests for PriceHistory dataclass."""

    def test_price_history_creation_empty(self):
        """Test empty PriceHistory creation."""
        ph = PriceHistory(game="csgo", title="Test Item")

        assert ph.game == "csgo"
        assert ph.title == "Test Item"
        assert ph.points == []
        assert ph.collected_at is not None

    def test_price_history_creation_with_points(self):
        """Test PriceHistory creation with points."""
        now = datetime.now(UTC)
        points = [
            PricePoint(
                game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
            ),
            PricePoint(
                game="csgo", title="Item", price=Decimal("12.00"), timestamp=now
            ),
        ]

        ph = PriceHistory(game="csgo", title="Item", points=points)
        assert len(ph.points) == 2

    def test_average_price_empty(self):
        """Test average_price with empty points."""
        ph = PriceHistory(game="csgo", title="Item")
        assert ph.average_price == Decimal(0)

    def test_average_price_single_point(self):
        """Test average_price with single point."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
            ],
        )
        assert ph.average_price == Decimal("10.00")

    def test_average_price_multiple_points(self):
        """Test average_price with multiple points."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("20.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("30.00"), timestamp=now
                ),
            ],
        )
        assert ph.average_price == Decimal("20.00")

    def test_min_price_empty(self):
        """Test min_price with empty points."""
        ph = PriceHistory(game="csgo", title="Item")
        assert ph.min_price == Decimal(0)

    def test_min_price_with_points(self):
        """Test min_price with points."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("15.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("25.00"), timestamp=now
                ),
            ],
        )
        assert ph.min_price == Decimal("10.00")

    def test_max_price_empty(self):
        """Test max_price with empty points."""
        ph = PriceHistory(game="csgo", title="Item")
        assert ph.max_price == Decimal(0)

    def test_max_price_with_points(self):
        """Test max_price with points."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("15.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("25.00"), timestamp=now
                ),
            ],
        )
        assert ph.max_price == Decimal("25.00")

    def test_total_volume_empty(self):
        """Test total_volume with empty points."""
        ph = PriceHistory(game="csgo", title="Item")
        assert ph.total_volume == 0

    def test_total_volume_with_points(self):
        """Test total_volume with points."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo",
                    title="Item",
                    price=Decimal("10.00"),
                    timestamp=now,
                    volume=5,
                ),
                PricePoint(
                    game="csgo",
                    title="Item",
                    price=Decimal("10.00"),
                    timestamp=now,
                    volume=3,
                ),
                PricePoint(
                    game="csgo",
                    title="Item",
                    price=Decimal("10.00"),
                    timestamp=now,
                    volume=7,
                ),
            ],
        )
        assert ph.total_volume == 15

    def test_price_volatility_empty(self):
        """Test price_volatility with empty points."""
        ph = PriceHistory(game="csgo", title="Item")
        assert ph.price_volatility == 0.0

    def test_price_volatility_single_point(self):
        """Test price_volatility with single point."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
            ],
        )
        assert ph.price_volatility == 0.0

    def test_price_volatility_same_prices(self):
        """Test price_volatility with same prices (no volatility)."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
            ],
        )
        assert ph.price_volatility == 0.0

    def test_price_volatility_with_variation(self):
        """Test price_volatility with price variation."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("10.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("20.00"), timestamp=now
                ),
            ],
        )
        volatility = ph.price_volatility
        assert volatility > 0.0
        # Mean is 15, std_dev / mean should be around 0.333
        assert 0.3 < volatility < 0.4

    def test_price_volatility_zero_mean(self):
        """Test price_volatility when mean is zero."""
        now = datetime.now(UTC)
        ph = PriceHistory(
            game="csgo",
            title="Item",
            points=[
                PricePoint(
                    game="csgo", title="Item", price=Decimal("0.00"), timestamp=now
                ),
                PricePoint(
                    game="csgo", title="Item", price=Decimal("0.00"), timestamp=now
                ),
            ],
        )
        assert ph.price_volatility == 0.0


# ============================================================================
# HistoricalDataCollector Tests
# ============================================================================


class TestHistoricalDataCollector:
    """Tests for HistoricalDataCollector class."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_sales_history = AsyncMock(return_value={"sales": []})
        api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": []}
        )
        return api

    @pytest.fixture()
    def collector(self, mock_api):
        """Create HistoricalDataCollector with mock API."""
        return HistoricalDataCollector(api=mock_api)

    def test_collector_init(self, mock_api):
        """Test collector initialization."""
        collector = HistoricalDataCollector(api=mock_api)
        assert collector.api == mock_api
        assert collector._cache == {}
        assert collector._cache_ttl == timedelta(minutes=60)

    def test_collector_init_custom_ttl(self, mock_api):
        """Test collector initialization with custom TTL."""
        collector = HistoricalDataCollector(api=mock_api, cache_ttl_minutes=30)
        assert collector._cache_ttl == timedelta(minutes=30)

    @pytest.mark.asyncio()
    async def test_collect_price_history_empty_result(self, collector, mock_api):
        """Test collecting price history with no data."""
        result = await collector.collect_price_history("csgo", "Test Item", days=30)

        assert isinstance(result, PriceHistory)
        assert result.game == "csgo"
        assert result.title == "Test Item"
        assert len(result.points) == 0

    @pytest.mark.asyncio()
    async def test_collect_price_history_with_sales(self, collector, mock_api):
        """Test collecting price history with sales data."""
        now = datetime.now(UTC)
        mock_api.get_sales_history.return_value = {
            "sales": [
                {"price": {"USD": 1500}, "date": now.isoformat()},
                {"price": {"USD": 1600}, "date": now.isoformat()},
            ]
        }

        result = await collector.collect_price_history("csgo", "AK-47", days=30)

        assert len(result.points) == 2
        assert result.points[0].price == Decimal("15.00")  # 1500 cents -> $15.00
        assert result.points[1].price == Decimal("16.00")

    @pytest.mark.asyncio()
    async def test_collect_price_history_with_aggregated(self, collector, mock_api):
        """Test collecting price history with aggregated data."""
        mock_api.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [
                {
                    "title": "AWP | Asiimov",
                    "offerBestPrice": 5000,
                    "orderBestPrice": 4800,
                }
            ]
        }

        result = await collector.collect_price_history("csgo", "AWP | Asiimov", days=30)

        # Should have 2 points - one for offer, one for order
        assert len(result.points) == 2
        assert any(p.source == "aggregated_offer" for p in result.points)
        assert any(p.source == "aggregated_order" for p in result.points)

    @pytest.mark.asyncio()
    async def test_collect_price_history_cache_hit(self, collector, mock_api):
        """Test cache hit on second call."""
        # First call
        await collector.collect_price_history("csgo", "Item", days=30)

        # Second call should use cache
        await collector.collect_price_history("csgo", "Item", days=30)

        # API should only be called once
        assert mock_api.get_sales_history.call_count == 1

    @pytest.mark.asyncio()
    async def test_collect_price_history_cache_bypass(self, collector, mock_api):
        """Test bypassing cache."""
        # First call
        await collector.collect_price_history("csgo", "Item", days=30)

        # Second call bypassing cache
        await collector.collect_price_history("csgo", "Item", days=30, use_cache=False)

        # API should be called twice
        assert mock_api.get_sales_history.call_count == 2

    @pytest.mark.asyncio()
    async def test_collect_price_history_api_error(self, collector, mock_api):
        """Test handling API errors gracefully."""
        mock_api.get_sales_history.side_effect = Exception("API Error")
        mock_api.get_aggregated_prices_bulk.side_effect = Exception("API Error")

        # Should not raise, returns empty history
        result = await collector.collect_price_history("csgo", "Item", days=30)

        assert isinstance(result, PriceHistory)
        assert len(result.points) == 0

    @pytest.mark.asyncio()
    async def test_collect_from_sales_history_price_formats(self, collector, mock_api):
        """Test parsing different price formats from sales history."""
        now = datetime.now(UTC)
        mock_api.get_sales_history.return_value = {
            "sales": [
                # Dict format with USD
                {"price": {"USD": 1500}, "date": now.isoformat()},
                # Dict format with amount
                {"price": {"amount": 2000}, "date": now.isoformat()},
                # Raw integer format
                {"price": 2500, "date": now.isoformat()},
            ]
        }

        result = await collector.collect_price_history("csgo", "Item", days=30)

        assert len(result.points) == 3

    @pytest.mark.asyncio()
    async def test_collect_from_sales_history_timestamp_formats(
        self, collector, mock_api
    ):
        """Test parsing different timestamp formats."""
        mock_api.get_sales_history.return_value = {
            "sales": [
                {"price": 1000, "date": "2025-01-01T12:00:00+00:00"},
                {"price": 1000, "timestamp": "2025-01-01T12:00:00Z"},
                {"price": 1000},  # No timestamp
            ]
        }

        result = await collector.collect_price_history("csgo", "Item", days=30)

        assert len(result.points) == 3

    @pytest.mark.asyncio()
    async def test_collect_batch(self, collector, mock_api):
        """Test batch collection for multiple items."""
        titles = ["Item1", "Item2", "Item3"]

        results = await collector.collect_batch("csgo", titles, days=30)

        assert len(results) == 3
        assert "Item1" in results
        assert "Item2" in results
        assert "Item3" in results
        assert all(isinstance(v, PriceHistory) for v in results.values())

    @pytest.mark.asyncio()
    async def test_collect_batch_with_errors(self, collector, mock_api):
        """Test batch collection handles individual errors."""

        def side_effect(game, title, period):
            if title == "BadItem":
                raise Exception("Error")
            return {"sales": []}

        mock_api.get_sales_history.side_effect = side_effect

        results = await collector.collect_batch(
            "csgo", ["Item1", "BadItem", "Item2"], days=30
        )

        # Should have results for successful items
        assert "Item1" in results
        assert "Item2" in results

    def test_clear_cache(self, collector):
        """Test cache clearing."""
        # Add something to cache
        collector._cache["test:key"] = (datetime.now(UTC), MagicMock())
        assert len(collector._cache) == 1

        collector.clear_cache()

        assert len(collector._cache) == 0

    def test_get_cache_stats_empty(self, collector):
        """Test cache stats with empty cache."""
        stats = collector.get_cache_stats()

        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0
        assert stats["ttl_minutes"] == 60.0

    def test_get_cache_stats_with_entries(self, collector):
        """Test cache stats with entries."""
        now = datetime.now(UTC)

        # Add valid entry
        collector._cache["valid:key"] = (now, MagicMock())

        # Add expired entry
        old_time = now - timedelta(hours=2)
        collector._cache["expired:key"] = (old_time, MagicMock())

        stats = collector.get_cache_stats()

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 1  # Only the recent one

    @pytest.mark.asyncio()
    async def test_collect_from_aggregated_empty(self, collector, mock_api):
        """Test aggregated collection with empty response."""
        mock_api.get_aggregated_prices_bulk.return_value = {}

        await collector.collect_price_history("csgo", "Item", days=30)

        # Only sales history points (if any), no aggregated
        mock_api.get_aggregated_prices_bulk.assert_called_once()

    @pytest.mark.asyncio()
    async def test_collect_from_aggregated_title_mismatch(self, collector, mock_api):
        """Test aggregated collection when title doesn't match."""
        mock_api.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [{"title": "Different Item", "offerBestPrice": 5000}]
        }

        result = await collector.collect_price_history("csgo", "Target Item", days=30)

        # Should not include mismatched items
        assert not any(p.source.startswith("aggregated") for p in result.points)

    @pytest.mark.asyncio()
    async def test_collect_from_aggregated_zero_prices(self, collector, mock_api):
        """Test aggregated collection with zero prices."""
        mock_api.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [
                {
                    "title": "Item",
                    "offerBestPrice": 0,
                    "orderBestPrice": 0,
                }
            ]
        }

        result = await collector.collect_price_history("csgo", "Item", days=30)

        # Should not include zero price points
        assert not any(p.source.startswith("aggregated") for p in result.points)


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestHistoricalDataEdgeCases:
    """Edge case tests for historical data module."""

    def test_price_point_large_price(self):
        """Test PricePoint with very large price."""
        pp = PricePoint(
            game="csgo",
            title="Expensive Item",
            price=Decimal("99999.99"),
            timestamp=datetime.now(UTC),
        )
        assert pp.price == Decimal("99999.99")

    def test_price_point_small_price(self):
        """Test PricePoint with very small price."""
        pp = PricePoint(
            game="csgo",
            title="Cheap Item",
            price=Decimal("0.01"),
            timestamp=datetime.now(UTC),
        )
        assert pp.price == Decimal("0.01")

    def test_price_history_many_points(self):
        """Test PriceHistory with many points."""
        now = datetime.now(UTC)
        points = [
            PricePoint(
                game="csgo",
                title="Item",
                price=Decimal(str(i)),
                timestamp=now,
            )
            for i in range(1, 1001)
        ]

        ph = PriceHistory(game="csgo", title="Item", points=points)

        assert len(ph.points) == 1000
        assert ph.average_price == Decimal("500.5")  # Average of 1 to 1000
        assert ph.min_price == Decimal(1)
        assert ph.max_price == Decimal(1000)
        assert ph.total_volume == 0  # Default volume

    def test_price_history_high_volatility(self):
        """Test PriceHistory with high volatility."""
        now = datetime.now(UTC)
        points = [
            PricePoint(game="csgo", title="Item", price=Decimal(1), timestamp=now),
            PricePoint(game="csgo", title="Item", price=Decimal(100), timestamp=now),
        ]

        ph = PriceHistory(game="csgo", title="Item", points=points)

        # High volatility expected
        volatility = ph.price_volatility
        assert volatility > 0.9  # Very high volatility

    def test_special_characters_in_title(self):
        """Test handling special characters in item title."""
        pp = PricePoint(
            game="csgo",
            title="AK-47 | Redline (Field-Tested) ★",
            price=Decimal("15.00"),
            timestamp=datetime.now(UTC),
        )

        data = pp.to_dict()
        restored = PricePoint.from_dict(data)

        assert restored.title == pp.title

    def test_unicode_in_title(self):
        """Test handling unicode in item title."""
        pp = PricePoint(
            game="dota2",
            title="Бонусный предмет 🎮",
            price=Decimal("10.00"),
            timestamp=datetime.now(UTC),
        )

        data = pp.to_dict()
        restored = PricePoint.from_dict(data)

        assert restored.title == pp.title
