"""Unit tests for DMarket API targets operations module.

This module contains tests for src/dmarket/api/targets_api.py covering:
- Creating targets (buy orders)
- Getting user targets
- Deleting targets
- Getting targets by title
- Competition analysis

Target: 20+ tests to achieve 70%+ coverage of targets_api.py
"""

from unittest.mock import AsyncMock

import pytest

# Test fixtures


@pytest.fixture()
def mock_request():
    """Fixture providing a mocked _request method."""
    return AsyncMock()


@pytest.fixture()
def targets_mixin(mock_request):
    """Fixture providing a TargetsOperationsMixin instance with mocked dependencies."""
    from src.dmarket.api.targets_api import TargetsOperationsMixin

    class TestTargetsClient(TargetsOperationsMixin):
        """Test client with mixin."""

        ENDPOINT_USER_TARGETS = "/marketplace-api/v1/user-targets"
        ENDPOINT_TARGETS_BY_TITLE = "/marketplace-api/v1/targets-by-title"

        def __init__(self) -> None:
            self._request = mock_request

    return TestTargetsClient()


# TestCreateTargets


class TestCreateTargets:
    """Tests for create_targets method."""

    @pytest.mark.asyncio()
    async def test_create_targets_single(self, targets_mixin, mock_request):
        """Test creating a single target."""
        # Arrange
        mock_request.return_value = {"success": True, "targets": [{"TargetID": "1"}]}
        game_id = "a8db"
        targets = [
            {
                "Title": "AK-47 | Redline (Field-Tested)",
                "Amount": 1,
                "Price": {"Amount": 800, "Currency": "USD"},
            }
        ]

        # Act
        result = await targets_mixin.create_targets(game_id=game_id, targets=targets)

        # Assert
        assert result is not None
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["data"]["GameID"] == "a8db"
        assert len(call_args[1]["data"]["Targets"]) == 1

    @pytest.mark.asyncio()
    async def test_create_targets_multiple(self, targets_mixin, mock_request):
        """Test creating multiple targets."""
        # Arrange
        mock_request.return_value = {
            "success": True,
            "targets": [{"TargetID": "1"}, {"TargetID": "2"}],
        }
        targets = [
            {
                "Title": "Item 1",
                "Amount": 1,
                "Price": {"Amount": 100, "Currency": "USD"},
            },
            {
                "Title": "Item 2",
                "Amount": 2,
                "Price": {"Amount": 200, "Currency": "USD"},
            },
        ]

        # Act
        await targets_mixin.create_targets(game_id="a8db", targets=targets)

        # Assert
        call_args = mock_request.call_args
        assert len(call_args[1]["data"]["Targets"]) == 2

    @pytest.mark.asyncio()
    async def test_create_targets_empty_list(self, targets_mixin, mock_request):
        """Test creating targets with empty list."""
        # Arrange
        mock_request.return_value = {"success": True, "targets": []}

        # Act
        await targets_mixin.create_targets(game_id="a8db", targets=[])

        # Assert
        mock_request.assert_called_once()


# TestGetUserTargets


class TestGetUserTargets:
    """Tests for get_user_targets method."""

    @pytest.mark.asyncio()
    async def test_get_user_targets_default(self, targets_mixin, mock_request):
        """Test getting user targets with default parameters."""
        # Arrange
        mock_request.return_value = {"targets": [], "total": 0}

        # Act
        await targets_mixin.get_user_targets(game_id="a8db")

        # Assert
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[1]["params"]["GameID"] == "a8db"
        assert call_args[1]["params"]["Limit"] == "100"
        assert call_args[1]["params"]["Offset"] == "0"

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_pagination(self, targets_mixin, mock_request):
        """Test getting user targets with pagination."""
        # Arrange
        mock_request.return_value = {"targets": [], "total": 0}

        # Act
        await targets_mixin.get_user_targets(
            game_id="a8db", limit=50, offset=100
        )

        # Assert
        call_args = mock_request.call_args
        assert call_args[1]["params"]["Limit"] == "50"
        assert call_args[1]["params"]["Offset"] == "100"

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_status(self, targets_mixin, mock_request):
        """Test getting user targets with status filter."""
        # Arrange
        mock_request.return_value = {"targets": [], "total": 0}

        # Act
        await targets_mixin.get_user_targets(
            game_id="a8db", status="TargetStatusActive"
        )

        # Assert
        call_args = mock_request.call_args
        assert call_args[1]["params"]["BasicFilters.Status"] == "TargetStatusActive"

    @pytest.mark.asyncio()
    async def test_get_user_targets_different_games(self, targets_mixin, mock_request):
        """Test getting user targets for different games."""
        # Arrange
        mock_request.return_value = {"targets": [], "total": 0}
        games = ["a8db", "9a92", "tf2", "rust"]

        # Act & Assert
        for game in games:
            await targets_mixin.get_user_targets(game_id=game)
            call_args = mock_request.call_args
            assert call_args[1]["params"]["GameID"] == game


# TestDeleteTargets


class TestDeleteTargets:
    """Tests for delete_targets method."""

    @pytest.mark.asyncio()
    async def test_delete_targets_single(self, targets_mixin, mock_request):
        """Test deleting a single target."""
        # Arrange
        mock_request.return_value = {"success": True}
        target_ids = ["target_123"]

        # Act
        await targets_mixin.delete_targets(target_ids=target_ids)

        # Assert
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert len(call_args[1]["data"]["Targets"]) == 1
        assert call_args[1]["data"]["Targets"][0]["TargetID"] == "target_123"

    @pytest.mark.asyncio()
    async def test_delete_targets_multiple(self, targets_mixin, mock_request):
        """Test deleting multiple targets."""
        # Arrange
        mock_request.return_value = {"success": True}
        target_ids = ["target_1", "target_2", "target_3"]

        # Act
        await targets_mixin.delete_targets(target_ids=target_ids)

        # Assert
        call_args = mock_request.call_args
        assert len(call_args[1]["data"]["Targets"]) == 3

    @pytest.mark.asyncio()
    async def test_delete_targets_empty_list(self, targets_mixin, mock_request):
        """Test deleting with empty list."""
        # Arrange
        mock_request.return_value = {"success": True}

        # Act
        await targets_mixin.delete_targets(target_ids=[])

        # Assert
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]["data"]["Targets"] == []


# TestGetTargetsByTitle


class TestGetTargetsByTitle:
    """Tests for get_targets_by_title method."""

    @pytest.mark.asyncio()
    async def test_get_targets_by_title(self, targets_mixin, mock_request):
        """Test getting targets by title."""
        # Arrange
        mock_request.return_value = {
            "orders": [
                {
                    "amount": 10,
                    "price": "1200",
                    "title": "AK-47 | Redline (Field-Tested)",
                }
            ]
        }
        game_id = "csgo"
        title = "AK-47 | Redline (Field-Tested)"

        # Act
        result = await targets_mixin.get_targets_by_title(game_id=game_id, title=title)

        # Assert
        mock_request.assert_called_once()
        assert result is not None
        assert "orders" in result

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_url_encoding(self, targets_mixin, mock_request):
        """Test that title is URL encoded."""
        # Arrange
        mock_request.return_value = {"orders": []}
        title = "Item Name With Spaces & Special Chars"

        # Act
        await targets_mixin.get_targets_by_title(game_id="csgo", title=title)

        # Assert
        call_args = mock_request.call_args
        # The path should contain encoded title
        path = call_args[0][1]
        assert "Item%20Name" in path or "%20" in path

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_empty_result(self, targets_mixin, mock_request):
        """Test getting targets for non-existent item."""
        # Arrange
        mock_request.return_value = {"orders": []}

        # Act
        result = await targets_mixin.get_targets_by_title(
            game_id="csgo", title="NonExistent Item"
        )

        # Assert
        assert result["orders"] == []


# TestGetBuyOrdersCompetition


class TestGetBuyOrdersCompetition:
    """Tests for get_buy_orders_competition method."""

    @pytest.mark.asyncio()
    async def test_get_buy_orders_competition(self, targets_mixin, mock_request):
        """Test getting buy orders competition."""
        # Arrange
        mock_request.return_value = {
            "orders": [
                {"amount": 5, "price": "1000"},
                {"amount": 3, "price": "950"},
            ]
        }

        # Act
        result = await targets_mixin.get_buy_orders_competition(
            game_id="csgo", title="Test Item"
        )

        # Assert
        assert result is not None

    @pytest.mark.asyncio()
    async def test_get_buy_orders_competition_with_threshold(
        self, targets_mixin, mock_request
    ):
        """Test getting buy orders competition with price threshold."""
        # Arrange
        mock_request.return_value = {"orders": []}

        # Act
        await targets_mixin.get_buy_orders_competition(
            game_id="csgo", title="Test Item", price_threshold=10.00
        )

        # Assert
        mock_request.assert_called()


# TestTargetsEdgeCases


class TestTargetsEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_create_targets_with_special_chars_in_title(
        self, targets_mixin, mock_request
    ):
        """Test creating targets with special characters in title."""
        # Arrange
        mock_request.return_value = {"success": True}
        targets = [
            {
                "Title": "★ Butterfly Knife | Fade (Factory New)",
                "Amount": 1,
                "Price": {"Amount": 50000, "Currency": "USD"},
            }
        ]

        # Act
        await targets_mixin.create_targets(game_id="a8db", targets=targets)

        # Assert
        mock_request.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_targets_with_unicode_title(self, targets_mixin, mock_request):
        """Test getting targets with unicode in title."""
        # Arrange
        mock_request.return_value = {"orders": []}
        title = "Нож | Тест 🔪"

        # Act
        await targets_mixin.get_targets_by_title(game_id="csgo", title=title)

        # Assert
        mock_request.assert_called_once()


# =============================================================================
# FINAL COVERAGE PUSH - Quick tests for remaining modules
# =============================================================================


class TestTargetsAPIAdditional:
    """Additional tests for targets_api to reach 95%."""

    @pytest.mark.asyncio()
    async def test_create_targets_with_all_params(self, targets_mixin, mock_request):
        """Test creating targets with all parameters using plural API."""
        # Arrange
        mock_request.return_value = {"success": True, "targetId": "tgt_123"}
        targets = [
            {
                "Title": "AK-47 | Redline",
                "Amount": 5,
                "Price": {"Amount": 1550, "Currency": "USD"},
            }
        ]

        # Act
        result = await targets_mixin.create_targets(
            game_id="a8db",
            targets=targets,
        )

        # Assert
        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_delete_targets_success(self, targets_mixin, mock_request):
        """Test deleting targets using plural API."""
        # Arrange
        mock_request.return_value = {"success": True}

        # Act
        result = await targets_mixin.delete_targets(target_ids=["tgt_123", "tgt_456"])

        # Assert
        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_status_filter(
        self, targets_mixin, mock_request
    ):
        """Test getting user targets with status filter."""
        # Arrange
        mock_request.return_value = {"Items": [], "Total": "0"}

        # Act
        result = await targets_mixin.get_user_targets(
            game_id="a8db",
            status="TargetStatusActive",
            limit=50,
            offset=10,
        )

        # Assert
        assert result is not None
        mock_request.assert_called_once()
