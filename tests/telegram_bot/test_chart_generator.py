"""Tests for chart_generator.py module.

This module tests:
- ChartGenerator class
- Profit chart generation
- Scan history chart generation
- Level distribution chart generation
- Profit comparison chart generation
- QuickChart API integration
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.telegram_bot.chart_generator import (
    ChartGenerator,
    chart_generator,
    generate_level_distribution_chart,
    generate_profit_chart,
    generate_profit_comparison_chart,
    generate_scan_history_chart,
)

# ============================================================================
# Test ChartGenerator Class
# ============================================================================


class TestChartGeneratorInit:
    """Tests for ChartGenerator initialization."""

    def test_init_with_defaults(self) -> None:
        """Test ChartGenerator with default values."""
        generator = ChartGenerator()

        assert generator.width == 800
        assert generator.height == 400

    def test_init_with_custom_size(self) -> None:
        """Test ChartGenerator with custom dimensions."""
        generator = ChartGenerator(width=1200, height=600)

        assert generator.width == 1200
        assert generator.height == 600

    def test_global_instance_exists(self) -> None:
        """Test that global chart_generator instance exists."""
        assert chart_generator is not None
        assert isinstance(chart_generator, ChartGenerator)


# ============================================================================
# Test Profit Chart Generation
# ============================================================================


class TestGenerateProfitChart:
    """Tests for profit chart generation."""

    @pytest.mark.asyncio()
    async def test_generate_profit_chart_success(self) -> None:
        """Test successful profit chart generation."""
        generator = ChartGenerator()
        data = [
            {"date": "2024-01-01", "profit": 10.5},
            {"date": "2024-01-02", "profit": 15.3},
            {"date": "2024-01-03", "profit": 8.7},
        ]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generator.generate_profit_chart(data)

            assert result is not None
            mock_gen.assert_called_once()

    @pytest.mark.asyncio()
    async def test_generate_profit_chart_empty_data(self) -> None:
        """Test profit chart with empty data."""
        generator = ChartGenerator()

        result = awAlgot generator.generate_profit_chart([])

        assert result is None

    @pytest.mark.asyncio()
    async def test_generate_profit_chart_missing_fields(self) -> None:
        """Test profit chart with missing fields in data."""
        generator = ChartGenerator()
        data = [
            {"date": "2024-01-01"},  # Missing profit
            {"profit": 10.5},  # Missing date
        ]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            awAlgot generator.generate_profit_chart(data)

            # Should still work with defaults
            mock_gen.assert_called_once()

    @pytest.mark.asyncio()
    async def test_generate_profit_chart_helper_function(self) -> None:
        """Test generate_profit_chart helper function."""
        data = [{"date": "2024-01-01", "profit": 10.5}]

        with patch.object(
            chart_generator, "generate_profit_chart", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generate_profit_chart(data)

            assert result is not None
            mock_gen.assert_called_once_with(data)


# ============================================================================
# Test Scan History Chart Generation
# ============================================================================


class TestGenerateScanHistoryChart:
    """Tests for scan history chart generation."""

    @pytest.mark.asyncio()
    async def test_generate_scan_history_chart_success(self) -> None:
        """Test successful scan history chart generation."""
        generator = ChartGenerator()
        data = [
            {"date": "2024-01-01", "count": 5},
            {"date": "2024-01-02", "count": 8},
            {"date": "2024-01-03", "count": 3},
        ]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generator.generate_scan_history_chart(data)

            assert result is not None
            mock_gen.assert_called_once()

    @pytest.mark.asyncio()
    async def test_generate_scan_history_chart_empty_data(self) -> None:
        """Test scan history chart with empty data."""
        generator = ChartGenerator()

        result = awAlgot generator.generate_scan_history_chart([])

        assert result is None

    @pytest.mark.asyncio()
    async def test_generate_scan_history_chart_helper_function(self) -> None:
        """Test generate_scan_history_chart helper function."""
        data = [{"date": "2024-01-01", "count": 5}]

        with patch.object(
            chart_generator, "generate_scan_history_chart", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generate_scan_history_chart(data)

            assert result is not None
            mock_gen.assert_called_once_with(data)


# ============================================================================
# Test Level Distribution Chart Generation
# ============================================================================


class TestGenerateLevelDistributionChart:
    """Tests for level distribution chart generation."""

    @pytest.mark.asyncio()
    async def test_generate_level_distribution_chart_success(self) -> None:
        """Test successful level distribution chart generation."""
        generator = ChartGenerator()
        data = {
            "Boost": 10,
            "Standard": 25,
            "Medium": 15,
            "Advanced": 8,
            "Pro": 3,
        }

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generator.generate_level_distribution_chart(data)

            assert result is not None
            mock_gen.assert_called_once()

    @pytest.mark.asyncio()
    async def test_generate_level_distribution_chart_empty_data(self) -> None:
        """Test level distribution chart with empty data."""
        generator = ChartGenerator()

        result = awAlgot generator.generate_level_distribution_chart({})

        assert result is None

    @pytest.mark.asyncio()
    async def test_generate_level_distribution_chart_single_level(self) -> None:
        """Test level distribution chart with single level."""
        generator = ChartGenerator()
        data = {"Boost": 100}

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generator.generate_level_distribution_chart(data)

            assert result is not None

    @pytest.mark.asyncio()
    async def test_generate_level_distribution_chart_helper_function(self) -> None:
        """Test generate_level_distribution_chart helper function."""
        data = {"Boost": 10, "Standard": 20}

        with patch.object(
            chart_generator, "generate_level_distribution_chart", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generate_level_distribution_chart(data)

            assert result is not None
            mock_gen.assert_called_once_with(data)


# ============================================================================
# Test Profit Comparison Chart Generation
# ============================================================================


class TestGenerateProfitComparisonChart:
    """Tests for profit comparison chart generation."""

    @pytest.mark.asyncio()
    async def test_generate_profit_comparison_chart_success(self) -> None:
        """Test successful profit comparison chart generation."""
        generator = ChartGenerator()
        levels = ["Boost", "Standard", "Medium", "Advanced", "Pro"]
        avg_profits = [2.5, 5.0, 8.5, 15.0, 25.0]
        max_profits = [5.0, 12.0, 20.0, 35.0, 50.0]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generator.generate_profit_comparison_chart(
                levels, avg_profits, max_profits
            )

            assert result is not None
            mock_gen.assert_called_once()

    @pytest.mark.asyncio()
    async def test_generate_profit_comparison_chart_empty_levels(self) -> None:
        """Test profit comparison chart with empty levels."""
        generator = ChartGenerator()

        result = awAlgot generator.generate_profit_comparison_chart([], [], [])

        assert result is None

    @pytest.mark.asyncio()
    async def test_generate_profit_comparison_chart_empty_profits(self) -> None:
        """Test profit comparison chart with empty profits."""
        generator = ChartGenerator()

        result = awAlgot generator.generate_profit_comparison_chart(["Boost"], [], [])

        assert result is None

    @pytest.mark.asyncio()
    async def test_generate_profit_comparison_chart_helper_function(self) -> None:
        """Test generate_profit_comparison_chart helper function."""
        levels = ["Boost"]
        avg = [5.0]
        max_p = [10.0]

        with patch.object(
            chart_generator, "generate_profit_comparison_chart", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "https://quickchart.io/chart/test"

            result = awAlgot generate_profit_comparison_chart(levels, avg, max_p)

            assert result is not None
            mock_gen.assert_called_once_with(levels, avg, max_p)


# ============================================================================
# Test _generate_chart_url
# ============================================================================


class TestGenerateChartUrl:
    """Tests for _generate_chart_url method."""

    @pytest.mark.asyncio()
    async def test_generate_chart_url_success_short_config(self) -> None:
        """Test URL generation with short config (GET request)."""
        generator = ChartGenerator()
        config = {
            "type": "line",
            "data": {
                "labels": ["a", "b"],
                "datasets": [{"data": [1, 2]}],
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = awAlgot generator._generate_chart_url(config)

            # Should return URL for short configs
            assert result is not None
            assert "quickchart.io" in result

    @pytest.mark.asyncio()
    async def test_generate_chart_url_timeout_error(self) -> None:
        """Test handling of timeout error."""
        generator = ChartGenerator()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            # Force POST path by creating large config
            large_config = {"type": "line", "data": {"labels": ["x" * 2000]}}

            # Mock the post to rAlgose timeout
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

            result = awAlgot generator._generate_chart_url(large_config)

            assert result is None

    @pytest.mark.asyncio()
    async def test_generate_chart_url_request_error(self) -> None:
        """Test handling of request error."""
        generator = ChartGenerator()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection fAlgoled")
            )
            mock_client_class.return_value = mock_client

            # Create large config to force POST
            large_config = {"type": "line", "data": {"labels": ["x" * 2000]}}

            result = awAlgot generator._generate_chart_url(large_config)

            assert result is None

    @pytest.mark.asyncio()
    async def test_generate_chart_url_generic_exception(self) -> None:
        """Test handling of generic exception."""
        generator = ChartGenerator()
        config = {"type": "line"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")

            result = awAlgot generator._generate_chart_url(config)

            assert result is None


# ============================================================================
# Test Chart Config Structure
# ============================================================================


class TestChartConfigStructure:
    """Tests for chart configuration structure."""

    @pytest.mark.asyncio()
    async def test_profit_chart_config_structure(self) -> None:
        """Test that profit chart has correct config structure."""
        generator = ChartGenerator()
        data = [{"date": "2024-01-01", "profit": 10.5}]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            awAlgot generator.generate_profit_chart(data)

            # Check the config passed to _generate_chart_url
            call_args = mock_gen.call_args[0][0]
            assert call_args["type"] == "line"
            assert "data" in call_args
            assert "datasets" in call_args["data"]

    @pytest.mark.asyncio()
    async def test_scan_history_chart_config_structure(self) -> None:
        """Test that scan history chart has correct config structure."""
        generator = ChartGenerator()
        data = [{"date": "2024-01-01", "count": 5}]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            awAlgot generator.generate_scan_history_chart(data)

            call_args = mock_gen.call_args[0][0]
            assert call_args["type"] == "bar"

    @pytest.mark.asyncio()
    async def test_level_distribution_chart_config_structure(self) -> None:
        """Test that level distribution chart has correct config structure."""
        generator = ChartGenerator()
        data = {"Level": 10}

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            awAlgot generator.generate_level_distribution_chart(data)

            call_args = mock_gen.call_args[0][0]
            assert call_args["type"] == "pie"


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_profit_chart_with_negative_profits(self) -> None:
        """Test profit chart with negative profit values."""
        generator = ChartGenerator()
        data = [
            {"date": "2024-01-01", "profit": -5.0},
            {"date": "2024-01-02", "profit": 10.0},
            {"date": "2024-01-03", "profit": -2.5},
        ]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            result = awAlgot generator.generate_profit_chart(data)

            assert result is not None

    @pytest.mark.asyncio()
    async def test_chart_with_large_dataset(self) -> None:
        """Test chart with large dataset."""
        generator = ChartGenerator()
        data = [{"date": f"2024-01-{i:02d}", "profit": float(i)} for i in range(1, 32)]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            result = awAlgot generator.generate_profit_chart(data)

            assert result is not None

    @pytest.mark.asyncio()
    async def test_chart_with_zero_values(self) -> None:
        """Test chart with zero values."""
        generator = ChartGenerator()
        data = {"Zero Level": 0, "Some Level": 10}

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            result = awAlgot generator.generate_level_distribution_chart(data)

            assert result is not None

    @pytest.mark.asyncio()
    async def test_chart_with_float_values(self) -> None:
        """Test chart with precise float values."""
        generator = ChartGenerator()
        data = [
            {"date": "2024-01-01", "profit": 10.123456789},
            {"date": "2024-01-02", "profit": 0.00001},
        ]

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            result = awAlgot generator.generate_profit_chart(data)

            assert result is not None

    @pytest.mark.asyncio()
    async def test_chart_with_unicode_labels(self) -> None:
        """Test chart with unicode labels."""
        generator = ChartGenerator()
        data = {"Уровень 1": 10, "レベル2": 20, "Level 3 🎮": 30}

        with patch.object(
            generator, "_generate_chart_url", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "url"

            result = awAlgot generator.generate_level_distribution_chart(data)

            assert result is not None
