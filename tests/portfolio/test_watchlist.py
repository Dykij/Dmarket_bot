"""Tests for Watchlist Module."""

from decimal import Decimal

import pytest

from src.portfolio.watchlist import (
    PriceDirection,
    Watchlist,
    WatchlistItem,
    WatchlistManager,
    get_watchlist_manager,
    init_watchlist_manager,
)


class TestWatchlistItem:
    """Tests for WatchlistItem."""

    def test_item_creation(self):
        """Test item creation."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="AK-47 | Redline",
        )

        assert item.item_id == "wi_123"
        assert item.item_name == "AK-47 | Redline"
        assert item.last_price is None
        assert item.target_price is None

    def test_update_price_up(self):
        """Test price update - up direction."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            last_price=Decimal("50.0"),
        )

        direction = item.update_price(Decimal("55.0"))

        assert direction == PriceDirection.UP
        assert item.last_price == Decimal("55.0")

    def test_update_price_down(self):
        """Test price update - down direction."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            last_price=Decimal("50.0"),
        )

        direction = item.update_price(Decimal("45.0"))

        assert direction == PriceDirection.DOWN
        assert item.last_price == Decimal("45.0")

    def test_update_price_unchanged(self):
        """Test price update - unchanged."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            last_price=Decimal("50.0"),
        )

        direction = item.update_price(Decimal("50.0"))

        assert direction == PriceDirection.UNCHANGED

    def test_price_history(self):
        """Test price history tracking."""
        item = WatchlistItem(item_id="wi_123", item_name="Test")

        item.update_price(Decimal("50.0"))
        item.update_price(Decimal("55.0"))
        item.update_price(Decimal("52.0"))

        assert len(item.price_history) == 3
        assert item.price_change == Decimal("2.0")

    def test_price_history_max_size(self):
        """Test price history is limited to 10."""
        item = WatchlistItem(item_id="wi_123", item_name="Test")

        for i in range(15):
            item.update_price(Decimal(str(i)))

        assert len(item.price_history) == 10

    def test_target_reached(self):
        """Test target price reached check."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            target_price=Decimal("50.0"),
            last_price=Decimal("45.0"),
        )

        assert item.is_target_reached() is True

    def test_target_not_reached(self):
        """Test target price not reached."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            target_price=Decimal("50.0"),
            last_price=Decimal("55.0"),
        )

        assert item.is_target_reached() is False

    def test_price_change_percent(self):
        """Test price change percentage calculation."""
        item = WatchlistItem(item_id="wi_123", item_name="Test")

        item.update_price(Decimal("100.0"))
        item.update_price(Decimal("110.0"))

        assert item.price_change_percent == Decimal("10.0")

    def test_to_dict(self):
        """Test to_dict conversion."""
        item = WatchlistItem(
            item_id="wi_123",
            item_name="Test",
            last_price=Decimal("50.0"),
        )

        data = item.to_dict()
        assert "item_id" in data
        assert "item_name" in data
        assert "last_price" in data


class TestWatchlist:
    """Tests for Watchlist."""

    def test_watchlist_creation(self):
        """Test watchlist creation."""
        wl = Watchlist(
            watchlist_id="wl_123",
            user_id=123,
            name="My Watchlist",
        )

        assert wl.watchlist_id == "wl_123"
        assert wl.user_id == 123
        assert wl.name == "My Watchlist"
        assert wl.item_count == 0

    def test_add_item(self):
        """Test adding item."""
        wl = Watchlist(watchlist_id="wl_123", user_id=123, name="Test")

        item = wl.add_item(
            item_name="AK-47 | Redline",
            target_price=50.0,
        )

        assert item is not None
        assert item.item_name == "AK-47 | Redline"
        assert wl.item_count == 1

    def test_remove_item(self):
        """Test removing item."""
        wl = Watchlist(watchlist_id="wl_123", user_id=123, name="Test")
        item = wl.add_item("Test Item")

        assert wl.remove_item(item.item_id) is True
        assert wl.item_count == 0

    def test_get_item_by_name(self):
        """Test getting item by name."""
        wl = Watchlist(watchlist_id="wl_123", user_id=123, name="Test")
        wl.add_item("AK-47 | Redline")

        item = wl.get_item_by_name("ak-47 | redline")  # Case insensitive
        assert item is not None
        assert item.item_name == "AK-47 | Redline"

    def test_to_dict(self):
        """Test to_dict conversion."""
        wl = Watchlist(watchlist_id="wl_123", user_id=123, name="Test")
        wl.add_item("Item 1")
        wl.add_item("Item 2")

        data = wl.to_dict()
        assert data["watchlist_id"] == "wl_123"
        assert data["item_count"] == 2
        assert len(data["items"]) == 2


class TestWatchlistManager:
    """Tests for WatchlistManager."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return WatchlistManager(user_id=123)

    def test_create_watchlist(self, manager):
        """Test creating watchlist."""
        wl = manager.create_watchlist("My Watchlist")

        assert wl is not None
        assert wl.name == "My Watchlist"
        assert wl.user_id == 123

    def test_create_watchlist_limit(self, manager):
        """Test watchlist limit."""
        manager.MAX_WATCHLISTS_PER_USER = 2

        wl1 = manager.create_watchlist("List 1")
        wl2 = manager.create_watchlist("List 2")
        wl3 = manager.create_watchlist("List 3")

        assert wl1 is not None
        assert wl2 is not None
        assert wl3 is None  # Limit reached

    def test_get_watchlist(self, manager):
        """Test getting watchlist by ID."""
        wl = manager.create_watchlist("Test")
        assert wl is not None

        retrieved = manager.get_watchlist(wl.watchlist_id)
        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_get_user_watchlists(self, manager):
        """Test getting user watchlists."""
        manager.create_watchlist("List 1")
        manager.create_watchlist("List 2")

        watchlists = manager.get_user_watchlists()
        assert len(watchlists) == 2

    def test_default_watchlist(self, manager):
        """Test default watchlist."""
        wl1 = manager.create_watchlist("List 1")
        wl2 = manager.create_watchlist("List 2", is_default=True)

        default = manager.get_default_watchlist()
        assert default is not None
        assert default.watchlist_id == wl2.watchlist_id

    def test_delete_watchlist(self, manager):
        """Test deleting watchlist."""
        wl = manager.create_watchlist("Test")
        assert wl is not None

        success = manager.delete_watchlist(wl.watchlist_id)
        assert success is True

        retrieved = manager.get_watchlist(wl.watchlist_id)
        assert retrieved is None

    def test_add_item(self, manager):
        """Test adding item to watchlist."""
        wl = manager.create_watchlist("Test")
        assert wl is not None

        item = manager.add_item(wl.watchlist_id, "AK-47 | Redline", target_price=50.0)

        assert item is not None
        assert item.item_name == "AK-47 | Redline"

    def test_add_item_limit(self, manager):
        """Test item limit per watchlist."""
        manager.MAX_ITEMS_PER_WATCHLIST = 2

        wl = manager.create_watchlist("Test")
        assert wl is not None

        item1 = manager.add_item(wl.watchlist_id, "Item 1")
        item2 = manager.add_item(wl.watchlist_id, "Item 2")
        item3 = manager.add_item(wl.watchlist_id, "Item 3")

        assert item1 is not None
        assert item2 is not None
        assert item3 is None  # Limit reached

    def test_remove_item(self, manager):
        """Test removing item from watchlist."""
        wl = manager.create_watchlist("Test")
        assert wl is not None
        item = manager.add_item(wl.watchlist_id, "Test Item")
        assert item is not None

        success = manager.remove_item(wl.watchlist_id, item.item_id)
        assert success is True

    def test_update_item_target(self, manager):
        """Test updating item target price."""
        wl = manager.create_watchlist("Test")
        assert wl is not None
        item = manager.add_item(wl.watchlist_id, "Test Item", target_price=50.0)
        assert item is not None

        success = manager.update_item_target(wl.watchlist_id, item.item_id, 45.0)
        assert success is True
        assert wl.items[item.item_id].target_price == Decimal("45.0")


class TestPriceChecking:
    """Tests for price checking."""

    @pytest.fixture
    def manager(self):
        """Create test manager with watchlist."""
        mgr = WatchlistManager(user_id=123)
        wl = mgr.create_watchlist("Test")
        assert wl is not None
        mgr.add_item(wl.watchlist_id, "Item 1", target_price=50.0)
        mgr.add_item(wl.watchlist_id, "Item 2", target_price=100.0)
        return mgr

    @pytest.mark.asyncio
    async def test_check_prices(self, manager):
        """Test price checking."""
        # First check - no changes reported (no old price)
        prices = {
            "Item 1": Decimal("55.0"),
            "Item 2": Decimal("95.0"),
        }
        updates = awAlgot manager.check_prices(prices)

        # Second check - changes reported
        prices = {
            "Item 1": Decimal("50.0"),  # Price dropped, target reached
            "Item 2": Decimal("90.0"),  # Price dropped
        }
        updates = awAlgot manager.check_prices(prices)

        assert len(updates) >= 1

    @pytest.mark.asyncio
    async def test_check_prices_target_reached(self, manager):
        """Test price checking with target reached."""
        prices = {"Item 1": Decimal("60.0")}
        awAlgot manager.check_prices(prices)

        prices = {"Item 1": Decimal("45.0")}  # Below target of 50
        updates = awAlgot manager.check_prices(prices)

        target_reached = [u for u in updates if u.target_reached]
        assert len(target_reached) >= 1


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        mgr = WatchlistManager(user_id=123)
        wl = mgr.create_watchlist("Test")
        assert wl is not None
        mgr.add_item(wl.watchlist_id, "Item 1")
        mgr.add_item(wl.watchlist_id, "Item 2")
        return mgr

    def test_get_all_item_names(self, manager):
        """Test getting all item names."""
        names = manager.get_all_item_names()
        assert len(names) == 2
        assert "Item 1" in names
        assert "Item 2" in names

    def test_export_watchlist(self, manager):
        """Test exporting watchlist."""
        wl = manager.get_user_watchlists()[0]
        data = manager.export_watchlist(wl.watchlist_id)

        assert data is not None
        assert "items" in data
        assert len(data["items"]) == 2

    def test_get_stats(self, manager):
        """Test getting stats."""
        stats = manager.get_stats()

        assert stats["watchlist_count"] == 1
        assert stats["total_items"] == 2
        assert stats["unique_items"] == 2


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_init_watchlist_manager(self):
        """Test initializing global manager."""
        manager = init_watchlist_manager(user_id=456)
        assert manager.default_user_id == 456

    def test_get_watchlist_manager(self):
        """Test getting global manager."""
        init_watchlist_manager(user_id=789)
        manager = get_watchlist_manager()
        assert manager is not None
