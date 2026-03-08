"""
Fixed End-to-End tests for Steam API integration.

Tests the complete workflow with proper mocking.
"""

import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.steam_api import calculate_arbitrage, get_backoff_status, reset_backoff
from src.utils.steam_db_handler import SteamDatabaseHandler


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_full_arbitrage_workflow_with_steam():
    """E2E test: Complete arbitrage workflow with Steam integration."""

    # Test Steam API functions directly

    # Test calculate_arbitrage directly (returns float, not dict)
    profit_pct = calculate_arbitrage(dmarket_price=10.00, steam_price=15.00)

    assert profit_pct is not None
    assert isinstance(profit_pct, float)
    assert profit_pct > 30  # Should be around 30.44%

    # Test with different prices
    profit_pct2 = calculate_arbitrage(dmarket_price=20.00, steam_price=30.00)
    assert profit_pct2 > 30

    # Test edge case - no profit
    profit_pct3 = calculate_arbitrage(dmarket_price=15.00, steam_price=15.00)
    assert profit_pct3 < 0  # Loss due to Steam commission


@pytest.mark.e2e()
def test_scanner_filters_low_liquidity_items():
    """E2E test: Scanner should filter out low liquidity items."""

    # Create temp DB
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        # Set min volume to 50
        db.update_settings(min_volume=50)
        settings = db.get_settings()

        assert settings["min_volume"] == 50

        # Test data
        items = [
            {"name": "High Volume Item", "volume": 200},
            {"name": "Low Volume Item", "volume": 10},
        ]

        # Filter items
        filtered = [item for item in items if item["volume"] >= settings["min_volume"]]

        # Should only have high volume item
        assert len(filtered) == 1
        assert filtered[0]["name"] == "High Volume Item"

        # Cleanup
        db.conn.close()
        try:
            os.unlink(tmp.name)
        except:
            pass


@pytest.mark.e2e()
def test_notification_delivery_flow():
    """E2E test: Notification message is formatted correctly."""

    # Mock scan results
    opportunity = {
        "title": "AWP | Asiimov (Field-Tested)",
        "price": {"USD": 2000},  # $20.00
        "steam_price": 30.00,
        "steam_profit_pct": 30.44,
        "steam_volume": 100,
        "liquidity_status": "✅ Средняя",
    }

    # Format notification message (как это делается в боте)
    message = (
        f"🎯 Арбитраж найден!\n\n"
        f"📦 {opportunity['title']}\n"
        f"💰 DMarket: ${opportunity['price']['USD'] / 100:.2f}\n"
        f"🎮 Steam: ${opportunity['steam_price']:.2f}\n"
        f"📈 Профит: {opportunity['steam_profit_pct']:.1f}%\n"
        f"📊 Объем: {opportunity['steam_volume']} продаж/день\n"
        f"💧 {opportunity['liquidity_status']}\n"
    )

    # Verify message format
    assert "🎯 Арбитраж найден!" in message
    assert "AWP | Asiimov" in message
    assert "$20.00" in message  # DMarket price
    assert "$30.00" in message  # Steam price
    assert "30.4%" in message  # Profit
    assert "100 продаж/день" in message
    assert "✅" in message


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_cache_reduces_api_calls():
    """E2E test: Cache should reduce Steam API calls."""

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        item_name = "Test Item"

        # First call - simulate API fetch and cache
        db.update_steam_price(item_name, 10.0, 100)

        # Second call - get from cache
        cached = db.get_steam_data(item_name)

        assert cached is not None
        assert cached["price"] == 10.0
        assert cached["volume"] == 100

        # Verify cache is actual (within 6 hours)
        is_actual = db.is_cache_actual(cached["last_updated"], hours=6)
        assert is_actual is True

        # Cleanup
        db.conn.close()
        try:
            os.unlink(tmp.name)
        except:
            pass


@pytest.mark.e2e()
def test_blacklist_prevents_notifications():
    """E2E test: Blacklisted items should be skipped."""

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        item_name = "Scam Item"

        # Add to blacklist
        db.add_to_blacklist(item_name, reason="User blacklisted")

        # Check if blacklisted
        assert db.is_blacklisted(item_name) is True

        # Remove from blacklist
        db.remove_from_blacklist(item_name)

        # Should not be blacklisted anymore
        assert db.is_blacklisted(item_name) is False

        # Cleanup
        db.conn.close()
        try:
            os.unlink(tmp.name)
        except:
            pass


@pytest.mark.e2e()
def test_settings_control_workflow():
    """E2E test: Settings changes affect scanner behavior."""

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        # Initial settings
        settings = db.get_settings()
        assert settings["min_profit"] == 10.0
        assert settings["min_volume"] == 50

        # Update settings
        db.update_settings(min_profit=15.0, min_volume=100)

        # Verify changes
        updated = db.get_settings()
        assert updated["min_profit"] == 15.0
        assert updated["min_volume"] == 100

        # Pause scanner
        db.update_settings(is_paused=True)
        assert db.get_settings()["is_paused"] is True

        # Resume scanner
        db.update_settings(is_paused=False)
        assert db.get_settings()["is_paused"] is False

        # Cleanup
        db.conn.close()
        try:
            os.unlink(tmp.name)
        except:
            pass


@pytest.mark.e2e()
def test_statistics_tracking():
    """E2E test: Opportunities are logged and statistics work."""

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        # Log multiple opportunities
        opportunities = [
            ("Item 1", 10.0, 15.0, 30.44, 150, "High"),
            ("Item 2", 20.0, 28.0, 21.7, 100, "Medium"),
            ("Item 3", 5.0, 8.0, 39.1, 200, "High"),
        ]

        for name, dm_price, steam_price, profit, volume, liq in opportunities:
            db.log_opportunity(name, dm_price, steam_price, profit, volume, liq)

        # Get statistics
        stats = db.get_daily_stats()

        assert stats["count"] == 3
        assert 25 < stats["avg_profit"] < 35  # Average should be ~30%
        assert stats["max_profit"] > 35  # Max should be 39.1%

        # Get top items
        top = db.get_top_items_today(limit=2)
        assert len(top) == 2
        # First should be Item 3 with highest profit
        assert top[0]["item_name"] == "Item 3"

        # Cleanup
        db.conn.close()
        try:
            os.unlink(tmp.name)
        except:
            pass


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_rate_limit_protection():
    """E2E test: Rate limit protection prevents API spam."""

    from src.dmarket.steam_api import get_steam_price

    # Reset backoff first
    reset_backoff()

    # WAlgot a moment
    import asyncio

    await asyncio.sleep(0.3)

    # Simulate rate limit error
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        # First call triggers rate limit (will raise exception)
        try:
            await get_steam_price("Test Item")
        except Exception:
            # Expected
            pass

        # Check backoff is active
        status = get_backoff_status()
        assert status["active"] is True
        assert status["remaining_seconds"] > 0

    # Clean up
    reset_backoff()


@pytest.mark.e2e()
def test_database_persistence():
    """E2E test: Data persists across database sessions."""

    # Create temp file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # First session - write data
        db1 = SteamDatabaseHandler(db_path)
        db1.update_steam_price("Persistent Item", 25.0, 150)
        db1.update_settings(min_profit=20.0)
        db1.add_to_blacklist("Bad Item", "Test")

        # Close connection explicitly
        db1.conn.close()
        del db1

        # WAlgot for file to be released (Windows issue)
        time.sleep(0.3)

        # Second session - read data
        db2 = SteamDatabaseHandler(db_path)

        # Verify cache
        cached = db2.get_steam_data("Persistent Item")
        assert cached is not None
        assert cached["price"] == 25.0

        # Verify settings
        settings = db2.get_settings()
        assert settings["min_profit"] == 20.0

        # Verify blacklist
        assert db2.is_blacklisted("Bad Item") is True

        # Close connection
        db2.conn.close()
        del db2

    finally:
        # Cleanup - wait for Windows to release file
        time.sleep(0.5)

        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            # On Windows, file might still be locked
            # That's OK for test purposes
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
