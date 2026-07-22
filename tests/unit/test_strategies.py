"""Unit tests for strategy modules.

Tests: BaseStrategy volatility estimators, CrossMarketStrategy arbitrage detection,
and MarketMaker spread calculation.

Uses mocks for external dependencies (Config, self_reflection, API clients).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from src.strategies.base import BaseStrategy


# =====================================================================
# Helpers
# =====================================================================


class ConcreteStrategy(BaseStrategy):
    """Concrete implementation for testing abstract base."""

    def evaluate_opportunity(self, market_data):
        return {"action": "none"}


# =====================================================================
# BaseStrategy — Garman-Klass Volatility
# =====================================================================


class TestGarmanKlassVolatility:
    """Tests for Garman-Klass volatility estimator."""

    def test_basic_calculation(self) -> None:
        """OHLC data produces positive volatility."""
        vol = BaseStrategy.garman_klass_volatility(
            open_prices=[100.0, 102.0, 101.0],
            high=[105.0, 106.0, 104.0],
            low=[98.0, 99.0, 97.0],
            close=[103.0, 104.0, 102.0],
        )
        assert vol > 0.0

    def test_constant_price_zero_vol(self) -> None:
        """Constant prices → zero volatility."""
        vol = BaseStrategy.garman_klass_volatility(
            open_prices=[100.0, 100.0, 100.0],
            high=[100.0, 100.0, 100.0],
            low=[100.0, 100.0, 100.0],
            close=[100.0, 100.0, 100.0],
        )
        assert vol == pytest.approx(0.0)

    def test_insufficient_data(self) -> None:
        """Less than 2 data points → 0."""
        assert BaseStrategy.garman_klass_volatility([100], [105], [95], [102]) == pytest.approx(0.0)
        assert BaseStrategy.garman_klass_volatility([], [], [], []) == pytest.approx(0.0)

    def test_mismatched_lengths(self) -> None:
        """Mismatched array lengths → 0."""
        assert BaseStrategy.garman_klass_volatility(
            [100, 101], [105], [95], [102]
        ) == pytest.approx(0.0)

    def test_annualized_scaling(self) -> None:
        """Result should be annualized (√252 factor)."""
        vol = BaseStrategy.garman_klass_volatility(
            open_prices=[100.0, 101.0, 102.0, 103.0],
            high=[102.0, 103.0, 104.0, 105.0],
            low=[99.0, 100.0, 101.0, 102.0],
            close=[101.0, 102.0, 103.0, 104.0],
        )
        # Should be > 0 and reasonably scaled
        assert vol > 0.0
        assert vol < 100.0  # sanity check


# =====================================================================
# BaseStrategy — Realized Volatility
# =====================================================================


class TestRealizedVolatility:
    """Tests for realized volatility from close-to-close returns."""

    def test_basic_calculation(self) -> None:
        prices = [100.0, 102.0, 101.0, 105.0, 103.0]
        vol = BaseStrategy.realized_volatility(prices)
        assert vol > 0.0

    def test_single_price(self) -> None:
        assert BaseStrategy.realized_volatility([100.0]) == pytest.approx(0.0)

    def test_empty(self) -> None:
        assert BaseStrategy.realized_volatility([]) == pytest.approx(0.0)

    def test_constant_prices(self) -> None:
        """Constant prices → zero volatility."""
        vol = BaseStrategy.realized_volatility([100.0, 100.0, 100.0, 100.0])
        assert vol == pytest.approx(0.0)


# =====================================================================
# BaseStrategy — Spread Volatility
# =====================================================================


class TestSpreadVolatility:
    """Tests for spread-based volatility proxy."""

    def test_basic_spread(self) -> None:
        vol = BaseStrategy.spread_volatility(best_ask=110.0, best_bid=100.0)
        assert vol == pytest.approx(10.0)

    def test_zero_bid(self) -> None:
        """Zero bid → 100% volatility."""
        assert BaseStrategy.spread_volatility(110.0, 0.0) == pytest.approx(100.0)

    def test_tight_spread(self) -> None:
        vol = BaseStrategy.spread_volatility(100.5, 100.0)
        assert vol == pytest.approx(0.5)


# =====================================================================
# BaseStrategy — ATR
# =====================================================================


class TestATR:
    """Tests for Average True Range estimator."""

    def test_basic_atr(self) -> None:
        high = [110.0, 112.0, 115.0, 113.0, 116.0]
        low = [100.0, 102.0, 105.0, 103.0, 106.0]
        close = [105.0, 108.0, 110.0, 108.0, 112.0]
        atr = BaseStrategy.calculate_atr(high, low, close, period=3)
        assert atr > 0.0

    def test_insufficient_data(self) -> None:
        assert BaseStrategy.calculate_atr([110], [100], [105]) == pytest.approx(0.0)

    def test_atr_position_size(self) -> None:
        """ATR-based sizing returns positive quantity."""
        qty = BaseStrategy.atr_position_size(
            balance=1000.0, atr=2.0, item_price=10.0, risk_per_trade_pct=2.0
        )
        assert qty >= 1

    def test_atr_position_size_zero_atr(self) -> None:
        """Zero ATR → default to 1."""
        assert BaseStrategy.atr_position_size(100.0, 0.0, 10.0) == 1


# =====================================================================
# BaseStrategy — Position Sizing
# =====================================================================


class TestPositionSizing:
    """Tests for dynamic position sizing."""

    def test_basic_position_size(self) -> None:
        strategy = ConcreteStrategy("test")
        qty = strategy.calculate_position_size(
            current_balance=100.0, item_price=10.0, volatility_score=1.0
        )
        assert qty >= 1

    def test_zero_balance(self) -> None:
        strategy = ConcreteStrategy("test")
        qty = strategy.calculate_position_size(
            current_balance=0.0, item_price=10.0
        )
        assert qty == 1  # default

    def test_high_volatility_reduces_size(self) -> None:
        strategy = ConcreteStrategy("test")
        qty_low_vol = strategy.calculate_position_size(
            current_balance=100.0, item_price=5.0, volatility_score=1.0
        )
        qty_high_vol = strategy.calculate_position_size(
            current_balance=100.0, item_price=5.0, volatility_score=5.0
        )
        assert qty_low_vol >= qty_high_vol

    def test_item_exceeds_risk_tolerance(self) -> None:
        strategy = ConcreteStrategy("test")
        qty = strategy.calculate_position_size(
            current_balance=10.0, item_price=100.0, volatility_score=1.0
        )
        assert qty == 0


# =====================================================================
# BaseStrategy — Turnover Penalty
# =====================================================================


class TestTurnoverPenalty:
    """Tests for turnover regularization."""

    @patch("src.strategies.base.Config")
    def test_no_penalty_under_limit(self, mock_config) -> None:
        mock_config.TURNOVER_PENALTY_ENABLED = True
        mock_config.MAX_DAILY_TRADES = 200
        mock_config.TURNOVER_PENALTY_PER_TRADE = 0.002
        strategy = ConcreteStrategy("test")
        penalty = strategy.calculate_turnover_penalty()
        assert penalty == pytest.approx(1.0)

    @patch("src.strategies.base.Config")
    def test_penalty_over_limit(self, mock_config) -> None:
        mock_config.TURNOVER_PENALTY_ENABLED = True
        mock_config.MAX_DAILY_TRADES = 5
        mock_config.TURNOVER_PENALTY_PER_TRADE = 0.1
        strategy = ConcreteStrategy("test")
        strategy._daily_trade_count = 10
        strategy._daily_trades_reset_ts = float("inf")  # prevent reset
        penalty = strategy.calculate_turnover_penalty()
        assert penalty < 1.0
        assert penalty >= 0.1  # floor


# =====================================================================
# CrossMarketStrategy
# =====================================================================


class TestCrossMarketStrategy:
    """Tests for cross-market arbitrage detection."""

    @patch("src.strategies.cross_market.Config")
    def test_detect_opportunity_profitable(self, mock_config) -> None:
        """Profitable cross-market arb should return place_target."""
        mock_config.MIN_PRICE_USD = 0.5
        mock_config.MIN_SPREAD_PCT = 5.0
        mock_config.CROSS_MARKET_DESTINATION_FEE = 0.025
        mock_config.CROSS_MARKET_MAX_SPREAD_PCT = 15.0
        mock_config.SHARPE_OPTIMIZATION_ENABLED = False
        mock_config.USE_DYNAMIC_SIZING = False
        mock_config.MAX_POSITION_RISK_PCT = 15.0

        from src.strategies.cross_market import CrossMarketStrategy

        strategy = CrossMarketStrategy()

        # best_ask in cents (DMarket API format): 1000 cents = $10.00
        # Must be >1000 to trigger /100 conversion in cross_market.py
        market_data = {"title": "AK-47 | Redline", "best_ask": 1001, "current_balance": 50.0}

        # Mock cross-market data
        cross_data = MagicMock()
        cross_data.provider_prices = {"steam": 15.0, "waxpeer": 14.0}
        cross_data.buy_orders = {"csfloat": 12.0}
        cross_data.liquidity_score = 0.5
        cross_data.volatility_24h = 0.1
        cross_data.sales_count = 10
        cross_data.global_max_bid = 14.0
        cross_data.atr = 0.0

        result = strategy.evaluate_opportunity_enhanced(
            market_data, cross_market_data=cross_data
        )
        assert result["action"] == "place_target"
        assert result["net_margin_pct"] > 0

    @patch("src.strategies.cross_market.Config")
    def test_detect_no_opportunity(self, mock_config) -> None:
        """No profitable arb returns action=none."""
        mock_config.MIN_PRICE_USD = 0.5
        mock_config.MIN_SPREAD_PCT = 5.0
        mock_config.CROSS_MARKET_DESTINATION_FEE = 0.025

        from src.strategies.cross_market import CrossMarketStrategy

        strategy = CrossMarketStrategy()
        market_data = {"title": "Cheap Item", "best_ask": 500, "current_balance": 50.0}

        cross_data = MagicMock()
        cross_data.provider_prices = {"steam": 5.0}  # same as DMarket price
        cross_data.buy_orders = {}
        cross_data.liquidity_score = 0.5
        cross_data.volatility_24h = 0.1
        cross_data.sales_count = 5
        cross_data.global_max_bid = 0.0

        result = strategy.evaluate_opportunity_enhanced(
            market_data, cross_market_data=cross_data
        )
        assert result["action"] == "none"

    @patch("src.strategies.cross_market.Config")
    def test_no_cross_data_returns_none(self, mock_config) -> None:
        """No cross-market data → action=none."""
        mock_config.MIN_PRICE_USD = 0.5

        from src.strategies.cross_market import CrossMarketStrategy

        strategy = CrossMarketStrategy()
        result = strategy.evaluate_opportunity_enhanced(
            {"title": "X", "best_ask": 1000}
        )
        assert result["action"] == "none"


# =====================================================================
# MarketMaker
# =====================================================================


class TestMarketMaker:
    """Tests for MarketMaker spread calculation."""

    @patch("src.strategies.base.Config")
    @patch("src.strategies.market_maker.self_reflection")
    @patch("src.strategies.market_maker.Config")
    def test_spread_calculation(self, mock_mm_config, mock_sr, mock_base_config) -> None:
        """MarketMaker should calculate spread and return target price."""
        mock_mm_config.FEE_RATE = 0.01
        mock_mm_config.MIN_SPREAD_PCT = 0.1
        mock_base_config.USE_DYNAMIC_SIZING = False
        mock_base_config.SHARPE_OPTIMIZATION_ENABLED = False
        mock_base_config.MAX_POSITION_RISK_PCT = 15.0
        mock_base_config.TURNOVER_PENALTY_ENABLED = False
        mock_base_config.MIN_SPREAD_PCT = 0.1

        mock_sr._cached_result = None
        mock_sr.get_adjusted_spread.return_value = 0.1
        mock_sr.get_adjusted_risk_pct.return_value = 15.0

        from src.strategies.market_maker import MarketMaker

        strategy = MarketMaker()
        # Wide spread ($10) with low fee (1%) ensures positive net profit
        market_data = {
            "title": "AK-47 | Redline",
            "best_ask": 20.0,
            "best_bid": 10.0,
        }
        result = strategy.evaluate_opportunity(market_data, current_balance=100.0)

        assert result["action"] == "place_target"
        assert result["target_price"] < 20.0  # below ask
        assert result["target_price"] > 10.0  # above bid
        assert result["net_margin_pct"] > 0

    @patch("src.strategies.base.Config")
    @patch("src.strategies.market_maker.self_reflection")
    @patch("src.strategies.market_maker.Config")
    def test_no_spread_returns_none(self, mock_mm_config, mock_sr, mock_base_config) -> None:
        """Zero or negative spread → action=none."""
        mock_mm_config.FEE_RATE = 0.05
        mock_mm_config.MIN_SPREAD_PCT = 5.0
        mock_base_config.USE_DYNAMIC_SIZING = False
        mock_base_config.SHARPE_OPTIMIZATION_ENABLED = False
        mock_base_config.TURNOVER_PENALTY_ENABLED = False

        mock_sr._cached_result = None
        mock_sr.get_adjusted_spread.return_value = 5.0
        mock_sr.get_adjusted_risk_pct.return_value = 15.0

        from src.strategies.market_maker import MarketMaker

        strategy = MarketMaker()
        market_data = {"title": "X", "best_ask": 10.0, "best_bid": 10.0}
        result = strategy.evaluate_opportunity(market_data)
        assert result["action"] == "none"

    @patch("src.strategies.base.Config")
    @patch("src.strategies.market_maker.self_reflection")
    @patch("src.strategies.market_maker.Config")
    def test_negative_spread_returns_none(self, mock_mm_config, mock_sr, mock_base_config) -> None:
        """ask < bid (crossed book) → action=none."""
        mock_mm_config.FEE_RATE = 0.05
        mock_mm_config.MIN_SPREAD_PCT = 5.0
        mock_base_config.TURNOVER_PENALTY_ENABLED = False
        mock_base_config.MAX_DAILY_TRADES = 200

        mock_sr._cached_result = None
        mock_sr.get_adjusted_spread.return_value = 5.0

        from src.strategies.market_maker import MarketMaker

        strategy = MarketMaker()
        market_data = {"title": "X", "best_ask": 9.0, "best_bid": 10.0}
        result = strategy.evaluate_opportunity(market_data)
        assert result["action"] == "none"
