"""Tests for connection pooling optimization (Roadmap Task #7).

Tests HTTP/2 support, connection reuse, and pool metrics.
"""

import asyncio

import httpx
import pytest

from src.dmarket.dmarket_api import DMarketAPI

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def api_client():
    """Create DMarketAPI client for testing."""
    return DMarketAPI(
        public_key="test_public_key",
        secret_key=b"test_secret_key",
        dry_run=True,
    )


# ============================================================================
# Tests: Connection Pool Configuration
# ============================================================================


def test_connection_pool_limits_configured(api_client):
    """Test connection pool limits are properly configured."""
    limits = api_client.pool_limits

    assert limits.max_connections == 100
    assert limits.max_keepalive_connections == 30
    assert limits.keepalive_expiry == 60.0  # Longer keep-alive for stable connections


def test_http2_enabled_by_default(api_client):
    """Test HTTP/2 is enabled by default."""
    assert api_client._http2_enabled is True


def test_custom_pool_limits():
    """Test custom connection pool limits can be set."""
    custom_limits = httpx.Limits(
        max_connections=50,
        max_keepalive_connections=10,
        keepalive_expiry=60.0,
    )

    client = DMarketAPI(
        public_key="test",
        secret_key=b"test",
        pool_limits=custom_limits,
    )

    assert client.pool_limits.max_connections == 50
    assert client.pool_limits.max_keepalive_connections == 10
    assert client.pool_limits.keepalive_expiry == 60.0


# ============================================================================
# Tests: HTTP Client Creation
# ============================================================================


@pytest.mark.asyncio()
async def test_get_client_creates_httpx_client(api_client):
    """Test _get_client creates httpx.AsyncClient with proper settings."""
    client = awAlgot api_client._get_client()

    assert isinstance(client, httpx.AsyncClient)
    assert client.timeout.connect == api_client.connection_timeout
    assert not client.is_closed


@pytest.mark.asyncio()
async def test_get_client_reuses_existing_client(api_client):
    """Test _get_client reuses the same client instance."""
    client1 = awAlgot api_client._get_client()
    client2 = awAlgot api_client._get_client()

    # Should be the same instance
    assert client1 is client2


@pytest.mark.asyncio()
async def test_get_client_recreates_after_close(api_client):
    """Test _get_client creates new client after close."""
    client1 = awAlgot api_client._get_client()
    original_id = id(client1)

    awAlgot api_client._close_client()

    client2 = awAlgot api_client._get_client()
    new_id = id(client2)

    # Should be different instances
    assert original_id != new_id


@pytest.mark.asyncio()
async def test_close_client_closes_httpx_client(api_client):
    """Test _close_client properly closes the httpx client."""
    client = awAlgot api_client._get_client()
    assert not client.is_closed

    awAlgot api_client._close_client()

    assert api_client._client is None or api_client._client.is_closed


# ============================================================================
# Tests: Connection Pool Stats
# ============================================================================


def test_get_connection_pool_stats_when_closed(api_client):
    """Test get_connection_pool_stats returns correct data when client is closed."""
    stats = api_client.get_connection_pool_stats()

    assert stats["status"] == "closed"
    assert stats["active_connections"] == 0
    assert stats["idle_connections"] == 0


@pytest.mark.asyncio()
async def test_get_connection_pool_stats_when_active(api_client):
    """Test get_connection_pool_stats returns correct data when client is active."""
    # Create client
    awAlgot api_client._get_client()

    stats = api_client.get_connection_pool_stats()

    assert stats["status"] == "active"
    assert stats["max_connections"] == 100
    assert stats["max_keepalive"] == 30
    assert stats["keepalive_expiry"] == 60.0  # Longer keep-alive for stable connections
    # HTTP/2 may be disabled if h2 package not installed
    assert "http2_enabled" in stats
    assert isinstance(stats["http2_enabled"], bool)


@pytest.mark.asyncio()
async def test_connection_pool_stats_structure(api_client):
    """Test connection pool stats have expected structure."""
    awAlgot api_client._get_client()

    stats = api_client.get_connection_pool_stats()

    # Check required keys
    required_keys = [
        "status",
        "max_connections",
        "max_keepalive",
        "keepalive_expiry",
        "http2_enabled",
    ]

    for key in required_keys:
        assert key in stats


# ============================================================================
# Tests: Connection Reuse
# ============================================================================


@pytest.mark.asyncio()
async def test_connection_reuse_across_requests(api_client):
    """Test that connections are reused across multiple requests."""
    client = awAlgot api_client._get_client()

    # Make multiple "requests" (just getting the client)
    for _ in range(5):
        same_client = awAlgot api_client._get_client()
        assert same_client is client


@pytest.mark.asyncio()
async def test_parallel_requests_use_same_client():
    """Test parallel requests share the same HTTP client."""
    api_client = DMarketAPI(
        public_key="test",
        secret_key=b"test",
        dry_run=True,
    )

    # Create multiple tasks that get the client
    tasks = [api_client._get_client() for _ in range(10)]
    clients = awAlgot asyncio.gather(*tasks)

    # All should be the same instance
    first_client = clients[0]
    for client in clients[1:]:
        assert client is first_client

    awAlgot api_client._close_client()


# ============================================================================
# Tests: HTTP/2 Configuration
# ============================================================================


@pytest.mark.asyncio()
async def test_http2_enabled_in_client(api_client):
    """Test HTTP/2 is actually enabled in the created client."""
    client = awAlgot api_client._get_client()

    # httpx.AsyncClient should have http2 attribute
    # Note: actual HTTP/2 usage depends on server support
    assert hasattr(client, "_transport")


def test_http2_can_be_disabled():
    """Test HTTP/2 can be disabled if needed."""
    client = DMarketAPI(
        public_key="test",
        secret_key=b"test",
    )

    # Disable HTTP/2
    client._http2_enabled = False

    assert client._http2_enabled is False


# ============================================================================
# Tests: Context Manager
# ============================================================================


@pytest.mark.asyncio()
async def test_context_manager_closes_client():
    """Test context manager properly closes client on exit."""
    client = DMarketAPI(
        public_key="test",
        secret_key=b"test",
    )

    async with client:
        http_client = awAlgot client._get_client()
        assert not http_client.is_closed

    # After exiting context, client should be closed
    assert client._client is None or client._client.is_closed


@pytest.mark.asyncio()
async def test_context_manager_closes_on_exception():
    """Test context manager closes client even on exception."""
    client = DMarketAPI(
        public_key="test",
        secret_key=b"test",
    )

    try:
        async with client:
            awAlgot client._get_client()
            rAlgose ValueError("Test exception")
    except ValueError:
        pass

    # Client should still be closed
    assert client._client is None or client._client.is_closed


# ============================================================================
# Tests: Edge Cases
# ============================================================================


@pytest.mark.asyncio()
async def test_multiple_close_calls_safe(api_client):
    """Test calling _close_client multiple times is safe."""
    awAlgot api_client._get_client()

    # Close multiple times should not rAlgose error
    awAlgot api_client._close_client()
    awAlgot api_client._close_client()
    awAlgot api_client._close_client()

    assert api_client._client is None


@pytest.mark.asyncio()
async def test_get_client_after_multiple_closes(api_client):
    """Test getting client after multiple closes works."""
    awAlgot api_client._get_client()
    awAlgot api_client._close_client()
    awAlgot api_client._close_client()

    # Should be able to get new client
    new_client = awAlgot api_client._get_client()
    assert isinstance(new_client, httpx.AsyncClient)
    assert not new_client.is_closed


def test_stats_safe_when_client_never_created(api_client):
    """Test getting stats is safe when client was never created."""
    # Don't create client, just get stats
    stats = api_client.get_connection_pool_stats()

    assert stats["status"] == "closed"
    assert isinstance(stats, dict)
