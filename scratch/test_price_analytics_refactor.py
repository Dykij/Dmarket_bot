"""Smoke test for refactored price_analytics package — no external deps."""

import sys
import os
import random
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.analytics.price_analytics import (
    PriceAnalytics,
    Signal,
    Trend,
    LiquidityLevel,
    RSIResult,
    MACDResult,
    BollingerBands,
    LiquidityScore,
    TrendAnalysis,
    PriceAnalysis,
    create_price_analytics,
)
from src.analytics.price_analytics import enums, models, indicators, liquidity, trends, core


def test_imports():
    """All public symbols importable from the facade."""
    assert PriceAnalytics is core.PriceAnalytics
    assert Signal is enums.Signal
    assert Trend is enums.Trend
    assert LiquidityLevel is enums.LiquidityLevel
    assert RSIResult is models.RSIResult
    assert MACDResult is models.MACDResult
    assert BollingerBands is models.BollingerBands
    assert LiquidityScore is models.LiquidityScore
    assert TrendAnalysis is models.TrendAnalysis
    assert PriceAnalysis is models.PriceAnalysis
    print("[OK] all imports work")


def test_mixin_composition():
    """PriceAnalytics inherits from all three mixins."""
    a = PriceAnalytics()
    assert hasattr(a, "calculate_sma")
    assert hasattr(a, "calculate_ema")
    assert hasattr(a, "calculate_rsi")
    assert hasattr(a, "calculate_macd")
    assert hasattr(a, "calculate_bollinger_bands")
    assert hasattr(a, "calculate_liquidity")
    assert hasattr(a, "analyze_trend")
    assert hasattr(a, "_calculate_overall_signal")
    print("[OK] mixin composition works")


def test_full_pipeline():
    """Run the full analysis pipeline with random data."""
    random.seed(42)
    prices = [10 + random.gauss(0, 0.5) for _ in range(60)]

    a = PriceAnalytics()
    analysis = a.analyze_item(
        item_name="AK-47 | Redline (FT)",
        price_history=prices,
        current_price=Decimal("10.50"),
        listings_count=30,
        min_listing_price=Decimal("9.00"),
        max_listing_price=Decimal("12.00"),
    )

    # Verify the structure
    assert analysis.item_name == "AK-47 | Redline (FT)"
    assert analysis.current_price == Decimal("10.50")
    assert analysis.rsi is not None
    assert 0 <= analysis.rsi.value <= 100
    assert analysis.macd is not None
    assert analysis.bollinger is not None
    assert analysis.bollinger.upper > analysis.bollinger.middle > analysis.bollinger.lower
    assert analysis.sma_20 is not None
    assert analysis.sma_50 is not None
    assert analysis.ema_12 is not None
    assert analysis.ema_26 is not None
    assert analysis.trend is not None
    assert analysis.trend.trend in Trend
    assert analysis.liquidity is not None
    assert 0 <= analysis.liquidity.score <= 100
    assert analysis.liquidity.level in LiquidityLevel
    assert analysis.overall_signal in Signal
    assert 0 <= analysis.confidence <= 100
    print(f"[OK] full pipeline: {analysis.overall_signal.value} (conf={analysis.confidence})")


def test_to_dict():
    """to_dict works on full analysis."""
    random.seed(7)
    prices = [10 + random.gauss(0, 0.5) for _ in range(60)]
    a = PriceAnalytics()
    analysis = a.analyze_item("Item", prices, Decimal("10"))
    d = analysis.to_dict()
    assert d["item_name"] == "Item"
    assert d["current_price"] == "10"
    assert d["rsi"] is not None
    assert "value" in d["rsi"]
    assert "signal" in d["rsi"]
    assert d["overall_signal"] in [s.value for s in Signal]
    print("[OK] to_dict works")


def test_liquidity_levels():
    """All five liquidity levels are reachable."""
    a = PriceAnalytics()
    cases = [
        (150, LiquidityLevel.VERY_HIGH),
        (75, LiquidityLevel.HIGH),
        (35, LiquidityLevel.MEDIUM),
        (10, LiquidityLevel.LOW),
        (2, LiquidityLevel.VERY_LOW),
    ]
    for count, expected in cases:
        s = a.calculate_liquidity(count, Decimal("9"), Decimal("11"), Decimal("10"))
        assert s.level == expected, f"{count} -> {s.level}, expected {expected}"
    print("[OK] all 5 liquidity levels reachable")


def test_rsi_extremes():
    """RSI returns overbought/oversold signals at extremes."""
    a = PriceAnalytics()
    # Monotonically increasing prices -> RSI near 100
    up_prices = [10 + i * 0.1 for i in range(50)]
    rsi = a.calculate_rsi(up_prices)
    assert rsi.is_overbought
    assert rsi.signal in {Signal.SELL, Signal.STRONG_SELL}

    # Monotonically decreasing prices -> RSI near 0
    dn_prices = [20 - i * 0.1 for i in range(50)]
    rsi = a.calculate_rsi(dn_prices)
    assert rsi.is_oversold
    assert rsi.signal in {Signal.BUY, Signal.STRONG_BUY}
    print("[OK] RSI extremes correct")


def test_bollinger_position():
    """Bollinger position is in [0, 1]."""
    a = PriceAnalytics()
    random.seed(1)
    prices = [10 + random.gauss(0, 0.5) for _ in range(30)]
    bb = a.calculate_bollinger_bands(prices)
    assert 0 <= bb.position <= 1
    assert bb.signal in Signal
    print(f"[OK] Bollinger position={bb.position} signal={bb.signal.value}")


def test_factory():
    """create_price_analytics factory works."""
    a = create_price_analytics(rsi_period=21, macd_fast=8, macd_slow=21)
    assert a.rsi_period == 21
    assert a.macd_fast == 8
    assert a.macd_slow == 21
    print("[OK] factory works")


def test_trend_analysis():
    """Trend analysis returns proper Trend enum."""
    a = PriceAnalytics()
    random.seed(99)
    prices = [10 + random.gauss(0, 0.2) for _ in range(30)]
    t = a.analyze_trend(prices)
    assert t is not None
    assert t.trend in Trend
    assert 0 <= t.strength <= 100
    assert t.predicted_direction in {"up", "down", "sideways"}
    assert t.support_level <= t.resistance_level
    print(f"[OK] trend: {t.trend.value} dir={t.predicted_direction}")


if __name__ == "__main__":
    test_imports()
    test_mixin_composition()
    test_full_pipeline()
    test_to_dict()
    test_liquidity_levels()
    test_rsi_extremes()
    test_bollinger_position()
    test_factory()
    test_trend_analysis()
    print("\n[ALL PASS] price_analytics refactor: 9/9 smoke tests passed")
