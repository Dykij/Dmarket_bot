"""Tests for prometheus_metrics.py — Prometheus metrics collector."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.monitoring.prometheus_metrics import MetricPoint, PrometheusMetrics


class TestMetricPoint:

    def test_basic(self):
        mp = MetricPoint(name="test", value=42.0)
        assert mp.name == "test"
        assert mp.value == 42.0
        assert mp.labels == {}

    def test_with_labels(self):
        mp = MetricPoint(name="test", value=1.0, labels={"type": "buy"})
        assert mp.labels["type"] == "buy"


class TestPrometheusMetrics:

    def test_init(self):
        m = PrometheusMetrics(port=9999)
        assert m.port == 9999
        assert m._counters == {}
        assert m._gauges == {}

    def test_record_trade(self):
        m = PrometheusMetrics()
        m.record_trade("buy", "AK-47 | Redline", 15.50, success=True)
        assert len(m._counters) >= 2  # trade total + status total
        assert len(m._histograms) >= 1  # price histogram

    def test_record_trade_failure(self):
        m = PrometheusMetrics()
        m.record_trade("sell", "M4A4", 20.0, success=False)
        # Should have failure counter
        failure_keys = [k for k in m._counters if "failure" in k]
        assert len(failure_keys) >= 1

    def test_record_api_call(self):
        m = PrometheusMetrics()
        m.record_api_call("dmarket", "GET", 200, 0.35)
        assert len(m._counters) >= 1
        assert len(m._histograms) >= 1

    def test_update_balance(self):
        m = PrometheusMetrics()
        m.update_balance(available=150.0, reserved=25.0)
        assert m._gauges["dmarket_balance_available_usd"] == 150.0
        assert m._gauges["dmarket_balance_reserved_usd"] == 25.0
        assert m._gauges["dmarket_balance_total_usd"] == 175.0

    def test_update_drawdown(self):
        m = PrometheusMetrics()
        m.update_drawdown(current_pct=5.0, peak_usd=200.0)
        assert m._gauges["dmarket_drawdown_current_pct"] == 5.0
        assert m._gauges["dmarket_drawdown_peak_usd"] == 200.0

    def test_update_inventory(self):
        m = PrometheusMetrics()
        m.update_inventory(total_items=10, total_value_usd=150.0, locked_value_usd=30.0)
        assert m._gauges["dmarket_inventory_total_items"] == 10
        assert m._gauges["dmarket_inventory_total_value_usd"] == 150.0

    def test_update_circuit_breaker(self):
        m = PrometheusMetrics()
        m.update_circuit_breaker("api", "CLOSED", 0)
        assert "dmarket_circuit_breaker_state" in str(m._gauges.keys())

    def test_update_risk_metrics(self):
        m = PrometheusMetrics()
        m.update_risk_metrics(
            win_rate=0.55, sharpe_ratio=1.2,
            kelly_fraction=0.08, consecutive_losses=2,
        )
        assert m._gauges["dmarket_risk_win_rate"] == 0.55
        assert m._gauges["dmarket_risk_sharpe_ratio"] == 1.2

    def test_format_labels(self):
        m = PrometheusMetrics()
        result = m._format_labels({"type": "buy", "status": "success"})
        assert "type=\"buy\"" in result
        assert "status=\"success\"" in result

    def test_render_metrics_empty(self):
        m = PrometheusMetrics()
        output = m._render_metrics()
        assert isinstance(output, str)

    def test_render_metrics_with_data(self):
        m = PrometheusMetrics()
        m.record_trade("buy", "AK-47", 10.0)
        m.update_balance(100.0, 20.0)
        output = m._render_metrics()
        assert "dmarket_trades_total" in output
        assert "dmarket_balance_available_usd" in output

    def test_render_metrics_histogram(self):
        m = PrometheusMetrics()
        m.record_api_call("dmarket", "GET", 200, 0.1)
        m.record_api_call("dmarket", "GET", 200, 0.2)
        output = m._render_metrics()
        assert "_count 2" in output
        assert "_sum" in output

    @pytest.mark.asyncio
    async def test_start_stop(self):
        m = PrometheusMetrics(port=0)  # random port
        await m.start()
        assert m._server is not None
        await m.stop()
        assert m._server is not None  # server object still exists, just closed

    @pytest.mark.asyncio
    async def test_start_invalid_port(self):
        m = PrometheusMetrics(port=-1)
        await m.start()  # Should not raise, just log warning

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        m = PrometheusMetrics()
        await m.stop()  # Should not raise
