"""Unit tests for web_dashboard/app.py module.

Tests cover:
- FastAPI application initialization
- Root endpoint
- Health check endpoint
"""

from __future__ import annotations

import pytest

# Skip all tests if fastapi is not installed
fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from src.web_dashboard.app import app


@pytest.fixture()
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestAppRoot:
    """Tests for root endpoint."""

    def test_root_returns_200(self, client):
        """Test root endpoint returns 200 status."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_message(self, client):
        """Test root endpoint returns correct message."""
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert data["message"] == "DMarket Bot Dashboard API"

    def test_root_returns_version(self, client):
        """Test root endpoint returns version."""
        response = client.get("/")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200 status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        """Test health endpoint returns ok status."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestAppConfiguration:
    """Tests for app configuration."""

    def test_app_title(self):
        """Test app has correct title."""
        assert app.title == "DMarket Bot Dashboard API"

    def test_app_version(self):
        """Test app has correct version."""
        assert app.version == "1.0.0"

    def test_app_routes_count(self):
        """Test app has expected routes."""
        route_paths = [route.path for route in app.routes]
        assert "/" in route_paths
        assert "/api/v1/health" in route_paths


class TestContentType:
    """Tests for response content types."""

    def test_root_returns_json(self, client):
        """Test root endpoint returns JSON content type."""
        response = client.get("/")
        assert "application/json" in response.headers["content-type"]

    def test_health_returns_json(self, client):
        """Test health endpoint returns JSON content type."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]


class TestInvalidEndpoints:
    """Tests for invalid endpoints."""

    def test_invalid_endpoint_returns_404(self, client):
        """Test that invalid endpoint returns 404."""
        response = client.get("/invalid/endpoint")
        assert response.status_code == 404

    def test_post_to_get_endpoint_returns_405(self, client):
        """Test POST to GET-only endpoint returns 405."""
        response = client.post("/")
        assert response.status_code == 405

    def test_post_to_health_returns_405(self, client):
        """Test POST to health endpoint returns 405."""
        response = client.post("/api/v1/health")
        assert response.status_code == 405
