"""
prometheus_metrics.py — Prometheus metrics endpoint for DMarket bot.

Exposes trading metrics in Prometheus format for Grafana dashboards.

Usage:
    from src.monitoring.prometheus_metrics import metrics_server

    # Start metrics server (runs on port 9090 by default)
    await metrics_server.start()

    # Record metrics
    metrics_server.record_trade("buy", "AK-47 | Redline", 15.50, success=True)
    metrics_server.record_api_call("dmarket", "GET", 200, 0.35)
    metrics_server.update_balance(available=150.0, reserved=25.0)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("PrometheusMetrics")


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class PrometheusMetrics:
    """Prometheus-compatible metrics collector.

    Exposes metrics in Prometheus text format via HTTP endpoint.
    """

    def __init__(self, port: int = 9090) -> None:
        self.port = port
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._labels: dict[str, dict[str, str]] = {}
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the metrics HTTP server."""
        try:
            self._server = await asyncio.start_server(
                self._handle_request, "0.0.0.0", self.port
            )
            logger.info(f"[Prometheus] Metrics server started on port {self.port}")
        except Exception as e:
            logger.warning(f"[Prometheus] Failed to start server: {e}")

    async def stop(self) -> None:
        """Stop the metrics HTTP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("[Prometheus] Metrics server stopped")

    def record_trade(
        self,
        trade_type: str,
        item: str,
        price: float,
        success: bool = True,
    ) -> None:
        """Record a trade metric."""
        labels = {"type": trade_type, "item": item[:50]}

        # Increment counter
        key = f"dmarket_trades_total{{{self._format_labels(labels)}}}"
        self._counters[key] = self._counters.get(key, 0) + 1

        # Record price
        hist_key = "dmarket_trade_price_usd"
        if hist_key not in self._histograms:
            self._histograms[hist_key] = []
        self._histograms[hist_key].append(price)

        # Success/failure counter
        status = "success" if success else "failure"
        status_labels = {"type": trade_type, "status": status}
        status_key = f"dmarket_trade_status_total{{{self._format_labels(status_labels)}}}"
        self._counters[status_key] = self._counters.get(status_key, 0) + 1

    def record_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record an API call metric."""
        labels = {
            "endpoint": endpoint,
            "method": method,
            "status": str(status_code),
        }

        # Counter
        key = f"dmarket_api_calls_total{{{self._format_labels(labels)}}}"
        self._counters[key] = self._counters.get(key, 0) + 1

        # Duration histogram
        hist_key = f"dmarket_api_duration_seconds{{{self._format_labels({'endpoint': endpoint})}}}"
        if hist_key not in self._histograms:
            self._histograms[hist_key] = []
        self._histograms[hist_key].append(duration_seconds)

    def update_balance(self, available: float, reserved: float) -> None:
        """Update balance gauges."""
        self._gauges["dmarket_balance_available_usd"] = available
        self._gauges["dmarket_balance_reserved_usd"] = reserved
        self._gauges["dmarket_balance_total_usd"] = available + reserved

    def update_drawdown(self, current_pct: float, peak_usd: float) -> None:
        """Update drawdown gauges."""
        self._gauges["dmarket_drawdown_current_pct"] = current_pct
        self._gauges["dmarket_drawdown_peak_usd"] = peak_usd

    def update_inventory(
        self,
        total_items: int,
        total_value_usd: float,
        locked_value_usd: float,
    ) -> None:
        """Update inventory gauges."""
        self._gauges["dmarket_inventory_total_items"] = total_items
        self._gauges["dmarket_inventory_total_value_usd"] = total_value_usd
        self._gauges["dmarket_inventory_locked_value_usd"] = locked_value_usd

    def update_circuit_breaker(
        self, component: str, state: str, failures: int
    ) -> None:
        """Update circuit breaker gauges."""
        labels = {"component": component}
        state_key = f"dmarket_circuit_breaker_state{{{self._format_labels(labels)}}}"
        self._gauges[state_key] = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}.get(
            state, -1
        )

        fail_key = f"dmarket_circuit_breaker_failures{{{self._format_labels(labels)}}}"
        self._gauges[fail_key] = failures

    def update_risk_metrics(
        self,
        win_rate: float,
        sharpe_ratio: float,
        kelly_fraction: float,
        consecutive_losses: int,
    ) -> None:
        """Update risk management gauges."""
        self._gauges["dmarket_risk_win_rate"] = win_rate
        self._gauges["dmarket_risk_sharpe_ratio"] = sharpe_ratio
        self._gauges["dmarket_risk_kelly_fraction"] = kelly_fraction
        self._gauges["dmarket_risk_consecutive_losses"] = consecutive_losses

    def _format_labels(self, labels: dict[str, str]) -> str:
        """Format labels for Prometheus."""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return ", ".join(parts)

    def _render_metrics(self) -> str:
        """Render all metrics in Prometheus text format."""
        lines = []

        # Counters
        for key, value in self._counters.items():
            lines.append(f"# TYPE dmarket_trades_total counter")
            lines.append(f"{key} {value}")

        # Gauges
        for key, value in self._gauges.items():
            lines.append(f"# TYPE {key.split('{')[0]} gauge")
            lines.append(f"{key} {value}")

        # Histograms (simplified — just expose sum and count)
        for key, values in self._histograms.items():
            base_name = key.split("{")[0]
            lines.append(f"# TYPE {base_name} histogram")
            lines.append(f"{key}_count {len(values)}")
            lines.append(f"{key}_sum {sum(values):.4f}")

        return "\n".join(lines) + "\n"

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle HTTP request for metrics."""
        # Read request (we don't need the full request)
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        except asyncio.TimeoutError:
            writer.close()
            return

        # Always return metrics
        response_body = self._render_metrics()
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "\r\n"
            f"{response_body}"
        )

        writer.write(response.encode())
        await writer.drain()
        writer.close()


# Global singleton
metrics_server = PrometheusMetrics()
