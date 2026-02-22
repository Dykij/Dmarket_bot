"""Tests for inventory_manager module.

This module tests the InventoryManager class for automatic selling
and price undercutting.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestInventoryManager:
    """Tests for InventoryManager class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_inventory = AsyncMock(return_value={"objects": []})
        api.get_my_offers = AsyncMock(return_value={"objects": []})
        api.create_offer = AsyncMock(return_value={"success": True})
        api.edit_offer = AsyncMock(return_value={"success": True})
        api.delete_offer = AsyncMock(return_value={"success": True})
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.fixture
    def mock_bot(self):
        """Create mock Telegram bot."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        return bot

    @pytest.fixture
    def manager(self, mock_api, mock_bot):
        """Create InventoryManager instance."""
        from src.dmarket.inventory_manager import InventoryManager
        return InventoryManager(
            api_client=mock_api,
            telegram_bot=mock_bot,
            undercut_step=1,
            min_profit_margin=1.02,
        )

    def test_init(self, manager, mock_api):
        """Test initialization."""
        assert manager.api == mock_api
        assert manager.undercut_step == 1
        assert manager.min_profit_margin == 1.02
        assert manager.total_undercuts == 0
        assert manager.total_listed == 0
        assert manager.failed_listings == 0

    def test_init_with_config(self, mock_api, mock_bot):
        """Test initialization with config."""
        from src.dmarket.inventory_manager import InventoryManager
        config = {
            "repricing": {"enabled": False},
            "blacklist": {"enabled": False},
        }
        manager = InventoryManager(
            api_client=mock_api,
            telegram_bot=mock_bot,
            config=config,
        )
        assert manager.config == config

    def test_get_statistics(self, manager):
        """Test getting statistics."""
        manager.total_undercuts = 10
        manager.total_listed = 20
        manager.failed_listings = 2
        manager.relist_attempts["item1"] = 3

        stats = manager.get_statistics()

        assert stats["total_undercuts"] == 10
        assert stats["total_listed"] == 20
        assert stats["failed_listings"] == 2
        assert stats["active_relist_attempts"] == 1

    def test_relist_attempts_tracking(self, manager):
        """Test relist attempts are tracked correctly."""
        item_id = "item123"

        # Initially no attempts
        assert item_id not in manager.relist_attempts

        # Track first attempt
        manager.relist_attempts[item_id] = 1
        assert manager.relist_attempts[item_id] == 1

        # Track second attempt
        manager.relist_attempts[item_id] = 2
        assert manager.relist_attempts[item_id] == 2

    def test_max_relist_attempts(self, manager):
        """Test max relist attempts configuration."""
        assert manager.max_relist_attempts == 5  # Default

    def test_check_interval(self, manager):
        """Test check interval configuration."""
        assert manager.check_interval == 1800  # 30 minutes default

    def test_undercut_step(self, manager):
        """Test undercut step configuration."""
        assert manager.undercut_step == 1

    def test_min_profit_margin(self, manager):
        """Test minimum profit margin configuration."""
        assert manager.min_profit_margin == 1.02

    @pytest.mark.asyncio
    async def test_refresh_inventory_loop_runs(self, manager, mock_api):
        """Test that refresh inventory loop can be started."""
        # The loop should run without errors
        # We'll test it exits properly when cancelled
        import asyncio

        mock_api.get_my_offers.return_value = {"objects": []}
        mock_api.get_inventory.return_value = {"objects": []}

        # Run for a very short time
        task = asyncio.create_task(manager.refresh_inventory_loop())
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_get_market_min_price(self, manager, mock_api):
        """Test getting minimum market price."""
        mock_api.get_market_items.return_value = {
            "objects": [
                {"price": {"amount": 2500}},
                {"price": {"amount": 2600}},
            ]
        }

        price = await manager._get_market_min_price("AK-47 | Redline")

        # Should return lowest price
        assert price == 2500

    @pytest.mark.asyncio
    async def test_get_market_min_price_no_items(self, manager, mock_api):
        """Test getting market price with no listings."""
        mock_api.get_market_items.return_value = {"objects": []}

        price = await manager._get_market_min_price("Rare Item")

        assert price == 0

    @pytest.mark.asyncio
    async def test_send_telegram_message(self, manager, mock_bot):
        """Test sending Telegram notification."""
        await manager._send_telegram_message("Test message")

        # Should not raise error even if bot is mocked

    @pytest.mark.asyncio
    async def test_send_telegram_message_no_bot(self, mock_api):
        """Test sending message without bot configured."""
        from src.dmarket.inventory_manager import InventoryManager
        manager = InventoryManager(
            api_client=mock_api,
            telegram_bot=None,
        )

        # Should not raise
        await manager._send_telegram_message("Test message")
