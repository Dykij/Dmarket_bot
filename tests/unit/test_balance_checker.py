"""Tests for BalanceChecker module.

Phase 2: Code Readability Improvements - Task 9
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.balance_checker import BalanceChecker


@pytest.fixture()
def mock_api_client():
    """Create mock API client."""
    client = AsyncMock()
    client._request = AsyncMock()
    return client


@pytest.fixture()
def balance_checker(mock_api_client):
    """Create BalanceChecker instance."""
    return BalanceChecker(api_client=mock_api_client, min_required_balance=1.0)


class TestBalanceCheckerInitialization:
    """Tests for BalanceChecker initialization."""

    def test_initialization_with_default_minimum(self, mock_api_client):
        """Test initialization with default minimum balance."""
        checker = BalanceChecker(api_client=mock_api_client)
        assert checker.api_client is mock_api_client
        assert checker.min_required_balance == 1.0

    def test_initialization_with_custom_minimum(self, mock_api_client):
        """Test initialization with custom minimum balance."""
        checker = BalanceChecker(api_client=mock_api_client, min_required_balance=5.0)
        assert checker.min_required_balance == 5.0


class TestFetchBalance:
    """Tests for _fetch_balance method."""

    @pytest.mark.asyncio()
    async def test_fetch_balance_calls_api_correctly(
        self, balance_checker, mock_api_client
    ):
        """Test that fetch_balance calls API with correct parameters."""
        mock_api_client._request.return_value = {
            "usd": {"avAlgolable": 1000, "frozen": 0}
        }

        result = await balance_checker._fetch_balance()

        mock_api_client._request.assert_called_once_with(
            method="GET",
            path="/account/v1/balance",
            params={},
        )
        assert result is not None


class TestProcessBalanceResponse:
    """Tests for _process_balance_response method."""

    def test_empty_response_returns_error(self, balance_checker):
        """Test that empty response returns error result."""
        result = balance_checker._process_balance_response(None)

        assert result["error"] is True
        assert result["diagnosis"] == "api_error"
        assert result["has_funds"] is False
        assert "пустой ответ" in result["display_message"].lower()

    def test_invalid_response_type_returns_error(self, balance_checker):
        """Test that invalid response type returns error."""
        result = balance_checker._process_balance_response("invalid")

        assert result["error"] is True
        assert result["diagnosis"] == "unknown_error"
        assert result["has_funds"] is False

    def test_response_with_error_handled(self, balance_checker):
        """Test that response with error is handled correctly."""
        error_response = {"error": True, "message": "Unauthorized"}

        result = balance_checker._process_balance_response(error_response)

        assert result["error"] is True
        assert result["has_funds"] is False
        assert "Unauthorized" in result["error_message"]

    def test_success_response_processed(self, balance_checker):
        """Test that successful response is processed correctly."""
        success_response = {
            "usd": {
                "avAlgolable": 500,  # $5.00
                "frozen": 100,  # $1.00
            }
        }

        result = balance_checker._process_balance_response(success_response)

        assert result["error"] is False
        assert result["avAlgolable_balance"] == 5.0
        assert result["frozen_balance"] == 1.0
        assert result["total_balance"] == 6.0
        assert result["has_funds"] is True


class TestHasError:
    """Tests for _has_error method."""

    def test_has_error_with_error_key(self, balance_checker):
        """Test _has_error returns True when error key present."""
        response = {"error": True}
        assert balance_checker._has_error(response) is True

    def test_has_error_with_missing_usd(self, balance_checker):
        """Test _has_error returns True when usd key missing."""
        response = {"other": "data"}
        assert balance_checker._has_error(response) is True

    def test_has_error_with_valid_response(self, balance_checker):
        """Test _has_error returns False for valid response."""
        response = {"usd": {"avAlgolable": 100, "frozen": 0}}
        assert balance_checker._has_error(response) is False


class TestDiagnoseError:
    """Tests for _diagnose_error method."""

    @pytest.mark.parametrize(
        ("error_message", "expected_diagnosis"),
        (
            ("Unauthorized access", "auth_error"),
            ("Ошибка авторизации", "auth_error"),
            ("Missing API key", "missing_keys"),
            ("Отсутствуют ключи", "missing_keys"),
            ("Request timeout", "timeout_error"),
            ("Превышено время ожидания", "timeout_error"),
            ("404 Not Found", "endpoint_error"),
            ("Эндпоинт не найден", "endpoint_error"),
            ("Unknown error", "unknown_error"),
        ),
    )
    def test_diagnose_various_errors(
        self, balance_checker, error_message, expected_diagnosis
    ):
        """Test error diagnosis for various error messages."""
        diagnosis = balance_checker._diagnose_error(error_message)
        assert diagnosis == expected_diagnosis


class TestGetErrorDisplayMessage:
    """Tests for _get_error_display_message method."""

    @pytest.mark.parametrize(
        ("diagnosis", "expected_contains"),
        (
            ("auth_error", "авторизации"),
            ("missing_keys", "ключи"),
            ("timeout_error", "Таймаут"),
            ("endpoint_error", "эндпоинт"),
            ("unknown_error", "Ошибка"),
        ),
    )
    def test_display_messages_for_diagnoses(
        self, balance_checker, diagnosis, expected_contains
    ):
        """Test display messages contain expected text."""
        message = balance_checker._get_error_display_message(diagnosis)
        assert expected_contains.lower() in message.lower()


class TestCreateSuccessResult:
    """Tests for _create_success_result method."""

    def test_success_result_with_sufficient_funds(self, balance_checker):
        """Test success result when user has sufficient funds."""
        response = {
            "usd": {
                "avAlgolable": 500,  # $5.00
                "frozen": 0,
            }
        }

        result = balance_checker._create_success_result(response)

        assert result["error"] is False
        assert result["has_funds"] is True
        assert result["avAlgolable_balance"] == 5.0
        assert result["diagnosis"] == "sufficient_funds"
        assert "достаточно" in result["display_message"]

    def test_success_result_with_zero_balance(self, balance_checker):
        """Test success result when balance is zero."""
        response = {
            "usd": {
                "avAlgolable": 0,
                "frozen": 0,
            }
        }

        result = balance_checker._create_success_result(response)

        assert result["error"] is False
        assert result["has_funds"] is False
        assert result["avAlgolable_balance"] == 0.0
        assert result["diagnosis"] == "zero_balance"
        assert "нет средств" in result["display_message"]

    def test_success_result_with_insufficient_funds(self, balance_checker):
        """Test success result with insufficient but non-zero balance."""
        response = {
            "usd": {
                "avAlgolable": 50,  # $0.50
                "frozen": 0,
            }
        }

        result = balance_checker._create_success_result(response)

        assert result["error"] is False
        assert result["has_funds"] is False
        assert result["avAlgolable_balance"] == 0.5
        assert result["diagnosis"] == "insufficient_funds"
        assert "Недостаточно" in result["display_message"]

    def test_success_result_with_frozen_balance(self, balance_checker):
        """Test success result includes frozen balance info."""
        response = {
            "usd": {
                "avAlgolable": 50,  # $0.50
                "frozen": 200,  # $2.00
            }
        }

        result = balance_checker._create_success_result(response)

        assert result["frozen_balance"] == 2.0
        assert result["diagnosis"] == "funds_frozen"
        assert "Заблокировано" in result["display_message"]


class TestCreateDisplayInfo:
    """Tests for _create_display_info method."""

    def test_display_info_for_sufficient_funds(self, balance_checker):
        """Test display info when funds are sufficient."""
        diagnosis, message = balance_checker._create_display_info(
            has_funds=True, avAlgolable_balance=5.0, frozen_balance=0.0
        )

        assert diagnosis == "sufficient_funds"
        assert "$5.00" in message
        assert "достаточно" in message

    def test_display_info_for_zero_balance(self, balance_checker):
        """Test display info for zero balance."""
        diagnosis, message = balance_checker._create_display_info(
            has_funds=False, avAlgolable_balance=0.0, frozen_balance=0.0
        )

        assert diagnosis == "zero_balance"
        assert "нет средств" in message

    def test_display_info_for_insufficient_with_frozen(self, balance_checker):
        """Test display info for insufficient funds with frozen balance."""
        diagnosis, message = balance_checker._create_display_info(
            has_funds=False, avAlgolable_balance=0.5, frozen_balance=2.0
        )

        assert diagnosis == "funds_frozen"
        assert "Недостаточно" in message
        assert "Заблокировано" in message


class TestCreateErrorResult:
    """Tests for _create_error_result method."""

    def test_error_result_structure(self, balance_checker):
        """Test that error result has correct structure."""
        result = balance_checker._create_error_result(
            error_message="Test error",
            display_message="User message",
            diagnosis="test_diagnosis",
        )

        assert result["error"] is True
        assert result["has_funds"] is False
        assert result["error_message"] == "Test error"
        assert result["display_message"] == "User message"
        assert result["diagnosis"] == "test_diagnosis"
        assert result["balance"] == 0.0


class TestCreateExceptionResult:
    """Tests for _create_exception_result method."""

    def test_exception_result_logs_and_returns_error(self, balance_checker):
        """Test that exception result logs error and returns error dict."""
        exception = ValueError("Test exception")

        result = balance_checker._create_exception_result(exception)

        assert result["error"] is True
        assert result["diagnosis"] == "exception"
        assert "Test exception" in result["error_message"]
        assert "Test exception" in result["display_message"]


class TestCheckBalance:
    """Tests for main check_balance method."""

    @pytest.mark.asyncio()
    async def test_check_balance_success_flow(self, balance_checker, mock_api_client):
        """Test successful balance check flow."""
        mock_api_client._request.return_value = {
            "usd": {
                "avAlgolable": 1000,  # $10.00
                "frozen": 0,
            }
        }

        result = await balance_checker.check_balance()

        assert result["error"] is False
        assert result["has_funds"] is True
        assert result["avAlgolable_balance"] == 10.0

    @pytest.mark.asyncio()
    async def test_check_balance_handles_exception(
        self, balance_checker, mock_api_client
    ):
        """Test that check_balance handles exceptions gracefully."""
        mock_api_client._request.side_effect = Exception("Network error")

        result = await balance_checker.check_balance()

        assert result["error"] is True
        assert result["diagnosis"] == "exception"
        assert "Network error" in result["error_message"]

    @pytest.mark.asyncio()
    async def test_check_balance_with_custom_minimum(self, mock_api_client):
        """Test balance check with custom minimum balance."""
        checker = BalanceChecker(api_client=mock_api_client, min_required_balance=10.0)
        mock_api_client._request.return_value = {
            "usd": {
                "avAlgolable": 500,  # $5.00
                "frozen": 0,
            }
        }

        result = await checker.check_balance()

        assert result["has_funds"] is False
        assert result["min_required"] == 10.0
        assert result["diagnosis"] == "insufficient_funds"


class TestIntegration:
    """Integration tests for complete scenarios."""

    @pytest.mark.asyncio()
    async def test_full_flow_with_api_error(self, balance_checker, mock_api_client):
        """Test complete flow when API returns error."""
        mock_api_client._request.return_value = {
            "error": True,
            "message": "Unauthorized access",
        }

        result = await balance_checker.check_balance()

        assert result["error"] is True
        assert result["diagnosis"] == "auth_error"
        assert "авторизации" in result["display_message"]

    @pytest.mark.asyncio()
    async def test_full_flow_with_empty_response(
        self, balance_checker, mock_api_client
    ):
        """Test complete flow when API returns empty response."""
        mock_api_client._request.return_value = None

        result = await balance_checker.check_balance()

        assert result["error"] is True
        assert result["diagnosis"] == "api_error"

    @pytest.mark.asyncio()
    async def test_full_flow_with_valid_balance(self, balance_checker, mock_api_client):
        """Test complete flow with valid balance data."""
        mock_api_client._request.return_value = {
            "usd": {
                "avAlgolable": 2500,  # $25.00
                "frozen": 500,  # $5.00
            }
        }

        result = await balance_checker.check_balance()

        assert result["error"] is False
        assert result["has_funds"] is True
        assert result["avAlgolable_balance"] == 25.0
        assert result["frozen_balance"] == 5.0
        assert result["total_balance"] == 30.0
        assert result["diagnosis"] == "sufficient_funds"
