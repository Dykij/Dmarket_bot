"""
Integration tests for Steam Database Handler.

Tests cover:
- Cache workflow (save, retrieve, expiration)
- Arbitrage logging
- Settings persistence
- Blacklist management
- Statistics aggregation
"""

from datetime import datetime, timedelta

import pytest

from src.utils.steam_db_handler import SteamDatabaseHandler


class TestSteamDatabaseIntegration:
    """Integration tests for Steam database operations."""

    @pytest.fixture()
    def db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_steam.db"
        handler = SteamDatabaseHandler(str(db_path))
        return handler
        # Cleanup is automatic with tmp_path

    def test_cache_save_and_retrieve(self, db):
        """Test saving and retrieving cached Steam prices."""
        # Save price
        db.update_steam_price(
            name="AK-47 | Redline (Field-Tested)", price=10.50, volume=150, median_price=11.00
        )

        # Retrieve price
        data = db.get_steam_data("AK-47 | Redline (Field-Tested)")

        assert data is not None
        assert data["price"] == 10.50
        assert data["volume"] == 150
        assert data["median_price"] == 11.00
        assert "last_updated" in data

    def test_cache_freshness_check(self, db):
        """Test checking if cached data is still fresh."""
        # Save price
        db.update_steam_price(name="Test Item", price=5.0, volume=50)

        # Get data
        data = db.get_steam_data("Test Item")
        assert data is not None

        # Should be fresh (just saved)
        assert db.is_cache_actual(data["last_updated"], hours=6)

        # Simulate old data
        old_time = datetime.now() - timedelta(hours=7)
        assert not db.is_cache_actual(old_time, hours=6)

    def test_cache_update_existing(self, db):
        """Test updating existing cache entry."""
        name = "AWP | Asiimov (Field-Tested)"

        # Initial save
        db.update_steam_price(name, price=25.0, volume=100)
        data1 = db.get_steam_data(name)

        # Update
        db.update_steam_price(name, price=26.0, volume=110)
        data2 = db.get_steam_data(name)

        # Should have new values
        assert data2["price"] == 26.0
        assert data2["volume"] == 110
        assert data2["last_updated"] >= data1["last_updated"]

    def test_arbitrage_logging(self, db):
        """Test logging arbitrage opportunities."""
        db.log_opportunity(
            name="M4A4 | Howl (Factory New)",
            dmarket_price=1000.0,
            steam_price=1500.0,
            profit=30.44,
            volume=20,
            liquidity_status="⚠️ Низкая",
        )

        # Check stats
        stats = db.get_daily_stats()
        assert stats["count"] == 1
        assert stats["avg_profit"] == 30.44
        assert stats["max_profit"] == 30.44

    def test_multiple_arbitrage_logs(self, db):
        """Test logging multiple opportunities and stats."""
        # Log multiple opportunities
        db.log_opportunity("Item 1", 10.0, 15.0, 30.0, 100, "High")
        db.log_opportunity("Item 2", 20.0, 25.0, 8.0, 50, "Medium")
        db.log_opportunity("Item 3", 5.0, 10.0, 73.92, 150, "High")

        # Check stats
        stats = db.get_daily_stats()
        assert stats["count"] == 3

        # Average should be (30 + 8 + 73.92) / 3 = 37.31
        assert 37.0 < stats["avg_profit"] < 38.0

        # Max should be 73.92
        assert stats["max_profit"] == pytest.approx(73.92, abs=0.1)

    def test_settings_initialization(self, db):
        """Test that settings are initialized with defaults."""
        settings = db.get_settings()

        assert "min_profit" in settings
        assert "min_volume" in settings
        assert "is_paused" in settings

        # Default values
        assert settings["min_profit"] == 10.0
        assert settings["min_volume"] == 50
        assert settings["is_paused"] is False

    def test_settings_update(self, db):
        """Test updating settings."""
        # Update min_profit
        db.update_settings(min_profit=15.0)
        settings = db.get_settings()
        assert settings["min_profit"] == 15.0
        assert settings["min_volume"] == 50  # Unchanged

        # Update min_volume
        db.update_settings(min_volume=100)
        settings = db.get_settings()
        assert settings["min_profit"] == 15.0  # Still 15
        assert settings["min_volume"] == 100

        # Update is_paused
        db.update_settings(is_paused=True)
        settings = db.get_settings()
        assert settings["is_paused"] is True

    def test_settings_multiple_updates(self, db):
        """Test multiple simultaneous setting updates."""
        db.update_settings(min_profit=20.0, min_volume=200, is_paused=True)

        settings = db.get_settings()
        assert settings["min_profit"] == 20.0
        assert settings["min_volume"] == 200
        assert settings["is_paused"] is True

    def test_blacklist_add_and_check(self, db):
        """Test adding items to blacklist."""
        item = "Scam Item | Fake (Field-Tested)"

        # Initially not blacklisted
        assert not db.is_blacklisted(item)

        # Add to blacklist
        db.add_to_blacklist(item, reason="Suspicious pricing")

        # Now should be blacklisted
        assert db.is_blacklisted(item)

    def test_blacklist_removal(self, db):
        """Test removing items from blacklist."""
        item = "Temporarily Bad Item"

        # Add and verify
        db.add_to_blacklist(item, reason="Temporary issue")
        assert db.is_blacklisted(item)

        # Remove and verify
        db.remove_from_blacklist(item)
        assert not db.is_blacklisted(item)

    def test_blacklist_multiple_items(self, db):
        """Test managing multiple blacklisted items."""
        items = [("Item 1", "Reason 1"), ("Item 2", "Reason 2"), ("Item 3", "Reason 3")]

        # Add all
        for item, reason in items:
            db.add_to_blacklist(item, reason)

        # Verify all
        for item, _ in items:
            assert db.is_blacklisted(item)

        # Remove one
        db.remove_from_blacklist("Item 2")
        assert not db.is_blacklisted("Item 2")
        assert db.is_blacklisted("Item 1")
        assert db.is_blacklisted("Item 3")

    def test_cache_statistics(self, db):
        """Test cache statistics retrieval."""
        # Add some entries
        db.update_steam_price("Item 1", 10.0, 100)
        db.update_steam_price("Item 2", 20.0, 200)
        db.update_steam_price("Item 3", 30.0, 300)

        stats = db.get_cache_stats()

        assert stats["total"] == 3
        assert stats["actual"] == 3  # All fresh
        assert stats["stale"] == 0

    def test_top_items_today(self, db):
        """Test retrieving top arbitrage items."""
        # Log items with different profits
        db.log_opportunity("Low Profit", 10.0, 12.0, 5.0, 100, "High")
        db.log_opportunity("Medium Profit", 10.0, 15.0, 30.0, 100, "High")
        db.log_opportunity("High Profit", 10.0, 20.0, 73.92, 100, "High")

        # Get top items
        top_items = db.get_top_items_today(limit=2)

        assert len(top_items) == 2
        # Should be sorted by profit descending
        assert top_items[0]["item_name"] == "High Profit"
        assert top_items[1]["item_name"] == "Medium Profit"

    def test_database_persistence(self, tmp_path):
        """Test that data persists across database instances."""
        db_path = tmp_path / "persistent_test.db"

        # Create first instance and save data
        db1 = SteamDatabaseHandler(str(db_path))
        db1.update_steam_price("Persistent Item", 50.0, 500)
        db1.update_settings(min_profit=25.0)
        del db1  # Close connection

        # Create second instance and verify data
        db2 = SteamDatabaseHandler(str(db_path))
        data = db2.get_steam_data("Persistent Item")
        settings = db2.get_settings()

        assert data is not None
        assert data["price"] == 50.0
        assert settings["min_profit"] == 25.0

    def test_concurrent_operations(self, db):
        """Test multiple operations in sequence."""
        # Cache
        db.update_steam_price("Item A", 10.0, 100)

        # Settings
        db.update_settings(min_profit=12.0)

        # Log
        db.log_opportunity("Item A", 10.0, 15.0, 30.0, 100, "High")

        # Blacklist
        db.add_to_blacklist("Item B", "Test")

        # Verify all operations worked
        assert db.get_steam_data("Item A") is not None
        assert db.get_settings()["min_profit"] == 12.0
        assert db.get_daily_stats()["count"] == 1
        assert db.is_blacklisted("Item B")


class TestSteamDatabaseEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture()
    def db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_edge_cases.db"
        return SteamDatabaseHandler(str(db_path))

    def test_get_nonexistent_item(self, db):
        """Test retrieving data for item that doesn't exist."""
        data = db.get_steam_data("Nonexistent Item")
        assert data is None

    def test_remove_nonexistent_blacklist_item(self, db):
        """Test removing item that's not in blacklist."""
        # Should not raise error
        db.remove_from_blacklist("Not Blacklisted Item")

    def test_special_characters_in_item_name(self, db):
        """Test handling items with special characters."""
        special_name = "Item | With 'Quotes' & \"Symbols\" (Test)"

        db.update_steam_price(special_name, 15.0, 75)
        data = db.get_steam_data(special_name)

        assert data is not None
        assert data["price"] == 15.0

    def test_very_long_item_name(self, db):
        """Test handling very long item names."""
        long_name = "A" * 500  # Very long name

        db.update_steam_price(long_name, 5.0, 10)
        data = db.get_steam_data(long_name)

        assert data is not None

    def test_zero_values(self, db):
        """Test handling zero values."""
        db.update_steam_price("Zero Price Item", 0.0, 0)
        data = db.get_steam_data("Zero Price Item")

        assert data is not None
        assert data["price"] == 0.0
        assert data["volume"] == 0

    def test_negative_profit_logging(self, db):
        """Test logging opportunities with negative profit."""
        db.log_opportunity("Bad Deal", 10.0, 8.0, -20.0, 100, "High")

        stats = db.get_daily_stats()
        assert stats["count"] == 1
        assert stats["avg_profit"] < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
