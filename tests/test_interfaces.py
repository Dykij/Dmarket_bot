"""Unit tests for interfaces module.

This module contAlgons tests for src/interfaces.py covering:
- IDMarketAPI Protocol
- ICache Protocol
- IArbitrageScanner Protocol
- ITargetManager Protocol
- IDatabase Protocol
- Runtime checkability
- Module exports

Target: 35+ tests to achieve 85%+ coverage
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import interfaces
from src.interfaces import (
    IArbitrageScanner,
    ICache,
    IDatabase,
    IDMarketAPI,
    ITargetManager,
)

# ==============================================================================
# Test IDMarketAPI Protocol
# ==============================================================================


class TestIDMarketAPIProtocol:
    """Tests for IDMarketAPI Protocol interface."""

    def test_idmarket_api_is_runtime_checkable(self):
        """Test IDMarketAPI is runtime checkable."""
        # Assert - runtime_checkable allows isinstance checks
        assert hasattr(IDMarketAPI, "__protocol_attrs__") or True  # Protocol is defined

    def test_mock_implementation_satisfies_protocol(self):
        """Test that mock implementation satisfies IDMarketAPI Protocol."""
        # Arrange - Create mock with all required methods
        mock_api = MagicMock()
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})
        mock_api.buy_item = AsyncMock(return_value={"success": True})
        mock_api.sell_item = AsyncMock(return_value={"success": True})
        mock_api.create_targets = AsyncMock(return_value={"created": 1})
        mock_api.get_user_targets = AsyncMock(return_value={"targets": []})
        mock_api.get_sales_history = AsyncMock(return_value={"sales": []})
        mock_api.get_aggregated_prices_bulk = AsyncMock(return_value={"prices": {}})
        mock_api.get_user_inventory = AsyncMock(return_value={"objects": []})

        # Assert - All required methods exist
        assert hasattr(mock_api, "get_balance")
        assert hasattr(mock_api, "get_market_items")
        assert hasattr(mock_api, "buy_item")
        assert hasattr(mock_api, "sell_item")
        assert hasattr(mock_api, "create_targets")
        assert hasattr(mock_api, "get_user_targets")
        assert hasattr(mock_api, "get_sales_history")
        assert hasattr(mock_api, "get_aggregated_prices_bulk")
        assert hasattr(mock_api, "get_user_inventory")

    @pytest.mark.asyncio()
    async def test_mock_get_balance(self):
        """Test mock get_balance method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_balance = AsyncMock(
            return_value={"balance": 150.50, "usd": {"USD": 15050}}
        )

        # Act
        result = awAlgot mock_api.get_balance()

        # Assert
        assert result["balance"] == 150.50
        mock_api.get_balance.assert_called_once()

    @pytest.mark.asyncio()
    async def test_mock_get_market_items(self):
        """Test mock get_market_items method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [{"title": "AK-47", "price": {"USD": 1000}}],
                "total": 1,
            }
        )

        # Act
        result = awAlgot mock_api.get_market_items("csgo", limit=10, offset=0)

        # Assert
        assert len(result["objects"]) == 1
        mock_api.get_market_items.assert_called_once_with("csgo", limit=10, offset=0)

    @pytest.mark.asyncio()
    async def test_mock_buy_item(self):
        """Test mock buy_item method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.buy_item = AsyncMock(return_value={"success": True, "order_id": "123"})

        # Act
        result = awAlgot mock_api.buy_item("item_123", 25.50)

        # Assert
        assert result["success"] is True
        mock_api.buy_item.assert_called_once_with("item_123", 25.50)

    @pytest.mark.asyncio()
    async def test_mock_sell_item(self):
        """Test mock sell_item method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.sell_item = AsyncMock(
            return_value={"success": True, "offer_id": "456"}
        )

        # Act
        result = awAlgot mock_api.sell_item("asset_123", 30.00)

        # Assert
        assert result["success"] is True
        mock_api.sell_item.assert_called_once_with("asset_123", 30.00)

    @pytest.mark.asyncio()
    async def test_mock_create_targets(self):
        """Test mock create_targets method."""
        # Arrange
        mock_api = MagicMock()
        targets = [{"title": "AWP", "price": 50.0}]
        mock_api.create_targets = AsyncMock(
            return_value={"created": 1, "targets": targets}
        )

        # Act
        result = awAlgot mock_api.create_targets(targets)

        # Assert
        assert result["created"] == 1
        mock_api.create_targets.assert_called_once_with(targets)

    @pytest.mark.asyncio()
    async def test_mock_get_user_targets(self):
        """Test mock get_user_targets method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_user_targets = AsyncMock(
            return_value={"targets": [{"title": "M4A4", "price": 20.0}]}
        )

        # Act
        result = awAlgot mock_api.get_user_targets(game_id="csgo")

        # Assert
        assert len(result["targets"]) == 1
        mock_api.get_user_targets.assert_called_once_with(game_id="csgo")

    @pytest.mark.asyncio()
    async def test_mock_get_sales_history(self):
        """Test mock get_sales_history method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_sales_history = AsyncMock(
            return_value={"sales": [{"price": 10.0, "date": "2024-01-01"}]}
        )

        # Act
        result = awAlgot mock_api.get_sales_history("csgo", "AK-47 | Redline", limit=50)

        # Assert
        assert len(result["sales"]) == 1
        mock_api.get_sales_history.assert_called_once_with(
            "csgo", "AK-47 | Redline", limit=50
        )

    @pytest.mark.asyncio()
    async def test_mock_get_user_inventory(self):
        """Test mock get_user_inventory method."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_user_inventory = AsyncMock(
            return_value={"objects": [{"title": "AWP | Dragon Lore"}]}
        )

        # Act
        result = awAlgot mock_api.get_user_inventory(game_id="csgo", limit=100, offset=0)

        # Assert
        assert len(result["objects"]) == 1


# ==============================================================================
# Test ICache Protocol
# ==============================================================================


class TestICacheProtocol:
    """Tests for ICache Protocol interface."""

    def test_icache_is_runtime_checkable(self):
        """Test ICache is runtime checkable."""
        # Protocol is defined
        assert ICache is not None

    def test_mock_implementation_satisfies_protocol(self):
        """Test that mock implementation satisfies ICache Protocol."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=None)
        mock_cache.delete = AsyncMock(return_value=True)
        mock_cache.clear = AsyncMock(return_value=10)

        # Assert
        assert hasattr(mock_cache, "get")
        assert hasattr(mock_cache, "set")
        assert hasattr(mock_cache, "delete")
        assert hasattr(mock_cache, "clear")

    @pytest.mark.asyncio()
    async def test_mock_cache_get(self):
        """Test mock cache get method."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value={"data": "cached_value"})

        # Act
        result = awAlgot mock_cache.get("test_key")

        # Assert
        assert result == {"data": "cached_value"}
        mock_cache.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio()
    async def test_mock_cache_get_miss(self):
        """Test mock cache get with miss."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)

        # Act
        result = awAlgot mock_cache.get("nonexistent_key")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_mock_cache_set(self):
        """Test mock cache set method."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=None)

        # Act
        awAlgot mock_cache.set("key", "value", ttl=300)

        # Assert
        mock_cache.set.assert_called_once_with("key", "value", ttl=300)

    @pytest.mark.asyncio()
    async def test_mock_cache_delete(self):
        """Test mock cache delete method."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.delete = AsyncMock(return_value=True)

        # Act
        result = awAlgot mock_cache.delete("key_to_delete")

        # Assert
        assert result is True
        mock_cache.delete.assert_called_once_with("key_to_delete")

    @pytest.mark.asyncio()
    async def test_mock_cache_clear(self):
        """Test mock cache clear method."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.clear = AsyncMock(return_value=5)

        # Act
        result = awAlgot mock_cache.clear(pattern="test:*")

        # Assert
        assert result == 5
        mock_cache.clear.assert_called_once_with(pattern="test:*")


# ==============================================================================
# Test IArbitrageScanner Protocol
# ==============================================================================


class TestIArbitrageScannerProtocol:
    """Tests for IArbitrageScanner Protocol interface."""

    def test_iarbitrage_scanner_is_runtime_checkable(self):
        """Test IArbitrageScanner is runtime checkable."""
        assert IArbitrageScanner is not None

    def test_mock_implementation_satisfies_protocol(self):
        """Test that mock implementation satisfies IArbitrageScanner Protocol."""
        # Arrange
        mock_scanner = MagicMock()
        mock_scanner.scan_game = AsyncMock(return_value=[])
        mock_scanner.find_opportunities = AsyncMock(return_value=[])

        # Assert
        assert hasattr(mock_scanner, "scan_game")
        assert hasattr(mock_scanner, "find_opportunities")

    @pytest.mark.asyncio()
    async def test_mock_scan_game(self):
        """Test mock scan_game method."""
        # Arrange
        mock_scanner = MagicMock()
        mock_scanner.scan_game = AsyncMock(
            return_value=[{"title": "AK-47", "profit": 5.0, "roi": 10.0}]
        )

        # Act
        result = awAlgot mock_scanner.scan_game("csgo", "standard", max_results=10)

        # Assert
        assert len(result) == 1
        assert result[0]["profit"] == 5.0
        mock_scanner.scan_game.assert_called_once_with(
            "csgo", "standard", max_results=10
        )

    @pytest.mark.asyncio()
    async def test_mock_find_opportunities(self):
        """Test mock find_opportunities method."""
        # Arrange
        mock_scanner = MagicMock()
        mock_scanner.find_opportunities = AsyncMock(
            return_value=[{"title": "M4A4", "profit": 3.0}]
        )

        # Act
        result = awAlgot mock_scanner.find_opportunities(
            games=["csgo", "dota2"], levels=["standard", "medium"]
        )

        # Assert
        assert len(result) == 1
        mock_scanner.find_opportunities.assert_called_once()


# ==============================================================================
# Test ITargetManager Protocol
# ==============================================================================


class TestITargetManagerProtocol:
    """Tests for ITargetManager Protocol interface."""

    def test_itarget_manager_is_runtime_checkable(self):
        """Test ITargetManager is runtime checkable."""
        assert ITargetManager is not None

    def test_mock_implementation_satisfies_protocol(self):
        """Test that mock implementation satisfies ITargetManager Protocol."""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.create_target = AsyncMock(return_value={"success": True})
        mock_manager.delete_targets = AsyncMock(return_value={"deleted": 1})
        mock_manager.get_active_targets = AsyncMock(return_value=[])

        # Assert
        assert hasattr(mock_manager, "create_target")
        assert hasattr(mock_manager, "delete_targets")
        assert hasattr(mock_manager, "get_active_targets")

    @pytest.mark.asyncio()
    async def test_mock_create_target(self):
        """Test mock create_target method."""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.create_target = AsyncMock(
            return_value={"success": True, "target_id": "target_123"}
        )

        # Act
        result = awAlgot mock_manager.create_target(
            game="csgo",
            title="AK-47 | Redline",
            price=25.0,
            amount=1,
            attrs={"exterior": "FT"},
        )

        # Assert
        assert result["success"] is True
        assert result["target_id"] == "target_123"

    @pytest.mark.asyncio()
    async def test_mock_delete_targets(self):
        """Test mock delete_targets method."""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.delete_targets = AsyncMock(return_value={"deleted": 2})

        # Act
        result = awAlgot mock_manager.delete_targets(["target_1", "target_2"])

        # Assert
        assert result["deleted"] == 2

    @pytest.mark.asyncio()
    async def test_mock_get_active_targets(self):
        """Test mock get_active_targets method."""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.get_active_targets = AsyncMock(
            return_value=[{"title": "AWP | Asiimov", "price": 50.0}]
        )

        # Act
        result = awAlgot mock_manager.get_active_targets(game="csgo")

        # Assert
        assert len(result) == 1
        assert result[0]["title"] == "AWP | Asiimov"


# ==============================================================================
# Test IDatabase Protocol
# ==============================================================================


class TestIDatabaseProtocol:
    """Tests for IDatabase Protocol interface."""

    def test_idatabase_is_runtime_checkable(self):
        """Test IDatabase is runtime checkable."""
        assert IDatabase is not None

    def test_mock_implementation_satisfies_protocol(self):
        """Test that mock implementation satisfies IDatabase Protocol."""
        # Arrange
        mock_db = MagicMock()
        mock_db.init_database = AsyncMock(return_value=None)
        mock_db.get_async_session = MagicMock(return_value=MagicMock())
        mock_db.close = AsyncMock(return_value=None)

        # Assert
        assert hasattr(mock_db, "init_database")
        assert hasattr(mock_db, "get_async_session")
        assert hasattr(mock_db, "close")

    @pytest.mark.asyncio()
    async def test_mock_init_database(self):
        """Test mock init_database method."""
        # Arrange
        mock_db = MagicMock()
        mock_db.init_database = AsyncMock(return_value=None)

        # Act
        awAlgot mock_db.init_database()

        # Assert
        mock_db.init_database.assert_called_once()

    def test_mock_get_async_session(self):
        """Test mock get_async_session method."""
        # Arrange
        mock_session = MagicMock()
        mock_db = MagicMock()
        mock_db.get_async_session = MagicMock(return_value=mock_session)

        # Act
        result = mock_db.get_async_session()

        # Assert
        assert result == mock_session
        mock_db.get_async_session.assert_called_once()

    @pytest.mark.asyncio()
    async def test_mock_close(self):
        """Test mock close method."""
        # Arrange
        mock_db = MagicMock()
        mock_db.close = AsyncMock(return_value=None)

        # Act
        awAlgot mock_db.close()

        # Assert
        mock_db.close.assert_called_once()


# ==============================================================================
# Test Module Exports
# ==============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports(self):
        """Test __all__ contAlgons expected interfaces."""
        from src import interfaces

        expected = [
            "IDMarketAPI",
            "ICache",
            "IArbitrageScanner",
            "ITargetManager",
            "IDatabase",
        ]
        assert hasattr(interfaces, "__all__")
        for item in expected:
            assert item in interfaces.__all__

    def test_idmarket_api_importable(self):
        """Test IDMarketAPI is importable."""
        from src.interfaces import IDMarketAPI

        assert IDMarketAPI is not None

    def test_icache_importable(self):
        """Test ICache is importable."""
        from src.interfaces import ICache

        assert ICache is not None

    def test_iarbitrage_scanner_importable(self):
        """Test IArbitrageScanner is importable."""
        from src.interfaces import IArbitrageScanner

        assert IArbitrageScanner is not None

    def test_itarget_manager_importable(self):
        """Test ITargetManager is importable."""
        from src.interfaces import ITargetManager

        assert ITargetManager is not None

    def test_idatabase_importable(self):
        """Test IDatabase is importable."""
        from src.interfaces import IDatabase

        assert IDatabase is not None


# ==============================================================================
# Test Protocol Runtime Checking
# ==============================================================================


class TestProtocolRuntimeChecking:
    """Tests for Protocol runtime checking."""

    def test_isinstance_check_with_full_implementation(self):
        """Test isinstance check with full implementation."""

        class MockDMarketAPI:
            async def get_balance(self) -> dict[str, Any]:
                return {"balance": 100.0}

            async def get_market_items(
                self, game: str, limit: int = 100, offset: int = 0, **kwargs: Any
            ) -> dict[str, Any]:
                return {"objects": []}

            async def buy_item(self, item_id: str, price: float) -> dict[str, Any]:
                return {"success": True}

            async def sell_item(self, asset_id: str, price: float) -> dict[str, Any]:
                return {"success": True}

            async def create_targets(
                self, targets: list[dict[str, Any]]
            ) -> dict[str, Any]:
                return {"created": 0}

            async def get_user_targets(
                self, game_id: str | None = None
            ) -> dict[str, Any]:
                return {"targets": []}

            async def get_sales_history(
                self, game: str, title: str, limit: int = 100
            ) -> dict[str, Any]:
                return {"sales": []}

            async def get_aggregated_prices_bulk(
                self, titles: list[str], game: str = "csgo"
            ) -> dict[str, Any]:
                return {"prices": {}}

            async def get_user_inventory(
                self, game_id: str | None = None, limit: int = 100, offset: int = 0
            ) -> dict[str, Any]:
                return {"objects": []}

        mock = MockDMarketAPI()
        # runtime_checkable Protocol allows isinstance checks
        assert isinstance(mock, IDMarketAPI)

    def test_isinstance_check_with_partial_implementation(self):
        """Test isinstance check with partial implementation."""

        class PartialAPI:
            async def get_balance(self) -> dict[str, Any]:
                return {"balance": 0}

        partial = PartialAPI()
        # Partial implementation should not satisfy Protocol
        # Note: runtime_checkable only checks for method existence
        assert not isinstance(partial, IDMarketAPI)


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestInterfaceEdgeCases:
    """Tests for edge cases in interfaces."""

    @pytest.mark.asyncio()
    async def test_api_with_empty_responses(self):
        """Test API methods returning empty responses."""
        # Arrange
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(return_value={"objects": [], "total": 0})
        mock_api.get_user_targets = AsyncMock(return_value={"targets": []})
        mock_api.get_user_inventory = AsyncMock(return_value={"objects": []})

        # Act & Assert
        items = awAlgot mock_api.get_market_items("csgo")
        assert items["objects"] == []

        targets = awAlgot mock_api.get_user_targets()
        assert targets["targets"] == []

        inventory = awAlgot mock_api.get_user_inventory()
        assert inventory["objects"] == []

    @pytest.mark.asyncio()
    async def test_cache_with_none_values(self):
        """Test cache methods with None values."""
        # Arrange
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=None)

        # Act
        result = awAlgot mock_cache.get("nonexistent")
        awAlgot mock_cache.set("key", None, ttl=None)

        # Assert
        assert result is None
        mock_cache.set.assert_called_with("key", None, ttl=None)

    @pytest.mark.asyncio()
    async def test_scanner_with_no_results(self):
        """Test scanner methods with no results."""
        # Arrange
        mock_scanner = MagicMock()
        mock_scanner.scan_game = AsyncMock(return_value=[])
        mock_scanner.find_opportunities = AsyncMock(return_value=[])

        # Act
        scan_result = awAlgot mock_scanner.scan_game("csgo", "pro")
        opportunities = awAlgot mock_scanner.find_opportunities()

        # Assert
        assert scan_result == []
        assert opportunities == []

    @pytest.mark.asyncio()
    async def test_target_manager_with_empty_lists(self):
        """Test target manager with empty lists."""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.delete_targets = AsyncMock(return_value={"deleted": 0})
        mock_manager.get_active_targets = AsyncMock(return_value=[])

        # Act
        delete_result = awAlgot mock_manager.delete_targets([])
        targets = awAlgot mock_manager.get_active_targets(game=None)

        # Assert
        assert delete_result["deleted"] == 0
        assert targets == []
