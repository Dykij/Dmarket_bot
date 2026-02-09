"""Pact contract testing fixtures and configuration.

This module provides pytest fixtures for consumer-driven contract testing
using Pact. It configures the Pact mock server and provides helpers for
creating contract expectations.

Usage:
    @pytest.mark.asyncio()
    async def test_get_balance(pact: Pact):
        # Setup expectation
        (pact
            .upon_receiving("a request for user balance")
            .with_request("GET", "/account/v1/balance")
            .will_respond_with(200, body=expected_balance))

        # Make request to Pact mock server
        async with pact:
            result = await api_client.get_balance()
            assert result["balance"] >= 0

For more information:
- Pact documentation: https://docs.pact.io/
- Contract Testing Guide: docs/CONTRACT_TESTING.md
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Pact configuration constants
PACT_MOCK_HOST = "localhost"
PACT_MOCK_PORT = 1234
PACT_DIR = Path(__file__).parent / "pacts"
PACT_LOG_DIR = Path(__file__).parent / "logs"

# Consumer and Provider names
CONSUMER_NAME = "DMarketTelegramBot"
PROVIDER_NAME = "DMarketAPI"

# DMarket API version being tested
API_VERSION = "v1"


def ensure_pact_directories() -> None:
    """Ensure Pact output directories exist."""
    PACT_DIR.mkdir(parents=True, exist_ok=True)
    PACT_LOG_DIR.mkdir(parents=True, exist_ok=True)


# Create directories at module load
ensure_pact_directories()


# ============================================================================
# Pact Response Matchers (for flexible contract matching)
# ============================================================================


class PactMatchers:
    """Helper class for Pact matching rules.

    These matchers allow flexible contract verification without
    requiring exact value matches.
    """

    @staticmethod
    def like(example: Any) -> dict[str, Any]:
        """Match any value of the same type as the example.

        Args:
            example: An example value to match the type of

        Returns:
            Pact matcher dict

        Example:
            >>> PactMatchers.like(100)  # Matches any integer
            >>> PactMatchers.like("test")  # Matches any string
        """
        return {"pact:matcher:type": "type", "value": example}

    @staticmethod
    def each_like(example: Any, minimum: int = 1) -> dict[str, Any]:
        """Match an array where each element is like the example.

        Args:
            example: Example element to match against
            minimum: Minimum number of elements in array

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "type",
            "value": [example],
            "min": minimum,
        }

    @staticmethod
    def regex(pattern: str, example: str) -> dict[str, Any]:
        """Match a string against a regex pattern.

        Args:
            pattern: Regex pattern to match
            example: Example value that matches the pattern

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "regex",
            "regex": pattern,
            "value": example,
        }

    @staticmethod
    def decimal(example: float) -> dict[str, Any]:
        """Match a decimal number.

        Args:
            example: Example decimal value

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "decimal",
            "value": example,
        }

    @staticmethod
    def integer(example: int) -> dict[str, Any]:
        """Match an integer.

        Args:
            example: Example integer value

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "integer",
            "value": example,
        }

    @staticmethod
    def include(substring: str) -> dict[str, Any]:
        """Match a string that includes the substring.

        Args:
            substring: Substring to find

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "include",
            "value": substring,
        }

    @staticmethod
    def uuid(example: str = "ce118b6e-d8e1-11e7-9296-cec278b6b50a") -> dict[str, Any]:
        """Match a UUID string.

        Args:
            example: Example UUID value

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "regex",
            "regex": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            "value": example,
        }

    @staticmethod
    def iso8601_datetime(
        example: str = "2025-01-15T12:00:00Z",
    ) -> dict[str, Any]:
        """Match an ISO8601 datetime string.

        Args:
            example: Example datetime value

        Returns:
            Pact matcher dict
        """
        return {
            "pact:matcher:type": "regex",
            "regex": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$",
            "value": example,
        }


# ============================================================================
# Expected Response Bodies (Contract Definitions)
# ============================================================================


class DMarketContracts:
    """DMarket API contract definitions.

    These define the expected structure of API responses for contract testing.
    """

    @staticmethod
    def balance_response() -> dict[str, Any]:
        """Expected response for GET /account/v1/balance.

        Returns:
            Expected response body with matchers
        """
        return {
            "usd": PactMatchers.regex(r"^\d+$", "10000"),
            "usdAvailableToWithdraw": PactMatchers.regex(r"^\d+$", "9000"),
            "dmc": PactMatchers.regex(r"^\d+$", "5000"),
            "dmcAvailableToWithdraw": PactMatchers.regex(r"^\d+$", "4500"),
        }

    @staticmethod
    def market_items_response() -> dict[str, Any]:
        """Expected response for GET /exchange/v1/market/items.

        Returns:
            Expected response body with matchers
        """
        return {
            "cursor": PactMatchers.like("next_page_cursor"),
            "objects": PactMatchers.each_like(
                {
                    "itemId": PactMatchers.like("item_12345"),
                    "title": PactMatchers.like("AK-47 | Redline (Field-Tested)"),
                    "price": {
                        "USD": PactMatchers.regex(r"^\d+$", "1250"),
                    },
                    "suggestedPrice": {
                        "USD": PactMatchers.regex(r"^\d+$", "1300"),
                    },
                    "imageUrl": PactMatchers.regex(
                        r"^https?://", "https://example.com/img.png"
                    ),
                    "extra": {
                        "category": PactMatchers.like("Rifle"),
                        "exterior": PactMatchers.like("Field-Tested"),
                        "rarity": PactMatchers.like("Classified"),
                    },
                },
                minimum=0,
            ),
            "total": PactMatchers.integer(100),
        }

    @staticmethod
    def user_targets_response() -> dict[str, Any]:
        """Expected response for GET /marketplace-api/v1/user-targets.

        Returns:
            Expected response body with matchers
        """
        return {
            "Items": PactMatchers.each_like(
                {
                    "TargetID": PactMatchers.like("target_123"),
                    "Title": PactMatchers.like("AK-47 | Redline (Field-Tested)"),
                    "Amount": PactMatchers.integer(1),
                    "Price": {
                        "Amount": PactMatchers.integer(1200),
                        "Currency": PactMatchers.regex(r"^(USD|EUR|DMC)$", "USD"),
                    },
                    "Status": PactMatchers.regex(
                        r"^(TargetStatusActive|TargetStatusInactive)$",
                        "TargetStatusActive",
                    ),
                    "CreatedAt": PactMatchers.integer(1699876543),
                },
                minimum=0,
            ),
            "Total": PactMatchers.regex(r"^\d+$", "10"),
            "Cursor": PactMatchers.like("cursor_token"),
        }

    @staticmethod
    def create_targets_response() -> dict[str, Any]:
        """Expected response for POST /marketplace-api/v1/user-targets/create.

        Returns:
            Expected response body with matchers
        """
        return {
            "Result": PactMatchers.each_like(
                {
                    "TargetID": PactMatchers.like("new_target_123"),
                    "Title": PactMatchers.like("AK-47 | Redline (Field-Tested)"),
                    "Status": PactMatchers.regex(
                        r"^(Created|Updated|Error)$", "Created"
                    ),
                },
                minimum=1,
            ),
        }

    @staticmethod
    def user_inventory_response() -> dict[str, Any]:
        """Expected response for GET /marketplace-api/v1/user-inventory.

        Returns:
            Expected response body with matchers
        """
        return {
            "Items": PactMatchers.each_like(
                {
                    "ItemID": PactMatchers.like("inv_item_123"),
                    "Title": PactMatchers.like("AK-47 | Redline (Field-Tested)"),
                    "Image": PactMatchers.regex(
                        r"^https?://", "https://example.com/img.png"
                    ),
                    "Price": {
                        "USD": PactMatchers.regex(r"^\d+$", "1300"),
                    },
                    "InMarket": PactMatchers.like(False),
                    "Attributes": {
                        "exterior": PactMatchers.like("Field-Tested"),
                        "floatValue": PactMatchers.like("0.25"),
                    },
                },
                minimum=0,
            ),
            "Total": PactMatchers.regex(r"^\d+$", "5"),
            "Cursor": PactMatchers.like("cursor_token"),
        }

    @staticmethod
    def aggregated_prices_response() -> dict[str, Any]:
        """Expected response for POST /marketplace-api/v1/aggregated-prices.

        Returns:
            Expected response body with matchers
        """
        return {
            "aggregatedPrices": PactMatchers.each_like(
                {
                    "title": PactMatchers.like("AK-47 | Redline (Field-Tested)"),
                    "orderBestPrice": PactMatchers.regex(r"^\d+$", "1200"),
                    "orderCount": PactMatchers.integer(15),
                    "offerBestPrice": PactMatchers.regex(r"^\d+$", "1250"),
                    "offerCount": PactMatchers.integer(23),
                },
                minimum=0,
            ),
            "nextCursor": PactMatchers.like(""),
        }

    @staticmethod
    def error_response(
        code: str = "ERROR", message: str = "An error occurred"
    ) -> dict[str, Any]:
        """Expected error response structure.

        Args:
            code: Error code
            message: Error message

        Returns:
            Expected error response body
        """
        return {
            "error": {
                "code": PactMatchers.like(code),
                "message": PactMatchers.like(message),
            },
        }


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def pact_dir() -> Path:
    """Return the directory for Pact contract files."""
    ensure_pact_directories()
    return PACT_DIR


@pytest.fixture(scope="session")
def pact_log_dir() -> Path:
    """Return the directory for Pact log files."""
    ensure_pact_directories()
    return PACT_LOG_DIR


@pytest.fixture()
def pact_matchers() -> type[PactMatchers]:
    """Provide access to Pact matchers."""
    return PactMatchers


@pytest.fixture()
def dmarket_contracts() -> type[DMarketContracts]:
    """Provide access to DMarket contract definitions."""
    return DMarketContracts


@pytest.fixture()
def mock_pact_server_url() -> str:
    """Return the Pact mock server URL for tests.

    This fixture provides a consistent URL for tests to use when
    connecting to the Pact mock server.
    """
    return f"http://{PACT_MOCK_HOST}:{PACT_MOCK_PORT}"


@pytest.fixture()
def pact_headers() -> dict[str, str]:
    """Return common headers used in DMarket API requests.

    Note: Actual authentication headers (X-Api-Key, X-Sign-Date, X-Request-Sign)
    should be mocked/ignored in contract tests as they are implementation details.
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ============================================================================
# Pact Consumer Setup (requires pact-python v3)
# ============================================================================

# Note: The actual Pact consumer setup is conditional on pact-python being installed.
# This allows the test infrastructure to load without errors if pact isn't installed.
# pact-python v3 uses a new API with Pact class directly instead of Consumer/Provider.

try:
    from pact import Pact

    PACT_AVAILABLE = True

    class PactInteractionBuilder:
        """Compatibility wrapper for pact-python v3 API.

        This class provides a v2-style API that wraps v3 methods.
        The v2 API used:
            .given(...).upon_receiving(...)
            .with_request(method=..., path=..., headers=..., query=..., body=...)
            .will_respond_with(status=..., headers=..., body=...)

        The v3 API uses chainable methods:
            .upon_receiving(...).given(...)
            .with_request(method, path)
            .with_headers(...).with_query_parameters(...).with_body(...)
            .will_respond_with(status)
            .with_headers(...).with_body(...)
        """

        def __init__(self, pact_instance: Pact) -> None:
            self._pact = pact_instance
            self._interaction = None
            self._description: str | None = None
            self._provider_state: str | None = None

        def upon_receiving(self, description: str) -> PactInteractionBuilder:
            """Set the interaction description (v3 API: call first)."""
            self._description = description
            return self

        def given(self, provider_state: str) -> PactInteractionBuilder:
            """Set the provider state (v3 API: call after upon_receiving)."""
            self._provider_state = provider_state
            return self

        def with_request(
            self,
            method: str,
            path: str,
            headers: dict[str, str] | None = None,
            query: dict[str, str] | None = None,
            body: Any = None,
        ) -> PactInteractionBuilder:
            """Build the request (v2-style signature mapped to v3 chainable methods)."""
            # Create interaction with v3 API
            self._interaction = self._pact.upon_receiving(self._description or "")

            if self._provider_state:
                self._interaction = self._interaction.given(self._provider_state)

            # Add request
            self._interaction = self._interaction.with_request(method, path)

            # Add query parameters if present
            if query:
                self._interaction = self._interaction.with_query_parameters(query)

            # Add request headers if present
            if headers:
                self._interaction = self._interaction.with_headers(
                    headers, part="Request"
                )

            # Add request body if present
            if body is not None:
                self._interaction = self._interaction.with_body(body, part="Request")

            return self

        def will_respond_with(
            self,
            status: int,
            headers: dict[str, str] | None = None,
            body: Any = None,
        ) -> PactInteractionBuilder:
            """Build the response (v2-style signature mapped to v3 chainable methods)."""
            if self._interaction is None:
                msg = "with_request() must be called before will_respond_with()"
                raise ValueError(msg)

            # Set response status
            self._interaction = self._interaction.will_respond_with(status)

            # Add response headers if present
            if headers:
                self._interaction = self._interaction.with_headers(
                    headers, part="Response"
                )

            # Add response body if present
            if body is not None:
                self._interaction = self._interaction.with_body(body, part="Response")

            return self

    @pytest.fixture(scope="session")
    def pact() -> Generator:
        """Create and configure Pact consumer.

        This fixture sets up a Pact consumer using pact-python v3 API.

        Yields:
            Configured Pact instance
        """
        pact_instance = Pact(CONSUMER_NAME, PROVIDER_NAME)
        yield pact_instance

        # Write pact file when done
        pact_instance.write_file(str(PACT_DIR))

    @pytest.fixture()
    def pact_interaction(pact: Pact) -> PactInteractionBuilder:
        """Provide Pact interaction builder with v2-compatible API.

        This fixture provides a compatibility wrapper that allows using
        v2-style API calls with the v3 pact-python library.

        Usage (v2-style API):
            pact_interaction.upon_receiving("description")
                .given("provider state")
                .with_request(method="GET", path="/api", headers={...})
                .will_respond_with(status=200, headers={...}, body={...})

        Returns:
            PactInteractionBuilder instance
        """
        return PactInteractionBuilder(pact)

except ImportError:
    PACT_AVAILABLE = False

    @pytest.fixture(scope="session")
    def pact():
        """Placeholder fixture when pact-python is not installed."""
        pytest.skip("pact-python not installed. Install with: pip install pact-python")

    @pytest.fixture()
    def pact_interaction():
        """Placeholder fixture when pact-python is not installed."""
        pytest.skip("pact-python not installed. Install with: pip install pact-python")


# ============================================================================
# Helper Functions
# ============================================================================


def is_pact_available() -> bool:
    """Check if Pact is available for testing.

    Returns:
        True if pact-python is installed and available
    """
    return PACT_AVAILABLE


def get_pact_broker_url() -> str | None:
    """Get Pact Broker URL from environment.

    Returns:
        Pact Broker URL if configured, None otherwise
    """
    return os.environ.get("PACT_BROKER_URL")


def get_pact_broker_token() -> str | None:
    """Get Pact Broker authentication token from environment.

    Returns:
        Pact Broker token if configured, None otherwise
    """
    return os.environ.get("PACT_BROKER_TOKEN")
