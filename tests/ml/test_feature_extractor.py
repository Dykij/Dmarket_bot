"""Tests for src/ml/feature_extractor module.

Tests for MarketFeatureExtractor and PriceFeatures.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from src.ml.feature_extractor import (
    MarketFeatureExtractor,
    PriceFeatures,
    TrendDirection,
)


class TestTrendDirection:
    """Tests for TrendDirection enum."""

    def test_up_value(self):
        """Test UP trend value."""
        assert TrendDirection.UP == "up"

    def test_down_value(self):
        """Test DOWN trend value."""
        assert TrendDirection.DOWN == "down"

    def test_stable_value(self):
        """Test STABLE trend value."""
        assert TrendDirection.STABLE == "stable"

    def test_volatile_value(self):
        """Test VOLATILE trend value."""
        assert TrendDirection.VOLATILE == "volatile"


class TestPriceFeatures:
    """Tests for PriceFeatures dataclass."""

    def test_init_defaults(self):
        """Test default values initialization."""
        features = PriceFeatures(current_price=10.0)

        assert features.current_price == 10.0
        assert features.price_mean_7d == 0.0
        assert features.price_std_7d == 0.0
        assert features.rsi == 50.0
        assert features.volatility == 0.0
        assert features.trend_direction == TrendDirection.STABLE
        assert features.data_quality_score == 1.0

    def test_to_array(self):
        """Test to_array returns numpy array."""
        features = PriceFeatures(
            current_price=10.0,
            price_mean_7d=9.5,
            price_std_7d=0.5,
            rsi=55.0,
            volatility=0.1,
        )

        arr = features.to_array()

        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.float64
        assert len(arr) == 18  # Number of features

    def test_trend_to_numeric_up(self):
        """Test trend to numeric conversion for UP."""
        features = PriceFeatures(
            current_price=10.0,
            trend_direction=TrendDirection.UP,
        )
        assert features._trend_to_numeric() == 1.0

    def test_trend_to_numeric_down(self):
        """Test trend to numeric conversion for DOWN."""
        features = PriceFeatures(
            current_price=10.0,
            trend_direction=TrendDirection.DOWN,
        )
        assert features._trend_to_numeric() == -1.0

    def test_trend_to_numeric_stable(self):
        """Test trend to numeric conversion for STABLE."""
        features = PriceFeatures(
            current_price=10.0,
            trend_direction=TrendDirection.STABLE,
        )
        assert features._trend_to_numeric() == 0.0

    def test_trend_to_numeric_volatile(self):
        """Test trend to numeric conversion for VOLATILE."""
        features = PriceFeatures(
            current_price=10.0,
            trend_direction=TrendDirection.VOLATILE,
        )
        assert features._trend_to_numeric() == 0.5

    def test_feature_names(self):
        """Test feature_names returns list."""
        names = PriceFeatures.feature_names()

        assert isinstance(names, list)
        assert len(names) == 18
        assert "current_price" in names
        assert "rsi" in names
        assert "volatility" in names


class TestMarketFeatureExtractor:
    """Tests for MarketFeatureExtractor class."""

    def test_init(self):
        """Test extractor initialization."""
        extractor = MarketFeatureExtractor()

        assert extractor._price_cache == {}
        assert extractor._sales_cache == {}

    def test_extract_features_basic(self):
        """Test basic feature extraction."""
        extractor = MarketFeatureExtractor()

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=10.0,
        )

        assert isinstance(features, PriceFeatures)
        assert features.current_price == 10.0
        assert 0 <= features.hour_of_day <= 23
        assert 0 <= features.day_of_week <= 6

    def test_extract_features_with_price_history(self):
        """Test feature extraction with price history."""
        extractor = MarketFeatureExtractor()

        now = datetime.now(UTC)
        price_history = [
            (now - timedelta(days=7), 8.0),
            (now - timedelta(days=5), 9.0),
            (now - timedelta(days=3), 10.0),
            (now - timedelta(days=1), 11.0),
            (now - timedelta(hours=1), 10.5),
        ]

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=10.0,
            price_history=price_history,
        )

        assert features.price_mean_7d > 0
        assert features.price_std_7d >= 0
        assert features.price_min_7d > 0
        assert features.price_max_7d > 0
        # Quality should be higher with price history
        assert features.data_quality_score > 0.3

    def test_extract_features_with_sales_history(self):
        """Test feature extraction with sales history."""
        extractor = MarketFeatureExtractor()

        now = datetime.now(UTC)
        sales_history = [
            {"timestamp": now - timedelta(hours=1), "price": 10.0},
            {"timestamp": now - timedelta(hours=5), "price": 9.5},
            {"timestamp": now - timedelta(days=1), "price": 10.5},
            {"timestamp": now - timedelta(days=3), "price": 9.0},
        ]

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=10.0,
            sales_history=sales_history,
        )

        assert features.sales_count_24h >= 2
        assert features.sales_count_7d >= 4
        assert features.avg_sales_per_day > 0

    def test_extract_features_with_market_offers(self):
        """Test feature extraction with market offers."""
        extractor = MarketFeatureExtractor()

        market_offers = [
            {"price": {"USD": 950}},  # 9.50 USD
            {"price": {"USD": 1000}},  # 10.00 USD
            {"price": {"USD": 1050}},  # 10.50 USD
            {"price": {"USD": 1100}},  # 11.00 USD
        ]

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=10.0,
            market_offers=market_offers,
        )

        assert features.market_depth == 4.0
        assert 0 <= features.competition_level <= 1.0

    def test_extract_features_data_quality_no_history(self):
        """Test data quality score without history."""
        extractor = MarketFeatureExtractor()

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=10.0,
        )

        # Without any data, quality should be reduced
        assert features.data_quality_score < 1.0

    def test_calculate_rsi_basic(self):
        """Test RSI calculation."""
        extractor = MarketFeatureExtractor()

        # Uptrend prices
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

        rsi = extractor._calculate_rsi(prices)

        assert 0 <= rsi <= 100
        # Strong uptrend should have high RSI
        assert rsi > 50

    def test_calculate_rsi_downtrend(self):
        """Test RSI calculation for downtrend."""
        extractor = MarketFeatureExtractor()

        # Downtrend prices
        prices = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]

        rsi = extractor._calculate_rsi(prices)

        assert 0 <= rsi <= 100
        # Strong downtrend should have low RSI
        assert rsi < 50

    def test_calculate_rsi_single_price(self):
        """Test RSI calculation with single price."""
        extractor = MarketFeatureExtractor()

        rsi = extractor._calculate_rsi([10.0])

        assert rsi == 50.0  # Default neutral value

    def test_calculate_momentum(self):
        """Test momentum calculation."""
        extractor = MarketFeatureExtractor()

        # Upward momentum
        prices = [10, 10.5, 11, 11.5, 12]

        momentum = extractor._calculate_momentum(prices)

        assert momentum > 0  # Positive momentum

    def test_calculate_momentum_negative(self):
        """Test negative momentum calculation."""
        extractor = MarketFeatureExtractor()

        # Downward momentum
        prices = [12, 11.5, 11, 10.5, 10]

        momentum = extractor._calculate_momentum(prices)

        assert momentum < 0  # Negative momentum

    def test_calculate_momentum_single(self):
        """Test momentum with single price."""
        extractor = MarketFeatureExtractor()

        momentum = extractor._calculate_momentum([10.0])

        assert momentum == 0.0

    def test_determine_trend_up(self):
        """Test trend determination for uptrend."""
        extractor = MarketFeatureExtractor()

        trend = extractor._determine_trend(
            price_change_7d=10.0,  # +10% over 7 days
            volatility=0.05,
        )

        assert trend == TrendDirection.UP

    def test_determine_trend_down(self):
        """Test trend determination for downtrend."""
        extractor = MarketFeatureExtractor()

        trend = extractor._determine_trend(
            price_change_7d=-10.0,  # -10% over 7 days
            volatility=0.05,
        )

        assert trend == TrendDirection.DOWN

    def test_determine_trend_stable(self):
        """Test trend determination for stable."""
        extractor = MarketFeatureExtractor()

        trend = extractor._determine_trend(
            price_change_7d=2.0,  # +2% over 7 days (minor)
            volatility=0.05,
        )

        assert trend == TrendDirection.STABLE

    def test_determine_trend_volatile(self):
        """Test trend determination for volatile."""
        extractor = MarketFeatureExtractor()

        trend = extractor._determine_trend(
            price_change_7d=5.0,
            volatility=0.20,  # High volatility
        )

        assert trend == TrendDirection.VOLATILE

    def test_batch_extract(self):
        """Test batch feature extraction."""
        extractor = MarketFeatureExtractor()

        items = [
            {"title": "Item 1", "price": {"USD": 1000}},
            {"title": "Item 2", "price": {"USD": 2000}},
            {"name": "Item 3", "price": 1500},
        ]

        features_list = extractor.batch_extract(items)

        assert len(features_list) == 3
        assert all(isinstance(f, PriceFeatures) for f in features_list)
        assert features_list[0].current_price == 10.0  # 1000 cents = $10
        assert features_list[1].current_price == 20.0

    def test_batch_extract_empty(self):
        """Test batch extract with empty list."""
        extractor = MarketFeatureExtractor()

        features_list = extractor.batch_extract([])

        assert features_list == []

    def test_peak_hours_detection(self):
        """Test peak hours detection."""
        extractor = MarketFeatureExtractor()

        features = extractor.extract_features(
            item_name="Test",
            current_price=10.0,
        )

        # Just verify the flag is boolean
        assert isinstance(features.is_peak_hours, bool)

    def test_weekend_detection(self):
        """Test weekend detection."""
        extractor = MarketFeatureExtractor()

        features = extractor.extract_features(
            item_name="Test",
            current_price=10.0,
        )

        # Just verify the flag is correct type
        assert isinstance(features.is_weekend, bool)
        # Weekend should match day_of_week >= 5
        expected = features.day_of_week >= 5
        assert features.is_weekend == expected
