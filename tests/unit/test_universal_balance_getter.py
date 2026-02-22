"""Tests for UniversalBalanceGetter module.

Phase 2: Code Readability Improvements - Task 10
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.universal_balance_getter import UniversalBalanceGetter


@pytest.fixture()
def mock_api_client():
    """Create mock API client."""
    client = AsyncMock()
    client.public_key = "test_public_key"
    client.secret_key = "test_secret_key"
    client.direct_balance_request = AsyncMock()
    client._request = AsyncMock()
    return client


@pytest.fixture()
def balance_getter(mock_api_client):
    """Create UniversalBalanceGetter instance."""
    return UniversalBalanceGetter(api_client=mock_api_client)


class TestInitialization:
    """Tests for UniversalBalanceGetter initialization."""

    def test_initialization_with_valid_client(self, mock_api_client):
        """Test initialization with valid API client."""
        getter = UniversalBalanceGetter(api_client=mock_api_client)
        assert getter.api_client is mock_api_client
        assert getter.public_key == "test_public_key"
        assert getter.secret_key == "test_secret_key"

    def test_initialization_without_credentials(self):
        """Test initialization with client without credentials."""
        client = AsyncMock()
        client.public_key = None
        client.secret_key = None

        getter = UniversalBalanceGetter(api_client=client)
        assert getter.public_key is None
        assert getter.secret_key is None


class TestHasValidCredentials:
    """Tests for _has_valid_credentials method."""

    def test_valid_credentials(self, balance_getter):
        """Test with valid credentials."""
        assert balance_getter._has_valid_credentials() is True

    def test_missing_public_key(self, balance_getter):
        """Test with missing public key."""
        balance_getter.public_key = None
        assert balance_getter._has_valid_credentials() is False

    def test_missing_secret_key(self, balance_getter):
        """Test with missing secret key."""
        balance_getter.secret_key = None
        assert balance_getter._has_valid_credentials() is False

    def test_empty_credentials(self, balance_getter):
        """Test with empty string credentials."""
        balance_getter.public_key = ""
        balance_getter.secret_key = ""
        assert balance_getter._has_valid_credentials() is False


class TestTryDirectRequest:
    """Tests for _try_direct_request method."""

    @pytest.mark.asyncio()
    async def test_successful_direct_request(self, balance_getter, mock_api_client):
        """Test successful direct request."""
        mock_api_client.direct_balance_request.return_value = {
            "success": True,
            "data": {
                "balance": 10.0,
                "avAlgolable": 8.0,
                "total": 12.0,
                "locked": 2.0,
                "trade_protected": 0.0,
            },
        }

        result = await balance_getter._try_direct_request()

        assert result is not None
        assert result["balance"] == 10.0
        assert result["avAlgolable_balance"] == 8.0
        assert result["error"] is False

    @pytest.mark.asyncio()
    async def test_failed_direct_request(self, balance_getter, mock_api_client):
        """Test failed direct request."""
        mock_api_client.direct_balance_request.return_value = {
            "success": False,
            "error": "API Error",
        }

        result = await balance_getter._try_direct_request()

        assert result is None

    @pytest.mark.asyncio()
    async def test_direct_request_exception(self, balance_getter, mock_api_client):
        """Test direct request with exception."""
        mock_api_client.direct_balance_request.side_effect = Exception("Network error")

        result = await balance_getter._try_direct_request()

        assert result is None


class TestProcessDirectResponse:
    """Tests for _process_direct_response method."""

    def test_process_complete_response(self, balance_getter):
        """Test processing complete direct response."""
        response = {
            "data": {
                "balance": 10.0,
                "avAlgolable": 8.0,
                "total": 12.0,
                "locked": 2.0,
                "trade_protected": 1.0,
            }
        }

        result = balance_getter._process_direct_response(response)

        assert result["balance"] == 10.0
        assert result["avAlgolable_balance"] == 8.0
        assert result["total_balance"] == 12.0
        assert result["locked_balance"] == 2.0
        assert result["trade_protected_balance"] == 1.0
        assert result["error"] is False

    def test_process_minimal_response(self, balance_getter):
        """Test processing minimal direct response."""
        response = {
            "data": {
                "balance": 5.0,
            }
        }

        result = balance_getter._process_direct_response(response)

        assert result["balance"] == 5.0
        assert result["avAlgolable_balance"] == 5.0
        assert result["total_balance"] == 5.0


class TestGetBalanceEndpoints:
    """Tests for _get_balance_endpoints method."""

    def test_returns_correct_endpoints(self, balance_getter):
        """Test that method returns all expected endpoints."""
        endpoints = balance_getter._get_balance_endpoints()

        assert len(endpoints) == 4
        assert "/account/v1/balance" in endpoints
        assert "/api/v1/account/wallet/balance" in endpoints
        assert "/exchange/v1/user/balance" in endpoints
        assert "/api/v1/account/balance" in endpoints


class TestTryEndpointsForBalance:
    """Tests for _try_endpoints_for_balance method."""

    @pytest.mark.asyncio()
    async def test_first_endpoint_success(self, balance_getter, mock_api_client):
        """Test successful response from first endpoint."""
        mock_api_client._request.return_value = {
            "usd": {"amount": 1000, "avAlgolable": 800}
        }

        endpoints = ["/endpoint1", "/endpoint2"]
        response, endpoint, error = await balance_getter._try_endpoints_for_balance(
            endpoints
        )

        assert response is not None
        assert endpoint == "/endpoint1"
        assert error is None
        mock_api_client._request.assert_called_once()

    @pytest.mark.asyncio()
    async def test_fallback_to_second_endpoint(self, balance_getter, mock_api_client):
        """Test fallback to second endpoint after first fails."""
        mock_api_client._request.side_effect = [
            Exception("First endpoint failed"),
            {"usd": {"amount": 1000}},
        ]

        endpoints = ["/endpoint1", "/endpoint2"]
        response, endpoint, error = await balance_getter._try_endpoints_for_balance(
            endpoints
        )

        assert response is not None
        assert endpoint == "/endpoint2"
        assert error is None

    @pytest.mark.asyncio()
    async def test_all_endpoints_fail(self, balance_getter, mock_api_client):
        """Test when all endpoints fail."""
        mock_api_client._request.side_effect = Exception("All endpoints failed")

        endpoints = ["/endpoint1", "/endpoint2"]
        response, endpoint, error = await balance_getter._try_endpoints_for_balance(
            endpoints
        )

        assert response is None
        assert endpoint is None
        assert error is not None


class TestResponseHasError:
    """Tests for _response_has_error method."""

    def test_response_with_error_key(self, balance_getter):
        """Test response with error key."""
        response = {"error": "Some error"}
        assert balance_getter._response_has_error(response) is True

    def test_response_with_code_key(self, balance_getter):
        """Test response with code key."""
        response = {"code": "ERROR_CODE"}
        assert balance_getter._response_has_error(response) is True

    def test_valid_response(self, balance_getter):
        """Test valid response without errors."""
        response = {"usd": {"amount": 1000}}
        assert balance_getter._response_has_error(response) is False


class TestIsAuthError:
    """Tests for _is_auth_error method."""

    @pytest.mark.parametrize(
        ("error_code", "status_code", "expected"),
        (
            ("Unauthorized", 401, True),
            ("Unauthorized", 200, True),
            ("OTHER_ERROR", 401, True),
            ("OTHER_ERROR", 403, False),
            ("OTHER_ERROR", 500, False),
        ),
    )
    def test_auth_error_detection(
        self, balance_getter, error_code, status_code, expected
    ):
        """Test authentication error detection."""
        result = balance_getter._is_auth_error(error_code, status_code)
        assert result is expected


class TestParseBalanceFromResponse:
    """Tests for _parse_balance_from_response method."""

    def test_parse_usd_dict_format(self, balance_getter):
        """Test parsing USD dict format."""
        response = {"usd": {"amount": 1000, "avAlgolable": 800, "total": 1200}}

        amount, avAlgolable, total = balance_getter._parse_balance_from_response(response)

        assert amount == 1000
        assert avAlgolable == 800
        assert total == 1200

    def test_parse_balance_format(self, balance_getter):
        """Test parsing balance format."""
        response = {"balance": 1000, "avAlgolable": 800, "total": 1200}

        amount, avAlgolable, total = balance_getter._parse_balance_from_response(response)

        assert amount == 1000
        assert avAlgolable == 800
        assert total == 1200

    def test_parse_unknown_format(self, balance_getter):
        """Test parsing unknown format returns zeros."""
        response = {"unknown_field": "value"}

        amount, avAlgolable, total = balance_getter._parse_balance_from_response(response)

        assert amount == 0
        assert avAlgolable == 0
        assert total == 0


class TestCreateBalanceResponse:
    """Tests for _create_balance_response method."""

    def test_basic_balance_response(self, balance_getter):
        """Test creating basic balance response."""
        result = balance_getter._create_balance_response(
            usd_amount=1000, usd_avAlgolable=800, usd_total=1200
        )

        assert result["balance"] == 10.0
        assert result["avAlgolable_balance"] == 8.0
        assert result["total_balance"] == 12.0
        assert result["has_funds"] is True
        assert result["error"] is False

    def test_balance_with_locked(self, balance_getter):
        """Test balance response with locked balance."""
        result = balance_getter._create_balance_response(
            usd_amount=1000, usd_avAlgolable=800, usd_total=1200, locked_balance=2.0
        )

        assert result["locked_balance"] == 2.0

    def test_balance_with_additional_info(self, balance_getter):
        """Test balance response with additional info."""
        result = balance_getter._create_balance_response(
            usd_amount=1000,
            usd_avAlgolable=800,
            usd_total=1200,
            additional_info={"method": "direct", "endpoint": "/test"},
        )

        assert result["method"] == "direct"
        assert result["endpoint"] == "/test"


class TestDetermineStatusCode:
    """Tests for _determine_status_code method."""

    @pytest.mark.parametrize(
        ("error_message", "expected_code"),
        (
            ("404 Not Found", 404),
            ("Resource not found", 404),
            ("401 Unauthorized", 401),
            ("Unauthorized access", 401),
            ("Unknown error", 500),
        ),
    )
    def test_status_code_determination(
        self, balance_getter, error_message, expected_code
    ):
        """Test status code determination from error message."""
        code = balance_getter._determine_status_code(error_message)
        assert code == expected_code


class TestDetermineErrorCode:
    """Tests for _determine_error_code method."""

    @pytest.mark.parametrize(
        ("error_message", "expected_code"),
        (
            ("404 Not Found", "NOT_FOUND"),
            ("Resource not found", "NOT_FOUND"),
            ("401 Unauthorized", "UNAUTHORIZED"),
            ("Unauthorized access", "UNAUTHORIZED"),
            ("Unknown error", "REQUEST_FAlgoLED"),
        ),
    )
    def test_error_code_determination(
        self, balance_getter, error_message, expected_code
    ):
        """Test error code determination from error message."""
        code = balance_getter._determine_error_code(error_message)
        assert code == expected_code


class TestGetBalance:
    """Tests for main get_balance method."""

    @pytest.mark.asyncio()
    async def test_get_balance_without_credentials(self, balance_getter):
        """Test get_balance without valid credentials."""
        balance_getter.public_key = None
        balance_getter.secret_key = None

        result = await balance_getter.get_balance()

        assert result["error"] is True
        assert result["error_code"] == "MISSING_API_KEYS"

    @pytest.mark.asyncio()
    async def test_get_balance_via_direct_request(
        self, balance_getter, mock_api_client
    ):
        """Test successful balance retrieval via direct request."""
        mock_api_client.direct_balance_request.return_value = {
            "success": True,
            "data": {"balance": 10.0, "avAlgolable": 8.0, "total": 12.0},
        }

        result = await balance_getter.get_balance()

        assert result["error"] is False
        assert result["balance"] == 10.0
        assert result["avAlgolable_balance"] == 8.0

    @pytest.mark.asyncio()
    async def test_get_balance_fallback_to_internal(
        self, balance_getter, mock_api_client
    ):
        """Test fallback to internal endpoints when direct request fails."""
        mock_api_client.direct_balance_request.return_value = None
        mock_api_client._request.return_value = {
            "usd": {"amount": 1500, "avAlgolable": 1200}
        }

        result = await balance_getter.get_balance()

        assert result["error"] is False
        assert result["balance"] == 15.0

    @pytest.mark.asyncio()
    async def test_get_balance_handles_exception(self, balance_getter, mock_api_client):
        """Test that get_balance handles exceptions gracefully."""
        mock_api_client.direct_balance_request.side_effect = Exception("Critical error")
        mock_api_client._request.side_effect = Exception("Internal error")

        result = await balance_getter.get_balance()

        assert result["error"] is True
        assert result["error_code"] in {
            "EXCEPTION",
            "REQUEST_FAlgoLED",
        }  # Either is valid


class TestIntegration:
    """Integration tests for complete scenarios."""

    @pytest.mark.asyncio()
    async def test_full_flow_success_direct(self, balance_getter, mock_api_client):
        """Test complete successful flow with direct request."""
        mock_api_client.direct_balance_request.return_value = {
            "success": True,
            "data": {
                "balance": 25.50,
                "avAlgolable": 20.00,
                "total": 30.00,
                "locked": 5.00,
                "trade_protected": 0.50,
            },
        }

        result = await balance_getter.get_balance()

        assert result["error"] is False
        assert result["balance"] == 25.50
        assert result["avAlgolable_balance"] == 20.00
        assert result["total_balance"] == 30.00
        assert result["locked_balance"] == 5.00
        assert result["has_funds"] is True

    @pytest.mark.asyncio()
    async def test_full_flow_with_fallback(self, balance_getter, mock_api_client):
        """Test complete flow with fallback to internal endpoints."""
        # Direct request fails
        mock_api_client.direct_balance_request.return_value = {"success": False}

        # Internal endpoint succeeds
        mock_api_client._request.return_value = {
            "usd": {"amount": 3000, "avAlgolable": 2500, "total": 3500}
        }

        result = await balance_getter.get_balance()

        assert result["error"] is False
        assert result["balance"] == 30.0
        assert result["avAlgolable_balance"] == 25.0
        assert result["total_balance"] == 35.0
