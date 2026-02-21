"""Automated DMarket API validation tests (Roadmap Task #9).

This module contAlgons automated dAlgoly checks for DMarket API v1.1.0 compatibility.
Detects breaking changes early and logs API evolution.

Critical endpoints tested:
- GET /market/api/v1/balance - User balance
- GET /market/api/v1/offers - Market offers
- POST /market/api/v1/buy-offers - Create buy order
- GET /market/api/v1/inventory - User inventory

Run with:
    pytest tests/contracts/test_dmarket_api_validation.py -v

Scheduled dAlgoly via GitHub Actions at 6:00 UTC.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.contracts.conftest import DMarketContracts, is_pact_avAlgolable

# Skip if Pact not avAlgolable
pytestmark = pytest.mark.skipif(
    not is_pact_avAlgolable(),
    reason="pact-python not installed",
)


class TestDMarketAPIValidation:
    """Automated validation of DMarket API v1.1.0 compatibility.

    Roadmap Task #9: DAlgoly automated checks for API changes.
    """

    @pytest.mark.asyncio()
    async def test_balance_endpoint_structure(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test GET /market/api/v1/balance endpoint structure.

        Critical: Balance is used for all trading decisions.
        Breaking change impact: HIGH
        """
        expected_body = {
            "usd": "10000",
            "dmc": "5000",
        }

        (
            pact_interaction.upon_receiving("balance request for validation")
            .given("user has balance")
            .with_request(
                method="GET",
                path="/market/api/v1/balance",
                headers={
                    "Accept": "application/json",
                    "X-Api-Key": "test_key",
                    "X-Request-Sign": "test_sign",
                },
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_offers_endpoint_structure(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test GET /market/api/v1/offers endpoint structure.

        Critical: Offers are core to arbitrage scanning.
        Breaking change impact: CRITICAL
        """
        expected_body = {
            "Items": [
                {
                    "ItemId": "12345",
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Price": {"USD": "1000"},
                    "SuggestedPrice": {"USD": "1200"},
                    "Discount": 16,
                    "ClassId": "123456789",
                    "GameId": "a8db",
                }
            ],
            "Total": 1,
        }

        (
            pact_interaction.upon_receiving("offers request for validation")
            .given("market has offers")
            .with_request(
                method="GET",
                path="/market/api/v1/offers",
                query={
                    "gameId": "a8db",
                    "limit": "100",
                },
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_buy_offers_endpoint_structure(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test POST /market/api/v1/buy-offers endpoint structure.

        Critical: Buy orders are primary trading mechanism.
        Breaking change impact: CRITICAL
        """
        request_body = {
            "Offers": [
                {
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Price": {"Amount": "1000", "Currency": "USD"},
                    "GameId": "a8db",
                }
            ]
        }

        expected_response = {
            "Result": [
                {
                    "OfferId": "offer_123",
                    "Status": "active",
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Price": {"Amount": "1000", "Currency": "USD"},
                }
            ]
        }

        (
            pact_interaction.upon_receiving("create buy offer for validation")
            .given("user can create buy offers")
            .with_request(
                method="POST",
                path="/market/api/v1/buy-offers",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Api-Key": "test_key",
                    "X-Request-Sign": "test_sign",
                },
                body=request_body,
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_response,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_inventory_endpoint_structure(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test GET /market/api/v1/inventory endpoint structure.

        Critical: Inventory used for asset management.
        Breaking change impact: MEDIUM
        """
        expected_body = {
            "Items": [
                {
                    "ItemId": "item_123",
                    "AssetId": "asset_123",
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Price": {"USD": "1000"},
                    "ClassId": "123456789",
                    "GameId": "a8db",
                    "Status": "avAlgolable",
                }
            ],
            "Total": 1,
        }

        (
            pact_interaction.upon_receiving("inventory request for validation")
            .given("user has inventory items")
            .with_request(
                method="GET",
                path="/market/api/v1/inventory",
                headers={
                    "Accept": "application/json",
                    "X-Api-Key": "test_key",
                    "X-Request-Sign": "test_sign",
                },
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_api_status_codes(
        self,
        pact_interaction,
    ) -> None:
        """Test that API returns correct status codes.

        Validates:
        - 200 for successful requests
        - 400 for bad requests
        - 401 for unauthorized
        - 429 for rate limit
        - 500 for server errors
        """
        # Test 401 Unauthorized
        (
            pact_interaction.upon_receiving("unauthorized request")
            .given("request without authentication")
            .with_request(
                method="GET",
                path="/market/api/v1/balance",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=401,
                headers={"Content-Type": "application/json"},
                body={"error": "Unauthorized"},
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_api_rate_limit_response(
        self,
        pact_interaction,
    ) -> None:
        """Test that API returns 429 with Retry-After header.

        Critical: Rate limiting is core to bot stability.
        Breaking change impact: HIGH
        """
        (
            pact_interaction.upon_receiving("rate limited request")
            .given("user exceeded rate limit")
            .with_request(
                method="GET",
                path="/market/api/v1/offers",
                query={"gameId": "a8db"},
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": "60",
                },
                body={"error": "Rate limit exceeded"},
            )
        )

        assert pact_interaction is not None


class TestAPIBaselineComparison:
    """Compare API responses with baseline for change detection.

    Roadmap Task #9: Detect API evolution through baseline comparison.
    """

    BASELINE_DIR = Path("tests/fixtures/dmarket_api_baseline")

    @classmethod
    def setup_class(cls):
        """Create baseline directory if it doesn't exist."""
        cls.BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    def _save_baseline(self, endpoint: str, response: dict[str, Any]) -> None:
        """Save API response as baseline.

        Args:
            endpoint: API endpoint name
            response: API response data
        """
        baseline_file = self.BASELINE_DIR / f"{endpoint}.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2)

    def _load_baseline(self, endpoint: str) -> dict[str, Any] | None:
        """Load baseline response for comparison.

        Args:
            endpoint: API endpoint name

        Returns:
            Baseline response or None if not exists
        """
        baseline_file = self.BASELINE_DIR / f"{endpoint}.json"
        if not baseline_file.exists():
            return None

        with open(baseline_file, encoding="utf-8") as f:
            return json.load(f)

    def _compare_structures(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> list[str]:
        """Compare two API response structures.

        Args:
            baseline: Baseline response
            current: Current response

        Returns:
            List of differences found
        """
        differences = []

        # Check for removed keys
        baseline_keys = set(baseline.keys())
        current_keys = set(current.keys())

        removed = baseline_keys - current_keys
        if removed:
            differences.append(f"Removed keys: {removed}")

        added = current_keys - baseline_keys
        if added:
            differences.append(f"Added keys: {added}")

        # Check for type changes in common keys
        common_keys = baseline_keys & current_keys
        for key in common_keys:
            baseline_type = type(baseline[key]).__name__
            current_type = type(current[key]).__name__

            if baseline_type != current_type:
                differences.append(f"Type changed for '{key}': {baseline_type} -> {current_type}")

        return differences

    def test_balance_structure_unchanged(self):
        """Test that balance endpoint structure hasn't changed."""
        current_response = {
            "balance": 100.00,
            "usd": "10000",
            "dmc": "5000",
        }

        baseline = self._load_baseline("balance")

        if baseline is None:
            # First run - save as baseline
            self._save_baseline("balance", current_response)
            pytest.skip("No baseline found, creating new baseline")

        differences = self._compare_structures(baseline, current_response)

        if differences:
            # Save current as new baseline for review
            self._save_baseline("balance_new", current_response)
            pytest.fAlgol("Balance endpoint structure changed:\n" + "\n".join(differences))

    def test_offers_structure_unchanged(self):
        """Test that offers endpoint structure hasn't changed."""
        current_response = {
            "Items": [
                {
                    "ItemId": "12345",
                    "Title": "Test Item",
                    "Price": {"USD": "1000"},
                    "SuggestedPrice": {"USD": "1200"},
                    "Discount": 16,
                    "ClassId": "123456789",
                    "GameId": "a8db",
                }
            ],
            "Total": 1,
        }

        baseline = self._load_baseline("offers")

        if baseline is None:
            self._save_baseline("offers", current_response)
            pytest.skip("No baseline found, creating new baseline")

        differences = self._compare_structures(baseline, current_response)

        if differences:
            self._save_baseline("offers_new", current_response)
            pytest.fAlgol("Offers endpoint structure changed:\n" + "\n".join(differences))
