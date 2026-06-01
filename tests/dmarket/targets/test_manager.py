"""Tests for src/dmarket/targets/manager.py - TargetManager class."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def create_mock_api() -> AsyncMock:
    """Create a mock API client."""
    mock = AsyncMock()
    mock.create_target = AsyncMock(return_value={"id": "target123", "status": "active"})
    mock.get_user_targets = AsyncMock(return_value={"items": []})
    mock.delete_target = AsyncMock(return_value={"success": True})
    mock.get_targets_by_title = AsyncMock(return_value={"items": []})
    mock.get_closed_targets = AsyncMock(return_value={"trades": []})
    return mock


def create_manager(mock_api: AsyncMock | None = None):
    """Create a TargetManager instance with mocked dependencies."""
    from src.dmarket.targets.manager import TargetManager

    if mock_api is None:
        mock_api = create_mock_api()

    with patch("src.dmarket.targets.manager.LiquidityAnalyzer"):
        manager = TargetManager(api_client=mock_api, enable_liquidity_filter=False)

    return manager, mock_api


class TestTargetManagerInit:
    """Tests for TargetManager initialization."""

    def test_init_with_api_client(self) -> None:
        """Test TargetManager initializes with API client."""
        manager, mock_api = create_manager()
        assert manager.api is mock_api

    def test_init_without_liquidity_filter(self) -> None:
        """Test TargetManager initializes without liquidity filter."""
        manager, _ = create_manager()
        assert manager.liquidity_analyzer is None

    def test_init_with_liquidity_filter(self) -> None:
        """Test TargetManager initializes with liquidity filter."""
        from src.dmarket.targets.manager import TargetManager

        mock_api = create_mock_api()

        with patch("src.dmarket.targets.manager.LiquidityAnalyzer") as MockAnalyzer:
            MockAnalyzer.return_value = MagicMock()
            manager = TargetManager(api_client=mock_api, enable_liquidity_filter=True)

        assert manager.liquidity_analyzer is not None


class TestCreateTarget:
    """Tests for create_target method."""

    @pytest.mark.asyncio()
    async def test_create_target_success(self) -> None:
        """Test creating a target successfully."""
        manager, mock_api = create_manager()
        mock_api.create_target.return_value = {"id": "target123", "status": "active"}

        result = await manager.create_target(
            game="csgo", title="AK-47 | Redline (Field-Tested)", price=10.50
        )

        assert result["id"] == "target123"
        assert result["status"] == "active"

    @pytest.mark.asyncio()
    async def test_create_target_with_amount(self) -> None:
        """Test creating a target with custom amount."""
        manager, mock_api = create_manager()

        await manager.create_target(
            game="csgo", title="AK-47 | Redline", price=10.50, amount=5
        )

        call_args = mock_api.create_target.call_args[0][0]
        assert call_args["amount"] == "5"

    @pytest.mark.asyncio()
    async def test_create_target_empty_title_raises_error(self) -> None:
        """Test that empty title raises ValueError."""
        manager, _ = create_manager()

        with pytest.raises(ValueError, match="Название предмета не может быть пустым"):
            await manager.create_target(game="csgo", title="", price=10.0)

    @pytest.mark.asyncio()
    async def test_create_target_zero_price_raises_error(self) -> None:
        """Test that zero price raises ValueError."""
        manager, _ = create_manager()

        with pytest.raises(ValueError, match="Цена должна быть больше 0"):
            await manager.create_target(game="csgo", title="AK-47", price=0)

    @pytest.mark.asyncio()
    async def test_create_target_negative_price_raises_error(self) -> None:
        """Test that negative price raises ValueError."""
        manager, _ = create_manager()

        with pytest.raises(ValueError, match="Цена должна быть больше 0"):
            await manager.create_target(game="csgo", title="AK-47", price=-5.0)

    @pytest.mark.asyncio()
    async def test_create_target_invalid_amount_too_low(self) -> None:
        """Test that amount < 1 raises ValueError."""
        manager, _ = create_manager()

        with pytest.raises(ValueError, match="Количество должно быть от 1 до 100"):
            await manager.create_target(
                game="csgo", title="AK-47", price=10.0, amount=0
            )

    @pytest.mark.asyncio()
    async def test_create_target_invalid_amount_too_high(self) -> None:
        """Test that amount > 100 raises ValueError."""
        manager, _ = create_manager()

        with pytest.raises(ValueError, match="Количество должно быть от 1 до 100"):
            await manager.create_target(
                game="csgo", title="AK-47", price=10.0, amount=101
            )

    @pytest.mark.asyncio()
    async def test_create_target_converts_price_to_cents(self) -> None:
        """Test that price is converted to cents."""
        manager, mock_api = create_manager()

        await manager.create_target(game="csgo", title="AK-47 | Redline", price=10.50)

        call_args = mock_api.create_target.call_args[0][0]
        assert call_args["price"] == "1050"

    @pytest.mark.asyncio()
    async def test_create_target_with_game_id(self) -> None:
        """Test that game code is converted to gameId."""
        manager, mock_api = create_manager()

        await manager.create_target(game="csgo", title="AK-47", price=10.0)

        call_args = mock_api.create_target.call_args[0][0]
        assert "gameId" in call_args

    @pytest.mark.asyncio()
    async def test_create_target_api_error(self) -> None:
        """Test handling API error during target creation."""
        manager, mock_api = create_manager()
        mock_api.create_target.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await manager.create_target(game="csgo", title="AK-47", price=10.0)


class TestGetUserTargets:
    """Tests for get_user_targets method."""

    @pytest.mark.asyncio()
    async def test_get_user_targets_returns_list(self) -> None:
        """Test get_user_targets returns a list."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.return_value = {
            "items": [{"id": "target1"}, {"id": "target2"}]
        }

        result = await manager.get_user_targets()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_game_filter(self) -> None:
        """Test get_user_targets with game filter."""
        manager, mock_api = create_manager()

        await manager.get_user_targets(game="csgo")

        call_args = mock_api.get_user_targets.call_args[0][0]
        assert "gameId" in call_args

    @pytest.mark.asyncio()
    async def test_get_user_targets_with_status_filter(self) -> None:
        """Test get_user_targets with status filter."""
        manager, mock_api = create_manager()

        await manager.get_user_targets(status="inactive")

        call_args = mock_api.get_user_targets.call_args[0][0]
        assert call_args["status"] == "inactive"

    @pytest.mark.asyncio()
    async def test_get_user_targets_all_status(self) -> None:
        """Test get_user_targets with 'all' status doesn't add status param."""
        manager, mock_api = create_manager()

        await manager.get_user_targets(status="all")

        call_args = mock_api.get_user_targets.call_args[0][0]
        assert "status" not in call_args

    @pytest.mark.asyncio()
    async def test_get_user_targets_api_error_returns_empty_list(self) -> None:
        """Test get_user_targets returns empty list on API error."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.side_effect = Exception("API Error")

        result = await manager.get_user_targets()

        assert result == []


class TestDeleteTarget:
    """Tests for delete_target method."""

    @pytest.mark.asyncio()
    async def test_delete_target_success(self) -> None:
        """Test successful target deletion."""
        manager, mock_api = create_manager()

        result = await manager.delete_target("target123")

        assert result is True
        mock_api.delete_target.assert_called_once_with("target123")

    @pytest.mark.asyncio()
    async def test_delete_target_failure(self) -> None:
        """Test failed target deletion."""
        manager, mock_api = create_manager()
        mock_api.delete_target.side_effect = Exception("API Error")

        result = await manager.delete_target("target123")

        assert result is False


class TestDeleteAllTargets:
    """Tests for delete_all_targets method."""

    @pytest.mark.asyncio()
    async def test_delete_all_targets_dry_run(self) -> None:
        """Test dry run mode returns preview."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.return_value = {
            "items": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
        }

        result = await manager.delete_all_targets(dry_run=True)

        assert result["dry_run"] is True
        assert result["would_delete"] == 3
        mock_api.delete_target.assert_not_called()

    @pytest.mark.asyncio()
    async def test_delete_all_targets_actual_delete(self) -> None:
        """Test actual deletion of all targets."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.return_value = {"items": [{"id": "t1"}, {"id": "t2"}]}

        result = await manager.delete_all_targets(dry_run=False)

        assert result["deleted"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2


class TestGetTargetsByTitle:
    """Tests for get_targets_by_title method."""

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_returns_list(self) -> None:
        """Test get_targets_by_title returns a list."""
        manager, mock_api = create_manager()
        mock_api.get_targets_by_title.return_value = {
            "items": [{"id": "t1", "price": 1000}]
        }

        result = await manager.get_targets_by_title(
            game="csgo", title="AK-47 | Redline"
        )

        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_api_error_returns_empty_list(self) -> None:
        """Test returns empty list on API error."""
        manager, mock_api = create_manager()
        mock_api.get_targets_by_title.side_effect = Exception("API Error")

        result = await manager.get_targets_by_title(game="csgo", title="AK-47")

        assert result == []


class TestCreateSmartTargets:
    """Tests for create_smart_targets method."""

    @pytest.mark.asyncio()
    async def test_create_smart_targets_without_competition_check(self) -> None:
        """Test creating targets without competition check."""
        manager, _mock_api = create_manager()
        items = [{"title": "AK-47", "price": 10.0}]

        with patch.object(manager, "_delay", new_callable=AsyncMock):
            results = await manager.create_smart_targets(
                game="csgo", items=items, check_competition=False
            )

        assert results[0]["status"] == "created"

    @pytest.mark.asyncio()
    async def test_create_smart_targets_respects_max_targets(self) -> None:
        """Test that max_targets limit is respected."""
        manager, _mock_api = create_manager()
        items = [{"title": f"Item {i}", "price": 10.0} for i in range(20)]

        with patch.object(manager, "_delay", new_callable=AsyncMock):
            results = await manager.create_smart_targets(
                game="csgo", items=items, max_targets=5, check_competition=False
            )

        assert len(results) == 5

    @pytest.mark.asyncio()
    async def test_create_smart_targets_skips_invalid_items(self) -> None:
        """Test that items without title or price are skipped."""
        manager, _mock_api = create_manager()
        items = [
            {"title": "", "price": 10.0},
            {"title": "Valid Item", "price": 0},
            {"title": "Valid Item 2", "price": 10.0},
        ]

        with patch.object(manager, "_delay", new_callable=AsyncMock):
            results = await manager.create_smart_targets(
                game="csgo", items=items, check_competition=False
            )

        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_create_smart_targets_handles_api_error(self) -> None:
        """Test handling API errors during creation."""
        manager, mock_api = create_manager()
        mock_api.create_target.side_effect = Exception("API Error")

        items = [{"title": "AK-47", "price": 10.0}]

        with patch.object(manager, "_delay", new_callable=AsyncMock):
            results = await manager.create_smart_targets(
                game="csgo", items=items, check_competition=False
            )

        assert results[0]["status"] == "error"


class TestGetClosedTargets:
    """Tests for get_closed_targets method."""

    @pytest.mark.asyncio()
    async def test_get_closed_targets_returns_list(self) -> None:
        """Test get_closed_targets returns formatted list."""
        manager, mock_api = create_manager()
        mock_api.get_closed_targets.return_value = {
            "trades": [
                {
                    "TargetID": "t1",
                    "Title": "AK-47",
                    "Price": 1000,
                    "GameID": "csgo",
                    "Status": "successful",
                }
            ]
        }

        result = await manager.get_closed_targets(limit=50, days=7)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "t1"
        assert result[0]["price"] == 10.0

    @pytest.mark.asyncio()
    async def test_get_closed_targets_api_error_returns_empty(self) -> None:
        """Test returns empty list on API error."""
        manager, mock_api = create_manager()
        mock_api.get_closed_targets.side_effect = Exception("API Error")

        result = await manager.get_closed_targets()

        assert result == []


class TestGetTargetStatistics:
    """Tests for get_target_statistics method."""

    @pytest.mark.asyncio()
    async def test_get_target_statistics_basic(self) -> None:
        """Test basic statistics calculation."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.return_value = {"items": [{"id": "t1"}, {"id": "t2"}]}
        mock_api.get_closed_targets.return_value = {
            "trades": [
                {"TargetID": "t3", "Status": "successful", "Price": 1000},
                {"TargetID": "t4", "Status": "successful", "Price": 2000},
                {"TargetID": "t5", "Status": "failed", "Price": 500},
            ]
        }

        result = await manager.get_target_statistics(game="csgo", days=7)

        assert result["game"] == "csgo"
        assert result["active_count"] == 2
        assert result["closed_count"] == 3

    @pytest.mark.asyncio()
    async def test_get_target_statistics_empty_targets(self) -> None:
        """Test statistics with no targets."""
        manager, mock_api = create_manager()
        mock_api.get_user_targets.return_value = {"items": []}
        mock_api.get_closed_targets.return_value = {"trades": []}

        result = await manager.get_target_statistics(game="csgo")

        assert result["active_count"] == 0
        assert result["closed_count"] == 0
        assert result["success_rate"] == 0.0


class TestAnalyzeTargetCompetition:
    """Tests for analyze_target_competition method."""

    @pytest.mark.asyncio()
    async def test_analyze_target_competition_calls_module(self) -> None:
        """Test that it delegates to competition module."""
        manager, _ = create_manager()

        with patch(
            "src.dmarket.targets.manager.analyze_target_competition",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = {"competition_count": 5}

            result = await manager.analyze_target_competition(
                game="csgo", title="AK-47"
            )

            assert result["competition_count"] == 5


class TestAssessCompetition:
    """Tests for assess_competition method."""

    @pytest.mark.asyncio()
    async def test_assess_competition_calls_module(self) -> None:
        """Test that it delegates to competition module."""
        manager, _ = create_manager()

        with patch(
            "src.dmarket.targets.manager.assess_competition", new_callable=AsyncMock
        ) as mock_assess:
            mock_assess.return_value = {"should_proceed": True}

            result = await manager.assess_competition(
                game="csgo", title="AK-47", max_competition=3
            )

            assert result["should_proceed"] is True


class TestFilterLowCompetitionItems:
    """Tests for filter_low_competition_items method."""

    @pytest.mark.asyncio()
    async def test_filter_low_competition_items_calls_module(self) -> None:
        """Test that it delegates to competition module."""
        manager, _ = create_manager()

        with patch(
            "src.dmarket.targets.manager.filter_low_competition_items",
            new_callable=AsyncMock,
        ) as mock_filter:
            mock_filter.return_value = [{"title": "Item1"}]

            items = [{"title": "Item1"}, {"title": "Item2"}]
            result = await manager.filter_low_competition_items(
                game="csgo", items=items, max_competition=3
            )

            assert len(result) == 1


class TestDelay:
    """Tests for _delay method."""

    @pytest.mark.asyncio()
    async def test_delay_sleeps(self) -> None:
        """Test that _delay calls asyncio.sleep."""
        manager, _ = create_manager()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await manager._delay(0.5)
            mock_sleep.assert_called_once_with(0.5)
