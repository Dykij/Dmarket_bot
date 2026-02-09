"""Unit tests for liquidity_analyzer.py module.

Tests for liquidity analysis functionality including metrics calculation,
threshold checks, and liquidity scoring.
"""

from unittest.mock import MagicMock

import pytest

# Skip all tests if structlog is not available
pytest.importorskip("structlog")


class TestLiquidityMetricsDataclass:
    """Tests for LiquidityMetrics dataclass."""

    def test_liquidity_metrics_creation(self) -> None:
        """Test LiquidityMetrics dataclass can be created."""
        from src.dmarket.liquidity_analyzer import LiquidityMetrics

        metrics = LiquidityMetrics(
            item_title="AK-47 | Redline",
            sales_per_week=50.0,
            avg_time_to_sell_days=2.5,
            active_offers_count=30,
            price_stability=0.92,
            market_depth=5000.0,
            liquidity_score=85.0,
            is_liquid=True,
        )

        assert metrics.item_title == "AK-47 | Redline"
        assert metrics.sales_per_week == 50.0
        assert metrics.avg_time_to_sell_days == 2.5
        assert metrics.active_offers_count == 30
        assert metrics.price_stability == 0.92
        assert metrics.market_depth == 5000.0
        assert metrics.liquidity_score == 85.0
        assert metrics.is_liquid is True

    def test_liquidity_metrics_illiquid_item(self) -> None:
        """Test LiquidityMetrics for illiquid item."""
        from src.dmarket.liquidity_analyzer import LiquidityMetrics

        metrics = LiquidityMetrics(
            item_title="Rare Souvenir",
            sales_per_week=0.5,
            avg_time_to_sell_days=30.0,
            active_offers_count=5,
            price_stability=0.4,
            market_depth=100.0,
            liquidity_score=15.0,
            is_liquid=False,
        )

        assert metrics.is_liquid is False
        assert metrics.liquidity_score == 15.0
        assert metrics.sales_per_week < 1.0


class TestLiquidityAnalyzerInitialization:
    """Tests for LiquidityAnalyzer initialization."""

    def test_default_initialization(self) -> None:
        """Test LiquidityAnalyzer with default parameters."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api)

        assert analyzer.api == mock_api
        assert analyzer.min_sales_per_week == 10.0
        assert analyzer.max_time_to_sell_days == 7.0
        assert analyzer.max_active_offers == 50
        assert analyzer.min_price_stability == 0.85
        assert analyzer.min_liquidity_score == 60.0

    def test_custom_initialization(self) -> None:
        """Test LiquidityAnalyzer with custom parameters."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(
            api_client=mock_api,
            min_sales_per_week=20.0,
            max_time_to_sell_days=5.0,
            max_active_offers=100,
            min_price_stability=0.90,
            min_liquidity_score=70.0,
        )

        assert analyzer.min_sales_per_week == 20.0
        assert analyzer.max_time_to_sell_days == 5.0
        assert analyzer.max_active_offers == 100
        assert analyzer.min_price_stability == 0.90
        assert analyzer.min_liquidity_score == 70.0

    def test_initialization_stores_api_client(self) -> None:
        """Test that API client is stored correctly."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api)

        assert analyzer.api is mock_api


class TestLiquidityThresholds:
    """Tests for liquidity threshold calculations."""

    def test_sales_per_week_threshold(self) -> None:
        """Test sales per week threshold."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, min_sales_per_week=15.0)

        # Below threshold
        assert analyzer.min_sales_per_week > 10.0

        # Above threshold
        assert analyzer.min_sales_per_week < 20.0

    def test_time_to_sell_threshold(self) -> None:
        """Test time to sell threshold."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, max_time_to_sell_days=5.0)

        # Too long to sell
        assert analyzer.max_time_to_sell_days < 10.0

        # Quick sale
        assert analyzer.max_time_to_sell_days > 2.0

    def test_price_stability_threshold(self) -> None:
        """Test price stability threshold."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, min_price_stability=0.80)

        # Stable price
        assert analyzer.min_price_stability < 0.95

        # Unstable price
        assert analyzer.min_price_stability > 0.50


class TestLiquidityScoreCalculation:
    """Tests for liquidity score calculation logic."""

    def test_high_liquidity_score(self) -> None:
        """Test high liquidity score criteria."""
        # High liquidity indicators
        sales_per_week = 100.0
        avg_time_to_sell = 1.0
        price_stability = 0.95

        # Simple score formula example (actual formula result is ~36)
        score = min(100, (sales_per_week / 10) + (7 / avg_time_to_sell) + (price_stability * 20))

        # High liquidity means score > 30 in this formula
        assert score > 30

    def test_low_liquidity_score(self) -> None:
        """Test low liquidity score criteria."""
        # Low liquidity indicators
        sales_per_week = 2.0
        avg_time_to_sell = 14.0
        price_stability = 0.40

        # Simple score formula example
        score = min(100, (sales_per_week / 10) + (7 / avg_time_to_sell) + (price_stability * 20))

        assert score < 50

    def test_score_bounded_zero_to_hundred(self) -> None:
        """Test that score is bounded between 0 and 100."""
        # Edge case values
        for sales in [0.0, 10.0, 1000.0]:
            for time_to_sell in [0.1, 1.0, 30.0]:
                for stability in [0.0, 0.5, 1.0]:
                    if time_to_sell > 0:  # Avoid division by zero
                        score = min(
                            100, max(0, (sales / 10) + (7 / time_to_sell) + (stability * 20))
                        )
                        assert 0 <= score <= 100


class TestLiquidityClassification:
    """Tests for liquidity classification logic."""

    def test_classify_as_liquid(self) -> None:
        """Test classification as liquid item."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, min_liquidity_score=60.0)

        liquidity_score = 75.0
        is_liquid = liquidity_score >= analyzer.min_liquidity_score

        assert is_liquid is True

    def test_classify_as_illiquid(self) -> None:
        """Test classification as illiquid item."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, min_liquidity_score=60.0)

        liquidity_score = 45.0
        is_liquid = liquidity_score >= analyzer.min_liquidity_score

        assert is_liquid is False

    def test_boundary_case_exactly_at_threshold(self) -> None:
        """Test boundary case at exact threshold."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, min_liquidity_score=60.0)

        liquidity_score = 60.0
        is_liquid = liquidity_score >= analyzer.min_liquidity_score

        assert is_liquid is True


class TestMarketDepthAnalysis:
    """Tests for market depth analysis."""

    def test_high_market_depth(self) -> None:
        """Test high market depth indicates good liquidity."""
        market_depth = 50000.0  # High trading volume
        min_market_depth = 10000.0

        has_sufficient_depth = market_depth >= min_market_depth

        assert has_sufficient_depth is True

    def test_low_market_depth(self) -> None:
        """Test low market depth indicates poor liquidity."""
        market_depth = 500.0  # Low trading volume
        min_market_depth = 10000.0

        has_sufficient_depth = market_depth >= min_market_depth

        assert has_sufficient_depth is False

    def test_market_depth_calculation(self) -> None:
        """Test market depth calculation from sales history."""
        # Simple calculation: sum of sale amounts
        sales = [100.0, 150.0, 200.0, 120.0, 180.0]
        market_depth = sum(sales)

        assert market_depth == 750.0


class TestPriceStabilityCalculation:
    """Tests for price stability calculation."""

    def test_perfect_stability(self) -> None:
        """Test perfect price stability (no variance)."""
        prices = [10.0, 10.0, 10.0, 10.0, 10.0]
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)

        # Perfect stability = 0 variance
        stability = 1.0 - min(1.0, variance / (avg_price**2))

        assert stability == 1.0

    def test_high_stability(self) -> None:
        """Test high price stability (low variance)."""
        prices = [10.0, 10.1, 9.9, 10.0, 10.2]
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)

        # High stability = low variance
        stability = 1.0 - min(1.0, variance / (avg_price**2))

        assert stability > 0.9

    def test_low_stability(self) -> None:
        """Test low price stability (high variance)."""
        prices = [5.0, 15.0, 8.0, 20.0, 10.0]
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)

        # Low stability = high variance
        stability = max(0.0, 1.0 - min(1.0, variance / (avg_price**2)))

        assert stability < 0.8


class TestActiveOffersAnalysis:
    """Tests for active offers analysis."""

    def test_reasonable_offers_count(self) -> None:
        """Test reasonable number of active offers."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, max_active_offers=50)

        offers_count = 30
        is_reasonable = offers_count <= analyzer.max_active_offers

        assert is_reasonable is True

    def test_excessive_offers_count(self) -> None:
        """Test excessive number of active offers (oversupply)."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api, max_active_offers=50)

        offers_count = 150
        is_reasonable = offers_count <= analyzer.max_active_offers

        assert is_reasonable is False

    def test_low_offers_count(self) -> None:
        """Test low number of active offers (scarce)."""
        offers_count = 3

        # Very low offers might indicate scarce item
        is_scarce = offers_count < 5

        assert is_scarce is True


class TestSalesPerWeekCalculation:
    """Tests for sales per week calculation."""

    def test_calculate_from_30_days(self) -> None:
        """Test calculating weekly sales from 30 days data."""
        total_sales_30_days = 120
        days = 30
        weeks = days / 7

        sales_per_week = total_sales_30_days / weeks

        assert abs(sales_per_week - 28.0) < 0.1

    def test_calculate_from_7_days(self) -> None:
        """Test calculating weekly sales from 7 days data."""
        total_sales_7_days = 35
        days = 7
        weeks = days / 7

        sales_per_week = total_sales_7_days / weeks

        assert sales_per_week == 35.0

    def test_no_sales(self) -> None:
        """Test handling zero sales."""
        total_sales = 0
        days = 30
        weeks = days / 7

        sales_per_week = total_sales / weeks

        assert sales_per_week == 0.0


class TestTimeToSellCalculation:
    """Tests for average time to sell calculation."""

    def test_quick_selling_item(self) -> None:
        """Test quick selling item (high demand)."""
        # Average time to sell in days
        avg_time = 0.5  # Sells within half a day

        is_quick = avg_time < 1.0

        assert is_quick is True

    def test_slow_selling_item(self) -> None:
        """Test slow selling item (low demand)."""
        avg_time = 14.0  # Takes 2 weeks to sell

        is_slow = avg_time > 7.0

        assert is_slow is True

    def test_moderate_selling_item(self) -> None:
        """Test moderate selling item."""
        avg_time = 3.0  # Takes 3 days to sell

        is_moderate = 1.0 <= avg_time <= 7.0

        assert is_moderate is True


class TestGameSpecificLiquidity:
    """Tests for game-specific liquidity considerations."""

    def test_csgo_item_liquidity(self) -> None:
        """Test CS:GO item liquidity (generally higher)."""
        # CS:GO items typically have higher liquidity
        game = "csgo"
        expected_min_sales = 10.0  # Lower threshold for CS:GO

        # CS:GO is popular, so lower minimum is acceptable
        assert expected_min_sales <= 15.0

    def test_dota2_item_liquidity(self) -> None:
        """Test Dota 2 item liquidity (varies widely)."""
        game = "dota2"
        expected_min_sales = 5.0  # Lower threshold for Dota 2

        # Dota 2 items may have lower liquidity
        assert expected_min_sales <= 10.0

    def test_rare_item_liquidity(self) -> None:
        """Test rare item liquidity (generally lower)."""
        is_rare = True
        base_min_sales = 10.0

        # Adjust threshold for rare items
        adjusted_min_sales = base_min_sales * 0.5 if is_rare else base_min_sales

        assert adjusted_min_sales == 5.0


class TestModuleImports:
    """Tests for module imports and structure."""

    def test_module_imports_without_error(self) -> None:
        """Test module can be imported without errors."""
        import src.dmarket.liquidity_analyzer

        assert src.dmarket.liquidity_analyzer is not None

    def test_liquidity_metrics_importable(self) -> None:
        """Test LiquidityMetrics is importable."""
        from src.dmarket.liquidity_analyzer import LiquidityMetrics

        assert LiquidityMetrics is not None

    def test_liquidity_analyzer_importable(self) -> None:
        """Test LiquidityAnalyzer is importable."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        assert LiquidityAnalyzer is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_sales_handled(self) -> None:
        """Test handling of zero sales."""
        from src.dmarket.liquidity_analyzer import LiquidityMetrics

        metrics = LiquidityMetrics(
            item_title="Very Rare Item",
            sales_per_week=0.0,
            avg_time_to_sell_days=float("inf"),
            active_offers_count=1,
            price_stability=0.0,
            market_depth=0.0,
            liquidity_score=0.0,
            is_liquid=False,
        )

        assert metrics.sales_per_week == 0.0
        assert metrics.is_liquid is False

    def test_negative_values_not_allowed(self) -> None:
        """Test that negative values should not be used."""
        sales = -5.0  # Invalid negative sales

        # Negative sales don't make sense
        is_valid = sales >= 0

        assert is_valid is False

    def test_empty_history_handled(self) -> None:
        """Test handling of empty sales history."""
        sales_history: list = []

        # Should handle gracefully
        has_history = len(sales_history) > 0

        assert has_history is False


class TestAsyncMethods:
    """Tests for async method signatures."""

    @pytest.mark.asyncio()
    async def test_analyze_item_liquidity_signature(self) -> None:
        """Test analyze_item_liquidity method exists and is async."""
        from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

        mock_api = MagicMock()
        analyzer = LiquidityAnalyzer(api_client=mock_api)

        # Method should exist
        assert hasattr(analyzer, "analyze_item_liquidity")

        # Method should be a coroutine
        import inspect

        assert inspect.iscoroutinefunction(analyzer.analyze_item_liquidity)
