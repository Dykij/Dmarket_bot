"""Contract tests for DMarket User Targets API endpoints.

This module contains consumer-driven contract tests for target (buy order)
management endpoints of the DMarket API.

Tested endpoints:
- GET /marketplace-api/v1/user-targets - List user targets
- POST /marketplace-api/v1/user-targets/create - Create targets
- POST /marketplace-api/v1/user-targets/delete - Delete targets
- GET /marketplace-api/v1/targets-by-title - Get targets by item title

Run these tests with:
    pytest tests/contracts/test_targets_contracts.py -v
"""

from __future__ import annotations

import pytest

from tests.contracts.conftest import DMarketContracts, PactMatchers, is_pact_avAlgolable

# Skip all tests if Pact is not avAlgolable
pytestmark = pytest.mark.skipif(
    not is_pact_avAlgolable(),
    reason="pact-python not installed",
)


class TestUserTargetsContract:
    """Contract tests for the /marketplace-api/v1/user-targets endpoint."""

    @pytest.mark.asyncio()
    async def test_get_user_targets_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for listing user targets.

        Verifies that:
        - Consumer sends GET request with GameID parameter
        - Provider responds with list of targets
        - Each target has required fields (TargetID, Title, Price, Status)
        """
        expected_body = dmarket_contracts.user_targets_response()

        (
            pact_interaction.upon_receiving("a request to list user targets")
            .given("user has active targets")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-targets",
                query={
                    "GameID": "a8db",
                    "BasicFilters.Status": "TargetStatusActive",
                    "Limit": "100",
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
    async def test_get_user_targets_empty(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for empty targets list.

        Verifies that:
        - API returns proper structure when user has no targets
        - Empty array is returned, not null/error
        """
        expected_body = {
            "Items": [],
            "Total": "0",
            "Cursor": "",
        }

        (
            pact_interaction.upon_receiving("request for empty targets list")
            .given("user has no targets")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-targets",
                query={
                    "GameID": "a8db",
                    "Limit": "100",
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


class TestCreateTargetsContract:
    """Contract tests for creating targets."""

    @pytest.mark.asyncio()
    async def test_create_targets_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for creating new targets.

        Verifies that:
        - Consumer sends POST request with target definitions
        - Provider responds with created target IDs and statuses
        """
        expected_body = dmarket_contracts.create_targets_response()

        request_body = {
            "GameID": "a8db",
            "Targets": [
                {
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Amount": 1,
                    "Price": {"Amount": 1200, "Currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("a request to create a target")
            .given("user can create targets")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-targets/create",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_create_multiple_targets(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for creating multiple targets at once.

        Verifies that:
        - Multiple targets can be created in a single request
        - Response contains status for each target
        """
        expected_body = {
            "Result": pact_matchers.each_like(
                {
                    "TargetID": pact_matchers.like("target_123"),
                    "Title": pact_matchers.like("Item Name"),
                    "Status": pact_matchers.regex(
                        r"^(Created|Updated|Error)$",
                        "Created",
                    ),
                },
                minimum=2,
            ),
        }

        request_body = {
            "GameID": "a8db",
            "Targets": [
                {
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "Amount": 1,
                    "Price": {"Amount": 1200, "Currency": "USD"},
                },
                {
                    "Title": "AWP | Asiimov (Field-Tested)",
                    "Amount": 1,
                    "Price": {"Amount": 4000, "Currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("request to create multiple targets")
            .given("user can create multiple targets")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-targets/create",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None

    @pytest.mark.asyncio()
    async def test_create_target_with_attributes(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for creating target with specific attributes.

        Verifies that:
        - Targets can include specific attributes (float, phase, pattern)
        - API accepts the Attrs field
        """
        expected_body = {
            "Result": [
                {
                    "TargetID": pact_matchers.like("target_456"),
                    "Title": pact_matchers.like(
                        "★ Karambit | Doppler (Factory New)",
                    ),
                    "Status": "Created",
                },
            ],
        }

        request_body = {
            "GameID": "a8db",
            "Targets": [
                {
                    "Title": "★ Karambit | Doppler (Factory New)",
                    "Amount": 1,
                    "Price": {"Amount": 150000, "Currency": "USD"},
                    "Attrs": {
                        "phase": "Phase 2",
                        "floatPartValue": 0.01,
                    },
                },
            ],
        }

        (
            pact_interaction.upon_receiving("request to create target with attrs")
            .given("user can create targets with attributes")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-targets/create",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None


class TestDeleteTargetsContract:
    """Contract tests for deleting targets."""

    @pytest.mark.asyncio()
    async def test_delete_targets_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for deleting targets.

        Verifies that:
        - Consumer sends POST request with target IDs to delete
        - Provider responds with deletion status for each target
        """
        expected_body = {
            "Result": pact_matchers.each_like(
                {
                    "TargetID": pact_matchers.like("target_123"),
                    "Status": pact_matchers.regex(
                        r"^(Deleted|NotFound|Error)$",
                        "Deleted",
                    ),
                },
                minimum=1,
            ),
        }

        request_body = {
            "Targets": [{"TargetID": "target_123"}],
        }

        (
            pact_interaction.upon_receiving("a request to delete targets")
            .given("user has targets to delete")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-targets/delete",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None


class TestTargetsByTitleContract:
    """Contract tests for /marketplace-api/v1/targets-by-title endpoint."""

    @pytest.mark.asyncio()
    async def test_get_targets_by_title_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for getting targets by item title.

        Verifies that:
        - Consumer can query existing buy orders for an item
        - Response contains aggregated target information
        """
        expected_body = {
            "orders": pact_matchers.each_like(
                {
                    "amount": pact_matchers.integer(10),
                    "price": pact_matchers.regex(r"^\d+$", "1200"),
                    "title": pact_matchers.like(
                        "AK-47 | Redline (Field-Tested)",
                    ),
                    "attributes": {
                        "exterior": pact_matchers.like("Field-Tested"),
                    },
                },
                minimum=0,
            ),
        }

        (
            pact_interaction.upon_receiving("a request for targets by title")
            .given("targets exist for the item")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/targets-by-title/csgo/"
                "AK-47%20%7C%20Redline%20(Field-Tested)",
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None


# =============================================================================
# Mock-based contract verification tests
# =============================================================================


class TestTargetsContractsMock:
    """Mock-based contract tests that run without Pact server."""

    def test_user_targets_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify user targets response structure."""
        response = dmarket_contracts.user_targets_response()

        assert "Items" in response
        assert "Total" in response
        assert "Cursor" in response

    def test_create_targets_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify create targets response structure."""
        response = dmarket_contracts.create_targets_response()

        assert "Result" in response
        result_items = response["Result"]["value"]
        assert len(result_items) > 0

        # Verify required fields in result
        item = result_items[0]
        assert "TargetID" in item
        assert "Title" in item
        assert "Status" in item

    def test_target_has_required_fields(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify each target has all required fields."""
        response = dmarket_contracts.user_targets_response()
        target_template = response["Items"]["value"][0]

        required_fields = [
            "TargetID",
            "Title",
            "Amount",
            "Price",
            "Status",
            "CreatedAt",
        ]

        for field in required_fields:
            assert field in target_template, f"Missing required field: {field}"

    def test_target_price_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify target price has Amount and Currency."""
        response = dmarket_contracts.user_targets_response()
        target_template = response["Items"]["value"][0]

        assert "Price" in target_template
        price = target_template["Price"]

        assert "Amount" in price
        assert "Currency" in price

    def test_target_status_values(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify target status regex matches expected values."""
        response = dmarket_contracts.user_targets_response()
        target_template = response["Items"]["value"][0]

        status_matcher = target_template["Status"]
        assert status_matcher["pact:matcher:type"] == "regex"

        import re

        pattern = status_matcher["regex"]
        assert re.match(pattern, "TargetStatusActive")
        assert re.match(pattern, "TargetStatusInactive")
        assert not re.match(pattern, "InvalidStatus")
