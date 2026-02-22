from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from circuitbreaker import CircuitBreakerError

from src.dmarket.dmarket_api import DMarketAPI


@pytest.mark.asyncio()
async def test_direct_balance_request_uses_circuit_breaker():
    api = DMarketAPI("pub", "sec")

    # Mock the client
    mock_client = AsyncMock()
    # Mock _get_client to return our mock_client
    with patch.object(api, "_get_client", return_value=mock_client):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "1000",
            "usdAvAlgolableToWithdraw": "1000",
            "usdTradeProtected": "0",
        }

        # We need to patch call_with_circuit_breaker where it is imported in dmarket_api
        with patch(
            "src.dmarket.dmarket_api.call_with_circuit_breaker", new_callable=AsyncMock
        ) as mock_cb:
            mock_cb.return_value = mock_response

            result = await api.direct_balance_request()

            assert result["success"] is True
            assert result["data"]["balance"] == 10.0

            # Verify call_with_circuit_breaker was called
            mock_cb.assert_called_once()
            args, _ = mock_cb.call_args
            # First arg should be the function (client.get)
            assert args[0] == mock_client.get
            # Second arg should be the url
            assert "balance" in args[1]


@pytest.mark.asyncio()
async def test_direct_balance_request_handles_circuit_breaker_error():
    api = DMarketAPI("pub", "sec")

    # Mock the client
    mock_client = AsyncMock()

    with (
        patch.object(api, "_get_client", return_value=mock_client),
        patch(
            "src.dmarket.dmarket_api.call_with_circuit_breaker", new_callable=AsyncMock
        ) as mock_cb,
    ):
        # Create a mock circuit breaker with a name attribute
        mock_breaker = MagicMock()
        mock_breaker.name = "test_breaker"
        mock_cb.side_effect = CircuitBreakerError(mock_breaker)

        result = await api.direct_balance_request()

        assert result["success"] is False
        assert "Circuit breaker open" in result["error"]
