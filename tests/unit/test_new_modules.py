"""
test_new_modules.py — Tests for Walk-Forward, Portfolio Optimizer, ADF, Prometheus.

Covers:
- Walk-Forward Pipeline (window generation, optimization, aggregation)
- Portfolio Optimizer (Markowitz, efficient frontier, rebalancing)
- ADF Cointegration Test (stationarity detection)
- Prometheus Metrics (counter, gauge, histogram, HTTP endpoint)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ═══════════════════════════════════════════════════════════════════
# Walk-Forward Pipeline Tests
# ═══════════════════════════════════════════════════════════════════

class TestWalkForwardPipeline:
    """Tests for walk_forward.py."""

    def test_window_generation(self):
        from src.analytics.backtester.walk_forward import WalkForwardPipeline
        pipeline = WalkForwardPipeline(train_days=90, test_days=30, step_days=30)

        min_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        max_date = datetime(2025, 12, 31, tzinfo=timezone.utc)

        windows = pipeline._generate_windows(min_date, max_date)
        assert len(windows) > 0

        # Each window should have train before test
        for train_start, train_end, test_start, test_end in windows:
            assert train_start < train_end
            assert train_end <= test_start
            assert test_start < test_end

    def test_window_step_size(self):
        from src.analytics.backtester.walk_forward import WalkForwardPipeline
        pipeline = WalkForwardPipeline(train_days=90, test_days=30, step_days=30)

        min_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        max_date = datetime(2025, 12, 31, tzinfo=timezone.utc)

        windows = pipeline._generate_windows(min_date, max_date)

        # Windows should be stepped by step_days
        if len(windows) >= 2:
            step = (windows[1][0] - windows[0][0]).days
            assert step == 30

    def test_expand_grid(self):
        from src.analytics.backtester.walk_forward import WalkForwardPipeline
        pipeline = WalkForwardPipeline()

        grid = {"a": [1, 2], "b": [10, 20]}
        combos = pipeline._expand_grid(grid)
        assert len(combos) == 4
        assert {"a": 1, "b": 10} in combos
        assert {"a": 2, "b": 20} in combos

    def test_expand_grid_empty(self):
        from src.analytics.backtester.walk_forward import WalkForwardPipeline
        pipeline = WalkForwardPipeline()

        combos = pipeline._expand_grid({})
        assert len(combos) == 1
        assert combos[0] == {}

    def test_expand_grid_single_param(self):
        from src.analytics.backtester.walk_forward import WalkForwardPipeline
        pipeline = WalkForwardPipeline()

        grid = {"x": [1, 2, 3]}
        combos = pipeline._expand_grid(grid)
        assert len(combos) == 3


# ═══════════════════════════════════════════════════════════════════
# Portfolio Optimizer Tests
# ═══════════════════════════════════════════════════════════════════

class TestPortfolioOptimizer:
    """Tests for portfolio_optimizer.py."""

    def test_optimize_single_item(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        returns = {"AK-47": [0.01, -0.02, 0.03, 0.01, -0.01]}
        weights = optimizer.optimize(returns)
        assert abs(weights.weights.get("AK-47", 0) - 1.0) < 0.01

    def test_optimize_two_items(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        returns = {
            "AK-47": [0.01, -0.02, 0.03, 0.01, -0.01],
            "Karambit": [0.02, 0.01, -0.01, 0.02, 0.01],
        }
        weights = optimizer.optimize(returns)
        assert len(weights.weights) == 2
        # Weights should sum to ~1.0
        total = sum(weights.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_optimize_empty(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        weights = optimizer.optimize({})
        assert weights.weights == {}

    def test_weights_within_bounds(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer(max_weight=0.40)

        returns = {
            "A": [0.01, -0.02, 0.03, 0.01, -0.01],
            "B": [0.02, 0.01, -0.01, 0.02, 0.01],
            "C": [-0.01, 0.03, 0.01, -0.02, 0.02],
        }
        weights = optimizer.optimize(returns)
        for w in weights.weights.values():
            assert w <= 0.40 + 0.01  # Small tolerance

    def test_efficient_frontier(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        returns = {
            "A": [0.01, -0.02, 0.03, 0.01, -0.01],
            "B": [0.02, 0.01, -0.01, 0.02, 0.01],
        }
        frontier = optimizer.efficient_frontier(returns, n_points=5)
        assert len(frontier.points) == 5
        assert frontier.min_volatility_point is not None
        assert frontier.max_sharpe_point is not None

    def test_should_rebalance_no_drift(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.5, "B": 0.5}
        assert optimizer.should_rebalance(current, target, threshold=0.05) is False

    def test_should_rebalance_with_drift(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        current = {"A": 0.6, "B": 0.4}
        target = {"A": 0.5, "B": 0.5}
        assert optimizer.should_rebalance(current, target, threshold=0.05) is True

    def test_compute_rebalance_trades(self):
        from src.risk.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        current = {"A": 0.6, "B": 0.4}
        target = {"A": 0.5, "B": 0.5}
        trades = optimizer.compute_rebalance_trades(current, target, 100.0)
        assert len(trades) == 2
        # A should be sold, B should be bought
        for trade in trades:
            if trade["item"] == "A":
                assert trade["action"] == "sell"
            elif trade["item"] == "B":
                assert trade["action"] == "buy"


# ═══════════════════════════════════════════════════════════════════
# ADF Cointegration Test Tests
# ═══════════════════════════════════════════════════════════════════

class TestADFCointegration:
    """Tests for ADF cointegration in pair_trading.py."""

    def test_stationary_series_high_score(self):
        from src.analysis.algo_pack.pair_trading import PairTradingEstimator
        pt = PairTradingEstimator.__new__(PairTradingEstimator)

        # Generate stationary (mean-reverting) series
        import random
        random.seed(42)
        spread = [0.0]
        for i in range(100):
            spread.append(spread[-1] * 0.8 + random.gauss(0, 0.1))

        score = pt._cointegration_test(spread)
        assert score > 0.3  # Should detect some stationarity

    def test_random_walk_low_score(self):
        from src.analysis.algo_pack.pair_trading import PairTradingEstimator
        pt = PairTradingEstimator.__new__(PairTradingEstimator)

        # Generate random walk (non-stationary)
        import random
        random.seed(42)
        spread = [0.0]
        for i in range(100):
            spread.append(spread[-1] + random.gauss(0, 0.1))

        score = pt._cointegration_test(spread)
        assert score < 0.5  # Should detect non-stationarity

    def test_short_series_returns_zero(self):
        from src.analysis.algo_pack.pair_trading import PairTradingEstimator
        pt = PairTradingEstimator.__new__(PairTradingEstimator)

        score = pt._cointegration_test([1.0, 2.0, 3.0])
        assert score == 0.0

    def test_constant_series(self):
        from src.analysis.algo_pack.pair_trading import PairTradingEstimator
        pt = PairTradingEstimator.__new__(PairTradingEstimator)

        # Constant series is stationary
        spread = [5.0] * 50
        score = pt._cointegration_test(spread)
        # Should return some score (not crash)
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════
# Prometheus Metrics Tests
# ═══════════════════════════════════════════════════════════════════

class TestPrometheusMetrics:
    """Tests for prometheus_metrics.py."""

    def test_record_trade(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.record_trade("buy", "AK-47 | Redline", 15.50, success=True)
        output = metrics._render_metrics()
        assert "dmarket_trades_total" in output
        assert "dmarket_trade_price_usd" in output

    def test_record_api_call(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.record_api_call("dmarket", "GET", 200, 0.35)
        output = metrics._render_metrics()
        assert "dmarket_api_calls_total" in output
        assert "dmarket_api_duration_seconds" in output

    def test_update_balance(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.update_balance(available=150.0, reserved=25.0)
        output = metrics._render_metrics()
        assert "dmarket_balance_available_usd" in output
        assert "dmarket_balance_total_usd" in output

    def test_update_drawdown(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.update_drawdown(current_pct=5.0, peak_usd=200.0)
        output = metrics._render_metrics()
        assert "dmarket_drawdown_current_pct" in output

    def test_update_inventory(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.update_inventory(total_items=15, total_value_usd=150.0, locked_value_usd=50.0)
        output = metrics._render_metrics()
        assert "dmarket_inventory_total_items" in output

    def test_update_circuit_breaker(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.update_circuit_breaker("dmarket_api", "CLOSED", 0)
        output = metrics._render_metrics()
        assert "dmarket_circuit_breaker_state" in output

    def test_update_risk_metrics(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.update_risk_metrics(
            win_rate=0.65, sharpe_ratio=1.5, kelly_fraction=0.12, consecutive_losses=0
        )
        output = metrics._render_metrics()
        assert "dmarket_risk_win_rate" in output
        assert "dmarket_risk_sharpe_ratio" in output

    def test_format_labels(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        labels = metrics._format_labels({"type": "buy", "item": "AK-47"})
        assert 'type="buy"' in labels
        assert 'item="AK-47"' in labels

    def test_render_metrics_format(self):
        from src.monitoring.prometheus_metrics import PrometheusMetrics
        metrics = PrometheusMetrics()
        metrics.record_trade("buy", "test", 10.0)
        output = metrics._render_metrics()
        # Should be valid Prometheus text format
        assert "# TYPE" in output
        assert "\n" in output
