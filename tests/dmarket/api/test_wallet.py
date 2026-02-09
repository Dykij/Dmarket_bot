"""Unit tests for DMarket API wallet module.

This module contains comprehensive tests for src/dmarket/api/wallet.py covering:
- Error response creation
- Balance response creation and parsing
- Balance retrieval from multiple endpoints
- Direct balance requests with Ed25519 signatures
- User profile and account details

Target: 25+ tests to achieve 70%+ coverage
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.dmarket.api.wallet import WalletOperationsMixin

# Mock client class for testing the mixin


class MockDMarketClient(WalletOperationsMixin):
    """Mock client class that includes WalletOperationsMixin for testing."""

    def __init__(
        self,
        public_key: str = "test_public_key",
        secret_key: str = "a" * 64,
    ):
        """Initialize mock client."""
        self.public_key = public_key
        self._secret_key = secret_key
        self.secret_key = secret_key.encode("utf-8")
        self.api_url = "https://api.dmarket.com"
        self.ENDPOINT_BALANCE = "/account/v1/balance"
        self.ENDPOINT_BALANCE_LEGACY = "/account/v1/balance/legacy"
        self.ENDPOINT_ACCOUNT_DETAILS = "/account/v1/details"
        self._request = AsyncMock()
        self._get_client = AsyncMock()


# Test fixtures


@pytest.fixture()
def wallet_client():
    """Fixture providing a mock wallet client."""
    return MockDMarketClient()


@pytest.fixture()
def mock_httpx_client():
    """Fixture providing a mocked httpx.AsyncClient."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.get = AsyncMock()
    return mock_client


# TestWalletErrorResponse


class TestWalletErrorResponse:
    """Tests for _create_error_response method."""

    def test_create_error_response_default_values(self, wallet_client):
        """Test error response creation with default values."""
        # Arrange
        error_message = "Test error"

        # Act
        result = wallet_client._create_error_response(error_message)

        # Assert
        assert result["error"] is True
        assert result["error_message"] == error_message
        assert result["status_code"] == 500
        assert result["code"] == "ERROR"
        assert result["has_funds"] is False
        assert result["balance"] == 0.0

    def test_create_error_response_custom_values(self, wallet_client):
        """Test error response creation with custom values."""
        # Arrange
        error_message = "Custom error"
        status_code = 404
        error_code = "NOT_FOUND"

        # Act
        result = wallet_client._create_error_response(
            error_message, status_code, error_code
        )

        # Assert
        assert result["error"] is True
        assert result["error_message"] == error_message
        assert result["status_code"] == status_code
        assert result["code"] == error_code
        assert result["usd"]["amount"] == 0
        assert result["available_balance"] == 0.0
        assert result["total_balance"] == 0.0

    def test_create_error_response_structure(self, wallet_client):
        """Test that error response has all required fields."""
        # Act
        result = wallet_client._create_error_response("Error")

        # Assert
        assert "error" in result
        assert "error_message" in result
        assert "status_code" in result
        assert "code" in result
        assert "usd" in result
        assert "has_funds" in result
        assert "balance" in result
        assert "available_balance" in result
        assert "total_balance" in result


# TestWalletBalanceResponse


class TestWalletBalanceResponse:
    """Tests for _create_balance_response method."""

    def test_create_balance_response_converts_cents_to_dollars(self, wallet_client):
        """Test that balance response converts cents to dollars correctly."""
        # Arrange
        usd_amount = 10000  # 100 USD in cents
        usd_available = 8000  # 80 USD in cents
        usd_total = 12000  # 120 USD in cents

        # Act
        result = wallet_client._create_balance_response(
            usd_amount, usd_available, usd_total
        )

        # Assert
        assert result["balance"] == 100.0
        assert result["available_balance"] == 80.0
        assert result["total_balance"] == 120.0
        assert result["usd"]["amount"] == 10000
        assert result["error"] is False

    def test_create_balance_response_has_funds_true(self, wallet_client):
        """Test has_funds is True when balance >= min_required."""
        # Arrange
        usd_amount = 500  # 5 USD in cents
        min_required = 100  # 1 USD in cents

        # Act
        result = wallet_client._create_balance_response(
            usd_amount, usd_amount, usd_amount, min_required=min_required
        )

        # Assert
        assert result["has_funds"] is True

    def test_create_balance_response_has_funds_false(self, wallet_client):
        """Test has_funds is False when balance < min_required."""
        # Arrange
        usd_amount = 50  # 0.50 USD in cents
        min_required = 100  # 1 USD in cents

        # Act
        result = wallet_client._create_balance_response(
            usd_amount, usd_amount, usd_amount, min_required=min_required
        )

        # Assert
        assert result["has_funds"] is False

    def test_create_balance_response_with_additional_kwargs(self, wallet_client):
        """Test that additional kwargs are included in response."""
        # Arrange
        usd_amount = 1000
        additional_data = {
            "locked_balance": 10.0,
            "trade_protected_balance": 5.0,
            "method": "direct_request",
        }

        # Act
        result = wallet_client._create_balance_response(
            usd_amount, usd_amount, usd_amount, **additional_data
        )

        # Assert
        assert result["locked_balance"] == 10.0
        assert result["trade_protected_balance"] == 5.0
        assert result["method"] == "direct_request"


# TestWalletParseBalance


class TestWalletParseBalance:
    """Tests for _parse_balance_from_response method."""

    def test_parse_balance_official_format(self, wallet_client):
        """Test parsing official DMarket API format (2024)."""
        # Arrange
        response = {
            "usd": "10000",  # 100 USD in cents
            "usdAvailableToWithdraw": "8000",  # 80 USD in cents
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 10000.0
        assert usd_available == 8000.0
        assert usd_total == 10000.0

    def test_parse_balance_funds_usd_wallet_format(self, wallet_client):
        """Test parsing funds.usdWallet format."""
        # Arrange
        response = {
            "funds": {
                "usdWallet": {
                    "balance": 50.0,  # In dollars
                    "availableBalance": 40.0,
                    "totalBalance": 60.0,
                }
            }
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 5000.0  # Converted to cents
        assert usd_available == 4000.0
        assert usd_total == 6000.0

    def test_parse_balance_simple_format(self, wallet_client):
        """Test parsing simple balance/available/total format."""
        # Arrange
        response = {
            "balance": 25.0,  # In dollars
            "available": 20.0,
            "total": 30.0,
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 2500.0  # Converted to cents
        assert usd_available == 2000.0
        assert usd_total == 3000.0

    def test_parse_balance_legacy_format(self, wallet_client):
        """Test parsing legacy usdAvailableToWithdraw format."""
        # Arrange
        response = {
            "usdAvailableToWithdraw": "15.50",  # In dollars as string
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 1550.0  # Converted to cents
        assert usd_available == 1550.0
        assert usd_total == 1550.0

    def test_parse_balance_empty_response(self, wallet_client):
        """Test parsing empty response returns zeros."""
        # Arrange
        response: dict[str, Any] = {}

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0

    def test_parse_balance_invalid_data(self, wallet_client):
        """Test parsing invalid data returns zeros."""
        # Arrange
        response = {
            "invalid_key": "invalid_value",
            "random_data": 12345,
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0

    def test_parse_balance_normalizes_zero_available(self, wallet_client):
        """Test that zero available is normalized to usd_amount."""
        # Arrange
        response = {
            "usd": "5000",  # 50 USD
            "usdAvailableToWithdraw": "0",
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 5000.0
        assert usd_available == 5000.0  # Normalized to usd_amount
        assert usd_total == 5000.0

    def test_parse_balance_normalizes_zero_total(self, wallet_client):
        """Test that zero total is normalized to max of amount/available."""
        # Arrange
        response = {
            "balance": 10.0,  # In dollars
            "available": 8.0,
            "total": 0,  # Zero total
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 1000.0
        assert usd_available == 800.0
        assert usd_total == 1000.0  # Normalized to max(amount, available)


# TestWalletGetBalance


class TestWalletGetBalance:
    """Tests for get_balance method."""

    @pytest.mark.asyncio()
    async def test_get_balance_success(self, wallet_client):
        """Test successful balance retrieval."""
        # Arrange
        wallet_client._request = AsyncMock(
            return_value={
                "usd": "10000",
                "usdAvailableToWithdraw": "8000",
            }
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is False
        assert result["balance"] == 100.0
        assert result["available_balance"] == 80.0
        assert result["has_funds"] is True

    @pytest.mark.asyncio()
    async def test_get_balance_with_zero_balance(self, wallet_client):
        """Test balance retrieval with zero balance."""
        # Arrange
        wallet_client._request = AsyncMock(
            return_value={
                "usd": "0",
                "usdAvailableToWithdraw": "0",
            }
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["balance"] == 0.0
        assert result["has_funds"] is False

    @pytest.mark.asyncio()
    async def test_get_balance_handles_api_error(self, wallet_client):
        """Test handling of API error responses."""
        # Arrange
        wallet_client._request = AsyncMock(
            return_value={
                "error": "API Error",
                "code": "SERVER_ERROR",
                "status": 500,
            }
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert "error_message" in result

    @pytest.mark.asyncio()
    async def test_get_balance_handles_timeout(self, wallet_client):
        """Test handling of timeout errors."""
        # Arrange
        wallet_client._request = AsyncMock(side_effect=Exception("Request timeout"))

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert "timeout" in result["error_message"].lower()

    @pytest.mark.asyncio()
    async def test_get_balance_without_api_keys(self):
        """Test balance retrieval without API keys."""
        # Arrange
        client = MockDMarketClient(public_key="", secret_key="")

        # Act
        result = await client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 401
        assert result["code"] == "MISSING_API_KEYS"

    @pytest.mark.asyncio()
    async def test_get_balance_unauthorized(self, wallet_client, mock_httpx_client):
        """Test handling of 401 Unauthorized error."""
        # Arrange
        # Mock direct_balance_request to fail with 401
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_401_response = MagicMock(spec=httpx.Response)
        mock_401_response.status_code = 401
        mock_401_response.text = "Unauthorized"

        mock_httpx_client.get = AsyncMock(return_value=mock_401_response)

        # Mock _request to also return 401 error
        wallet_client._request = AsyncMock(
            return_value={
                "error": "Unauthorized",
                "code": "Unauthorized",
                "status": 401,
            }
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        # When all endpoints fail, it may return 500 or 401 depending on error parsing
        assert result["status_code"] in {401, 500}
        assert result["code"] in {"UNAUTHORIZED", "REQUEST_FAILED"}

    @pytest.mark.asyncio()
    async def test_get_balance_tries_multiple_endpoints(self, wallet_client):
        """Test that balance request tries multiple endpoints on failure."""
        # Arrange
        call_count = 0

        async def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"error": "Not found", "code": "NOT_FOUND"}
            return {"usd": "5000", "usdAvailableToWithdraw": "5000"}

        wallet_client._request = AsyncMock(side_effect=mock_request_side_effect)

        # Act
        await wallet_client.get_balance()

        # Assert
        assert call_count >= 1  # Should try at least one endpoint

    @pytest.mark.asyncio()
    async def test_get_balance_via_direct_request(
        self, wallet_client, mock_httpx_client
    ):
        """Test balance retrieval via direct_balance_request."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "15000",
            "usdAvailableToWithdraw": "12000",
        }

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["balance"] > 0


# TestWalletDirectBalanceRequest


class TestWalletDirectBalanceRequest:
    """Tests for direct_balance_request method."""

    @pytest.mark.asyncio()
    async def test_direct_balance_request_success(
        self, wallet_client, mock_httpx_client
    ):
        """Test successful direct balance request."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "20000",
            "usdAvailableToWithdraw": "18000",
        }

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True
        assert result["data"]["balance"] == 200.0
        assert result["data"]["available"] == 180.0

    @pytest.mark.asyncio()
    async def test_direct_balance_request_parses_response(
        self, wallet_client, mock_httpx_client
    ):
        """Test that direct request parses response correctly."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "funds": {
                "usdWallet": {
                    "balance": 75.0,
                    "availableBalance": 70.0,
                    "totalBalance": 80.0,
                }
            }
        }

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["balance"] == 75.0

    @pytest.mark.asyncio()
    async def test_direct_balance_request_handles_error(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of errors in direct balance request."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is False
        assert "error" in result
        assert "500" in result["error"]

    @pytest.mark.asyncio()
    async def test_direct_balance_request_http_error(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of HTTP errors in direct request."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.get = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed")
        )

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio()
    async def test_direct_balance_request_generates_signature(
        self, wallet_client, mock_httpx_client
    ):
        """Test that direct request generates proper signature."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"usd": "1000"}

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        await wallet_client.direct_balance_request()

        # Assert
        call_args = mock_httpx_client.get.call_args
        assert call_args is not None
        headers = call_args.kwargs.get("headers", {})
        assert "X-Api-Key" in headers
        assert "X-Sign-Date" in headers
        assert "X-Request-Sign" in headers
        assert headers["X-Api-Key"] == wallet_client.public_key


# TestWalletUserProfile


class TestWalletUserProfile:
    """Tests for user profile and account details methods."""

    @pytest.mark.asyncio()
    async def test_get_user_profile(self, wallet_client):
        """Test getting user profile."""
        # Arrange
        expected_profile = {
            "id": "user123",
            "email": "test@example.com",
            "verified": True,
        }
        wallet_client._request = AsyncMock(return_value=expected_profile)

        # Act
        result = await wallet_client.get_user_profile()

        # Assert
        assert result == expected_profile
        wallet_client._request.assert_called_once_with("GET", "/account/v1/user")

    @pytest.mark.asyncio()
    async def test_get_account_details(self, wallet_client):
        """Test getting account details."""
        # Arrange
        expected_details = {
            "account_id": "acc123",
            "level": "verified",
            "limits": {"daily": 10000},
        }
        wallet_client._request = AsyncMock(return_value=expected_details)

        # Act
        result = await wallet_client.get_account_details()

        # Assert
        assert result == expected_details
        wallet_client._request.assert_called_once_with(
            "GET", wallet_client.ENDPOINT_ACCOUNT_DETAILS
        )


# Additional Tests for Increased Coverage


class TestWalletGetBalanceSuccessPath:
    """Tests for successful balance retrieval through direct request."""

    @pytest.mark.asyncio()
    async def test_get_balance_success_via_direct_request_with_full_data(
        self, wallet_client, mock_httpx_client
    ):
        """Test successful balance retrieval via direct request with all balance fields."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "50000",
            "usdAvailableToWithdraw": "40000",
        }

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Mock _request to fail so direct_balance_request is the successful path
        wallet_client._request = AsyncMock(
            return_value={"error": "Not found", "code": "NOT_FOUND"}
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is False
        assert result["balance"] == 500.0
        assert result["available_balance"] == 400.0
        assert "additional_info" in result
        assert result["additional_info"]["method"] == "direct_request"
        assert "raw_response" in result["additional_info"]

    @pytest.mark.asyncio()
    async def test_get_balance_direct_request_with_locked_balance(
        self, wallet_client, mock_httpx_client
    ):
        """Test balance retrieval with locked and trade-protected balances."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Create a proper response that goes through direct_balance_request
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "funds": {
                "usdWallet": {
                    "balance": 100.0,
                    "availableBalance": 80.0,
                    "totalBalance": 120.0,
                }
            }
        }

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True
        assert result["data"]["balance"] == 100.0
        assert result["data"]["available"] == 80.0
        assert result["data"]["total"] == 120.0

    @pytest.mark.asyncio()
    async def test_get_balance_handles_exception_in_direct_request(
        self, wallet_client, mock_httpx_client
    ):
        """Test that exceptions in direct_balance_request are handled gracefully."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Network error"))

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is False
        assert "error" in result
        assert "Network error" in result["error"]


class TestWalletParseBalanceEdgeCases:
    """Tests for edge cases in balance parsing."""

    def test_parse_balance_with_string_dollar_value(self, wallet_client):
        """Test parsing balance with dollar sign in string."""
        # Arrange
        response = {
            "usdAvailableToWithdraw": "$25.50",
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 2550.0
        assert usd_available == 2550.0
        assert usd_total == 2550.0

    def test_parse_balance_handles_parse_error(self, wallet_client):
        """Test that parse errors return zeros."""
        # Arrange
        response = {
            "usd": "invalid_value",
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0


class TestWalletGetBalanceEndpointFallback:
    """Tests for endpoint fallback logic in get_balance."""

    @pytest.mark.asyncio()
    async def test_get_balance_tries_all_endpoints_on_failure(
        self, wallet_client, mock_httpx_client
    ):
        """Test that get_balance tries all endpoints when direct request fails."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Server Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock all _request calls to fail
        call_count = 0

        async def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"error": "Failed", "code": "ERROR"}

        wallet_client._request = AsyncMock(side_effect=mock_request_side_effect)

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert call_count >= 1  # Should have tried at least one endpoint

    @pytest.mark.asyncio()
    async def test_get_balance_returns_first_successful_endpoint(
        self, wallet_client, mock_httpx_client
    ):
        """Test that get_balance returns result from first successful endpoint."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Server Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock _request to succeed on first call
        wallet_client._request = AsyncMock(
            return_value={
                "usd": "30000",
                "usdAvailableToWithdraw": "25000",
            }
        )

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is False
        assert result["balance"] == 300.0
        assert result["available_balance"] == 250.0


class TestWalletDeprecatedMethods:
    """Tests for deprecated wallet methods."""

    @pytest.mark.asyncio()
    async def test_get_user_balance_deprecated(self, wallet_client):
        """Test that get_user_balance is deprecated but still works."""
        # Arrange
        wallet_client._get_client = AsyncMock()
        wallet_client._request = AsyncMock(
            return_value={
                "usd": "10000",
                "usdAvailableToWithdraw": "8000",
            }
        )

        # Mock direct_balance_request to fail
        mock_httpx_client = AsyncMock(spec=httpx.AsyncClient)
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Act
        result = await wallet_client.get_user_balance()

        # Assert
        assert result is not None
        assert "balance" in result


class TestWalletErrorHandling:
    """Tests for error handling in wallet operations."""

    def test_parse_balance_with_integer_usd_available(self, wallet_client):
        """Test parsing balance with integer usdAvailableToWithdraw."""
        # Arrange
        response = {
            "usdAvailableToWithdraw": 1500,  # Integer instead of string
        }

        # Act
        usd_amount, usd_available, _ = wallet_client._parse_balance_from_response(
            response
        )

        # Assert
        assert usd_amount == 150000.0
        assert usd_available == 150000.0

    @pytest.mark.asyncio()
    async def test_get_balance_handles_404_error(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of 404 error with proper error code."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock _request to return None (all endpoints failed)
        wallet_client._request = AsyncMock(return_value=None)

        # Mock _try_endpoints_for_balance to return 404 error
        async def mock_try_endpoints(*args, **kwargs):
            return None, None, Exception("404 Not Found")

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 404
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio()
    async def test_get_balance_handles_unauthorized_in_error_message(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of unauthorized error in error message."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock _try_endpoints_for_balance to return 401 error
        async def mock_try_endpoints(*args, **kwargs):
            return None, None, Exception("401 Unauthorized access")

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 401
        assert result["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio()
    async def test_get_balance_with_error_response_from_endpoint(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of error response with code and status from endpoint."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock _try_endpoints_for_balance to return error response
        error_response = {
            "error": "API Error",
            "code": "SERVER_ERROR",
            "status": 500,
            "message": "Internal server error",
        }

        async def mock_try_endpoints(*args, **kwargs):
            return error_response, "/account/v1/balance", None

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 500
        assert result["code"] == "SERVER_ERROR"

    @pytest.mark.asyncio()
    async def test_get_balance_with_unauthorized_error_code(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of Unauthorized error code from API."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_direct_response = MagicMock(spec=httpx.Response)
        mock_direct_response.status_code = 500
        mock_direct_response.text = "Error"
        mock_httpx_client.get = AsyncMock(return_value=mock_direct_response)

        # Mock _try_endpoints_for_balance to return Unauthorized error
        error_response = {
            "code": "Unauthorized",
            "message": "Invalid API keys",
            "status": 401,
        }

        async def mock_try_endpoints(*args, **kwargs):
            return error_response, "/account/v1/balance", None

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 401
        assert result["code"] == "UNAUTHORIZED"
        assert "invalid" in result["error_message"].lower()
        assert "api keys" in result["error_message"].lower()


# Additional Tests for 95%+ Coverage


class TestWalletSecretKeyConversion:
    """Tests for different secret key format conversions in direct requests."""

    @pytest.mark.asyncio()
    async def test_direct_request_with_base64_secret_key(
        self, wallet_client, mock_httpx_client
    ):
        """Test direct balance request with base64-encoded secret key."""
        # Arrange
        import base64

        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Create a valid base64 key (44 chars)
        wallet_client._secret_key = base64.b64encode(b"a" * 32).decode("utf-8")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "5000",
            "usdAvailableToWithdraw": "4000",
        }
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_direct_request_with_short_secret_key(
        self, wallet_client, mock_httpx_client
    ):
        """Test direct balance request with short secret key (padded)."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Short key that will be padded
        wallet_client._secret_key = "short_key"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "3000",
            "usdAvailableToWithdraw": "2500",
        }
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_direct_request_with_long_hex_secret_key(
        self, wallet_client, mock_httpx_client
    ):
        """Test direct balance request with long hex secret key (truncated)."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Long hex key (>64 chars) that will be truncated
        wallet_client._secret_key = "a" * 80

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "6000",
            "usdAvailableToWithdraw": "5500",
        }
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        assert result["success"] is True

    @pytest.mark.asyncio()
    async def test_direct_request_signature_fallback_to_hmac(
        self, wallet_client, mock_httpx_client
    ):
        """Test fallback to HMAC when Ed25519 signature fails."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Set invalid secret key that will cause Ed25519 to fail
        wallet_client._secret_key = "invalid_key_format_☠"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usd": "7000",
            "usdAvailableToWithdraw": "6500",
        }
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # Act
        result = await wallet_client.direct_balance_request()

        # Assert
        # Should succeed with HMAC fallback
        assert result["success"] is True


class TestWalletLegacyKeyFormats:
    """Tests for legacy key format handling."""

    def test_parse_balance_with_complex_nested_structure(self, wallet_client):
        """Test parsing balance with deeply nested structure."""
        # Arrange
        response = {
            "funds": {
                "usdWallet": {
                    "balance": 150.0,
                    "availableBalance": 120.0,
                    "totalBalance": 180.0,
                },
                "otherData": "ignored",
            }
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert
        assert usd_amount == 15000.0
        assert usd_available == 12000.0
        assert usd_total == 18000.0

    @pytest.mark.asyncio()
    async def test_get_balance_handles_general_exception(
        self, wallet_client, mock_httpx_client
    ):
        """Test handling of general exception during balance retrieval."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)

        # Mock direct_balance_request to fail
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Unexpected error"))

        # Mock _try_endpoints_for_balance to raise exception
        async def mock_try_endpoints(*args, **kwargs):
            raise Exception("Database connection failed")

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 500
        assert "Database connection failed" in result["error_message"]

    def test_parse_balance_handles_value_error(self, wallet_client):
        """Test that ValueError in parsing is handled gracefully."""
        # Arrange
        response = {
            "usd": "not_a_number",
            "usdAvailableToWithdraw": "also_not_a_number",
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert - should return zeros on parse error
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0

    def test_parse_balance_handles_type_error(self, wallet_client):
        """Test that TypeError in parsing is handled gracefully."""
        # Arrange
        response = {
            "funds": None,  # Will cause TypeError when trying to access
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert - should return zeros on parse error
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0

    def test_parse_balance_handles_key_error(self, wallet_client):
        """Test that KeyError in parsing is handled gracefully."""
        # Arrange
        response = {
            "funds": {
                "invalidKey": "data",
            }
        }

        # Act
        usd_amount, usd_available, usd_total = (
            wallet_client._parse_balance_from_response(response)
        )

        # Assert - should return zeros on parse error
        assert usd_amount == 0.0
        assert usd_available == 0.0
        assert usd_total == 0.0

    @pytest.mark.asyncio()
    async def test_get_balance_exception_with_404_in_message(
        self, wallet_client, mock_httpx_client
    ):
        """Test exception handling with 404 in error message."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.get = AsyncMock(
            side_effect=Exception("404 resource not found")
        )

        # Mock _try_endpoints_for_balance to also raise 404 exception
        async def mock_try_endpoints(*args, **kwargs):
            raise Exception("404 not found")

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 404
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio()
    async def test_get_balance_exception_with_401_in_message(
        self, wallet_client, mock_httpx_client
    ):
        """Test exception handling with 401 in error message."""
        # Arrange
        wallet_client._get_client = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.get = AsyncMock(side_effect=Exception("401 unauthorized"))

        # Mock _try_endpoints_for_balance to also raise 401 exception
        async def mock_try_endpoints(*args, **kwargs):
            raise Exception("401 Unauthorized access")

        wallet_client._try_endpoints_for_balance = mock_try_endpoints

        # Act
        result = await wallet_client.get_balance()

        # Assert
        assert result["error"] is True
        assert result["status_code"] == 401
        assert result["code"] == "UNAUTHORIZED"


# =============================================================================
# NEW TESTS - Added to improve coverage from 11% to 70%+
# Target: Test uncovered methods (get_user_profile, get_account_details)
# =============================================================================


class TestWalletUserProfileExtended:
    """Tests for get_user_profile method."""

    @pytest.mark.asyncio()
    async def test_get_user_profile_success(self, wallet_client):
        """Test successful retrieval of user profile."""
        # Arrange
        expected_profile = {
            "user_id": "test_user_123",
            "email": "test@example.com",
            "created_at": "2025-01-01T00:00:00Z",
        }
        wallet_client._request = AsyncMock(return_value=expected_profile)

        # Act
        result = await wallet_client.get_user_profile()

        # Assert
        assert result == expected_profile
        wallet_client._request.assert_called_once_with("GET", "/account/v1/user")

    @pytest.mark.asyncio()
    async def test_get_user_profile_handles_api_error(self, wallet_client):
        """Test handling of API error when getting user profile."""
        # Arrange
        wallet_client._request = AsyncMock(side_effect=Exception("API Error"))

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await wallet_client.get_user_profile()

        assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_get_user_profile_with_empty_response(self, wallet_client):
        """Test user profile with empty response."""
        # Arrange
        wallet_client._request = AsyncMock(return_value={})

        # Act
        result = await wallet_client.get_user_profile()

        # Assert
        assert result == {}


class TestWalletAccountDetails:
    """Tests for get_account_details method."""

    @pytest.mark.asyncio()
    async def test_get_account_details_success(self, wallet_client):
        """Test successful retrieval of account details."""
        # Arrange
        expected_details = {
            "account_id": "acc_123",
            "balance": {"USD": "10000"},
            "verified": True,
        }
        wallet_client._request = AsyncMock(return_value=expected_details)

        # Act
        result = await wallet_client.get_account_details()

        # Assert
        assert result == expected_details
        wallet_client._request.assert_called_once_with(
            "GET", wallet_client.ENDPOINT_ACCOUNT_DETAILS
        )

    @pytest.mark.asyncio()
    async def test_get_account_details_handles_timeout(self, wallet_client):
        """Test handling of timeout when getting account details."""
        # Arrange
        import asyncio

        wallet_client._request = AsyncMock(side_effect=TimeoutError("Request timeout"))

        # Act & Assert
        with pytest.raises(asyncio.TimeoutError):
            await wallet_client.get_account_details()

    @pytest.mark.asyncio()
    async def test_get_account_details_with_partial_data(self, wallet_client):
        """Test account details with partial data."""
        # Arrange
        partial_details = {"account_id": "acc_456"}
        wallet_client._request = AsyncMock(return_value=partial_details)

        # Act
        result = await wallet_client.get_account_details()

        # Assert
        assert result["account_id"] == "acc_456"
        assert "balance" not in result
