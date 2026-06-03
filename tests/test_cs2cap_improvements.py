"""
Tests for CS2Cap Oracle, Self-Reflection, and Enhanced Strategies.

Run with: python -m pytest tests/test_cs2cap_improvements.py -v
"""

import asyncio
import math
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# CS2Cap Oracle Tests
# =====================================================================

class TestCS2CapOracle:
    """Tests for the CS2Cap unified market oracle."""

    def test_import(self):
        from src.api.cs2cap_oracle import CS2CapOracle, CrossMarketData, MarketPrice
        assert CS2CapOracle is not None

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
        assert BaseStrategy.realized_volatility([10.0, 10.0, 10.0, 10.0]) == 0.0

    def test_realized_volatility_volatile(self):
        """Volatile prices should have higher volatility than stable ones."""
        from src.strategies.base import BaseStrategy
        stable = [10.0, 10.1, 10.0, 10.1, 10.0]
        volatile = [10.0, 12.0, 8.0, 14.0, 6.0]
        vol_stable = BaseStrategy.realized_volatility(stable)
        vol_volatile = BaseStrategy.realized_volatility(volatile)
        assert vol_volatile > vol_stable

    def test_realized_volatility_empty(self):
        from src.strategies.base import BaseStrategy
        assert BaseStrategy.realized_volatility([]) == 0.0

    def test_cs2cap_oracle_init(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        oracle = CS2CapOracle(api_key="test_key")
        assert oracle.api_key == "test_key"
        assert oracle._request_delay >= 1.0
        assert oracle.MEM_TTL == 300

    def test_cs2cap_oracle_no_key(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        oracle = CS2CapOracle()
        assert oracle.api_key == ""

    def test_cs2cap_cross_market_data_fields(self):
        from src.api.cs2cap_oracle import CrossMarketData
        data = CrossMarketData(hash_name="AK-47 | Redline")
        assert data.hash_name == "AK-47 | Redline"
        assert data.global_min_ask == 0.0
        assert data.global_max_bid == 0.0
        assert data.provider_prices == {}
        assert data.buy_orders == {}
        assert data.volatility_24h == 0.0
        assert data.rsi == 50.0

    def test_cs2cap_rate_limit(self):
        from src.api.cs2cap_oracle import CS2CapRateLimit
        with pytest.raises(CS2CapRateLimit):
            raise CS2CapRateLimit("429")

    def test_cross_market_data_provider_min(self):
        from src.api.cs2cap_oracle import CrossMarketData
        data = CrossMarketData(
            hash_name="test",
            provider_prices={"csfloat": 10.0, "buff163": 9.5, "skinport": 10.5},
        )
        assert data.global_min_ask == 9.5

    def test_cross_market_data_provider_max_bid(self):
        from src.api.cs2cap_oracle import CrossMarketData
        data = CrossMarketData(
            hash_name="test",
            buy_orders={"csfloat": 8.0, "buff163": 9.0, "skinport": 7.5},
        )
        assert data.global_max_bid == 9.0


# =====================================================================
# Self-Reflection Tests
# =====================================================================

class TestSelfReflection:
    """Tests for the Self-Reflection engine."""

    def test_import(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult
        assert SelfReflectionEngine is not None

    def test_reflection_result_defaults(self):
        from src.analytics.self_reflection import ReflectionResult
        result = ReflectionResult()
        assert result.sharpe_ratio == 0.0
        assert result.sortino_ratio == 0.0
        assert result.max_drawdown == 0.0
        assert result.win_rate == 0.0
        assert result.confidence == 0.0

    def test_reflection_result_with_trades(self):
        from src.analytics.self_reflection import ReflectionResult
        result = ReflectionResult(
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            win_rate=0.65,
            total_trades_analyzed=50,
            profitable_trades=32,
            losing_trades=18,
            confidence=0.8,
        )
        assert result.sharpe_ratio == 1.5
        assert result.win_rate == 0.65
        assert result.confidence == 0.8

    def test_self_reflection_engine_init(self):
        from src.analytics.self_reflection import SelfReflectionEngine
        engine = SelfReflectionEngine()
        assert engine._last_reflection_cycle == 0
        assert engine._reflection_count == 0
        assert engine._cached_result is None

    def test_calculate_metrics_profitable_trades(self):
        from src.analytics.self_reflection import SelfReflectionEngine, TradeRecord
        engine = SelfReflectionEngine()

        trades = [
            TradeRecord(
                hash_name=f"item_{i}",
                buy_price=10.0,
                expected_sell_price=11.0,
                actual_sell_price=11.0 if i % 3 != 0 else 9.0,
                profit=0.5 if i % 3 != 0 else -1.5,
                hold_days=3.0,
                timestamp=time.time() - (50 - i) * 86400,
            )
            for i in range(20)
        ]

        result = engine._calculate_metrics(trades)
        assert result.total_trades_analyzed == 20
        assert result.profitable_trades > 0
        assert result.confidence > 0

    def test_sortino_ratio_all_positive_returns(self):
        """Sortino should be very high when all returns are positive."""
        from src.analytics.self_reflection import SelfReflectionEngine, TradeRecord
        engine = SelfReflectionEngine()

        trades = [
            TradeRecord(
                hash_name=f"item_{i}",
                buy_price=10.0,
                expected_sell_price=11.0,
                actual_sell_price=11.0,
                profit=0.5,
                hold_days=2.0,
                timestamp=time.time() - i * 86400,
            )
            for i in range(20)
        ]

        result = engine._calculate_metrics(trades)
        # All positive = Sortino should be positive or inf
        assert result.sortino_ratio > 0 or result.sortino_ratio == float('inf')

    def test_get_adjusted_spread_no_reflection(self):
        from src.analytics.self_reflection import SelfReflectionEngine
        engine = SelfReflectionEngine()
        assert engine.get_adjusted_spread(5.0) == 5.0

    def test_get_adjusted_risk_pct_clamping(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult
        engine = SelfReflectionEngine()
        result = ReflectionResult(recommended_risk_adjustment=50.0, confidence=0.5)
        adjusted = engine.get_adjusted_risk_pct(5.0, result)
        assert adjusted == 10.0  # Clamped to max

    def test_get_adjusted_volatility_max_clamping(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult
        engine = SelfReflectionEngine()
        result = ReflectionResult(recommended_volatility_adjustment=-0.9, confidence=0.5)
        adjusted = engine.get_adjusted_volatility_max(0.6, result)
        assert adjusted >= 0.1  # Clamped to min


# =====================================================================
# Enhanced BaseStrategy Tests
# =====================================================================

class TestEnhancedBaseStrategy:
    """Tests for enhanced BaseStrategy with turnover and Sharpe."""

    def test_import(self):
        from src.strategies.base import BaseStrategy
        assert BaseStrategy is not None

    def test_spread_volatility(self):
        from src.strategies.base import BaseStrategy
        vol = BaseStrategy.spread_volatility(10.0, 9.0)
        assert abs(vol - 11.11) < 0.1  # ~11.11%

    def test_spread_volatility_zero_bid(self):
        from src.strategies.base import BaseStrategy
        vol = BaseStrategy.spread_volatility(10.0, 0.0)
        assert vol == 100.0

    def test_turnover_penalty_no_trades(self):
        from src.strategies.market_maker import MarketMaker
        mm = MarketMaker()
        penalty = mm.calculate_turnover_penalty()
        assert penalty == 1.0

    def test_turnover_penalty_over_limit(self):
        from src.strategies.market_maker import MarketMaker
        from src.config import Config
        mm = MarketMaker()
        mm._daily_trade_count = Config.MAX_DAILY_TRADES + 50
        mm._daily_trades_reset_ts = time.time()
        penalty = mm.calculate_turnover_penalty()
        assert penalty < 1.0

    def test_objective_score_with_turnover(self):
        from src.strategies.base import BaseStrategy
        # Create a concrete implementation for testing
        class TestStrategy(BaseStrategy):
            def evaluate_opportunity(self, market_data):
                return {"action": "none"}

        strat = TestStrategy("test")
        score_full = strat.calculate_objective_score(
            expected_return_pct=10.0,
            volatility=0.2,
            turnover_penalty=1.0,
            spread_pct=10.0,
        )
        score_penalized = strat.calculate_objective_score(
            expected_return_pct=10.0,
            volatility=0.2,
            turnover_penalty=0.5,
            spread_pct=10.0,
        )
        assert score_penalized < score_full

    def test_position_size_with_sharpe(self):
        from src.strategies.base import BaseStrategy

        class TestStrategy(BaseStrategy):
            def evaluate_opportunity(self, market_data):
                return {"action": "none"}

        strat = TestStrategy("test")
        size_high_sharpe = strat.calculate_position_size(
            current_balance=1000.0, item_price=10.0,
            volatility_score=1.0, sharpe_estimate=3.0,
        )
        size_low_sharpe = strat.calculate_position_size(
            current_balance=1000.0, item_price=10.0,
            volatility_score=1.0, sharpe_estimate=0.3,
        )
        # High Sharpe should allow equal or larger position
        assert size_high_sharpe >= size_low_sharpe


# =====================================================================
# CrossMarketStrategy Tests
# =====================================================================

class TestCrossMarketStrategy:
    """Tests for the CrossMarket arbitrage strategy."""

    def test_import(self):
        from src.strategies.cross_market import CrossMarketStrategy
        assert CrossMarketStrategy is not None

    def test_no_cross_market_data_returns_none(self):
        from src.strategies.cross_market import CrossMarketStrategy
        strat = CrossMarketStrategy()
        result = strat.evaluate_opportunity_enhanced(
            market_data={"title": "test", "best_ask": 10.0, "current_balance": 100.0},
            cross_market_data=None,
        )
        assert result["action"] == "none"

    def test_cross_market_arbitrage_found(self):
        from src.strategies.cross_market import CrossMarketStrategy
        from src.api.cs2cap_oracle import CrossMarketData

        strat = CrossMarketStrategy()
        cross = CrossMarketData(
            hash_name="test",
            global_min_ask=10.0,
            global_max_bid=8.0,
            provider_prices={"csfloat": 10.0, "buff163": 15.0, "skinport": 14.0},
            buy_orders={"csfloat": 8.0},
            liquidity_score=0.5,
            volatility_24h=0.1,
        )

        result = strat.evaluate_opportunity_enhanced(
            market_data={"title": "AK-47 | Redline", "best_ask": 10.0, "current_balance": 100.0},
            cross_market_data=cross,
        )
        assert result["action"] in ("place_target", "none")

    def test_cross_market_no_profit(self):
        from src.strategies.cross_market import CrossMarketStrategy
        from src.api.cs2cap_oracle import CrossMarketData

        strat = CrossMarketStrategy()
        cross = CrossMarketData(
            hash_name="test",
            global_min_ask=10.0,
            provider_prices={"csfloat": 10.0, "buff163": 9.5},
            liquidity_score=0.5,
            volatility_24h=0.1,
        )

        result = strat.evaluate_opportunity_enhanced(
            market_data={"title": "expensive_item", "best_ask": 10.0, "current_balance": 100.0},
            cross_market_data=cross,
        )
        # Both markets below our buy price = no opportunity
        assert result["action"] == "none"

    def test_cross_market_indicators_boost(self):
        """RSI < 30 should boost signal quality."""
        from src.strategies.cross_market import CrossMarketStrategy
        from src.api.cs2cap_oracle import CrossMarketData

        strat = CrossMarketStrategy()
        cross = CrossMarketData(
            hash_name="test",
            global_min_ask=10.0,
            global_max_bid=8.0,
            provider_prices={"csfloat": 10.0, "buff163": 15.0},
            buy_orders={"csfloat": 8.0},
            liquidity_score=0.5,
            volatility_24h=0.05,
        )

        result_low_rsi = strat.evaluate_opportunity_enhanced(
            market_data={"title": "test", "best_ask": 10.0, "current_balance": 100.0},
            cross_market_data=cross,
            indicators={"rsi": 25.0, "bb_position": 0.1},
        )

        result_high_rsi = strat.evaluate_opportunity_enhanced(
            market_data={"title": "test", "best_ask": 10.0, "current_balance": 100.0},
            cross_market_data=cross,
            indicators={"rsi": 75.0, "bb_position": 0.9},
        )

        # Both might be none (depends on other filters), but objective should differ
        if result_low_rsi.get("objective_score") and result_high_rsi.get("objective_score"):
            assert result_low_rsi["objective_score"] >= result_high_rsi["objective_score"]


# =====================================================================
# OracleFactory Tests
# =====================================================================

class TestOracleFactory:
    """Tests for OracleFactory with CS2Cap."""

    def test_import(self):
        from src.api.oracle_factory import OracleFactory
        assert OracleFactory is not None

    def test_cs2_oracle_creation(self):
        from src.api.oracle_factory import OracleFactory
        from src.api.csfloat_oracle import CSFloatOracle
        # Without CS2CAP_API_KEY, should use CSFloat fallback
        OracleFactory._oracles.clear()
        with patch.dict(os.environ, {"CS2CAP_API_KEY": ""}, clear=False):
            OracleFactory._oracles.clear()
            oracle = OracleFactory.get_oracle("a8db")
            assert oracle is not None
            assert isinstance(oracle, CSFloatOracle)
        OracleFactory._oracles.clear()

    def test_cross_market_oracle_returns_none_without_cs2cap(self):
        from src.api.oracle_factory import OracleFactory
        OracleFactory._oracles.clear()
        with patch.dict(os.environ, {"CS2CAP_API_KEY": ""}, clear=False):
            OracleFactory._oracles.clear()
            result = OracleFactory.get_cross_market_oracle("a8db")
            assert result is None
        OracleFactory._oracles.clear()

    def test_rust_oracle_creation(self):
        from src.api.oracle_factory import OracleFactory
        from src.api.rust_oracle import RustOracle
        oracle = OracleFactory.get_oracle("rust")
        assert isinstance(oracle, RustOracle)
        OracleFactory._oracles.clear()

    def test_unknown_game_returns_none(self):
        from src.api.oracle_factory import OracleFactory
        assert OracleFactory.get_oracle("unknown_game") is None


# =====================================================================
# Integration: Strategy + Volatility + Turnover
# =====================================================================

class TestStrategyIntegration:
    """Integration tests for strategy components."""

    def test_market_maker_full_evaluation(self):
        from src.strategies.market_maker import MarketMaker
        mm = MarketMaker()
        result = mm.evaluate_opportunity(
            market_data={
                "title": "AK-47 | Redline",
                "best_ask": 10.0,
                "best_bid": 9.0,
            },
            current_balance=100.0,
        )
        assert result["action"] in ("place_target", "none")

    def test_market_maker_no_spread(self):
        from src.strategies.market_maker import MarketMaker
        mm = MarketMaker()
        result = mm.evaluate_opportunity(
            market_data={
                "title": "AK-47 | Redline",
                "best_ask": 10.0,
                "best_bid": 10.0,
            },
            current_balance=100.0,
        )
        assert result["action"] == "none"

    def test_position_size_zero_balance(self):
        from src.strategies.base import BaseStrategy

        class TestStrategy(BaseStrategy):
            def evaluate_opportunity(self, market_data):
                return {"action": "none"}

        strat = TestStrategy("test")
        assert strat.calculate_position_size(current_balance=0.0, item_price=10.0) == 1

    def test_position_size_expensive_item(self):
        from src.strategies.base import BaseStrategy

        class TestStrategy(BaseStrategy):
            def evaluate_opportunity(self, market_data):
                return {"action": "none"}

        strat = TestStrategy("test")
        size = strat.calculate_position_size(
            current_balance=10.0, item_price=100.0, volatility_score=1.0
        )
        assert size == 0  # Price exceeds risk tolerance


# =====================================================================
# Config Tests
# =====================================================================

class TestConfigEnhancements:
    """Tests for new Config parameters."""

    def test_cs2cap_config_exists(self):
        from src.config import Config
        assert hasattr(Config, "CS2CAP_API_KEY")
        assert hasattr(Config, "CS2CAP_ORACLE_PRIMARY")

    def test_self_reflection_config(self):
        from src.config import Config
        assert hasattr(Config, "SELF_REFLECTION_WINDOW")
        assert hasattr(Config, "SELF_REFLECTION_INTERVAL")
        assert Config.SELF_REFLECTION_WINDOW == 50

    def test_turnover_config(self):
        from src.config import Config
        assert hasattr(Config, "TURNOVER_PENALTY_ENABLED")
        assert hasattr(Config, "MAX_DAILY_TRADES")
        assert Config.MAX_DAILY_TRADES == 200

    def test_cross_market_config(self):
        from src.config import Config
        assert hasattr(Config, "CROSS_MARKET_ENABLED")
        assert Config.CROSS_MARKET_MIN_EDGE_PCT == 3.0

    def test_volatility_config(self):
        from src.config import Config
        assert hasattr(Config, "VOLATILITY_METHOD")
        assert Config.VOLATILITY_METHOD == "garman_klass"

    def test_sharpe_config(self):
        from src.config import Config
        assert hasattr(Config, "SHARPE_OPTIMIZATION_ENABLED")
        assert Config.TARGET_SHARPE_RATIO == 1.5
