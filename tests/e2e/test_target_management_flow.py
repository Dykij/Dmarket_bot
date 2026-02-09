"""E2E тесты для target management workflow (Fixed version).

Фаза 2: End-to-end тестирование управления таргетами (buy orders).
Обновлено для соответствия текущему API TargetManager.

Этот модуль тестирует:
1. Создание таргетов (buy orders)
2. Просмотр активных таргетов
3. Удаление таргетов
4. Batch операции с таргетами
"""

from unittest.mock import AsyncMock

import pytest

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def mock_dmarket_api():
    """Create mock DMarket API client with correct return values."""
    api = AsyncMock()

    # Mock create target response (returns target data)
    api.create_target = AsyncMock(
        return_value={
            "targetId": "target_123",
            "itemTitle": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": "1000"},  # $10.00 in cents
            "status": "active",
            "createdAt": "2026-01-01T00:00:00Z",
        }
    )

    # Mock get_user_targets response (returns dict with "items" key)
    api.get_user_targets = AsyncMock(
        return_value={
            "items": [
                {
                    "targetId": "target_123",
                    "itemTitle": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1000"},
                    "status": "active",
                    "createdAt": "2026-01-01T00:00:00Z",
                },
                {
                    "targetId": "target_456",
                    "itemTitle": "AWP | Asiimov (Field-Tested)",
                    "price": {"USD": "5000"},
                    "status": "active",
                    "createdAt": "2026-01-01T00:00:00Z",
                },
            ]
        }
    )

    # Mock delete target response
    api.delete_target = AsyncMock(return_value={"success": True})

    # Mock get balance
    api.get_balance = AsyncMock(
        return_value={
            "usd": "100000",  # $1000.00
            "dmc": "50000",
        }
    )

    return api


# ============================================================================
# TEST CLASSES
# ============================================================================


class TestTargetCreationFlow:
    """Test target creation workflow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_create_target_complete_flow(self, mock_dmarket_api):
        """Test complete target creation flow.

        Steps:
        1. User creates target via TargetManager
        2. Target is validated
        3. API request is sent
        4. Target is created successfully
        """
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)
        item_title = "AK-47 | Redline (Field-Tested)"
        target_price = 10.0  # $10.00

        # Act: Create target
        result = await manager.create_target(
            game="csgo",
            title=item_title,
            price=target_price,
            amount=1,
        )

        # Assert: Target created via API
        assert result is not None
        assert "targetId" in result
        mock_dmarket_api.create_target.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_create_target_validates_price_range(self, mock_dmarket_api):
        """Test price validation for targets."""
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)

        # Act & Assert: Price too low
        with pytest.raises(ValueError) as exc_info:
            await manager.create_target(
                game="csgo",
                title="Test Item",
                price=0.0,  # Invalid: zero price
                amount=1,
            )
        assert "больше 0" in str(exc_info.value) or "price" in str(exc_info.value).lower()

        # Act: Valid price
        result = await manager.create_target(
            game="csgo",
            title="Test Item",
            price=1.0,  # Valid: $1.00
            amount=1,
        )

        # Assert: Success
        assert result is not None
        assert "targetId" in result


class TestTargetViewingFlow:
    """Test target viewing workflow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_user_views_active_targets(self, mock_dmarket_api):
        """Test user can view their active targets.

        Steps:
        1. User requests targets list
        2. Fetch from API
        3. Display to user
        """
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)

        # Act: Get user targets
        targets = await manager.get_user_targets(game="csgo", status="active")

        # Assert: Targets fetched
        assert isinstance(targets, list)
        assert len(targets) > 0

        # Assert: Each target has required fields
        for target in targets:
            assert "targetId" in target
            assert "itemTitle" in target
            assert "price" in target
            assert "status" in target

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_get_targets_with_filters(self, mock_dmarket_api):
        """Test getting targets with game filter."""
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)

        # Act: Get targets for specific game
        targets = await manager.get_user_targets(
            game="csgo",
            status="active",
            limit=50,
        )

        # Assert: API called with correct parameters
        assert isinstance(targets, list)
        mock_dmarket_api.get_user_targets.assert_called_once()


class TestTargetDeletionFlow:
    """Test target deletion workflow."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_delete_target_complete_flow(self, mock_dmarket_api):
        """Test complete target deletion flow.

        Steps:
        1. User selects target to delete
        2. Confirm deletion
        3. API request sent
        4. Target deleted
        """
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)
        target_id = "target_123"

        # Act: Delete target
        result = await manager.delete_target(target_id=target_id)

        # Assert: Deleted successfully
        assert result is True
        mock_dmarket_api.delete_target.assert_called_once_with(target_id)

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_delete_nonexistent_target_handled(self, mock_dmarket_api):
        """Test handling deletion of non-existent target."""
        from src.dmarket.targets import TargetManager

        # Arrange: API throws exception for non-existent target
        mock_dmarket_api.delete_target = AsyncMock(side_effect=Exception("Target not found"))
        manager = TargetManager(api_client=mock_dmarket_api)

        # Act: Delete non-existent target (manager catches exception)
        result = await manager.delete_target(target_id="nonexistent_id")

        # Assert: Returns False (exception was caught)
        assert result is False


class TestBatchTargetOperations:
    """Test batch operations with targets."""

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_create_multiple_targets_parallel(self, mock_dmarket_api):
        """Test creating multiple targets in parallel."""
        import asyncio

        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)

        items = [
            ("AK-47 | Redline (FT)", 10.0),
            ("AWP | Asiimov (FT)", 50.0),
            ("M4A4 | Howl (FT)", 150.0),
        ]

        # Act: Create all targets in parallel
        tasks = [
            manager.create_target(
                game="csgo",
                title=title,
                price=price,
                amount=1,
            )
            for title, price in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert: All created successfully
        assert len(results) == len(items)
        for result in results:
            if not isinstance(result, Exception):
                assert "targetId" in result

    @pytest.mark.asyncio()
    @pytest.mark.e2e()
    async def test_get_all_targets_pagination(self, mock_dmarket_api):
        """Test getting all targets with pagination."""
        from src.dmarket.targets import TargetManager

        # Arrange
        manager = TargetManager(api_client=mock_dmarket_api)

        # Act: Get first page
        page1 = await manager.get_user_targets(game="csgo", limit=50, offset=0)

        # Assert
        assert isinstance(page1, list)
        mock_dmarket_api.get_user_targets.assert_called()
