"""Tests for Adaptive Polling Engine.

Tests intelligent polling optimization for DMarket API.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.adaptive_polling import (
    AdaptivePollingEngine,
    CachedPrice,
    DeltaTracker,
    MarketActivity,
    PollConfig,
    PollPriority,
    PriceChange,
    create_polling_engine,
)


class TestPriceChange:
    """Tests for PriceChange dataclass."""

    def test_price_change_significant_increase(self):
        """Test significant price increase detection."""
        change = PriceChange(
            item_id="test123",
            item_name="AK-47 | Redline",
            old_price=10.0,
            new_price=10.50,
            change_percent=5.0,
        )
        assert change.is_significant is True

    def test_price_change_significant_decrease(self):
        """Test significant price decrease detection."""
        change = PriceChange(
            item_id="test123",
            item_name="AK-47 | Redline",
            old_price=10.0,
            new_price=9.0,
            change_percent=-10.0,
        )
        assert change.is_significant is True

    def test_price_change_not_significant(self):
        """Test insignificant price change."""
        change = PriceChange(
            item_id="test123",
            item_name="AK-47 | Redline",
            old_price=10.0,
            new_price=10.05,
            change_percent=0.5,
        )
        assert change.is_significant is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        change = PriceChange(
            item_id="test123",
            item_name="Test Item",
            old_price=10.0,
            new_price=11.0,
            change_percent=10.0,
        )
        result = change.to_dict()

        assert result["item_id"] == "test123"
        assert result["item_name"] == "Test Item"
        assert result["old_price"] == 10.0
        assert result["new_price"] == 11.0
        assert result["change_percent"] == 10.0
        assert result["is_significant"] is True


class TestPollConfig:
    """Tests for PollConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PollConfig()

        assert config.base_interval == 30.0
        assert config.min_interval == 10.0
        assert config.max_interval == 120.0
        assert config.items_per_batch == 100

    def test_priority_multipliers(self):
        """Test priority multipliers are correct."""
        config = PollConfig()

        assert config.priority_multipliers[PollPriority.CRITICAL] < 1.0
        assert config.priority_multipliers[PollPriority.HIGH] < 1.0
        assert config.priority_multipliers[PollPriority.NORMAL] == 1.0
        assert config.priority_multipliers[PollPriority.LOW] > 1.0


class TestAdaptivePollingEngine:
    """Tests for AdaptivePollingEngine."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = AsyncMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline",
                    "price": {"USD": "1000"},  # $10.00
                    "amount": 5,
                },
                {
                    "itemId": "item2",
                    "title": "AWP | Asiimov",
                    "price": {"USD": "2500"},  # $25.00
                    "amount": 3,
                },
            ]
        })
        return api

    @pytest.fixture
    def engine(self, mock_api):
        """Create polling engine fixture."""
        return AdaptivePollingEngine(
            api_client=mock_api,
            games=["csgo"],
            whitelist_items=["ak-47 | redline"],
        )

    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine.is_running is False
        assert "csgo" in engine.games
        assert "ak-47 | redline" in engine.whitelist_items

    def test_stats(self, engine):
        """Test statistics reporting."""
        stats = engine.stats

        assert stats["is_running"] is False
        assert stats["poll_count"] == 0
        assert stats["changes_detected"] == 0
        assert stats["cached_items"] == 0

    def test_add_to_whitelist(self, engine):
        """Test adding items to whitelist."""
        engine.add_to_whitelist("AWP | Dragon Lore")
        assert "awp | dragon lore" in engine.whitelist_items

    def test_remove_from_whitelist(self, engine):
        """Test removing items from whitelist."""
        engine.remove_from_whitelist("ak-47 | redline")
        assert "ak-47 | redline" not in engine.whitelist_items

    @pytest.mark.asyncio
    async def test_force_poll(self, engine, mock_api):
        """Test forced polling."""
        changes = awAlgot engine.force_poll("csgo")

        # First poll should not detect changes (just caching)
        assert isinstance(changes, list)
        mock_api.get_market_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_poll_detects_changes(self, engine, mock_api):
        """Test change detection after multiple polls.

        The polling logic works as follows:
        1. First poll: item is added to _known_item_ids, on_new_listing called
        2. Second poll: item is already known, added to _price_cache
        3. Third poll: price change can be detected
        """
        # First poll - items added to known_item_ids
        awAlgot engine.force_poll("csgo")

        # Second poll - items added to price cache
        awAlgot engine.force_poll("csgo")

        # Update mock to return different price
        mock_api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline",
                    "price": {"USD": "1100"},  # $11.00 (was $10.00)
                    "amount": 5,
                },
            ]
        })

        # Third poll - should detect change
        changes = awAlgot engine.force_poll("csgo")
        assert len(changes) == 1
        assert changes[0].old_price == 10.0
        assert changes[0].new_price == 11.0

    def test_get_market_activity_peak(self, engine):
        """Test peak hours detection."""
        with patch("src.dmarket.adaptive_polling.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(
                hour=15,  # 3 PM UTC - peak hour
                weekday=MagicMock(return_value=2),  # Wednesday
            )
            mock_dt.now.return_value.hour = 15
            mock_dt.now.return_value.weekday.return_value = 2

            activity = engine._get_market_activity()
            # During configured peak hours
            assert activity in [MarketActivity.PEAK, MarketActivity.NORMAL]

    def test_calculate_interval_base(self, engine):
        """Test base interval calculation."""
        interval = engine._calculate_interval()

        # Should be within configured bounds
        assert interval >= engine.config.min_interval
        assert interval <= engine.config.max_interval

    def test_get_cached_price(self, engine):
        """Test getting cached price."""
        # Add to cache
        engine._price_cache["test_id"] = CachedPrice(
            item_id="test_id",
            item_name="Test Item",
            price=10.0,
            quantity=1,
            last_updated=datetime.now(UTC),
        )

        price = engine.get_cached_price("test_id")
        assert price == 10.0

    def test_get_cached_price_not_found(self, engine):
        """Test getting non-existent cached price."""
        price = engine.get_cached_price("nonexistent")
        assert price is None

    def test_get_volatile_items(self, engine):
        """Test getting volatile items."""
        # Add items with different change counts
        engine._price_cache["stable"] = CachedPrice(
            item_id="stable",
            item_name="Stable Item",
            price=10.0,
            quantity=1,
            last_updated=datetime.now(UTC),
            change_count=1,
        )
        engine._price_cache["volatile"] = CachedPrice(
            item_id="volatile",
            item_name="Volatile Item",
            price=10.0,
            quantity=1,
            last_updated=datetime.now(UTC),
            change_count=5,
        )

        volatile = engine.get_volatile_items(min_changes=3)
        assert len(volatile) == 1
        assert volatile[0].item_name == "Volatile Item"

    def test_clear_cache(self, engine):
        """Test cache clearing."""
        engine._price_cache["test"] = CachedPrice(
            item_id="test",
            item_name="Test",
            price=10.0,
            quantity=1,
            last_updated=datetime.now(UTC),
        )
        engine._known_item_ids.add("test")
        engine._changes_detected = 5
        engine._poll_count = 10

        engine.clear_cache()

        assert len(engine._price_cache) == 0
        assert len(engine._known_item_ids) == 0
        assert engine._changes_detected == 0
        assert engine._poll_count == 0


class TestDeltaTracker:
    """Tests for DeltaTracker."""

    @pytest.fixture
    def tracker(self):
        """Create delta tracker fixture."""
        return DeltaTracker(max_history=100)

    def test_update_new_item(self, tracker):
        """Test tracking new item."""
        result = tracker.update("item1", {"price": 10.0, "quantity": 5})

        assert result is not None
        assert result.get("_new") is True
        assert result.get("price") == 10.0

    def test_update_no_change(self, tracker):
        """Test no change detection."""
        tracker.update("item1", {"price": 10.0, "quantity": 5})
        result = tracker.update("item1", {"price": 10.0, "quantity": 5})

        assert result is None

    def test_update_price_change(self, tracker):
        """Test price change detection."""
        tracker.update("item1", {"price": 10.0, "quantity": 5})
        result = tracker.update("item1", {"price": 11.0, "quantity": 5})

        assert result is not None
        assert "price" in result
        assert result["price"]["old"] == 10.0
        assert result["price"]["new"] == 11.0

    def test_get_snapshot(self, tracker):
        """Test getting snapshot."""
        tracker.update("item1", {"price": 10.0})

        snapshot = tracker.get_snapshot("item1")
        assert snapshot is not None
        assert snapshot["price"] == 10.0

    def test_get_snapshot_not_found(self, tracker):
        """Test getting non-existent snapshot."""
        snapshot = tracker.get_snapshot("nonexistent")
        assert snapshot is None

    def test_get_recent_changes(self, tracker):
        """Test getting recent changes."""
        tracker.update("item1", {"price": 10.0})
        tracker.update("item1", {"price": 11.0})
        tracker.update("item1", {"price": 12.0})

        changes = tracker.get_recent_changes(limit=10)
        assert len(changes) == 2  # 2 changes (first was new item)

    def test_max_history_trimming(self):
        """Test history trimming when max reached."""
        tracker = DeltaTracker(max_history=5)

        for i in range(10):
            tracker.update(f"item{i}", {"price": i})

        # Should have trimmed to max
        assert len(tracker._snapshots) <= 5


class TestCreatePollingEngine:
    """Tests for factory function."""

    def test_create_polling_engine(self):
        """Test factory creates engine correctly."""
        mock_api = AsyncMock()

        engine = create_polling_engine(
            api_client=mock_api,
            games=["csgo", "dota2"],
            whitelist_items=["test item"],
        )

        assert isinstance(engine, AdaptivePollingEngine)
        assert engine.games == ["csgo", "dota2"]
        assert "test item" in engine.whitelist_items
