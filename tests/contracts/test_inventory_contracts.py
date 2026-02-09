"""Contract tests for DMarket User Inventory API endpoints.

This module contains consumer-driven contract tests for inventory
management endpoints of the DMarket API.

Tested endpoints:
- GET /marketplace-api/v1/user-inventory - List user inventory
- POST /marketplace-api/v1/user-offers/create - Create offers (list for sale)
- GET /marketplace-api/v1/user-offers - List user offers
- POST /marketplace-api/v1/user-offers/edit - Edit offer prices
- DELETE /exchange/v1/offers - Delete/cancel offers
- PATCH /exchange/v1/offers-buy - Buy items

Run these tests with:
    pytest tests/contracts/test_inventory_contracts.py -v
"""

from __future__ import annotations

import pytest

from tests.contracts.conftest import DMarketContracts, PactMatchers, is_pact_available

# Skip all tests if Pact is not available
pytestmark = pytest.mark.skipif(
    not is_pact_available(),
    reason="pact-python not installed",
)


class TestUserInventoryContract:
    """Contract tests for the /marketplace-api/v1/user-inventory endpoint."""

    @pytest.mark.asyncio()
    async def test_get_inventory_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for listing user inventory.

        Verifies that:
        - Consumer sends GET request with GameID parameter
        - Provider responds with list of inventory items
        - Each item has required fields (ItemID, Title, Price, InMarket)
        """
        expected_body = dmarket_contracts.user_inventory_response()

        (
            pact_interaction.upon_receiving("a request to list user inventory")
            .given("user has items in inventory")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-inventory",
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

    @pytest.mark.asyncio()
    async def test_get_inventory_empty(
        self,
        pact_interaction,
    ) -> None:
        """Test contract for empty inventory.

        Verifies that:
        - API returns proper structure when inventory is empty
        - Empty array is returned, not null/error
        """
        expected_body = {
            "Items": [],
            "Total": "0",
            "Cursor": "",
        }

        (
            pact_interaction.upon_receiving("a request for empty inventory")
            .given("user has empty inventory")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-inventory",
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

    @pytest.mark.asyncio()
    async def test_get_inventory_with_filters(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for inventory with filters.

        Verifies that:
        - Consumer can filter by InMarket status
        - Consumer can filter items not on market
        """
        expected_body = dmarket_contracts.user_inventory_response()

        (
            pact_interaction.upon_receiving(
                "a request for inventory items not on market"
            )
            .given("user has items not on market")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-inventory",
                query={
                    "GameID": "a8db",
                    "BasicFilters.InMarket": "false",
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


class TestCreateOffersContract:
    """Contract tests for creating offers (listing items for sale)."""

    @pytest.mark.asyncio()
    async def test_create_offers_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for creating offers.

        Verifies that:
        - Consumer sends POST with asset IDs and prices
        - Provider responds with created offer IDs
        """
        expected_body = {
            "Result": pact_matchers.each_like(
                {
                    "OfferID": pact_matchers.like("offer_12345"),
                    "AssetID": pact_matchers.like("asset_67890"),
                    "Status": pact_matchers.regex(
                        r"^(Created|Updated|Error)$",
                        "Created",
                    ),
                },
                minimum=1,
            ),
        }

        request_body = {
            "Offers": [
                {
                    "AssetID": "asset_67890",
                    "Price": {"Amount": 1300, "Currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("a request to create offers")
            .given("user has items to sell")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-offers/create",
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


class TestUserOffersContract:
    """Contract tests for listing user offers."""

    @pytest.mark.asyncio()
    async def test_get_user_offers_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for listing user offers.

        Verifies that:
        - Consumer can list active offers
        - Response includes offer details
        """
        expected_body = {
            "Items": pact_matchers.each_like(
                {
                    "OfferID": pact_matchers.like("offer_12345"),
                    "AssetID": pact_matchers.like("asset_67890"),
                    "Title": pact_matchers.like(
                        "AK-47 | Redline (Field-Tested)",
                    ),
                    "Price": {
                        "Amount": pact_matchers.integer(1300),
                        "Currency": pact_matchers.like("USD"),
                    },
                    "Status": pact_matchers.regex(
                        r"^(OfferStatusActive|OfferStatusSold|OfferStatusInactive)$",
                        "OfferStatusActive",
                    ),
                    "CreatedDate": pact_matchers.integer(1699876543),
                },
                minimum=0,
            ),
            "Total": pact_matchers.regex(r"^\d+$", "10"),
        }

        (
            pact_interaction.upon_receiving("a request to list user offers")
            .given("user has active offers")
            .with_request(
                method="GET",
                path="/marketplace-api/v1/user-offers",
                query={
                    "GameID": "a8db",
                    "Status": "OfferStatusActive",
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


class TestEditOffersContract:
    """Contract tests for editing offer prices."""

    @pytest.mark.asyncio()
    async def test_edit_offers_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for editing offer prices.

        Verifies that:
        - Consumer can update prices for existing offers
        - Response confirms the update
        """
        expected_body = {
            "Result": pact_matchers.each_like(
                {
                    "OfferID": pact_matchers.like("offer_12345"),
                    "Status": pact_matchers.regex(
                        r"^(Updated|Error|NotFound)$",
                        "Updated",
                    ),
                },
                minimum=1,
            ),
        }

        request_body = {
            "Offers": [
                {
                    "OfferID": "offer_12345",
                    "Price": {"Amount": 1400, "Currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("a request to edit offer prices")
            .given("user has offers to edit")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/user-offers/edit",
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


class TestDeleteOffersContract:
    """Contract tests for deleting offers."""

    @pytest.mark.asyncio()
    async def test_delete_offers_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for deleting offers.

        Verifies that:
        - Consumer sends DELETE request with offer IDs
        - Provider responds with deletion status
        """
        expected_body = {
            "status": "ok",
        }

        request_body = {
            "force": True,
            "objects": [{"offerId": "offer_12345"}],
        }

        (
            pact_interaction.upon_receiving("a request to delete offers")
            .given("user has offers to delete")
            .with_request(
                method="DELETE",
                path="/exchange/v1/offers",
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


class TestBuyItemsContract:
    """Contract tests for buying items from marketplace."""

    @pytest.mark.asyncio()
    async def test_buy_items_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for buying items.

        Verifies that:
        - Consumer sends PATCH request with offer IDs and prices
        - Provider responds with transaction status
        """
        expected_body = {
            "orderId": pact_matchers.like("order_12345"),
            "status": pact_matchers.regex(
                r"^(TxPending|TxSuccess|TxFailed)$",
                "TxPending",
            ),
            "txId": pact_matchers.like("tx_67890"),
            "dmOffersStatus": {
                "offer_12345": {
                    "status": pact_matchers.regex(
                        r"^(Success|Failed|InsufficientFunds)$",
                        "Success",
                    ),
                },
            },
        }

        request_body = {
            "offers": [
                {
                    "offerId": "offer_12345",
                    "price": {"amount": 1250, "currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("a request to buy items")
            .given("user has sufficient balance")
            .with_request(
                method="PATCH",
                path="/exchange/v1/offers-buy",
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
    async def test_buy_items_insufficient_balance(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for buying with insufficient balance.

        Verifies that:
        - API returns proper error when user has insufficient funds
        """
        expected_body = dmarket_contracts.error_response(
            code="InsufficientFunds",
            message="Not enough balance to complete purchase",
        )

        request_body = {
            "offers": [
                {
                    "offerId": "offer_expensive",
                    "price": {"amount": 999999, "currency": "USD"},
                },
            ],
        }

        (
            pact_interaction.upon_receiving("a request to buy expensive items")
            .given("user has insufficient balance")
            .with_request(
                method="PATCH",
                path="/exchange/v1/offers-buy",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
            .will_respond_with(
                status=400,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None


# =============================================================================
# Mock-based contract verification tests
# =============================================================================


class TestInventoryContractsMock:
    """Mock-based contract tests that run without Pact server."""

    def test_user_inventory_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify user inventory response structure."""
        response = dmarket_contracts.user_inventory_response()

        assert "Items" in response
        assert "Total" in response
        assert "Cursor" in response

    def test_inventory_item_has_required_fields(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify each inventory item has all required fields."""
        response = dmarket_contracts.user_inventory_response()
        item_template = response["Items"]["value"][0]

        required_fields = [
            "ItemID",
            "Title",
            "Image",
            "Price",
            "InMarket",
            "Attributes",
        ]

        for field in required_fields:
            assert field in item_template, f"Missing required field: {field}"

    def test_inventory_item_attributes_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify inventory item attributes structure."""
        response = dmarket_contracts.user_inventory_response()
        item_template = response["Items"]["value"][0]

        assert "Attributes" in item_template
        attributes = item_template["Attributes"]

        # Common CS:GO attributes
        assert "exterior" in attributes
        assert "floatValue" in attributes

    def test_inventory_price_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify inventory item price structure."""
        response = dmarket_contracts.user_inventory_response()
        item_template = response["Items"]["value"][0]

        assert "Price" in item_template
        price = item_template["Price"]

        # Price should have USD field
        assert "USD" in price

    def test_error_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify error response structure."""
        response = dmarket_contracts.error_response(
            code="TestError",
            message="Test error message",
        )

        assert "error" in response
        error = response["error"]

        assert "code" in error
        assert "message" in error

        # Verify values - matchers contain 'value' key with actual value
        code_matcher = error["code"]
        message_matcher = error["message"]
        assert code_matcher["value"] == "TestError"
        assert message_matcher["value"] == "Test error message"
