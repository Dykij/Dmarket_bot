"""Tests for Long Polling Client.

Tests long-polling functionality for DMarket API.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.dmarket.long_polling import (
    BatchUpdateChecker,
    CacheEntry,
    LongPollingClient,
    MarketUpdate,
    UpdateType,
    create_batch_checker,
    create_long_polling_client,
)


class TestMarketUpdate:
    """Tests for MarketUpdate dataclass."""

    def test_price_change_significant(self):
        """Test significant price change detection."""
        update = MarketUpdate(
            type=UpdateType.PRICE_CHANGE,
            item_id="test123",
            item_name="AK-47 | Redline",
            game="csgo",
            old_price=10.0,
            new_price=12.0,
            price_change_percent=20.0,
        )
        assert update.is_significant is True

    def test_price_change_not_significant(self):
        """Test insignificant price change."""
        update = MarketUpdate(
            type=UpdateType.PRICE_CHANGE,
            item_id="test123",
            item_name="AK-47 | Redline",
            game="csgo",
            old_price=10.0,
            new_price=10.05,
            price_change_percent=0.5,
        )
        assert update.is_significant is False

    def test_new_listing_significant(self):
        """Test new listing is always significant."""
        update = MarketUpdate(
            type=UpdateType.NEW_LISTING,
            item_id="test123",
            item_name="AK-47 | Redline",
            game="csgo",
            new_price=10.0,
        )
        assert update.is_significant is True

    def test_no_change_not_significant(self):
        """Test no change is never significant."""
        update = MarketUpdate(
            type=UpdateType.NO_CHANGE,
            item_id="test123",
            item_name="AK-47 | Redline",
            game="csgo",
        )
        assert update.is_significant is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        update = MarketUpdate(
            type=UpdateType.PRICE_CHANGE,
            item_id="test123",
            item_name="Test Item",
            game="csgo",
            old_price=10.0,
            new_price=11.0,
            price_change_percent=10.0,
        )
        result = update.to_dict()

        assert result["type"] == "price_change"
        assert result["item_id"] == "test123"
        assert result["item_name"] == "Test Item"
        assert result["game"] == "csgo"
        assert result["old_price"] == 10.0
        assert result["new_price"] == 11.0
        assert result["is_significant"] is True


class TestLongPollingClient:
    """Tests for LongPollingClient."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = AsyncMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline",
                    "price": {"USD": "1000"},
                    "amount": 5,
                },
                {
                    "itemId": "item2",
                    "title": "AWP | Asiimov",
                    "price": {"USD": "2500"},
                    "amount": 3,
                },
            ]
        })
        return api

    @pytest.fixture
    def client(self, mock_api):
        """Create long-polling client fixture."""
        return LongPollingClient(
            api=mock_api,
            poll_interval=15.0,
            timeout=30.0,
        )

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.poll_interval == 15.0
        assert client.timeout == 30.0
        assert client.max_items == 100

    def test_min_poll_interval(self, mock_api):
        """Test minimum poll interval is enforced."""
        client = LongPollingClient(
            api=mock_api,
            poll_interval=5.0,  # Below minimum
        )
        assert client.poll_interval == 10.0  # Should be clamped to 10

    @pytest.mark.asyncio
    async def test_poll_with_delta_first_time(self, client, mock_api):
        """Test first poll caches items."""
        updates = awAlgot client._poll_with_delta("csgo", None, None)

        # First poll should detect new listings
        assert len(updates) == 2
        for update in updates:
            assert update.type == UpdateType.NEW_LISTING

    @pytest.mark.asyncio
    async def test_poll_with_delta_detects_price_change(self, client, mock_api):
        """Test price change detection."""
        # First poll
        awAlgot client._poll_with_delta("csgo", None, None)

        # Update mock with changed price
        mock_api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline",
                    "price": {"USD": "1200"},  # Changed from 1000
                    "amount": 5,
                },
            ]
        })

        # Second poll
        updates = awAlgot client._poll_with_delta("csgo", None, None)

        assert len(updates) == 1
        assert updates[0].type == UpdateType.PRICE_CHANGE
        assert updates[0].old_price == 10.0
        assert updates[0].new_price == 12.0
        assert updates[0].price_change_percent == 20.0

    @pytest.mark.asyncio
    async def test_poll_with_delta_no_change(self, client, mock_api):
        """Test no updates when nothing changed."""
        # First poll
        awAlgot client._poll_with_delta("csgo", None, None)

        # Second poll with same data
        updates = awAlgot client._poll_with_delta("csgo", None, None)

        # Should be empty (no changes)
        assert len(updates) == 0

    def test_process_item_new(self, client):
        """Test processing new item."""
        item = {
            "itemId": "new_item",
            "title": "New Item",
            "price": {"USD": "1500"},
            "amount": 1,
        }

        update = client._process_item(item, "csgo")

        assert update is not None
        assert update.type == UpdateType.NEW_LISTING
        assert update.new_price == 15.0

    def test_process_item_price_change(self, client):
        """Test processing item with price change."""
        # Add to cache first
        client._cache["item1"] = CacheEntry(
            item_id="item1",
            price=10.0,
            quantity=5,
            etag=None,
            last_modified=datetime.now(UTC),
            data_hash="10.0:5",
        )

        item = {
            "itemId": "item1",
            "title": "Test Item",
            "price": {"USD": "1200"},  # Changed
            "amount": 5,
        }

        update = client._process_item(item, "csgo")

        assert update is not None
        assert update.type == UpdateType.PRICE_CHANGE
        assert update.old_price == 10.0
        assert update.new_price == 12.0

    def test_process_item_quantity_change(self, client):
        """Test processing item with quantity change."""
        # Add to cache
        client._cache["item1"] = CacheEntry(
            item_id="item1",
            price=10.0,
            quantity=5,
            etag=None,
            last_modified=datetime.now(UTC),
            data_hash="10.0:5",
        )

        item = {
            "itemId": "item1",
            "title": "Test Item",
            "price": {"USD": "1000"},  # Same price
            "amount": 3,  # Changed quantity
        }

        update = client._process_item(item, "csgo")

        assert update is not None
        assert update.type == UpdateType.QUANTITY_CHANGE
        assert update.old_quantity == 5
        assert update.new_quantity == 3

    def test_get_cached_item(self, client):
        """Test getting cached item."""
        client._cache["test"] = CacheEntry(
            item_id="test",
            price=10.0,
            quantity=1,
            etag=None,
            last_modified=datetime.now(UTC),
            data_hash="10.0:1",
        )

        cached = client.get_cached_item("test")
        assert cached is not None
        assert cached.price == 10.0

    def test_get_cached_item_not_found(self, client):
        """Test getting non-existent cached item."""
        cached = client.get_cached_item("nonexistent")
        assert cached is None

    def test_clear_cache(self, client):
        """Test clearing cache."""
        client._cache["test"] = CacheEntry(
            item_id="test",
            price=10.0,
            quantity=1,
            etag=None,
            last_modified=datetime.now(UTC),
            data_hash="10.0:1",
        )
        client._last_etag["csgo"] = "etag123"

        client.clear_cache()

        assert len(client._cache) == 0
        assert len(client._last_etag) == 0

    def test_stop(self, client):
        """Test stopping client."""
        client._running = True
        client.stop()
        assert client._running is False


class TestBatchUpdateChecker:
    """Tests for BatchUpdateChecker."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = AsyncMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline",
                    "price": {"USD": "800"},  # $8.00
                    "amount": 5,
                },
            ]
        })
        return api

    @pytest.fixture
    def checker(self, mock_api):
        """Create batch checker fixture."""
        return BatchUpdateChecker(api=mock_api, check_interval=30.0)

    def test_watch_item(self, checker):
        """Test adding item to watch list."""
        checker.watch_item("AK-47 | Redline", 10.0)
        assert "AK-47 | Redline" in checker._watched_items
        assert checker._watched_items["AK-47 | Redline"] == 10.0

    def test_unwatch_item(self, checker):
        """Test removing item from watch list."""
        checker.watch_item("AK-47 | Redline", 10.0)
        checker.unwatch_item("AK-47 | Redline")
        assert "AK-47 | Redline" not in checker._watched_items

    @pytest.mark.asyncio
    async def test_check_prices_target_hit(self, checker, mock_api):
        """Test price check when target is hit."""
        checker.watch_item("AK-47 | Redline", 10.0)  # Target: $10

        # Mock returns $8 which is below target
        alerts = awAlgot checker.check_prices("csgo")

        assert len(alerts) == 1
        assert alerts[0]["item_name"] == "AK-47 | Redline"
        assert alerts[0]["current_price"] == 8.0
        assert alerts[0]["target_price"] == 10.0

    @pytest.mark.asyncio
    async def test_check_prices_target_not_hit(self, checker, mock_api):
        """Test price check when target not hit."""
        checker.watch_item("AK-47 | Redline", 5.0)  # Target: $5

        # Mock returns $8 which is above target
        alerts = awAlgot checker.check_prices("csgo")

        assert len(alerts) == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_long_polling_client(self):
        """Test creating long-polling client."""
        mock_api = AsyncMock()
        client = create_long_polling_client(mock_api, poll_interval=20.0)

        assert isinstance(client, LongPollingClient)
        assert client.poll_interval == 20.0

    def test_create_batch_checker(self):
        """Test creating batch checker."""
        mock_api = AsyncMock()
        checker = create_batch_checker(mock_api, check_interval=45.0)

        assert isinstance(checker, BatchUpdateChecker)
        assert checker.check_interval == 45.0
