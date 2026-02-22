"""Unit tests for the market analyzer module."""

from datetime import UTC, datetime, timedelta

import pytest

from src.utils.market_analyzer import (
    PATTERN_BREAKOUT,
    PATTERN_FOMO,
    PATTERN_PANIC,
    TREND_DOWN,
    TREND_STABLE,
    TREND_UP,
    MarketAnalyzer,
    analyze_market_opportunity,
    batch_analyze_items,
)


@pytest.fixture()
def sample_price_history():
    """Sample price history data for testing."""
    return [
        {
            "price": 10.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=6)).timestamp(),
        },
        {
            "price": 10.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
        },
        {
            "price": 11.2,
            "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
        },
        {
            "price": 11.8,
            "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
        },
        {
            "price": 11.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
        },
        {
            "price": 12.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
        },
        {"price": 12.5, "timestamp": datetime.now(UTC).timestamp()},
    ]


@pytest.fixture()
def sample_item_data():
    """Sample item data for testing."""
    return {
        "itemId": "test-item-123",
        "title": "AK-47 | Redline",
        "price": {"amount": 1250},  # $12.50
        "gameId": "csgo",
        "extra": {
            "categoryPath": "Rifle",
            "rarity": "Classified",
            "exterior": "Field-Tested",
        },
    }


@pytest.fixture()
def downtrend_price_history():
    """Sample price history with downward trend."""
    return [
        {
            "price": 15.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=6)).timestamp(),
        },
        {
            "price": 14.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
        },
        {
            "price": 14.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
        },
        {
            "price": 13.2,
            "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
        },
        {
            "price": 12.8,
            "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
        },
        {
            "price": 12.3,
            "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
        },
        {"price": 12.0, "timestamp": datetime.now(UTC).timestamp()},
    ]


@pytest.fixture()
def volatile_price_history():
    """Sample price history with volatile pattern."""
    return [
        {
            "price": 10.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=6)).timestamp(),
        },
        {
            "price": 12.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
        },
        {
            "price": 9.8,
            "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
        },
        {
            "price": 11.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
        },
        {
            "price": 10.2,
            "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
        },
        {
            "price": 13.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
        },
        {"price": 11.5, "timestamp": datetime.now(UTC).timestamp()},
    ]


class TestMarketAnalyzer:
    """Tests for the MarketAnalyzer class."""

    def test_init(self):
        """Test that the analyzer initializes with correct parameters."""
        analyzer = MarketAnalyzer(min_data_points=8)
        assert analyzer.min_data_points == 8

    @pytest.mark.asyncio()
    async def test_analyze_price_history_uptrend(self, sample_price_history):
        """Test analyzing a price history with upward trend."""
        analyzer = MarketAnalyzer()
        result = await analyzer.analyze_price_history(sample_price_history)

        assert result["trend"] == TREND_UP
        assert result["confidence"] > 0.5
        assert result["insufficient_data"] is False
        assert result["current_price"] == 12.5
        assert result["avg_price"] > 0
        assert result["price_change_24h"] > 0

    @pytest.mark.asyncio()
    async def test_analyze_price_history_downtrend(self, downtrend_price_history):
        """Test analyzing a price history with downward trend."""
        analyzer = MarketAnalyzer()
        result = await analyzer.analyze_price_history(downtrend_price_history)

        assert result["trend"] == TREND_DOWN
        assert result["confidence"] > 0.5
        assert result["price_change_24h"] < 0

    @pytest.mark.asyncio()
    async def test_analyze_price_history_volatile(self, volatile_price_history):
        """Test analyzing a price history with volatile pattern."""
        analyzer = MarketAnalyzer()
        result = await analyzer.analyze_price_history(volatile_price_history)

        assert result["volatility"] != "low"
        assert result["volatility_ratio"] > 0.05

    @pytest.mark.asyncio()
    async def test_analyze_price_history_insufficient_data(self):
        """Test behavior with insufficient data points."""
        analyzer = MarketAnalyzer(min_data_points=10)
        result = await analyzer.analyze_price_history(
            [
                {"price": 10.0, "timestamp": datetime.now(UTC).timestamp()},
            ],
        )

        assert result["insufficient_data"] is True
        assert result["trend"] == TREND_STABLE
        assert result["confidence"] == 0.0

    def test_analyze_trend(self):
        """Test the _analyze_trend method."""
        analyzer = MarketAnalyzer()

        # Test upward trend
        trend, confidence = analyzer._analyze_trend([10.0, 10.5, 11.0, 11.5, 12.0])
        assert trend == TREND_UP
        assert confidence > 0.9

        # Test downward trend
        trend, confidence = analyzer._analyze_trend([12.0, 11.5, 11.0, 10.5, 10.0])
        assert trend == TREND_DOWN
        assert confidence > 0.9

        # Test stable trend
        trend, confidence = analyzer._analyze_trend([10.0, 10.0, 10.0, 10.0, 10.0])
        assert trend == TREND_STABLE

        # Test volatile trend
        trend, confidence = analyzer._analyze_trend([10.0, 12.0, 9.0, 11.0, 10.0])
        assert confidence < 0.7

    def test_detect_patterns(self):
        """Test pattern detection."""
        analyzer = MarketAnalyzer()
        timestamps = [
            (datetime.now(UTC) - timedelta(days=x)).timestamp()
            for x in range(10, 0, -1)
        ]

        # Test breakout pattern
        breakout_prices = [10.0, 10.1, 10.2, 10.1, 10.3, 10.2, 10.1, 10.4, 11.0, 12.0]
        patterns = analyzer._detect_patterns(breakout_prices, timestamps)
        pattern_types = [p["type"] for p in patterns]
        assert PATTERN_BREAKOUT in pattern_types

        # Test FOMO pattern
        fomo_prices = [10.0, 10.2, 10.5, 10.7, 10.9, 11.0, 11.2, 11.5, 12.0, 14.0]
        patterns = analyzer._detect_patterns(fomo_prices, timestamps)
        pattern_types = [p["type"] for p in patterns]
        assert PATTERN_FOMO in pattern_types

        # Test panic pattern
        panic_prices = [10.0, 9.8, 9.5, 9.3, 9.0, 8.8, 8.5, 8.0, 7.5, 6.0]
        patterns = analyzer._detect_patterns(panic_prices, timestamps)
        pattern_types = [p["type"] for p in patterns]
        assert PATTERN_PANIC in pattern_types


@pytest.mark.asyncio()
class TestMarketOpportunity:
    """Tests for market opportunity analysis functions."""

    async def test_analyze_market_opportunity_uptrend(
        self,
        sample_item_data,
        sample_price_history,
    ):
        """Test market opportunity analysis with upward trend."""
        result = await analyze_market_opportunity(
            sample_item_data,
            sample_price_history,
            "csgo",
        )

        assert "opportunity_score" in result
        assert result["opportunity_score"] >= 0
        assert result["opportunity_score"] <= 100
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert "market_analysis" in result
        assert result["current_price"] == 12.50
        assert result["game"] == "csgo"

    async def test_analyze_market_opportunity_downtrend(
        self,
        sample_item_data,
        downtrend_price_history,
    ):
        """Test market opportunity analysis with downward trend."""
        result = await analyze_market_opportunity(
            sample_item_data,
            downtrend_price_history,
            "csgo",
        )

        assert "opportunity_score" in result
        assert "market_analysis" in result
        assert result["market_analysis"]["trend"] == TREND_DOWN

    async def test_analyze_market_opportunity_with_patterns(self, sample_item_data):
        """Test market opportunity analysis with specific patterns."""
        # Create price history with FOMO pattern
        fomo_history = [
            {
                "price": 10.0,
                "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
            },
            {
                "price": 10.5,
                "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
            },
            {
                "price": 11.2,
                "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
            },
            {
                "price": 12.8,
                "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
            },
            {
                "price": 14.5,
                "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
            },
            {"price": 17.0, "timestamp": datetime.now(UTC).timestamp()},
        ]

        result = await analyze_market_opportunity(
            sample_item_data,
            fomo_history,
            "csgo",
        )

        # Check if FOMO pattern is detected and included in reasons
        pattern_types = [p["type"] for p in result["market_analysis"]["patterns"]]
        assert PATTERN_FOMO in pattern_types

        # FOMO should contribute to a high opportunity score for selling
        assert result["opportunity_score"] > 50
        assert any("FOMO" in reason for reason in result["reasons"])

    async def test_batch_analyze_items(self, sample_item_data, sample_price_history):
        """Test batch analysis of multiple items."""
        items = [sample_item_data, sample_item_data.copy()]
        items[1]["itemId"] = "test-item-456"

        price_histories = {
            "test-item-123": sample_price_history,
            "test-item-456": sample_price_history,
        }

        results = await batch_analyze_items(items, price_histories, "csgo")

        assert len(results) == 2
        assert results[0]["item_id"] == "test-item-123"
        assert results[1]["item_id"] == "test-item-456"
        assert all(isinstance(r["opportunity_score"], int | float) for r in results)
        assert all(isinstance(r["reasons"], list) for r in results)
