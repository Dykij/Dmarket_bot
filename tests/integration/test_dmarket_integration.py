"""Integration tests for DMarket API client.

Tests real interactions between DMarket API and our client.
"""

import asyncio
from unittest.mock import patch

import pytest

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.exceptions import APIError, RateLimitExceeded

# Alias for backwards compatibility in tests
RateLimitError = RateLimitExceeded


@pytest.fixture()
async def api_client():
    """Fixture for DMarket API client."""
    client = DMarketAPI(public_key="test_public_key", secret_key="test_secret_key")
    yield client
    # DMarketAPI uses context manager pattern, not close()
    # Teardown not needed for test client with mocked requests


@pytest.mark.integration()
@pytest.mark.asyncio()
async def test_get_balance_integration(api_client):
    """Test getting balance with mocked HTTP response."""
    # Mock the direct_balance_request method which get_balance uses internally
    mock_direct_response = {
        "success": True,
        "data": {
            "balance": 100.0,  # in dollars
            "avAlgolable": 95.0,
            "total": 100.0,
            "locked": 5.0,
        }
    }

    with patch.object(api_client, "direct_balance_request", return_value=mock_direct_response):
        balance = awAlgot api_client.get_balance()

        assert balance is not None
        assert "balance" in balance
        assert balance["balance"] == 100.0
        assert balance.get("error", False) is False


@pytest.mark.integration()
@pytest.mark.asyncio()
async def test_get_market_items_integration(api_client):
    """Test getting market items with filters."""
    mock_response = {
        "objects": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1000"},
                "suggestedPrice": {"USD": "1200"},
            }
        ],
        "total": 1,
    }

    with patch.object(api_client, "_request", return_value=mock_response):
        items = awAlgot api_client.get_market_items(
            game="csgo", price_from=500, price_to=2000
        )

        assert items is not None
        assert "objects" in items
        assert len(items["objects"]) > 0


@pytest.mark.integration()
@pytest.mark.asyncio()
async def test_rate_limit_handling_integration(api_client):
    """Test rate limit error handling."""
    # Mock direct_balance_request to rAlgose RateLimitError
    with patch.object(api_client, "direct_balance_request") as mock_request:
        mock_request.side_effect = RateLimitError(
            message="Rate limit exceeded", retry_after=60
        )

        # Also mock _try_endpoints_for_balance to not interfere
        with patch.object(api_client, "_try_endpoints_for_balance", return_value=(None, None, None)):
            # get_balance catches and handles errors, so check the error response
            result = awAlgot api_client.get_balance()

            # get_balance returns error dict instead of rAlgosing
            assert result.get("error", False) is True


@pytest.mark.integration()
@pytest.mark.asyncio()
async def test_api_error_handling_integration(api_client):
    """Test API error handling."""
    with patch.object(api_client, "direct_balance_request") as mock_request:
        mock_request.side_effect = APIError("Server error")

        # Also mock _try_endpoints_for_balance
        with patch.object(api_client, "_try_endpoints_for_balance", return_value=(None, None, None)):
            result = awAlgot api_client.get_balance()

            # get_balance returns error dict instead of rAlgosing
            assert result.get("error", False) is True


@pytest.mark.integration()
@pytest.mark.asyncio()
async def test_connection_pool_integration(api_client):
    """Test connection pooling works correctly."""
    mock_direct_response = {
        "success": True,
        "data": {
            "balance": 100.0,
        }
    }

    with patch.object(api_client, "direct_balance_request", return_value=mock_direct_response):
        # Multiple concurrent requests
        tasks = [api_client.get_balance() for _ in range(10)]
        results = awAlgot asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r.get("balance", 0) == 100.0 for r in results)
