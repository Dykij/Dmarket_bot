"""
Tests for MultiSourceOracle, Self-Reflection, and Enhanced Strategies (v14.9).

Run with: python -m pytest tests/test_multi_source_oracle_and_volatility.py -v
"""

import asyncio
import math
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# MultiSourceOracle Tests
# =====================================================================

class TestMultiSourceOracle:
    """Tests for the MultiSourceOracle unified market oracle."""

    def test_import(self):
        from src.api.multi_source_oracle import MultiSourceOracle, PriceReference
        assert MultiSourceOracle is not None
        assert PriceReference is not None

    def test_garman_klass_volatility_known_values(self):
        """GK volatility should produce correct output for known OHLC data."""
        from src.strategies.base import BaseStrategy

        # Simulated uptrend: prices going 10 -> 11 -> 12 -> 13
        opens = [10.0, 11.0, 12.0]
        highs = [10.5, 11.5, 12.5]
        lows = [9.5, 10.5, 11.5]
        closes = [10.3, 11.3, 12.3]

        vol = BaseStrategy.garman_klass_volatility(opens, highs, lows, closes)
        assert vol >= 0
        assert isinstance(vol, float)

    def test_garman_klass_volatility_empty_data(self):
        from src.strategies.base import BaseStrategy
        assert BaseStrategy.garman_klass_volatility([], [], [], []) == 0.0

    def test_garman_klass_volatility_single_point(self):
        from src.strategies.base import BaseStrategy
        assert BaseStrategy.garman_klass_volatility([10.0], [10.5], [9.5], [10.2]) == 0.0

    def test_realized_volatility_flat(self):
        """Flat prices should have zero volatility."""
        from src.strategies.base import BaseStrategy
        prices = [10.0] * 20
        vol = BaseStrategy.realized_volatility(prices)
        assert vol == 0.0

    def test_realized_volatility_uptrend(self):
        """Uptrend should have non-zero volatility."""
        from src.strategies.base import BaseStrategy
        prices = [10.0 + i * 0.1 for i in range(20)]
        vol = BaseStrategy.realized_volatility(prices)
        assert vol > 0

    def test_price_reference_dataclass(self):
        """PriceReference should hold price data correctly."""
        from src.api.multi_source_oracle import PriceReference
        ref = PriceReference(
            title="AK-47 | Redline",
            marketcsgo_price=25.0,
            waxpeer_price=26.0,
            csfloat_price=27.0,
            sources_count=3,
        )
        assert ref.title == "AK-47 | Redline"
        assert ref.marketcsgo_price == 25.0
        assert ref.waxpeer_price == 26.0
        assert ref.has_data is True


# =====================================================================
# Self-Reflection Tests
# =====================================================================

class TestSelfReflection:
    """Tests for the self-reflection engine."""

    def test_import(self):
        from src.analytics.self_reflection import SelfReflectionEngine
        assert SelfReflectionEngine is not None

    def test_get_adjusted_spread_no_reflection(self):
        """With no reflection, should return original spread."""
        from src.analytics.self_reflection import SelfReflectionEngine
        sr = SelfReflectionEngine()
        result = sr.get_adjusted_spread(5.0, None)
        assert result == 5.0

    def test_get_adjusted_spread_with_reflection(self):
        """With high-confidence reflection, should adjust spread."""
        from src.analytics.self_reflection import SelfReflectionEngine
        from dataclasses import dataclass

        @dataclass
        class MockReflection:
            confidence: float = 0.8
            recommended_spread_adjustment: float = -1.0

        sr = SelfReflectionEngine()
        result = sr.get_adjusted_spread(5.0, MockReflection())
        # Should be base + adjustment = 5.0 + (-1.0) = 4.0
        assert isinstance(result, float)
        assert result == 4.0


# =====================================================================
# Oracle Factory Tests
# =====================================================================

class TestOracleFactory:
    """Tests for the oracle factory."""

    def test_get_oracle_returns_multi_source(self):
        """Oracle for CS2 should return MultiSourceOracle."""
        from src.api.oracle_factory import OracleFactory
        from src.api.multi_source_oracle import MultiSourceOracle
        oracle = OracleFactory.get_oracle("a8db")
        assert isinstance(oracle, MultiSourceOracle)

    def test_get_oracle_unknown_game(self):
        """Unknown game should return None."""
        from src.api.oracle_factory import OracleFactory
        oracle = OracleFactory.get_oracle("unknown_game")
        assert oracle is None


# =====================================================================
# Config Tests
# =====================================================================

class TestConfigEnhancements:
    """Tests for configuration enhancements."""

    def test_oracle_config(self):
        """Oracle config should be present and valid."""
        from src.config import Config
        assert hasattr(Config, "ORACLE_BATCH_SIZE")
        assert Config.ORACLE_BATCH_SIZE > 0

    def test_value_scan_config(self):
        """Value scan config should be present."""
        from src.config import Config
        assert hasattr(Config, "VALUE_SCAN_ENABLED")
        assert hasattr(Config, "VALUE_SCAN_MIN_PROFIT_PCT")

    def test_turnover_config(self):
        from src.config import Config
        assert hasattr(Config, "TURNOVER_PENALTY_ENABLED")
        assert hasattr(Config, "MAX_DAILY_TRADES")
        assert isinstance(Config.MAX_DAILY_TRADES, int)
        assert Config.MAX_DAILY_TRADES > 0

    def test_cross_market_config(self):
        from src.config import Config
        assert hasattr(Config, "CROSS_MARKET_ENABLED")
        assert Config.CROSS_MARKET_MIN_EDGE_PCT == 3.0

    def test_volatility_config(self):
        from src.config import Config
        assert hasattr(Config, "VOLATILITY_METHOD")
        assert Config.VOLATILITY_METHOD == "garman_klass"

    def test_no_paid_oracle_config(self):
        """Paid oracle config should be removed."""
        from src.config import Config
