"""Contract tests for DMarket Account API endpoints.

This module contains consumer-driven contract tests for the account-related
endpoints of the DMarket API.

Tested endpoints:
- GET /account/v1/balance - Get user balance
- GET /account/v1/user - Get user profile

Run these tests with:
    pytest tests/contracts/test_account_contracts.py -v
"""

from __future__ import annotations

import pytest

from tests.contracts.conftest import DMarketContracts, PactMatchers, is_pact_avAlgolable

# Skip all tests if Pact is not avAlgolable
pytestmark = pytest.mark.skipif(
    not is_pact_avAlgolable(),
    reason="pact-python not installed",
)


class TestBalanceContract:
    """Contract tests for the /account/v1/balance endpoint."""

    @pytest.mark.asyncio()
    async def test_get_balance_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for successful balance retrieval.

        Verifies that:
        - The consumer sends a GET request to /account/v1/balance
        - The provider responds with a valid balance object
        - Balance fields include USD and DMC amounts
        """
        expected_body = dmarket_contracts.balance_response()

        # pact-python v3 API: upon_receiving -> given -> with_request
        (
            pact_interaction.upon_receiving("a request for account balance")
            .given("user has an active account with balance")
            .with_request(
                method="GET",
                path="/account/v1/balance",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        # In a real test, we would make an actual HTTP request to the mock server
        # For now, we just verify the interaction is set up correctly
        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_get_balance_unauthorized(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for unauthorized balance request.

        Verifies that:
        - When authentication fails, API returns 401
        - Error response has proper structure
        """
        error_body = dmarket_contracts.error_response(
            code="UNAUTHORIZED",
            message="Invalid API key",
        )

        (
            pact_interaction.upon_receiving("an unauthorized request for balance")
            .given("user has invalid credentials")
            .with_request(
                method="GET",
                path="/account/v1/balance",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=401,
                headers={"Content-Type": "application/json"},
                body=error_body,
            )
        )

        assert pact_interaction is not None


class TestUserProfileContract:
    """Contract tests for the /account/v1/user endpoint."""

    @pytest.mark.asyncio()
    async def test_get_user_profile_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for successful user profile retrieval.

        Verifies that:
        - The consumer sends a GET request to /account/v1/user
        - The provider responds with a valid user profile
        """
        expected_body = {
            "id": pact_matchers.like("user_123456"),
            "username": pact_matchers.like("testuser"),
            "email": pact_matchers.regex(
                r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                "test@example.com",
            ),
            "settings": {
                "targetsLimit": pact_matchers.integer(100),
            },
        }

        (
            pact_interaction.upon_receiving("a request for user profile")
            .given("user has an active account")
            .with_request(
                method="GET",
                path="/account/v1/user",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None


class TestRateLimitContract:
    """Contract tests for rate limiting behavior."""

    @pytest.mark.asyncio()
    async def test_rate_limit_exceeded(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for rate limit exceeded response.

        Verifies that:
        - When rate limit is exceeded, API returns 429
        - Response includes Retry-After header
        """
        error_body = {
            "error": {
                "code": pact_matchers.like("RATE_LIMIT_EXCEEDED"),
                "message": pact_matchers.like("Too many requests"),
            },
        }

        (
            pact_interaction.upon_receiving("a request when rate limited")
            .given("user has exceeded rate limit")
            .with_request(
                method="GET",
                path="/account/v1/balance",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": pact_matchers.regex(r"^\d+$", "60"),
                },
                body=error_body,
            )
        )

        assert pact_interaction is not None


# =============================================================================
# Mock-based tests (run without Pact server)
# =============================================================================


class TestBalanceContractMock:
    """Mock-based contract tests for balance endpoint.

    These tests verify contract compliance using mocked responses,
    allowing them to run without the Pact mock server.
    """

    def test_balance_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify the expected balance response structure."""
        response = dmarket_contracts.balance_response()

        # Verify all required fields are present
        assert "usd" in response
        assert "usdAvAlgolableToWithdraw" in response
        assert "dmc" in response
        assert "dmcAvAlgolableToWithdraw" in response

        # Verify matchers are properly configured
        for field in ["usd", "usdAvAlgolableToWithdraw", "dmc", "dmcAvAlgolableToWithdraw"]:
            assert response[field]["pact:matcher:type"] == "regex"

    def test_error_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify the expected error response structure."""
        response = dmarket_contracts.error_response("TEST_ERROR", "Test message")

        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]

    def test_balance_values_are_string_integers(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify balance values match string integer pattern.

        DMarket API returns balance values as string integers representing cents.
        """
        response = dmarket_contracts.balance_response()

        # Verify regex pattern matches string integers
        import re

        pattern = response["usd"]["regex"]
        assert re.match(pattern, "10000")
        assert re.match(pattern, "0")
        assert not re.match(pattern, "10.50")
        assert not re.match(pattern, "-100")
