"""Tests for advanced health check server (Roadmap Task #5).

Tests HTTP endpoints, dependency checks, and metrics.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.telegram_bot.health_check import HealthCheckServer, init_health_check_server

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_db_manager():
    """Create mock database manager."""
    db = MagicMock()
    db.execute_query = AsyncMock(return_value=None)
    return db


@pytest.fixture()
def mock_redis_client():
    """Create mock Redis client."""
    redis = MagicMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture()
def mock_dmarket_api():
    """Create mock DMarket API client."""
    api = MagicMock()
    api.get_balance = AsyncMock(return_value={"usd": "10000", "error": False})
    return api


@pytest.fixture()
def mock_bot_app():
    """Create mock bot application."""
    bot = MagicMock()
    bot.bot = MagicMock()
    bot.bot.get_me = AsyncMock(return_value={"id": 123, "username": "test_bot"})
    return bot


@pytest.fixture()
async def health_server(mock_db_manager, mock_redis_client, mock_dmarket_api, mock_bot_app):
    """Create health check server with mocked dependencies."""
    server = HealthCheckServer(
        host="127.0.0.1",
        port=8089,  # Use different port to avoid conflicts
        db_manager=mock_db_manager,
        redis_client=mock_redis_client,
        dmarket_api=mock_dmarket_api,
        bot_app=mock_bot_app,
    )

    await server.start()
    server.set_status("running")

    yield server

    await server.stop()


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_health_server_initialization():
    """Test health server initializes correctly."""
    server = HealthCheckServer(host="0.0.0.0", port=8080)

    assert server.host == "0.0.0.0"
    assert server.port == 8080
    assert server.status == "starting"
    assert server.version == "1.0.0"
    assert server.total_updates == 0
    assert server.total_errors == 0


def test_init_health_check_server():
    """Test global health check server initialization."""
    server = init_health_check_server(host="localhost", port=8081)

    assert server is not None
    assert server.host == "localhost"
    assert server.port == 8081


# ============================================================================
# Tests: HTTP Endpoints
# ============================================================================


@pytest.mark.asyncio()
async def test_health_endpoint_all_healthy(health_server):
    """Test /health endpoint when all services are healthy."""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/health") as response:
            assert response.status == 200

            data = await response.json()

            assert data["status"] == "healthy"
            assert "checks" in data
            assert data["checks"]["database"] is True
            assert data["checks"]["redis"] is True
            assert data["checks"]["dmarket_api"] is True
            assert data["checks"]["telegram_api"] is True
            assert "uptime_seconds" in data
            assert "version" in data
            assert data["version"] == "1.0.0"
            assert "timestamp" in data


@pytest.mark.asyncio()
async def test_health_endpoint_database_unhealthy(health_server, mock_db_manager):
    """Test /health endpoint when database is down."""
    # Make database check fail
    mock_db_manager.execute_query = AsyncMock(side_effect=Exception("DB Error"))

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/health") as response:
            assert response.status == 503  # Service Unavailable

            data = await response.json()

            assert data["status"] == "unhealthy"
            assert data["checks"]["database"] is False


@pytest.mark.asyncio()
async def test_ready_endpoint_when_ready(health_server):
    """Test /ready endpoint when bot is ready."""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/ready") as response:
            assert response.status == 200

            data = await response.json()

            assert data["ready"] is True
            assert data["status"] == "running"


@pytest.mark.asyncio()
async def test_ready_endpoint_when_not_ready(health_server):
    """Test /ready endpoint when bot is not ready."""
    health_server.set_status("starting")

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/ready") as response:
            assert response.status == 503

            data = await response.json()

            assert data["ready"] is False
            assert data["status"] == "starting"


@pytest.mark.asyncio()
async def test_live_endpoint(health_server):
    """Test /live endpoint always returns alive."""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/live") as response:
            assert response.status == 200

            data = await response.json()

            assert data["alive"] is True
            assert "uptime_seconds" in data


@pytest.mark.asyncio()
async def test_metrics_endpoint(health_server):
    """Test /metrics endpoint returns detailed metrics."""
    # Update some metrics
    health_server.update_metrics(updates_count=10, errors_count=2)

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8089/metrics") as response:
            assert response.status == 200

            data = await response.json()

            assert data["status"] == "running"
            assert data["total_updates"] == 10
            assert data["total_errors"] == 2
            assert data["error_rate"] == 0.2
            assert "uptime_seconds" in data
            assert "timestamp" in data


# ============================================================================
# Tests: Health Checks
# ============================================================================


@pytest.mark.asyncio()
async def test_check_database_success(health_server):
    """Test database health check succeeds."""
    result = await health_server._check_database()
    assert result is True


@pytest.mark.asyncio()
async def test_check_database_failure(health_server, mock_db_manager):
    """Test database health check fails gracefully."""
    mock_db_manager.execute_query = AsyncMock(side_effect=Exception("Connection error"))

    result = await health_server._check_database()
    assert result is False


@pytest.mark.asyncio()
async def test_check_redis_success(health_server):
    """Test Redis health check succeeds."""
    result = await health_server._check_redis()
    assert result is True


@pytest.mark.asyncio()
async def test_check_redis_failure(health_server, mock_redis_client):
    """Test Redis health check fails gracefully."""
    mock_redis_client.ping = AsyncMock(side_effect=Exception("Connection refused"))

    result = await health_server._check_redis()
    assert result is False


@pytest.mark.asyncio()
async def test_check_dmarket_api_success(health_server):
    """Test DMarket API health check succeeds."""
    result = await health_server._check_dmarket_api()
    assert result is True


@pytest.mark.asyncio()
async def test_check_dmarket_api_failure(health_server, mock_dmarket_api):
    """Test DMarket API health check fails gracefully."""
    mock_dmarket_api.get_balance = AsyncMock(return_value={"error": True})

    result = await health_server._check_dmarket_api()
    assert result is False


@pytest.mark.asyncio()
async def test_check_telegram_api_success(health_server):
    """Test Telegram API health check succeeds."""
    result = await health_server._check_telegram_api()
    assert result is True


@pytest.mark.asyncio()
async def test_check_telegram_api_failure(health_server, mock_bot_app):
    """Test Telegram API health check fails gracefully."""
    mock_bot_app.bot.get_me = AsyncMock(side_effect=Exception("API Error"))

    result = await health_server._check_telegram_api()
    assert result is False


# ============================================================================
# Tests: Metrics
# ============================================================================


def test_update_metrics_updates_count():
    """Test update_metrics increments counters."""
    server = HealthCheckServer()

    assert server.total_updates == 0
    assert server.total_errors == 0

    server.update_metrics(updates_count=5, errors_count=1)

    assert server.total_updates == 5
    assert server.total_errors == 1
    assert server.last_update_time is not None


def test_update_metrics_multiple_calls():
    """Test update_metrics accumulates correctly."""
    server = HealthCheckServer()

    server.update_metrics(updates_count=3)
    server.update_metrics(updates_count=7, errors_count=2)

    assert server.total_updates == 10
    assert server.total_errors == 2


def test_set_status():
    """Test set_status updates status."""
    server = HealthCheckServer()

    assert server.status == "starting"

    server.set_status("running")
    assert server.status == "running"

    server.set_status("stopping")
    assert server.status == "stopping"


# ============================================================================
# Tests: Edge Cases
# ============================================================================


@pytest.mark.asyncio()
async def test_health_check_without_dependencies():
    """Test health check works without any dependencies configured."""
    server = HealthCheckServer(
        host="127.0.0.1",
        port=8090,
        db_manager=None,
        redis_client=None,
        dmarket_api=None,
        bot_app=None,
    )

    await server.start()
    server.set_status("running")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:8090/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] == "healthy"
                # All checks should pass (return True) when dependencies not configured
                assert all(data["checks"].values())
    finally:
        await server.stop()


@pytest.mark.asyncio()
async def test_uptime_tracking():
    """Test uptime is tracked correctly."""
    server = HealthCheckServer(host="127.0.0.1", port=8091)

    start_time = server.start_time

    # Wait a bit
    await asyncio.sleep(0.5)

    uptime = time.time() - start_time
    assert uptime >= 0.5

    await server.start()
    server.set_status("running")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:8091/metrics") as response:
                data = await response.json()
                assert data["uptime_seconds"] >= 0
    finally:
        await server.stop()
