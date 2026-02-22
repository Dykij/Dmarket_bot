"""Unit tests for MarketDepthAnalyzer.

Tests the refactored market depth analysis functionality.
Phase 2 - Week 3-4
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.market_depth_analyzer import MarketDepthAnalyzer, analyze_market_depth


@pytest.fixture()
def mock_api():
    """Mock DMarket API client."""
    api = AsyncMock()
    api._close_client = AsyncMock()
    return api


@pytest.fixture()
def sample_aggregated_prices():
    """Sample aggregated prices response."""
    return {
        "aggregatedPrices": [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "orderCount": 50,
                "offerCount": 30,
                "orderBestPrice": 1000,  # $10.00 in cents
                "offerBestPrice": 1200,  # $12.00 in cents
            },
            {
                "title": "AWP | Asiimov (Field-Tested)",
                "orderCount": 20,
                "offerCount": 80,
                "orderBestPrice": 5000,  # $50.00
                "offerBestPrice": 5500,  # $55.00
            },
        ]
    }


@pytest.fixture()
def sample_market_items():
    """Sample market items response."""
    return {
        "items": [
            {"title": "AK-47 | Redline (Field-Tested)"},
            {"title": "AWP | Asiimov (Field-Tested)"},
        ]
    }


class TestMarketDepthAnalyzerInitialization:
    """Test analyzer initialization."""

    def test_init_with_api_client(self, mock_api):
        """Test initialization with provided API client."""
        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        assert analyzer.dmarket_api is mock_api
        assert analyzer._owns_client is False

    def test_init_without_api_client(self):
        """Test initialization without API client."""
        analyzer = MarketDepthAnalyzer()

        assert analyzer.dmarket_api is None
        assert analyzer._owns_client is True


class TestMarketDepthAnalysis:
    """Test main analysis functionality."""

    @pytest.mark.asyncio()
    async def test_analyze_with_provided_items(
        self, mock_api, sample_aggregated_prices
    ):
        """Test analysis with provided item list."""
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value=sample_aggregated_prices
        )

        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        result = await analyzer.analyze(
            game="csgo",
            items=["AK-47 | Redline (Field-Tested)"],
            limit=10,
        )

        assert result["game"] == "csgo"
        assert result["items_analyzed"] == 2
        assert len(result["market_depth"]) == 2
        assert "summary" in result
        assert "timestamp" in result

    @pytest.mark.asyncio()
    async def test_analyze_fetches_popular_items(
        self, mock_api, sample_market_items, sample_aggregated_prices
    ):
        """Test analysis fetches popular items when none provided."""
        mock_api.get_market_items = AsyncMock(return_value=sample_market_items)
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value=sample_aggregated_prices
        )

        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        result = await analyzer.analyze(game="csgo", items=None, limit=10)

        assert result["items_analyzed"] > 0
        mock_api.get_market_items.assert_called_once()

    @pytest.mark.asyncio()
    async def test_analyze_handles_empty_items(self, mock_api):
        """Test analysis with empty item list."""
        mock_api.get_market_items = AsyncMock(return_value={"items": []})

        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        result = await analyzer.analyze(game="csgo", items=None, limit=10)

        assert result["items_analyzed"] == 0
        assert result["market_depth"] == []
        assert result["summary"] == {}

    @pytest.mark.asyncio()
    async def test_analyze_handles_api_error(self, mock_api):
        """Test analysis handles API errors gracefully."""
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            side_effect=Exception("API Error")
        )

        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        result = await analyzer.analyze(
            game="csgo",
            items=["Test Item"],
            limit=10,
        )

        assert result["items_analyzed"] == 0
        assert "error" in result
        assert "API Error" in result["error"]


class TestItemAnalysis:
    """Test individual item analysis methods."""

    def test_analyze_single_item(self):
        """Test single item depth metrics calculation."""
        analyzer = MarketDepthAnalyzer()

        price_data = {
            "title": "Test Item",
            "orderCount": 50,
            "offerCount": 30,
            "orderBestPrice": 1000,  # $10.00
            "offerBestPrice": 1200,  # $12.00
        }

        result = analyzer._analyze_single_item(price_data)

        assert result["title"] == "Test Item"
        assert result["order_count"] == 50
        assert result["offer_count"] == 30
        assert result["total_volume"] == 80
        assert result["order_price"] == 10.0
        assert result["offer_price"] == 12.0
        assert result["spread"] == 2.0
        assert result["spread_percent"] == 20.0
        assert result["buy_pressure"] == 62.5
        assert result["sell_pressure"] == 37.5
        assert result["liquidity_score"] == 100
        assert result["market_balance"] == "buyer_dominated"

    def test_calculate_pressure(self):
        """Test pressure calculation."""
        analyzer = MarketDepthAnalyzer()

        pressure = analyzer._calculate_pressure(50, 100)
        assert pressure == 50.0

        # Zero total
        pressure = analyzer._calculate_pressure(50, 0)
        assert pressure == 0.0

    def test_calculate_spread_percent(self):
        """Test spread percentage calculation."""
        analyzer = MarketDepthAnalyzer()

        spread_pct = analyzer._calculate_spread_percent(2.0, 10.0)
        assert spread_pct == 20.0

        # Zero order price
        spread_pct = analyzer._calculate_spread_percent(2.0, 0.0)
        assert spread_pct == 0.0

    @pytest.mark.parametrize(
        ("buy_pressure", "sell_pressure", "expected_balance", "expected_desc"),
        (
            (70, 30, "buyer_dominated", "Преобладают покупатели"),
            (30, 70, "seller_dominated", "Преобладают продавцы"),
            (50, 50, "balanced", "Сбалансированный рынок"),
            (60, 40, "balanced", "Сбалансированный рынок"),
        ),
    )
    def test_determine_market_balance(
        self, buy_pressure, sell_pressure, expected_balance, expected_desc
    ):
        """Test market balance determination."""
        analyzer = MarketDepthAnalyzer()

        balance, desc = analyzer._determine_market_balance(buy_pressure, sell_pressure)

        assert balance == expected_balance
        assert desc == expected_desc


class TestSummaryCalculation:
    """Test summary statistics calculation."""

    def test_calculate_summary_with_data(self):
        """Test summary calculation with valid data."""
        analyzer = MarketDepthAnalyzer()

        depth_analysis = [
            {
                "liquidity_score": 100,
                "spread_percent": 20.0,
                "arbitrage_potential": True,
            },
            {
                "liquidity_score": 80,
                "spread_percent": 10.0,
                "arbitrage_potential": False,
            },
        ]

        summary = analyzer._calculate_summary(depth_analysis)

        assert summary["items_analyzed"] == 2
        assert summary["average_liquidity_score"] == 90.0
        assert summary["average_spread_percent"] == 15.0
        assert summary["high_liquidity_items"] == 2
        assert summary["arbitrage_opportunities"] == 1
        assert summary["market_health"] == "excellent"

    def test_calculate_summary_empty(self):
        """Test summary with empty data."""
        analyzer = MarketDepthAnalyzer()

        summary = analyzer._calculate_summary([])

        assert summary == {}

    @pytest.mark.parametrize(
        ("avg_liquidity", "expected_health"),
        (
            (80, "excellent"),
            (60, "good"),
            (35, "moderate"),
            (15, "poor"),
        ),
    )
    def test_determine_market_health(self, avg_liquidity, expected_health):
        """Test market health determination."""
        analyzer = MarketDepthAnalyzer()

        health = analyzer._determine_market_health(avg_liquidity)

        assert health == expected_health


class TestAsyncContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio()
    async def test_context_manager_with_own_client(self):
        """Test context manager creates and closes client."""
        analyzer = MarketDepthAnalyzer()

        async with analyzer as ctx:
            assert ctx is analyzer
            assert ctx.dmarket_api is not None

    @pytest.mark.asyncio()
    async def test_context_manager_with_provided_client(self, mock_api):
        """Test context manager with provided client doesn't close it."""
        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        async with analyzer:
            pass

        mock_api._close_client.assert_not_called()


class TestBackwardCompatibility:
    """Test legacy function wrapper."""

    @pytest.mark.asyncio()
    async def test_legacy_function_wrapper(self, mock_api, sample_aggregated_prices):
        """Test legacy analyze_market_depth function."""
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value=sample_aggregated_prices
        )

        result = await analyze_market_depth(
            game="csgo",
            items=["Test Item"],
            limit=10,
            dmarket_api=mock_api,
        )

        assert result["game"] == "csgo"
        assert "market_depth" in result
        assert "summary" in result


class TestHelperMethods:
    """Test helper methods."""

    def test_empty_result(self):
        """Test empty result structure."""
        analyzer = MarketDepthAnalyzer()

        result = analyzer._empty_result("csgo")

        assert result["game"] == "csgo"
        assert result["items_analyzed"] == 0
        assert result["market_depth"] == []
        assert result["summary"] == {}

    def test_error_result(self):
        """Test error result structure."""
        analyzer = MarketDepthAnalyzer()

        result = analyzer._error_result("csgo", "Test error")

        assert result["game"] == "csgo"
        assert result["items_analyzed"] == 0
        assert result["error"] == "Test error"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_analyze_item_with_zero_counts(self):
        """Test item analysis with zero order/offer counts."""
        analyzer = MarketDepthAnalyzer()

        price_data = {
            "title": "Zero Volume Item",
            "orderCount": 0,
            "offerCount": 0,
            "orderBestPrice": 0,
            "offerBestPrice": 0,
        }

        result = analyzer._analyze_single_item(price_data)

        assert result["total_volume"] == 0
        assert result["buy_pressure"] == 0.0
        assert result["sell_pressure"] == 0.0
        assert result["spread_percent"] == 0.0

    def test_analyze_item_with_high_liquidity(self):
        """Test item with very high liquidity is capped at 100."""
        analyzer = MarketDepthAnalyzer()

        price_data = {
            "title": "High Volume Item",
            "orderCount": 1000,
            "offerCount": 1000,
            "orderBestPrice": 1000,
            "offerBestPrice": 1100,
        }

        result = analyzer._analyze_single_item(price_data)

        # liquidity_score = min(100, total_volume * 2)
        assert result["liquidity_score"] == 100

    @pytest.mark.asyncio()
    async def test_analyze_with_invalid_aggregated_response(self, mock_api):
        """Test handling of invalid aggregated prices response."""
        mock_api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"invalid": "response"}
        )

        analyzer = MarketDepthAnalyzer(dmarket_api=mock_api)

        result = await analyzer.analyze(
            game="csgo",
            items=["Test"],
            limit=10,
        )

        assert result["items_analyzed"] == 0
        assert result["market_depth"] == []
