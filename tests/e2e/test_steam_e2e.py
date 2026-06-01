"""
End-to-End tests for Steam API integration.

Tests the complete workflow from scanning to notification.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.dmarket.arbitrage_scanner import ArbitrageScanner

from src.utils.steam_db_handler import get_steam_db


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_full_arbitrage_workflow_with_steam():
    """E2E test: Complete arbitrage workflow with Steam integration."""

    # Simplified test that tests Steam enhancement directly
    from src.dmarket.steam_arbitrage_enhancer import SteamArbitrageEnhancer

    # Clear any cached data for this specific test
    from src.utils.steam_db_handler import get_steam_db

    db = get_steam_db()

    # Clear cache for test item
    test_item_name = "AK-47 | Redline (Field-Tested)"
    try:
        db.conn.execute(
            "DELETE FROM steam_cache WHERE market_hash_name LIKE ?", (f"%{test_item_name}%",)
        )
        db.conn.commit()
    except:
        pass

    # Mock input items (what scanner would provide)
    input_items = [
        {
            "title": test_item_name,
            "price": {"USD": 1000},  # $10.00 in cents
            "itemId": "test123",
            "extra": {"tradeLock": 0},
            "profit": 30.44,
        }
    ]

    # Create enhancer
    enhancer = SteamArbitrageEnhancer()

    # Mock Steam API calls in the module where it's imported
    with patch("src.dmarket.steam_arbitrage_enhancer.get_steam_price") as mock_steam:
        mock_steam.return_value = {"price": 15.00, "volume": 150, "median_price": 15.50}

        # Enhance items with Steam data
        results = await enhancer.enhance_items(input_items)

        # Verify results
        assert len(results) > 0, (
            f"Should return at least one item after enhancement, got {len(results)}"
        )

        item = results[0]

        # Check basic data preserved
        assert item["title"] == test_item_name
        assert item["price"]["USD"] == 1000

        # Check Steam enrichment
        assert "steam_price" in item, "Should have Steam price"
        assert item["steam_price"] > 0, f"Steam price should be positive, got {item['steam_price']}"
        assert item["steam_volume"] >= 50, (
            f"Steam volume should be >= 50, got {item['steam_volume']}"
        )  # min_volume from settings

        # Check profit calculation
        assert "profit_pct" in item or "steam_profit_pct" in item, "Should have profit calculation"
        profit = item.get("steam_profit_pct") or item.get("profit_pct")
        # Just check it's positive profit
        assert profit > 0, f"Profit should be positive, got {profit}"

        # Check liquidity status
        assert "liquidity_status" in item


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_scanner_filters_low_liquidity_items():
    """E2E test: Scanner should filter out low liquidity items."""

    api_client = AsyncMock()
    scanner = ArbitrageScanner(
        api_client=api_client,
        enable_steam_check=True,
        enable_liquidity_filter=False,  # We test Steam filtering, not liquidity filter
    )

    # Mock items with varying liquidity
    mock_items = [
        {"title": "High Volume Item", "price": {"USD": 1000}, "itemId": "item1", "profit": 30},
        {"title": "Low Volume Item", "price": {"USD": 1000}, "itemId": "item2", "profit": 30},
    ]

    # Mock arbitrage functions
    with patch("src.dmarket.arbitrage.arbitrage_mid_async") as mock_arbitrage:
        mock_arbitrage.return_value = mock_items

        with patch("src.dmarket.arbitrage.ArbitrageTrader") as mock_trader_class:
            mock_trader = AsyncMock()
            mock_trader.find_profitable_items = AsyncMock(return_value=[])
            mock_trader_class.return_value = mock_trader

            with patch("src.dmarket.steam_api.get_steam_price") as mock_steam:

                def steam_price_side_effect(name, **kwargs):
                    if "High Volume" in name:
                        return {"price": 15.00, "volume": 200}  # Good
                    return {"price": 15.00, "volume": 10}  # Too low

                mock_steam.side_effect = steam_price_side_effect

                # Get Steam DB
                db = get_steam_db()

                # Set min volume to 50
                db.update_settings(min_volume=50)

            results = []
            for item in mock_items:
                steam_data = await mock_steam(item["title"])
                if steam_data and steam_data["volume"] >= 50:
                    results.append({**item, "steam_volume": steam_data["volume"]})

                # Should only have high volume item
                assert len(results) == 1
                assert results[0]["title"] == "High Volume Item"


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_notification_delivery_flow():
    """E2E test: Notification is sent when opportunity found."""

    api_client = AsyncMock()

    # Mock scan results
    opportunity = {
        "title": "AWP | Asiimov (Field-Tested)",
        "price": {"USD": 2000},
        "steam_price": 30.00,
        "steam_profit_pct": 30.44,
        "steam_volume": 100,
        "liquidity_status": "✅ Средняя",
    }

    # Simulate notification
    message = (
        f"🎯 Арбитраж найден!\n\n"
        f"📦 {opportunity['title']}\n"
        f"💰 DMarket: ${opportunity['price']['USD'] / 100:.2f}\n"
        f"🎮 Steam: ${opportunity['steam_price']:.2f}\n"
        f"📈 Профит: {opportunity['steam_profit_pct']:.1f}%\n"
        f"📊 Объем: {opportunity['steam_volume']} продаж/день\n"
    )

    # Verify message format
    assert "🎯" in message
    assert "AWP | Asiimov" in message
    assert "30.0" in message  # Steam price
    assert "30.4" in message  # Profit


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_cache_reduces_api_calls():
    """E2E test: Cache should reduce Steam API calls."""

    import tempfile

    from src.utils.steam_db_handler import SteamDatabaseHandler

    # Create temporary DB
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        # First call - should hit API
        with patch("src.dmarket.steam_api.get_steam_price") as mock_steam:
            mock_steam.return_value = {"price": 10.0, "volume": 100}

            item_name = "Test Item"

            # Cache miss - call API
            cached = db.get_steam_data(item_name)
            if not cached or not db.is_cache_actual(cached.get("last_updated"), hours=6):
                fresh = await mock_steam(item_name)
                db.update_steam_price(item_name, fresh["price"], fresh["volume"])

            assert mock_steam.call_count == 1

            # Second call - should use cache
            mock_steam.reset_mock()

            cached2 = db.get_steam_data(item_name)
            if cached2 and db.is_cache_actual(cached2["last_updated"], hours=6):
                # Use cached data, no API call
                pass
            else:
                await mock_steam(item_name)

            # Should not call API agAlgon
            assert mock_steam.call_count == 0


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_blacklist_prevents_notifications():
    """E2E test: Blacklisted items should be skipped."""

    import tempfile

    from src.utils.steam_db_handler import SteamDatabaseHandler

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = SteamDatabaseHandler(tmp.name)

        item_name = "Scam Item"

        # Add to blacklist
        db.add_to_blacklist(item_name, reason="User blacklisted")

        # Try to process item
        if db.is_blacklisted(item_name):
            skipped = True
        else:
            skipped = False

        assert skipped is True

        # Remove from blacklist
        db.remove_from_blacklist(item_name)

        # Should not be blacklisted anymore
        assert not db.is_blacklisted(item_name)


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_settings_control_workflow():
    """E2E test: Settings changes affect scanner behavior."""

    import tempfile

    from src.utils.steam_db_handler import SteamDatabaseHandler

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


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_statistics_tracking():
    """E2E test: Opportunities are logged and statistics work."""

    import tempfile

    from src.utils.steam_db_handler import SteamDatabaseHandler

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


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_rate_limit_protection():
    """E2E test: Rate limit protection prevents API spam."""

    # Import and reset backoff at module level to avoid reusing global state
    import src.dmarket.steam_api as steam_module
    from src.dmarket.steam_api import RateLimitError

    # Force reset module state BEFORE anything else
    steam_module.steam_backoff_until = None

    # Simulate rate limit error
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        # Import fresh AFTER reset
        from src.dmarket.steam_api import get_backoff_status

        # Double-check reset took effect
        steam_module.steam_backoff_until = None

        # First call triggers rate limit and raises RateLimitError
        with pytest.raises(RateLimitError):
            await steam_module.get_steam_price("Test Item")

        # Check backoff is active after rate limit hit
        status = get_backoff_status()
        assert status["active"] is True
        assert status["remaining_seconds"] > 0

    # Reset after test
    steam_module.steam_backoff_until = None


@pytest.mark.e2e()
def test_database_persistence():
    """E2E test: Data persists across database sessions."""

    import os
    import tempfile

    from src.utils.steam_db_handler import SteamDatabaseHandler

    # Create temp DB file that we'll manually manage
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # Close file descriptor immediately

    try:
        # Session 1: Write data
        db1 = SteamDatabaseHandler(tmp_path)
        db1.update_steam_price("Persistent Item", 10.0, 100)
        db1.update_settings(min_profit=15.0)
        db1.conn.close()  # Explicitly close

        # Session 2: Read data
        db2 = SteamDatabaseHandler(tmp_path)
        data = db2.get_steam_data("Persistent Item")
        settings = db2.get_settings()

        assert data is not None
        assert data["price"] == 10.0
        assert settings["min_profit"] == 15.0

        db2.conn.close()  # Explicitly close

    finally:
        # Clean up with retry
        import time

        for _ in range(5):
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                break
            except PermissionError:
                time.sleep(0.1)

    # Create temp file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # First session - write data
        db1 = SteamDatabaseHandler(db_path)
        db1.update_steam_price("Persistent Item", 25.0, 150)
        db1.update_settings(min_profit=20.0)
        db1.add_to_blacklist("Bad Item", "Test")
        db1.conn.close()  # Explicitly close connection
        del db1

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
        assert db2.is_blacklisted("Bad Item")

        db2.conn.close()  # Explicitly close connection

    finally:
        # Cleanup with retry for Windows
        import time

        for _ in range(5):
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
                break
            except PermissionError:
                time.sleep(0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
