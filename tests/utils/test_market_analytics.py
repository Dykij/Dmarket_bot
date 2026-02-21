"""Tests for market_analytics module.

Comprehensive tests for technical indicators, market analyzer,
and trading signals functionality.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest

from src.utils.market_analytics import (
    MarketAnalyzer,
    PricePoint,
    SignalType,
    TechnicalIndicators,
    TrendDirection,
)


class TestPricePoint:
    """Tests for PricePoint class."""

    def test_create_price_point(self) -> None:
        """Test creating a price point."""
        timestamp = datetime.now(UTC)
        pp = PricePoint(timestamp=timestamp, price=10.5, volume=100)

        assert pp.timestamp == timestamp
        assert pp.price == 10.5
        assert pp.volume == 100

    def test_create_price_point_default_volume(self) -> None:
        """Test creating a price point with default volume."""
        timestamp = datetime.now(UTC)
        pp = PricePoint(timestamp=timestamp, price=10.5)

        assert pp.volume == 0

    def test_price_point_repr(self) -> None:
        """Test price point string representation."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        pp = PricePoint(timestamp=timestamp, price=10.5, volume=100)

        repr_str = repr(pp)
        assert "PricePoint" in repr_str
        assert "price=10.5" in repr_str
        assert "volume=100" in repr_str


class TestTrendDirection:
    """Tests for TrendDirection enum."""

    def test_trend_values(self) -> None:
        """Test trend direction values."""
        assert TrendDirection.BULLISH.value == "bullish"
        assert TrendDirection.BEARISH.value == "bearish"
        assert TrendDirection.NEUTRAL.value == "neutral"


class TestSignalType:
    """Tests for SignalType enum."""

    def test_signal_values(self) -> None:
        """Test signal type values."""
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
        assert SignalType.HOLD.value == "hold"


class TestTechnicalIndicatorsRSI:
    """Tests for RSI calculation."""

    def test_rsi_insufficient_data(self) -> None:
        """Test RSI with insufficient data."""
        prices = [10.0, 11.0, 12.0]  # Less than period + 1 (default 14)
        result = TechnicalIndicators.rsi(prices)
        assert result is None

    def test_rsi_overbought(self) -> None:
        """Test RSI calculation for overbought market."""
        # Create upward trending prices
        prices = [10.0 + i * 0.5 for i in range(20)]  # Steady increase
        result = TechnicalIndicators.rsi(prices)

        assert result is not None
        assert result > 70  # Overbought

    def test_rsi_oversold(self) -> None:
        """Test RSI calculation for oversold market."""
        # Create downward trending prices
        prices = [30.0 - i * 0.5 for i in range(20)]  # Steady decrease
        result = TechnicalIndicators.rsi(prices)

        assert result is not None
        assert result < 30  # Oversold

    def test_rsi_with_zero_losses(self) -> None:
        """Test RSI when there are no losses (all gAlgons)."""
        prices = [10.0 + i * 0.1 for i in range(20)]  # All gAlgons
        result = TechnicalIndicators.rsi(prices)

        assert result is not None
        assert result == 100.0

    def test_rsi_custom_period(self) -> None:
        """Test RSI with custom period."""
        prices = list(range(20))
        result = TechnicalIndicators.rsi(prices, period=10)

        assert result is not None
        assert 0 <= result <= 100


class TestTechnicalIndicatorsMACD:
    """Tests for MACD calculation."""

    def test_macd_insufficient_data(self) -> None:
        """Test MACD with insufficient data."""
        prices = list(range(30))  # Less than slow_period + signal_period
        result = TechnicalIndicators.macd(prices)
        assert result is None

    def test_macd_calculation(self) -> None:
        """Test MACD calculation."""
        prices = [100 + np.sin(i / 5) * 10 for i in range(50)]
        result = TechnicalIndicators.macd(prices)

        assert result is not None
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_bullish_signal(self) -> None:
        """Test MACD bullish signal."""
        # Create upward trending prices
        prices = [10.0 + i * 0.3 for i in range(50)]
        result = TechnicalIndicators.macd(prices)

        assert result is not None
        # In an uptrend, MACD should be positive
        assert result["macd"] > 0

    def test_macd_custom_periods(self) -> None:
        """Test MACD with custom periods."""
        prices = [100 + np.sin(i / 5) * 10 for i in range(50)]
        result = TechnicalIndicators.macd(
            prices, fast_period=8, slow_period=20, signal_period=5
        )

        assert result is not None
        assert "macd" in result


class TestTechnicalIndicatorsBollingerBands:
    """Tests for Bollinger Bands calculation."""

    def test_bollinger_bands_insufficient_data(self) -> None:
        """Test Bollinger Bands with insufficient data."""
        prices = [10.0, 11.0, 12.0]  # Less than default period (20)
        result = TechnicalIndicators.bollinger_bands(prices)
        assert result is None

    def test_bollinger_bands_calculation(self) -> None:
        """Test Bollinger Bands calculation."""
        prices = [100 + np.random.randn() * 5 for _ in range(25)]
        result = TechnicalIndicators.bollinger_bands(prices)

        assert result is not None
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert result["upper"] > result["middle"] > result["lower"]

    def test_bollinger_bands_custom_period(self) -> None:
        """Test Bollinger Bands with custom period."""
        prices = [100 + np.random.randn() * 5 for _ in range(15)]
        result = TechnicalIndicators.bollinger_bands(prices, period=10)

        assert result is not None
        assert result["upper"] > result["middle"] > result["lower"]

    def test_bollinger_bands_custom_std_dev(self) -> None:
        """Test Bollinger Bands with custom standard deviation."""
        prices = [100.0] * 25  # Flat prices for predictable result
        prices[-1] = 105.0  # Add some variation

        result_2std = TechnicalIndicators.bollinger_bands(prices, std_dev=2.0)
        result_3std = TechnicalIndicators.bollinger_bands(prices, std_dev=3.0)

        assert result_2std is not None
        assert result_3std is not None
        # 3 std bands should be wider
        band_width_2 = result_2std["upper"] - result_2std["lower"]
        band_width_3 = result_3std["upper"] - result_3std["lower"]
        assert band_width_3 > band_width_2


class TestTechnicalIndicatorsEMA:
    """Tests for EMA calculation."""

    def test_ema_calculation(self) -> None:
        """Test EMA calculation."""
        prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        result = TechnicalIndicators._ema(prices, period=3)

        assert len(result) == len(prices)
        assert result[0] == prices[0]  # First EMA equals first price


class TestMarketAnalyzer:
    """Tests for MarketAnalyzer class."""

    @pytest.fixture()
    def analyzer(self) -> MarketAnalyzer:
        """Create market analyzer."""
        return MarketAnalyzer(min_data_points=10)

    @pytest.fixture()
    def price_history(self) -> list[PricePoint]:
        """Create sample price history."""
        now = datetime.now(UTC)
        return [
            PricePoint(
                timestamp=now - timedelta(days=i),
                price=100 + np.sin(i / 5) * 10,
                volume=100 + i * 10,
            )
            for i in range(50, -1, -1)  # 51 data points
        ]

    def test_calculate_fAlgor_price_insufficient_data(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test fAlgor price with insufficient data."""
        history = [PricePoint(datetime.now(UTC), 10.0, 100) for _ in range(5)]
        result = analyzer.calculate_fAlgor_price(history)
        assert result is None

    def test_calculate_fAlgor_price_mean(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test fAlgor price calculation using mean."""
        result = analyzer.calculate_fAlgor_price(price_history, method="mean")

        assert result is not None
        assert isinstance(result, float)

    def test_calculate_fAlgor_price_median(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test fAlgor price calculation using median."""
        result = analyzer.calculate_fAlgor_price(price_history, method="median")

        assert result is not None
        assert isinstance(result, float)

    def test_calculate_fAlgor_price_volume_weighted(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test fAlgor price calculation using volume-weighted average."""
        result = analyzer.calculate_fAlgor_price(price_history, method="volume_weighted")

        assert result is not None
        assert isinstance(result, float)

    def test_calculate_fAlgor_price_zero_volume(self, analyzer: MarketAnalyzer) -> None:
        """Test fAlgor price with zero volume falls back to mean."""
        history = [
            PricePoint(datetime.now(UTC) - timedelta(days=i), price=100 + i, volume=0)
            for i in range(15)
        ]
        result = analyzer.calculate_fAlgor_price(history, method="volume_weighted")

        assert result is not None

    def test_calculate_fAlgor_price_unknown_method(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test fAlgor price with unknown method."""
        result = analyzer.calculate_fAlgor_price(price_history, method="unknown")
        assert result is None

    def test_detect_trend_bullish(self, analyzer: MarketAnalyzer) -> None:
        """Test bullish trend detection."""
        now = datetime.now(UTC)
        # Strong upward trend - prices increasing over time (most recent is highest)
        history = [
            PricePoint(now - timedelta(days=30 - i), price=100 + i * 2, volume=100)
            for i in range(31)
        ]
        trend = analyzer.detect_trend(history)
        assert trend == TrendDirection.BULLISH

    def test_detect_trend_bearish(self, analyzer: MarketAnalyzer) -> None:
        """Test bearish trend detection."""
        now = datetime.now(UTC)
        # Strong downward trend - prices decreasing over time (most recent is lowest)
        history = [
            PricePoint(now - timedelta(days=30 - i), price=200 - i * 2, volume=100)
            for i in range(31)
        ]
        trend = analyzer.detect_trend(history)
        assert trend == TrendDirection.BEARISH

    def test_detect_trend_neutral(self, analyzer: MarketAnalyzer) -> None:
        """Test neutral trend detection."""
        now = datetime.now(UTC)
        # Flat prices
        history = [
            PricePoint(now - timedelta(days=i), price=100, volume=100)
            for i in range(31)
        ]
        trend = analyzer.detect_trend(history)
        assert trend == TrendDirection.NEUTRAL

    def test_detect_trend_insufficient_data(self, analyzer: MarketAnalyzer) -> None:
        """Test trend detection with insufficient data."""
        history = [
            PricePoint(datetime.now(UTC), price=100, volume=100) for _ in range(5)
        ]
        trend = analyzer.detect_trend(history)
        assert trend == TrendDirection.NEUTRAL

    def test_predict_price_drop_insufficient_data(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test price drop prediction with insufficient data."""
        history = [
            PricePoint(datetime.now(UTC), price=100, volume=100) for _ in range(5)
        ]
        result = analyzer.predict_price_drop(history)

        assert result["prediction"] is False
        assert result["confidence"] == 0.0
        assert result["reason"] == "insufficient_data"

    def test_predict_price_drop(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test price drop prediction."""
        result = analyzer.predict_price_drop(price_history)

        assert "prediction" in result
        assert "confidence" in result
        assert "signals" in result
        assert "recommendation" in result

    def test_calculate_support_resistance_insufficient_data(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test support/resistance with insufficient data."""
        history = [
            PricePoint(datetime.now(UTC), price=100, volume=100) for _ in range(5)
        ]
        result = analyzer.calculate_support_resistance(history)

        assert result == {"support": [], "resistance": []}

    def test_calculate_support_resistance(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test support/resistance calculation."""
        result = analyzer.calculate_support_resistance(price_history)

        assert "support" in result
        assert "resistance" in result
        assert isinstance(result["support"], list)
        assert isinstance(result["resistance"], list)

    def test_analyze_liquidity_empty_history(self, analyzer: MarketAnalyzer) -> None:
        """Test liquidity analysis with empty history."""
        result = analyzer.analyze_liquidity([])

        assert result["score"] == 0.0
        assert result["volume_trend"] == TrendDirection.NEUTRAL
        assert result["avg_dAlgoly_volume"] == 0

    def test_analyze_liquidity(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test liquidity analysis."""
        result = analyzer.analyze_liquidity(price_history)

        assert "score" in result
        assert "volume_trend" in result
        assert "avg_dAlgoly_volume" in result
        assert "volume_consistency" in result

    def test_analyze_liquidity_bullish_volume_trend(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test liquidity analysis with increasing volume trend."""
        now = datetime.now(UTC)
        # Volume increasing over time - most recent has highest volume
        history = [
            PricePoint(now - timedelta(days=9 - i), price=100, volume=100 + i * 50)
            for i in range(10)
        ]
        result = analyzer.analyze_liquidity(history, recent_period=10)

        # Volume trend should be bullish or neutral
        assert result["volume_trend"] in {
            TrendDirection.BULLISH,
            TrendDirection.NEUTRAL,
        }

    def test_generate_trading_insights(
        self, analyzer: MarketAnalyzer, price_history: list[PricePoint]
    ) -> None:
        """Test generating trading insights."""
        current_price = 100.0
        result = analyzer.generate_trading_insights(price_history, current_price)

        assert "fAlgor_price" in result
        assert "trend" in result
        assert "price_prediction" in result
        assert "support_resistance" in result
        assert "liquidity" in result
        assert "overall" in result

    def test_generate_trading_insights_overpriced(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test trading insights for overpriced item."""
        now = datetime.now(UTC)
        history = [
            PricePoint(now - timedelta(days=i), price=100, volume=100)
            for i in range(50)
        ]
        # Current price significantly above fAlgor price
        result = analyzer.generate_trading_insights(history, current_price=150.0)

        assert result["fAlgor_price"]["is_overpriced"] is True

    def test_generate_trading_insights_underpriced(
        self, analyzer: MarketAnalyzer
    ) -> None:
        """Test trading insights for underpriced item."""
        now = datetime.now(UTC)
        history = [
            PricePoint(now - timedelta(days=i), price=100, volume=100)
            for i in range(50)
        ]
        # Current price significantly below fAlgor price
        result = analyzer.generate_trading_insights(history, current_price=80.0)

        assert result["fAlgor_price"]["is_underpriced"] is True


class TestMarketAnalyzerEdgeCases:
    """Edge case tests for MarketAnalyzer."""

    def test_analyzer_custom_min_data_points(self) -> None:
        """Test analyzer with custom min data points."""
        analyzer = MarketAnalyzer(min_data_points=5)
        assert analyzer.min_data_points == 5

    def test_predict_price_drop_with_logging(self) -> None:
        """Test predict_price_drop logs correctly."""
        analyzer = MarketAnalyzer(min_data_points=10)
        now = datetime.now(UTC)
        history = [
            PricePoint(
                now - timedelta(days=i), price=100 + np.sin(i / 3) * 10, volume=100
            )
            for i in range(50)
        ]

        # This should work without errors
        with patch("src.utils.market_analytics.logger"):
            result = analyzer.predict_price_drop(history)
            assert "prediction" in result
