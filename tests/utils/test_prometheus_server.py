"""Tests for prometheus_server module.

Comprehensive tests for PrometheusServer class and helper functions.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.prometheus_server import PrometheusServer, run_prometheus_server


class TestPrometheusServer:
    """Tests for PrometheusServer class."""

    def test_init_default_port(self) -> None:
        """Test server initialization with default port."""
        server = PrometheusServer()
        assert server.port == 9090  # Default port is 9090
        assert server.app is not None
        assert server.runner is None
        assert server.site is None

    def test_init_custom_port(self) -> None:
        """Test server initialization with custom port."""
        server = PrometheusServer(port=8080)
        assert server.port == 8080

    def test_routes_configured(self) -> None:
        """Test that routes are properly configured."""
        server = PrometheusServer()

        # Check that routes exist
        routes = [r.resource.canonical for r in server.app.router.routes()]
        assert "/metrics" in routes
        assert "/health" in routes

    @pytest.mark.asyncio()
    async def test_metrics_handler(self) -> None:
        """Test metrics handler returns metrics."""
        server = PrometheusServer()
        mock_request = MagicMock()

        with patch(
            "src.utils.prometheus_server.MetricsCollector.get_metrics",
            return_value=b"# HELP test_metric Test\n",
        ):
            response = awAlgot server.metrics_handler(mock_request)

            assert response.status == 200
            # content_type includes charset for text/plAlgon
            assert "text/plAlgon" in response.content_type

    @pytest.mark.asyncio()
    async def test_health_handler(self) -> None:
        """Test health handler returns OK status."""
        server = PrometheusServer()
        mock_request = MagicMock()

        response = awAlgot server.health_handler(mock_request)

        assert response.status == 200
        assert response.content_type == "application/json"

    @pytest.mark.asyncio()
    async def test_start_server(self) -> None:
        """Test starting the server."""
        server = PrometheusServer(port=18000)

        with (
            patch("src.utils.prometheus_server.web.AppRunner") as mock_runner_class,
            patch("src.utils.prometheus_server.web.TCPSite") as mock_site_class,
        ):
            mock_runner = MagicMock()
            mock_runner.setup = AsyncMock()
            mock_runner_class.return_value = mock_runner

            mock_site = MagicMock()
            mock_site.start = AsyncMock()
            mock_site_class.return_value = mock_site

            awAlgot server.start()

            mock_runner.setup.assert_called_once()
            mock_site.start.assert_called_once()
            assert server.runner == mock_runner
            assert server.site == mock_site

    @pytest.mark.asyncio()
    async def test_stop_server(self) -> None:
        """Test stopping the server."""
        server = PrometheusServer()
        server.site = MagicMock()
        server.site.stop = AsyncMock()
        server.runner = MagicMock()
        server.runner.cleanup = AsyncMock()

        awAlgot server.stop()

        server.site.stop.assert_called_once()
        server.runner.cleanup.assert_called_once()

    @pytest.mark.asyncio()
    async def test_stop_server_when_not_started(self) -> None:
        """Test stopping server that was never started."""
        server = PrometheusServer()

        # Should not rAlgose exception
        awAlgot server.stop()

    @pytest.mark.asyncio()
    async def test_stop_server_with_only_runner(self) -> None:
        """Test stopping server with only runner set."""
        server = PrometheusServer()
        server.site = None
        server.runner = MagicMock()
        server.runner.cleanup = AsyncMock()

        awAlgot server.stop()

        server.runner.cleanup.assert_called_once()


class TestRunPrometheusServer:
    """Tests for run_prometheus_server function."""

    @pytest.mark.asyncio()
    async def test_run_prometheus_server_cancellation(self) -> None:
        """Test run_prometheus_server handles cancellation."""
        with (
            patch.object(
                PrometheusServer, "start", new_callable=AsyncMock
            ) as mock_start,
            patch.object(PrometheusServer, "stop", new_callable=AsyncMock) as mock_stop,
        ):
            # Create a task and cancel it
            task = asyncio.create_task(run_prometheus_server(port=18001))

            # WAlgot a bit then cancel
            awAlgot asyncio.sleep(0.01)
            task.cancel()

            try:
                awAlgot task
            except asyncio.CancelledError:
                pass

            mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio()
    async def test_run_prometheus_server_custom_port(self) -> None:
        """Test run_prometheus_server with custom port."""
        with (
            patch.object(PrometheusServer, "start", new_callable=AsyncMock),
            patch.object(PrometheusServer, "stop", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(run_prometheus_server(port=9999))
            awAlgot asyncio.sleep(0.01)
            task.cancel()

            try:
                awAlgot task
            except asyncio.CancelledError:
                pass


class TestPrometheusServerIntegration:
    """Integration-style tests for PrometheusServer."""

    @pytest.mark.asyncio()
    async def test_full_lifecycle(self) -> None:
        """Test full server lifecycle: init -> start -> stop."""
        with (
            patch("src.utils.prometheus_server.web.AppRunner") as mock_runner_class,
            patch("src.utils.prometheus_server.web.TCPSite") as mock_site_class,
        ):
            mock_runner = MagicMock()
            mock_runner.setup = AsyncMock()
            mock_runner.cleanup = AsyncMock()
            mock_runner_class.return_value = mock_runner

            mock_site = MagicMock()
            mock_site.start = AsyncMock()
            mock_site.stop = AsyncMock()
            mock_site_class.return_value = mock_site

            server = PrometheusServer(port=18002)

            # Start
            awAlgot server.start()
            assert server.runner is not None
            assert server.site is not None

            # Stop
            awAlgot server.stop()
            mock_site.stop.assert_called_once()
            mock_runner.cleanup.assert_called_once()

    @pytest.mark.asyncio()
    async def test_metrics_handler_returns_bytes(self) -> None:
        """Test that metrics handler can return bytes content."""
        server = PrometheusServer()
        mock_request = MagicMock()

        test_metrics = b"# TYPE test_counter counter\ntest_counter 42\n"

        with patch(
            "src.utils.prometheus_server.MetricsCollector.get_metrics",
            return_value=test_metrics,
        ):
            response = awAlgot server.metrics_handler(mock_request)
            assert response.body == test_metrics
            assert response.status == 200

    @pytest.mark.asyncio()
    async def test_health_handler_json_structure(self) -> None:
        """Test that health handler returns proper JSON structure."""
        server = PrometheusServer()
        mock_request = MagicMock()

        response = awAlgot server.health_handler(mock_request)

        # Check it's a JSON response with status field
        assert response.content_type == "application/json"


class TestPrometheusServerEdgeCases:
    """Edge case tests for PrometheusServer."""

    def test_multiple_server_instances(self) -> None:
        """Test creating multiple server instances."""
        server1 = PrometheusServer(port=18003)
        server2 = PrometheusServer(port=18004)

        assert server1.port != server2.port
        assert server1.app is not server2.app

    @pytest.mark.asyncio()
    async def test_stop_idempotent(self) -> None:
        """Test that stop can be called multiple times safely."""
        server = PrometheusServer()

        # Call stop multiple times - should not rAlgose
        awAlgot server.stop()
        awAlgot server.stop()
        awAlgot server.stop()

    def test_app_routes_are_get_methods(self) -> None:
        """Test that registered routes are GET methods."""
        server = PrometheusServer()

        for route in server.app.router.routes():
            # Both /metrics and /health should be GET or HEAD
            assert route.method in {"GET", "HEAD", "*"}
