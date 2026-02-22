"""Unit tests for DirectBalanceRequester.

Tests the refactored direct balance request functionality.
Phase 2 - Week 3-4
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.direct_balance_requester import DirectBalanceRequester


@pytest.fixture()
def mock_client_func():
    """Mock client getter function."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()

    async def get_client():
        return mock_client

    return get_client


@pytest.fixture()
def requester(mock_client_func):
    """DirectBalanceRequester instance."""
    return DirectBalanceRequester(
        api_url="https://api.dmarket.com",
        public_key="test_public_key",
        secret_key="a" * 64,  # 64 char hex key
        get_client_func=mock_client_func,
    )


@pytest.fixture()
def sample_balance_response():
    """Sample successful balance response."""
    return {
        "usd": "2550",  # $25.50 in cents
        "usdAvAlgolableToWithdraw": "2000",  # $20.00
        "usdTradeProtected": "500",  # $5.00
        "dmc": "0",
        "dmcAvAlgolableToWithdraw": "0",
    }


class TestDirectBalanceRequesterInitialization:
    """Test requester initialization."""

    def test_init_stores_credentials(self, mock_client_func):
        """Test initialization stores credentials correctly."""
        requester = DirectBalanceRequester(
            api_url="https://test.com",
            public_key="pub_key",
            secret_key="secret_key",
            get_client_func=mock_client_func,
        )

        assert requester.api_url == "https://test.com"
        assert requester.public_key == "pub_key"
        assert requester._secret_key == "secret_key"
        assert requester._get_client == mock_client_func


class TestBalanceRequest:
    """Test main balance request functionality."""

    @pytest.mark.asyncio()
    async def test_successful_balance_request(
        self, requester, mock_client_func, sample_balance_response
    ):
        """Test successful balance request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_balance_response

        await mock_client_func()

        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            return_value=mock_response,
        ):
            result = await requester.request()

        assert result["success"] is True
        assert "data" in result
        assert result["data"]["balance"] == 25.50
        assert result["data"]["avAlgolable"] == 20.00
        assert result["data"]["trade_protected"] == 5.00
        assert result["data"]["locked"] == 0.50

    @pytest.mark.asyncio()
    async def test_request_with_401_error(self, requester, mock_client_func):
        """Test request with authentication error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            return_value=mock_response,
        ):
            result = await requester.request()

        assert result["success"] is False
        assert result["status_code"] == 401
        assert "Authentication error" in result["error"]

    @pytest.mark.asyncio()
    async def test_request_with_http_error(self, requester, mock_client_func):
        """Test request with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            return_value=mock_response,
        ):
            result = await requester.request()

        assert result["success"] is False
        assert result["status_code"] == 500
        assert "HTTP 500" in result["error"]

    @pytest.mark.asyncio()
    async def test_request_with_json_decode_error(self, requester, mock_client_func):
        """Test request with JSON decode error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("error", "", 0)
        mock_response.text = "invalid json"

        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            return_value=mock_response,
        ):
            result = await requester.request()

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio()
    async def test_request_with_circuit_breaker_error(self, requester):
        """Test request with circuit breaker error."""
        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            side_effect=Exception("Circuit breaker open"),
        ):
            result = await requester.request()

        assert result["success"] is False
        assert "error" in result


class TestSignatureGeneration:
    """Test signature generation methods."""

    def test_generate_signature_with_ed25519(self, requester):
        """Test signature generation with Ed25519."""
        timestamp = "1234567890"

        with patch.object(requester, "_sign_with_ed25519", return_value="test_sig"):
            signature = requester._generate_signature(timestamp)

        assert signature == "test_sig"

    def test_generate_signature_fallback_to_hmac(self, requester):
        """Test signature falls back to HMAC if Ed25519 fails."""
        timestamp = "1234567890"

        with patch.object(
            requester, "_sign_with_ed25519", side_effect=Exception("Ed25519 error")
        ), patch.object(requester, "_sign_with_hmac", return_value="hmac_sig"):
            signature = requester._generate_signature(timestamp)

        assert signature == "hmac_sig"

    def test_sign_with_hmac(self, requester):
        """Test HMAC-SHA256 signing."""
        message = "test_message"

        signature = requester._sign_with_hmac(message)

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex = 64 chars


class TestSecretKeyParsing:
    """Test secret key parsing from different formats."""

    def test_parse_hex_key_64_chars(self):
        """Test parsing 64-char hex key."""
        requester = DirectBalanceRequester(
            api_url="test",
            public_key="test",
            secret_key="a" * 64,
            get_client_func=AsyncMock(),
        )

        key_bytes = requester._parse_secret_key()

        assert len(key_bytes) == 32
        assert key_bytes == bytes.fromhex("a" * 64)

    def test_parse_base64_key(self):
        """Test parsing base64 key."""
        import base64

        test_bytes = b"a" * 32
        b64_key = base64.b64encode(test_bytes).decode()

        requester = DirectBalanceRequester(
            api_url="test",
            public_key="test",
            secret_key=b64_key,
            get_client_func=AsyncMock(),
        )

        key_bytes = requester._parse_secret_key()

        assert key_bytes == test_bytes

    def test_parse_long_hex_key(self):
        """Test parsing key longer than 64 chars (takes first 64)."""
        requester = DirectBalanceRequester(
            api_url="test",
            public_key="test",
            secret_key="a" * 128,  # 128 chars
            get_client_func=AsyncMock(),
        )

        key_bytes = requester._parse_secret_key()

        assert len(key_bytes) == 32
        assert key_bytes == bytes.fromhex("a" * 64)

    def test_parse_short_key_fallback(self):
        """Test fallback for short key (pads to 32 bytes)."""
        requester = DirectBalanceRequester(
            api_url="test",
            public_key="test",
            secret_key="short",
            get_client_func=AsyncMock(),
        )

        key_bytes = requester._parse_secret_key()

        assert len(key_bytes) == 32
        assert key_bytes.startswith(b"short")


class TestBalanceDataParsing:
    """Test balance data parsing."""

    def test_parse_valid_balance_data(self, requester):
        """Test parsing valid balance data."""
        response_data = {
            "usd": "10000",  # $100.00
            "usdAvAlgolableToWithdraw": "8000",  # $80.00
            "usdTradeProtected": "1500",  # $15.00
        }

        balance_data = requester._parse_balance_data(response_data)

        assert balance_data["balance"] == 100.0
        assert balance_data["avAlgolable"] == 80.0
        assert balance_data["trade_protected"] == 15.0
        assert balance_data["locked"] == 5.0  # 100 - 80 - 15
        assert balance_data["total"] == 100.0

    def test_parse_balance_with_missing_fields(self, requester):
        """Test parsing with missing fields (defaults to 0)."""
        response_data = {}

        balance_data = requester._parse_balance_data(response_data)

        assert balance_data["balance"] == 0.0
        assert balance_data["avAlgolable"] == 0.0
        assert balance_data["total"] == 0.0

    def test_parse_balance_with_invalid_values(self, requester):
        """Test parsing with invalid numeric values."""
        response_data = {
            "usd": "invalid",
            "usdAvAlgolableToWithdraw": "not_a_number",
        }

        balance_data = requester._parse_balance_data(response_data)

        # Should return zeros on error
        assert balance_data["balance"] == 0.0
        assert balance_data["avAlgolable"] == 0.0


class TestRequestPreparation:
    """Test request preparation."""

    def test_prepare_request_returns_url_and_headers(self, requester):
        """Test request preparation returns URL and headers."""
        with patch.object(requester, "_generate_signature", return_value="test_sig"):
            url, headers = requester._prepare_request()

        assert url == "https://api.dmarket.com/account/v1/balance"
        assert headers["X-Api-Key"] == "test_public_key"
        assert headers["X-Request-Sign"] == "dmar ed25519 test_sig"
        assert "X-Sign-Date" in headers
        assert headers["Accept"] == "application/json"


class TestErrorResults:
    """Test error result methods."""

    def test_auth_error_result(self, requester):
        """Test authentication error result."""
        result = requester._auth_error_result()

        assert result["success"] is False
        assert result["status_code"] == 401
        assert "Authentication error" in result["error"]

    def test_http_error_result(self, requester):
        """Test HTTP error result."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        result = requester._http_error_result(mock_response)

        assert result["success"] is False
        assert result["status_code"] == 500
        assert "HTTP 500" in result["error"]

    def test_generic_error_result(self, requester):
        """Test generic error result."""
        result = requester._error_result("Test error")

        assert result["success"] is False
        assert result["error"] == "Test error"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio()
    async def test_request_with_empty_response(self, requester, mock_client_func):
        """Test request with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch(
            "src.dmarket.direct_balance_requester.call_with_circuit_breaker",
            return_value=mock_response,
        ):
            result = await requester.request()

        assert result["success"] is False

    def test_parse_balance_with_zero_values(self, requester):
        """Test parsing balance with all zero values."""
        response_data = {
            "usd": "0",
            "usdAvAlgolableToWithdraw": "0",
            "usdTradeProtected": "0",
        }

        balance_data = requester._parse_balance_data(response_data)

        assert balance_data["balance"] == 0.0
        assert balance_data["avAlgolable"] == 0.0
        assert balance_data["locked"] == 0.0

    def test_parse_balance_with_negative_locked(self, requester):
        """Test parsing when calculated locked is negative."""
        response_data = {
            "usd": "1000",  # $10.00
            "usdAvAlgolableToWithdraw": "1500",  # $15.00 (more than total)
            "usdTradeProtected": "0",
        }

        balance_data = requester._parse_balance_data(response_data)

        # locked = 10 - 15 - 0 = -5
        assert balance_data["locked"] == -5.0
