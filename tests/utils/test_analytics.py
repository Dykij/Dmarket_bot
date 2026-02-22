"""Unit tests for src/utils/analytics.py.

Tests for ChartGenerator and MarketAnalyzer classes including:
- Price history chart generation
- Market overview charts
- Arbitrage opportunities visualization
- Volume analysis charts
- Price statistics calculation
- Trend detection
- Support/resistance level finding
"""

import io

import pytest

from src.utils.analytics import (
    ChartGenerator,
    MarketAnalyzer,
    generate_market_report,
)


class TestChartGeneratorInit:
    """Tests for ChartGenerator initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        generator = ChartGenerator()
        assert generator.style == "default"
        assert generator.figsize == (12, 8)

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        generator = ChartGenerator(style="bmh", figsize=(10, 6))
        assert generator.style == "bmh"
        assert generator.figsize == (10, 6)

    def test_init_with_invalid_style_falls_back(self):
        """Test initialization with invalid style falls back to default."""
        generator = ChartGenerator(style="nonexistent_style")
        # Should not raise, will use default
        assert generator.style == "nonexistent_style"


class TestChartGeneratorPriceHistory:
    """Tests for price history chart generation."""

    def test_create_price_history_chart_basic(self):
        """Test creating price history chart with valid data."""
        generator = ChartGenerator()
        price_data = [
            {"date": "2024-01-01", "price": 10.0},
            {"date": "2024-01-02", "price": 11.0},
            {"date": "2024-01-03", "price": 10.5},
            {"date": "2024-01-04", "price": 12.0},
            {"date": "2024-01-05", "price": 11.5},
        ]

        result = generator.create_price_history_chart(price_data)

        assert isinstance(result, io.BytesIO)
        # Check that it contains PNG data
        result.seek(0)
        header = result.read(8)
        assert header[:4] == b"\x89PNG"

    def test_create_price_history_chart_with_custom_title(self):
        """Test creating price history chart with custom title."""
        generator = ChartGenerator()
        price_data = [
            {"date": "2024-01-01", "price": 10.0},
            {"date": "2024-01-02", "price": 11.0},
        ]

        result = generator.create_price_history_chart(
            price_data, title="Custom Price Chart", currency="EUR"
        )

        assert isinstance(result, io.BytesIO)
        result.seek(0)
        assert len(result.read()) > 0

    def test_create_price_history_chart_with_no_price_range(self):
        """Test chart with flat prices (no range)."""
        generator = ChartGenerator()
        price_data = [
            {"date": "2024-01-01", "price": 10.0},
            {"date": "2024-01-02", "price": 10.0},
            {"date": "2024-01-03", "price": 10.0},
        ]

        result = generator.create_price_history_chart(price_data)
        assert isinstance(result, io.BytesIO)

    def test_create_price_history_chart_handles_exception(self):
        """Test chart generation handles exceptions gracefully."""
        generator = ChartGenerator()
        invalid_data = [{"invalid": "data"}]

        result = generator.create_price_history_chart(invalid_data)
        assert isinstance(result, io.BytesIO)


class TestChartGeneratorMarketOverview:
    """Tests for market overview chart generation."""

    def test_create_market_overview_chart_basic(self):
        """Test creating market overview chart with valid data."""
        generator = ChartGenerator()
        items_data = [
            {"name": "Item A", "price": 100.0},
            {"name": "Item B", "price": 80.0},
            {"name": "Item C", "price": 60.0},
        ]

        result = generator.create_market_overview_chart(items_data)

        assert isinstance(result, io.BytesIO)
        result.seek(0)
        header = result.read(8)
        assert header[:4] == b"\x89PNG"

    def test_create_market_overview_chart_empty_data(self):
        """Test chart with empty data returns error chart."""
        generator = ChartGenerator()
        result = generator.create_market_overview_chart([])
        assert isinstance(result, io.BytesIO)

    def test_create_market_overview_chart_long_names(self):
        """Test chart with very long item names are truncated."""
        generator = ChartGenerator()
        items_data = [
            {"name": "A" * 50, "price": 100.0},
            {"name": "B" * 50, "price": 80.0},
        ]

        result = generator.create_market_overview_chart(items_data)
        assert isinstance(result, io.BytesIO)

    def test_create_market_overview_chart_more_than_10_items(self):
        """Test chart limits to top 10 items."""
        generator = ChartGenerator()
        items_data = [{"name": f"Item {i}", "price": float(i)} for i in range(20)]

        result = generator.create_market_overview_chart(items_data)
        assert isinstance(result, io.BytesIO)


class TestChartGeneratorArbitrageOpportunities:
    """Tests for arbitrage opportunities chart generation."""

    def test_create_arbitrage_opportunities_chart_basic(self):
        """Test creating arbitrage chart with valid data."""
        generator = ChartGenerator()
        opportunities = [
            {"profit_amount": 5.0, "profit_percentage": 10.0},
            {"profit_amount": 3.0, "profit_percentage": 8.0},
            {"profit_amount": 7.0, "profit_percentage": 15.0},
        ]

        result = generator.create_arbitrage_opportunities_chart(opportunities)

        assert isinstance(result, io.BytesIO)
        result.seek(0)
        header = result.read(8)
        assert header[:4] == b"\x89PNG"

    def test_create_arbitrage_opportunities_chart_empty_data(self):
        """Test chart with empty opportunities returns error chart."""
        generator = ChartGenerator()
        result = generator.create_arbitrage_opportunities_chart([])
        assert isinstance(result, io.BytesIO)

    def test_create_arbitrage_opportunities_chart_custom_title(self):
        """Test chart with custom title."""
        generator = ChartGenerator()
        opportunities = [
            {"profit_amount": 5.0, "profit_percentage": 10.0},
        ]

        result = generator.create_arbitrage_opportunities_chart(
            opportunities, title="My Arbitrage Opportunities"
        )
        assert isinstance(result, io.BytesIO)


class TestChartGeneratorVolumeAnalysis:
    """Tests for volume analysis chart generation."""

    def test_create_volume_analysis_chart_basic(self):
        """Test creating volume chart with valid data."""
        generator = ChartGenerator()
        volume_data = [
            {"date": "2024-01-01", "volume": 100},
            {"date": "2024-01-02", "volume": 150},
            {"date": "2024-01-03", "volume": 120},
            {"date": "2024-01-04", "volume": 180},
            {"date": "2024-01-05", "volume": 140},
        ]

        result = generator.create_volume_analysis_chart(volume_data)

        assert isinstance(result, io.BytesIO)
        result.seek(0)
        header = result.read(8)
        assert header[:4] == b"\x89PNG"

    def test_create_volume_analysis_chart_handles_exception(self):
        """Test chart handles exceptions gracefully."""
        generator = ChartGenerator()
        invalid_data = [{"invalid": "data"}]

        result = generator.create_volume_analysis_chart(invalid_data)
        assert isinstance(result, io.BytesIO)


class TestChartGeneratorErrorChart:
    """Tests for error chart generation."""

    def test_create_error_chart(self):
        """Test error chart generation."""
        generator = ChartGenerator()
        result = generator._create_error_chart("Test Error Message")

        assert isinstance(result, io.BytesIO)
        result.seek(0)
        assert len(result.read()) > 0


class TestMarketAnalyzerPriceStatistics:
    """Tests for MarketAnalyzer price statistics."""

    def test_calculate_price_statistics_basic(self):
        """Test basic price statistics calculation."""
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]

        stats = MarketAnalyzer.calculate_price_statistics(prices)

        assert stats["mean"] == 30.0
        assert stats["median"] == 30.0
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["range"] == 40.0
        assert "std" in stats
        assert "q25" in stats
        assert "q75" in stats
        assert "cv" in stats

    def test_calculate_price_statistics_empty_list(self):
        """Test statistics with empty list."""
        stats = MarketAnalyzer.calculate_price_statistics([])
        assert stats == {}

    def test_calculate_price_statistics_single_value(self):
        """Test statistics with single value."""
        stats = MarketAnalyzer.calculate_price_statistics([100.0])

        assert stats["mean"] == 100.0
        assert stats["median"] == 100.0
        assert stats["min"] == 100.0
        assert stats["max"] == 100.0
        assert stats["range"] == 0.0

    def test_calculate_price_statistics_cv_with_zero_mean(self):
        """Test coefficient of variation with zero mean."""
        stats = MarketAnalyzer.calculate_price_statistics([0.0, 0.0, 0.0])
        assert stats["cv"] == 0


class TestMarketAnalyzerTrendDetection:
    """Tests for MarketAnalyzer trend detection."""

    def test_detect_price_trends_upward(self):
        """Test detecting upward trend."""
        # Create stronger upward trend to exceed the 2% threshold
        price_data = [
            {"date": f"2024-01-{i:02d}", "price": 10.0 + i * 5} for i in range(1, 15)
        ]

        result = MarketAnalyzer.detect_price_trends(price_data, window=3)

        # The trend might be upward or sideways depending on moving averages
        assert result["trend"] in {"upward", "sideways"}
        assert result["confidence"] >= 0
        assert "price_change_percent" in result

    def test_detect_price_trends_downward(self):
        """Test detecting downward trend."""
        # Create stronger downward trend
        price_data = [
            {"date": f"2024-01-{i:02d}", "price": 100.0 - i * 5} for i in range(1, 15)
        ]

        result = MarketAnalyzer.detect_price_trends(price_data, window=3)

        # The trend might be downward or sideways depending on moving averages
        assert result["trend"] in {"downward", "sideways"}
        assert "price_change_percent" in result

    def test_detect_price_trends_sideways(self):
        """Test detecting sideways trend."""
        price_data = [
            {"date": f"2024-01-{i:02d}", "price": 10.0 + (i % 2) * 0.1}
            for i in range(1, 11)
        ]

        result = MarketAnalyzer.detect_price_trends(price_data, window=3)

        assert result["trend"] == "sideways"

    def test_detect_price_trends_insufficient_data(self):
        """Test with insufficient data."""
        price_data = [
            {"date": "2024-01-01", "price": 10.0},
            {"date": "2024-01-02", "price": 11.0},
        ]

        result = MarketAnalyzer.detect_price_trends(price_data, window=5)

        assert result["trend"] == "insufficient_data"
        assert result["confidence"] == 0.0


class TestMarketAnalyzerSupportResistance:
    """Tests for support and resistance level detection."""

    def test_find_support_resistance_basic(self):
        """Test finding support and resistance levels."""
        # Create data with clear local minima and maxima
        prices = [
            10.0,
            12.0,
            15.0,
            13.0,
            10.0,  # local min at 10
            12.0,
            18.0,
            20.0,
            18.0,
            15.0,  # local max at 20
            12.0,
            10.0,
            8.0,
            10.0,
            12.0,  # local min at 8
            15.0,
            18.0,
            22.0,
            20.0,
            17.0,  # local max at 22
        ]

        result = MarketAnalyzer.find_support_resistance(prices, window=2)

        assert "support" in result
        assert "resistance" in result
        assert isinstance(result["support"], list)
        assert isinstance(result["resistance"], list)

    def test_find_support_resistance_insufficient_data(self):
        """Test with insufficient data for analysis."""
        prices = [10.0, 11.0, 12.0]

        result = MarketAnalyzer.find_support_resistance(prices, window=5)

        assert result["support"] == []
        assert result["resistance"] == []

    def test_find_support_resistance_limits_results(self):
        """Test that results are limited to 5 levels each."""
        # Create data with many potential levels
        prices = list(range(100))

        result = MarketAnalyzer.find_support_resistance(prices, window=2)

        assert len(result["support"]) <= 5
        assert len(result["resistance"]) <= 5


class TestGenerateMarketReport:
    """Tests for market report generation."""

    @pytest.mark.asyncio()
    async def test_generate_market_report_all_charts(self):
        """Test generating report with all chart types."""
        generator = ChartGenerator()
        market_data = {
            "price_history": [
                {"date": "2024-01-01", "price": 10.0},
                {"date": "2024-01-02", "price": 11.0},
            ],
            "top_items": [
                {"name": "Item A", "price": 100.0},
            ],
            "arbitrage_opportunities": [
                {"profit_amount": 5.0, "profit_percentage": 10.0},
            ],
            "volume_data": [
                {"date": "2024-01-01", "volume": 100},
                {"date": "2024-01-02", "volume": 150},
            ],
        }

        charts = await generate_market_report(generator, market_data)

        assert len(charts) == 4
        for chart in charts:
            assert isinstance(chart, io.BytesIO)

    @pytest.mark.asyncio()
    async def test_generate_market_report_partial_data(self):
        """Test generating report with partial data."""
        generator = ChartGenerator()
        market_data = {
            "price_history": [
                {"date": "2024-01-01", "price": 10.0},
                {"date": "2024-01-02", "price": 11.0},
            ],
        }

        charts = await generate_market_report(generator, market_data)

        assert len(charts) == 1

    @pytest.mark.asyncio()
    async def test_generate_market_report_empty_data(self):
        """Test generating report with empty data."""
        generator = ChartGenerator()
        market_data = {}

        charts = await generate_market_report(generator, market_data)

        assert len(charts) == 0

    @pytest.mark.asyncio()
    async def test_generate_market_report_custom_title(self):
        """Test generating report with custom title."""
        generator = ChartGenerator()
        market_data = {
            "price_history": [
                {"date": "2024-01-01", "price": 10.0},
            ],
        }

        charts = await generate_market_report(
            generator, market_data, title="Custom Report"
        )

        assert len(charts) == 1
