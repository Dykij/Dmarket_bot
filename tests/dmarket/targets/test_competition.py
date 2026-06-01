"""Unit tests for src/dmarket/targets/competition.py module.

Tests for target competition analysis and filtering functions.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestAnalyzeTargetCompetition:
    """Tests for analyze_target_competition function."""

    @pytest.mark.asyncio()
    async def test_analyze_competition_returns_analysis_dict(self):
        """Test analyze_target_competition returns proper analysis dict."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(return_value=[])
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 1000}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "AK-47 | Redline")

        assert "title" in result
        assert "game" in result
        assert "total_orders" in result
        assert "best_price" in result
        assert "competition_level" in result
        assert result["title"] == "AK-47 | Redline"
        assert result["game"] == "csgo"

    @pytest.mark.asyncio()
    async def test_analyze_competition_with_no_competitors(self):
        """Test analyze_target_competition when no competitors exist."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(return_value=[])
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 1000}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["total_orders"] == 0
        assert result["best_price"] == 0.0
        assert result["competition_level"] == "low"

    @pytest.mark.asyncio()
    async def test_analyze_competition_with_few_competitors(self):
        """Test analyze_target_competition with few competitors (low competition)."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[
                {"price": "500"},
                {"price": "550"},
                {"price": "600"},
            ]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 1000}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["total_orders"] == 3
        assert result["competition_level"] == "low"

    @pytest.mark.asyncio()
    async def test_analyze_competition_with_medium_competition(self):
        """Test analyze_target_competition with medium competition."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        # 10 competitors = medium competition
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[{"price": str(i * 100)} for i in range(10)]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 2000}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["total_orders"] == 10
        assert result["competition_level"] == "medium"

    @pytest.mark.asyncio()
    async def test_analyze_competition_with_high_competition(self):
        """Test analyze_target_competition with high competition."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        # 20 competitors = high competition
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[{"price": str(i * 50)} for i in range(20)]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 2000}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["total_orders"] == 20
        assert result["competition_level"] == "high"

    @pytest.mark.asyncio()
    async def test_analyze_competition_calculates_best_price(self):
        """Test analyze_target_competition calculates best price correctly."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[
                {"price": "100"},
                {"price": "200"},
                {"price": "300"},
            ]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 500}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["best_price"] == 300.0  # Max of [100, 200, 300]

    @pytest.mark.asyncio()
    async def test_analyze_competition_calculates_average_price(self):
        """Test analyze_target_competition calculates average price."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[
                {"price": "100"},
                {"price": "200"},
                {"price": "300"},
            ]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 500}]}
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["average_price"] == 200.0  # (100 + 200 + 300) / 3

    @pytest.mark.asyncio()
    async def test_analyze_competition_handles_api_error(self):
        """Test analyze_target_competition handles API errors."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(side_effect=Exception("API Error"))

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert "error" in result
        assert result["title"] == "Test Item"

    @pytest.mark.asyncio()
    async def test_analyze_competition_uses_game_id_mapping(self):
        """Test analyze_target_competition uses correct game ID."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(return_value=[])
        mock_api.get_aggregated_prices_bulk = AsyncMock(return_value={})

        await analyze_target_competition(mock_api, "csgo", "Test Item")

        # Should use mapped game ID
        mock_api.get_targets_by_title.assert_called_once()
        call_kwargs = mock_api.get_targets_by_title.call_args
        assert call_kwargs[1]["game"] == "a8db"  # csgo -> a8db

    @pytest.mark.asyncio()
    async def test_analyze_competition_calculates_recommended_price(self):
        """Test analyze_target_competition calculates recommended price."""
        from src.dmarket.targets.competition import analyze_target_competition

        mock_api = AsyncMock()
        mock_api.get_targets_by_title = AsyncMock(
            return_value=[
                {"price": "500"},
            ]
        )
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": [{"offerBestPrice": 1000}]}  # $10.00
        )

        result = await analyze_target_competition(mock_api, "csgo", "Test Item")

        assert result["recommended_price"] > 0
        assert result["strategy"] != ""


class TestAssessCompetition:
    """Tests for assess_competition function."""

    @pytest.mark.asyncio()
    async def test_assess_competition_returns_assessment_dict(self):
        """Test assess_competition returns proper assessment dict."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 2,
                "total_amount": 5,
                "competition_level": "low",
                "best_price": 10.0,
                "average_price": 9.0,
            }
        )

        result = await assess_competition(mock_api, "csgo", "Test Item")

        assert "title" in result
        assert "game" in result
        assert "should_proceed" in result
        assert "competition_level" in result
        assert "total_orders" in result
        assert "recommendation" in result

    @pytest.mark.asyncio()
    async def test_assess_competition_recommends_proceed_with_low_competition(self):
        """Test assess_competition recommends proceeding with low competition."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 2,
                "total_amount": 3,
                "competition_level": "low",
                "best_price": 5.0,
                "average_price": 4.5,
            }
        )

        result = await assess_competition(
            mock_api, "csgo", "Test Item", max_competition=3
        )

        assert result["should_proceed"] is True

    @pytest.mark.asyncio()
    async def test_assess_competition_not_proceed_with_high_competition(self):
        """Test assess_competition does not recommend proceeding with high competition."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 10,
                "total_amount": 50,
                "competition_level": "high",
                "best_price": 5.0,
                "average_price": 4.5,
            }
        )

        result = await assess_competition(
            mock_api, "csgo", "Test Item", max_competition=3
        )

        assert result["should_proceed"] is False

    @pytest.mark.asyncio()
    async def test_assess_competition_with_zero_competitors(self):
        """Test assess_competition with zero competitors."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "none",
                "best_price": 0.0,
                "average_price": 0.0,
            }
        )

        result = await assess_competition(mock_api, "csgo", "Test Item")

        assert result["should_proceed"] is True
        assert "Нет конкурентов" in result["recommendation"]
        assert result["suggested_price"] is None

    @pytest.mark.asyncio()
    async def test_assess_competition_suggests_price(self):
        """Test assess_competition suggests price above best competitor."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 2,
                "total_amount": 3,
                "competition_level": "low",
                "best_price": 10.0,
                "average_price": 9.0,
            }
        )

        result = await assess_competition(
            mock_api, "csgo", "Test Item", max_competition=3
        )

        # Should suggest price above best_price
        assert result["suggested_price"] is not None
        assert result["suggested_price"] > 10.0

    @pytest.mark.asyncio()
    async def test_assess_competition_handles_api_error(self):
        """Test assess_competition handles API errors."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await assess_competition(mock_api, "csgo", "Test Item")

        assert result["should_proceed"] is False
        assert "error" in result
        assert "Ошибка" in result["recommendation"]

    @pytest.mark.asyncio()
    async def test_assess_competition_uses_price_threshold(self):
        """Test assess_competition passes price threshold to API."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "none",
                "best_price": 0.0,
                "average_price": 0.0,
            }
        )

        await assess_competition(mock_api, "csgo", "Test Item", price_threshold=100.0)

        mock_api.get_buy_orders_competition.assert_called_once()
        call_kwargs = mock_api.get_buy_orders_competition.call_args[1]
        assert call_kwargs["price_threshold"] == 100.0

    @pytest.mark.asyncio()
    async def test_assess_competition_includes_raw_data(self):
        """Test assess_competition includes raw API data."""
        from src.dmarket.targets.competition import assess_competition

        mock_api = AsyncMock()
        raw_response = {
            "total_orders": 5,
            "total_amount": 10,
            "competition_level": "medium",
            "best_price": 15.0,
            "average_price": 12.0,
            "extra_data": "value",
        }
        mock_api.get_buy_orders_competition = AsyncMock(return_value=raw_response)

        result = await assess_competition(mock_api, "csgo", "Test Item")

        assert result["raw_data"] == raw_response


class TestFilterLowCompetitionItems:
    """Tests for filter_low_competition_items function."""

    @pytest.mark.asyncio()
    async def test_filter_returns_low_competition_items(self):
        """Test filter_low_competition_items returns only low competition items."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()
        # Alternate between low and high competition
        call_count = [0]

        async def mock_get_competition(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return {
                    "total_orders": 10,  # High competition
                    "total_amount": 20,
                    "competition_level": "high",
                    "best_price": 5.0,
                    "average_price": 4.5,
                }
            return {
                "total_orders": 1,  # Low competition
                "total_amount": 1,
                "competition_level": "low",
                "best_price": 5.0,
                "average_price": 5.0,
            }

        mock_api.get_buy_orders_competition = mock_get_competition

        items = [
            {"title": "Item 1"},
            {"title": "Item 2"},
            {"title": "Item 3"},
            {"title": "Item 4"},
        ]

        result = await filter_low_competition_items(
            mock_api, "csgo", items, max_competition=3, request_delay=0
        )

        # Only odd items (1, 3) should pass (low competition)
        assert len(result) == 2

    @pytest.mark.asyncio()
    async def test_filter_skips_items_without_title(self):
        """Test filter_low_competition_items skips items without title."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "none",
                "best_price": 0.0,
                "average_price": 0.0,
            }
        )

        items = [
            {"title": "Item 1"},
            {"no_title": "value"},  # No title
            {"title": "Item 3"},
        ]

        result = await filter_low_competition_items(
            mock_api, "csgo", items, request_delay=0
        )

        # Only items with titles should be processed
        assert all("title" in item for item in result)

    @pytest.mark.asyncio()
    async def test_filter_adds_competition_data_to_items(self):
        """Test filter_low_competition_items adds competition data to filtered items."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 1,
                "total_amount": 1,
                "competition_level": "low",
                "best_price": 5.0,
                "average_price": 5.0,
            }
        )

        items = [{"title": "Test Item", "price": 100}]

        result = await filter_low_competition_items(
            mock_api, "csgo", items, request_delay=0
        )

        assert len(result) == 1
        assert "competition" in result[0]
        assert result[0]["title"] == "Test Item"
        assert result[0]["price"] == 100

    @pytest.mark.asyncio()
    async def test_filter_respects_request_delay(self):
        """Test filter_low_competition_items respects request delay."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "none",
                "best_price": 0.0,
                "average_price": 0.0,
            }
        )

        items = [{"title": f"Item {i}"} for i in range(3)]

        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None

            await filter_low_competition_items(
                mock_api, "csgo", items, request_delay=0.5
            )

            # Sleep should be called between requests
            assert mock_sleep.call_count == 3

    @pytest.mark.asyncio()
    async def test_filter_with_empty_items_list(self):
        """Test filter_low_competition_items with empty items list."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()

        result = await filter_low_competition_items(
            mock_api, "csgo", [], request_delay=0
        )

        assert result == []
        mock_api.get_buy_orders_competition.assert_not_called()

    @pytest.mark.asyncio()
    async def test_filter_uses_max_competition_threshold(self):
        """Test filter_low_competition_items uses custom max_competition."""
        from src.dmarket.targets.competition import filter_low_competition_items

        mock_api = AsyncMock()
        mock_api.get_buy_orders_competition = AsyncMock(
            return_value={
                "total_orders": 5,  # 5 orders
                "total_amount": 10,
                "competition_level": "medium",
                "best_price": 5.0,
                "average_price": 4.5,
            }
        )

        items = [{"title": "Test Item"}]

        # With max_competition=3, item should be filtered out
        result_low = await filter_low_competition_items(
            mock_api, "csgo", items, max_competition=3, request_delay=0
        )
        assert len(result_low) == 0

        # With max_competition=10, item should pass
        result_high = await filter_low_competition_items(
            mock_api, "csgo", items, max_competition=10, request_delay=0
        )
        assert len(result_high) == 1


class TestModuleExports:
    """Tests for module exports."""

    def test_module_exports_all_functions(self):
        """Test module exports all required functions."""
        from src.dmarket.targets import competition

        assert hasattr(competition, "analyze_target_competition")
        assert hasattr(competition, "assess_competition")
        assert hasattr(competition, "filter_low_competition_items")

        # Check __all__
        assert "analyze_target_competition" in competition.__all__
        assert "assess_competition" in competition.__all__
        assert "filter_low_competition_items" in competition.__all__
