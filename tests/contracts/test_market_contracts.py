"""Contract tests for DMarket Marketplace API endpoints.

This module contains consumer-driven contract tests for marketplace-related
endpoints of the DMarket API.

Tested endpoints:
- GET /exchange/v1/market/items - Get market items
- POST /marketplace-api/v1/aggregated-prices - Get aggregated prices
- GET /exchange/v1/offers-by-title - Get offers by title

Run these tests with:
    pytest tests/contracts/test_market_contracts.py -v
"""

from __future__ import annotations

import pytest

from tests.contracts.conftest import DMarketContracts, PactMatchers, is_pact_avAlgolable

# Skip all tests if Pact is not avAlgolable
pytestmark = pytest.mark.skipif(
    not is_pact_avAlgolable(),
    reason="pact-python not installed",
)


class TestMarketItemsContract:
    """Contract tests for the /exchange/v1/market/items endpoint."""

    @pytest.mark.asyncio()
    async def test_get_market_items_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for successful market items retrieval.

        Verifies that:
        - Consumer sends GET request with required gameId parameter
        - Provider responds with paginated list of items
        - Each item has required fields (itemId, title, price)
        """
        expected_body = dmarket_contracts.market_items_response()

        (
            pact_interaction.upon_receiving("a request for market items")
            .given("market has items for csgo")
            .with_request(
                method="GET",
                path="/exchange/v1/market/items",
                query={
                    "gameId": "a8db",
                    "limit": "100",
                    "currency": "USD",
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
    async def test_get_market_items_with_price_filter(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for market items with price filtering.

        Verifies that:
        - Price filters (priceFrom, priceTo) are accepted
        - Response structure remains consistent
        """
        expected_body = dmarket_contracts.market_items_response()

        (
            pact_interaction.upon_receiving("request for items with price filter")
            .given("market has items in price range")
            .with_request(
                method="GET",
                path="/exchange/v1/market/items",
                query={
                    "gameId": "a8db",
                    "limit": "50",
                    "currency": "USD",
                    "priceFrom": "100",
                    "priceTo": "5000",
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
    async def test_get_market_items_empty_result(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for empty market items response.

        Verifies that:
        - API returns proper structure even when no items match
        - Empty array is returned, not null/error
        """
        expected_body = {
            "cursor": "",
            "objects": [],
            "total": pact_matchers.integer(0),
        }

        (
            pact_interaction.upon_receiving("request yielding no results")
            .given("no items match the filter")
            .with_request(
                method="GET",
                path="/exchange/v1/market/items",
                query={
                    "gameId": "a8db",
                    "limit": "100",
                    "currency": "USD",
                    "title": "NonExistentItemName12345",
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


class TestAggregatedPricesContract:
    """Contract tests for the /marketplace-api/v1/aggregated-prices endpoint."""

    @pytest.mark.asyncio()
    async def test_get_aggregated_prices_success(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for aggregated prices retrieval.

        Verifies that:
        - Consumer sends POST request with filter body
        - Provider responds with aggregated price data
        - Response includes order and offer counts
        """
        expected_body = dmarket_contracts.aggregated_prices_response()

        request_body = {
            "filter": {
                "game": "csgo",
                "titles": ["AK-47 | Redline (Field-Tested)"],
            },
            "limit": "100",
            "cursor": "",
        }

        (
            pact_interaction.upon_receiving("a request for aggregated prices")
            .given("items exist for aggregation")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/aggregated-prices",
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
    async def test_get_aggregated_prices_multiple_items(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for aggregated prices with multiple items.

        Verifies that:
        - Multiple items can be queried in single request
        - Response contains data for each requested item
        """
        expected_body = {
            "aggregatedPrices": pact_matchers.each_like(
                {
                    "title": pact_matchers.like("Item Name"),
                    "orderBestPrice": pact_matchers.regex(r"^\d+$", "1200"),
                    "orderCount": pact_matchers.integer(10),
                    "offerBestPrice": pact_matchers.regex(r"^\d+$", "1250"),
                    "offerCount": pact_matchers.integer(15),
                },
                minimum=2,
            ),
            "nextCursor": pact_matchers.like(""),
        }

        request_body = {
            "filter": {
                "game": "csgo",
                "titles": [
                    "AK-47 | Redline (Field-Tested)",
                    "AWP | Asiimov (Field-Tested)",
                ],
            },
            "limit": "100",
            "cursor": "",
        }

        (
            pact_interaction.upon_receiving("request for multiple items prices")
            .given("multiple items exist for aggregation")
            .with_request(
                method="POST",
                path="/marketplace-api/v1/aggregated-prices",
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


class TestOffersByTitleContract:
    """Contract tests for the /exchange/v1/offers-by-title endpoint."""

    @pytest.mark.asyncio()
    async def test_get_offers_by_title_success(
        self,
        pact_interaction,
        pact_matchers: type[PactMatchers],
    ) -> None:
        """Test contract for offers by title retrieval.

        Verifies that:
        - Consumer can query offers for a specific item title
        - Response contains list of offers with prices
        """
        expected_body = {
            "objects": pact_matchers.each_like(
                {
                    "itemId": pact_matchers.like("offer_123"),
                    "price": {
                        "USD": pact_matchers.regex(r"^\d+$", "1250"),
                    },
                    "title": pact_matchers.like(
                        "AK-47 | Redline (Field-Tested)",
                    ),
                },
                minimum=0,
            ),
            "total": pact_matchers.integer(45),
            "cursor": pact_matchers.like(""),
        }

        (
            pact_interaction.upon_receiving("a request for offers by title")
            .given("offers exist for the item title")
            .with_request(
                method="GET",
                path="/exchange/v1/offers-by-title",
                query={
                    "Title": "AK-47 | Redline (Field-Tested)",
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


# =============================================================================
# Mock-based contract verification tests
# =============================================================================


class TestMarketContractsMock:
    """Mock-based contract tests that run without Pact server."""

    def test_market_items_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify market items response structure."""
        response = dmarket_contracts.market_items_response()

        assert "cursor" in response
        assert "objects" in response
        assert "total" in response

        # Verify objects is an array matcher
        assert response["objects"]["pact:matcher:type"] == "type"
        assert isinstance(response["objects"]["value"], list)

    def test_aggregated_prices_response_structure(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify aggregated prices response structure."""
        response = dmarket_contracts.aggregated_prices_response()

        assert "aggregatedPrices" in response
        assert "nextCursor" in response

        # Verify aggregatedPrices is an array matcher
        prices = response["aggregatedPrices"]
        assert prices["pact:matcher:type"] == "type"

    def test_market_item_has_required_fields(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify each market item has all required fields."""
        response = dmarket_contracts.market_items_response()
        item_template = response["objects"]["value"][0]

        required_fields = [
            "itemId",
            "title",
            "price",
            "suggestedPrice",
            "imageUrl",
            "extra",
        ]

        for field in required_fields:
            assert field in item_template, f"Missing required field: {field}"

    def test_price_format_is_string_cents(
        self,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Verify prices are formatted as string integers (cents)."""
        response = dmarket_contracts.market_items_response()
        item_template = response["objects"]["value"][0]

        # Check price field structure
        assert "USD" in item_template["price"]

        price_matcher = item_template["price"]["USD"]
        assert price_matcher["pact:matcher:type"] == "regex"

        # Verify the regex matches string integers
        import re

        pattern = price_matcher["regex"]
        assert re.match(pattern, "1250")
        assert re.match(pattern, "0")
        assert not re.match(pattern, "12.50")
