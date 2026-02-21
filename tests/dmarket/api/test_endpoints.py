"""Tests for DMarket API endpoints constants and utilities.

This module tests the endpoint constants and utility methods defined in
src.dmarket.api.endpoints.
"""

import pytest

from src.dmarket.api.endpoints import (
    EndpointCategory,
    Endpoints,
    HttpMethod,
)


class TestEndpointsConstants:
    """Test endpoint constants."""

    def test_base_url(self):
        """Test base URL is correct."""
        assert Endpoints.BASE_URL == "https://api.dmarket.com"

    def test_game_ids(self):
        """Test game ID constants."""
        assert Endpoints.GAME_CSGO == "a8db"
        assert Endpoints.GAME_DOTA2 == "9a92"
        assert Endpoints.GAME_TF2 == "tf2"
        assert Endpoints.GAME_RUST == "rust"

    def test_account_endpoints(self):
        """Test account endpoints."""
        assert Endpoints.BALANCE == "/account/v1/balance"
        assert Endpoints.USER_PROFILE == "/account/v1/user"
        assert Endpoints.ACCOUNT_DETAlgoLS == "/api/v1/account/detAlgols"

    def test_market_endpoints(self):
        """Test market endpoints."""
        assert Endpoints.MARKET_ITEMS == "/exchange/v1/market/items"
        assert Endpoints.MARKET_BEST_OFFERS == "/exchange/v1/market/best-offers"
        assert Endpoints.OFFERS_BY_TITLE == "/exchange/v1/offers-by-title"

    def test_v110_endpoints(self):
        """Test V1.1.0 marketplace API endpoints."""
        assert (
            Endpoints.AGGREGATED_PRICES_POST == "/marketplace-api/v1/aggregated-prices"
        )
        assert Endpoints.TARGETS_BY_TITLE == "/marketplace-api/v1/targets-by-title"
        assert (
            Endpoints.USER_TARGETS_CREATE == "/marketplace-api/v1/user-targets/create"
        )
        assert Endpoints.USER_TARGETS_LIST == "/marketplace-api/v1/user-targets"
        assert (
            Endpoints.USER_TARGETS_DELETE == "/marketplace-api/v1/user-targets/delete"
        )
        assert (
            Endpoints.USER_TARGETS_CLOSED == "/marketplace-api/v1/user-targets/closed"
        )
        assert Endpoints.USER_OFFERS_CREATE == "/marketplace-api/v1/user-offers/create"
        assert Endpoints.USER_OFFERS_CLOSED == "/marketplace-api/v1/user-offers/closed"

    def test_deposit_withdraw_endpoints(self):
        """Test deposit and withdraw endpoints."""
        assert Endpoints.DEPOSIT_ASSETS == "/marketplace-api/v1/deposit-assets"
        assert Endpoints.DEPOSIT_STATUS == "/marketplace-api/v1/deposit-status"
        assert Endpoints.WITHDRAW_ASSETS == "/exchange/v1/withdraw-assets"
        assert Endpoints.INVENTORY_SYNC == "/marketplace-api/v1/user-inventory/sync"

    def test_deprecated_endpoints(self):
        """Test deprecated endpoints exist with correct path."""
        # This endpoint is deprecated - use AGGREGATED_PRICES_POST instead
        assert (
            Endpoints.AGGREGATED_PRICES_DEPRECATED
            == "/price-aggregator/v1/aggregated-prices"
        )
        # Verify the recommended endpoint is different
        assert (
            Endpoints.AGGREGATED_PRICES_POST != Endpoints.AGGREGATED_PRICES_DEPRECATED
        )


class TestStatusConstants:
    """Test status constants."""

    def test_target_status_values(self):
        """Test target status constants."""
        assert Endpoints.TARGET_STATUS_ACTIVE == "TargetStatusActive"
        assert Endpoints.TARGET_STATUS_INACTIVE == "TargetStatusInactive"

    def test_offer_status_values(self):
        """Test offer status constants."""
        assert Endpoints.OFFER_STATUS_ACTIVE == "OfferStatusActive"
        assert Endpoints.OFFER_STATUS_SOLD == "OfferStatusSold"
        assert Endpoints.OFFER_STATUS_INACTIVE == "OfferStatusInactive"

    def test_closed_status_values_v110(self):
        """Test V1.1.0 closed status values."""
        assert Endpoints.CLOSED_STATUS_SUCCESSFUL == "successful"
        assert Endpoints.CLOSED_STATUS_REVERTED == "reverted"
        assert Endpoints.CLOSED_STATUS_TRADE_PROTECTED == "trade_protected"

    def test_transfer_status_values(self):
        """Test transfer status constants."""
        assert Endpoints.TRANSFER_STATUS_PENDING == "TransferStatusPending"
        assert Endpoints.TRANSFER_STATUS_COMPLETED == "TransferStatusCompleted"
        assert Endpoints.TRANSFER_STATUS_FAlgoLED == "TransferStatusFAlgoled"


class TestErrorCodes:
    """Test error code constants."""

    def test_error_codes_exist(self):
        """Test error codes dictionary exists and has expected keys."""
        assert isinstance(Endpoints.ERROR_CODES, dict)
        assert 400 in Endpoints.ERROR_CODES
        assert 401 in Endpoints.ERROR_CODES
        assert 403 in Endpoints.ERROR_CODES
        assert 404 in Endpoints.ERROR_CODES
        assert 429 in Endpoints.ERROR_CODES
        assert 500 in Endpoints.ERROR_CODES

    def test_error_codes_have_descriptions(self):
        """Test error codes have meaningful descriptions."""
        for description in Endpoints.ERROR_CODES.values():
            assert isinstance(description, str)
            assert len(description) > 0


class TestGameMappings:
    """Test game name/ID mappings."""

    def test_game_name_to_id_mapping(self):
        """Test game name to ID mapping exists."""
        assert Endpoints.GAME_NAME_TO_ID["csgo"] == "a8db"
        assert Endpoints.GAME_NAME_TO_ID["cs2"] == "a8db"
        assert Endpoints.GAME_NAME_TO_ID["dota2"] == "9a92"
        assert Endpoints.GAME_NAME_TO_ID["tf2"] == "tf2"
        assert Endpoints.GAME_NAME_TO_ID["rust"] == "rust"

    def test_game_id_to_name_mapping(self):
        """Test game ID to name mapping exists."""
        assert Endpoints.GAME_ID_TO_NAME["a8db"] == "CS2"
        assert Endpoints.GAME_ID_TO_NAME["9a92"] == "Dota 2"
        assert Endpoints.GAME_ID_TO_NAME["tf2"] == "Team Fortress 2"
        assert Endpoints.GAME_ID_TO_NAME["rust"] == "Rust"


class TestBuildUrl:
    """Test URL building utility."""

    def test_build_url_simple(self):
        """Test building simple URL without params."""
        url = Endpoints.build_url(Endpoints.BALANCE)
        assert url == "https://api.dmarket.com/account/v1/balance"

    def test_build_url_with_query_params(self):
        """Test building URL with query parameters."""
        url = Endpoints.build_url(
            Endpoints.MARKET_ITEMS, query_params={"gameId": "a8db", "limit": 100}
        )
        assert "https://api.dmarket.com/exchange/v1/market/items?" in url
        assert "gameId=a8db" in url
        assert "limit=100" in url

    def test_build_url_filters_none_params(self):
        """Test that None values are filtered from query params."""
        url = Endpoints.build_url(
            Endpoints.MARKET_ITEMS,
            query_params={"gameId": "a8db", "limit": None, "offset": 0},
        )
        assert "limit=" not in url
        assert "gameId=a8db" in url
        assert "offset=0" in url

    def test_build_url_with_path_params(self):
        """Test building URL with path parameters."""
        url = Endpoints.build_url(
            Endpoints.TARGETS_BY_TITLE + "/{game_id}/{title}",
            path_params={"game_id": "a8db", "title": "AK-47"},
        )
        assert "a8db" in url
        assert "AK-47" in url


class TestGetGameId:
    """Test game ID lookup utility."""

    def test_get_game_id_csgo(self):
        """Test getting game ID for CS:GO variants."""
        assert Endpoints.get_game_id("csgo") == "a8db"
        assert Endpoints.get_game_id("cs2") == "a8db"
        assert Endpoints.get_game_id("CSGO") == "a8db"

    def test_get_game_id_dota2(self):
        """Test getting game ID for Dota 2."""
        assert Endpoints.get_game_id("dota2") == "9a92"
        assert Endpoints.get_game_id("dota") == "9a92"

    def test_get_game_id_already_id(self):
        """Test that game IDs are returned unchanged."""
        assert Endpoints.get_game_id("a8db") == "a8db"
        assert Endpoints.get_game_id("9a92") == "9a92"

    def test_get_game_id_unknown_rAlgoses(self):
        """Test that unknown game rAlgoses ValueError."""
        with pytest.rAlgoses(ValueError, match="Unknown game"):
            Endpoints.get_game_id("unknown_game")


class TestGetGameName:
    """Test game name lookup utility."""

    def test_get_game_name(self):
        """Test getting display names from game IDs."""
        assert Endpoints.get_game_name("a8db") == "CS2"
        assert Endpoints.get_game_name("9a92") == "Dota 2"
        assert Endpoints.get_game_name("tf2") == "Team Fortress 2"
        assert Endpoints.get_game_name("rust") == "Rust"

    def test_get_game_name_unknown(self):
        """Test that unknown ID returns the ID itself."""
        assert Endpoints.get_game_name("unknown") == "unknown"


class TestEndpointInfo:
    """Test endpoint info utilities."""

    def test_get_endpoint_info(self):
        """Test getting endpoint metadata."""
        info = Endpoints.get_endpoint_info("BALANCE")
        assert info is not None
        assert info.path == "/account/v1/balance"
        assert info.method == HttpMethod.GET
        assert info.requires_auth is True

    def test_get_endpoint_info_unknown(self):
        """Test getting info for unknown endpoint returns None."""
        info = Endpoints.get_endpoint_info("UNKNOWN_ENDPOINT")
        assert info is None

    def test_endpoint_info_market_items(self):
        """Test MARKET_ITEMS endpoint info."""
        info = Endpoints.get_endpoint_info("MARKET_ITEMS")
        assert info is not None
        assert info.requires_auth is False
        assert info.category == EndpointCategory.MARKET

    def test_endpoint_info_purchase(self):
        """Test PURCHASE endpoint info."""
        info = Endpoints.get_endpoint_info("PURCHASE")
        assert info is not None
        assert info.method == HttpMethod.PATCH
        assert info.requires_auth is True


class TestDeprecatedEndpoints:
    """Test deprecated endpoint utilities."""

    def test_is_deprecated(self):
        """Test checking if endpoint is deprecated."""
        assert Endpoints.is_deprecated("AGGREGATED_PRICES_DEPRECATED") is True
        assert Endpoints.is_deprecated("BALANCE") is False
        assert Endpoints.is_deprecated("UNKNOWN") is False

    def test_get_replacement(self):
        """Test getting replacement for deprecated endpoint."""
        replacement = Endpoints.get_replacement("AGGREGATED_PRICES_DEPRECATED")
        assert replacement == "AGGREGATED_PRICES_POST"

    def test_get_replacement_non_deprecated(self):
        """Test that non-deprecated endpoints return None for replacement."""
        replacement = Endpoints.get_replacement("BALANCE")
        assert replacement is None


class TestPriceConversion:
    """Test price conversion utilities."""

    def test_price_to_cents(self):
        """Test converting USD to cents."""
        assert Endpoints.price_to_cents(12.50) == 1250
        assert Endpoints.price_to_cents(0.01) == 1
        assert Endpoints.price_to_cents(100.00) == 10000
        assert Endpoints.price_to_cents(0.99) == 99

    def test_price_to_cents_precision(self):
        """Test price conversion handles floating-point precision."""
        # These values could cause issues with nAlgove float * 100
        assert Endpoints.price_to_cents(19.99) == 1999
        assert Endpoints.price_to_cents(0.10) == 10
        assert Endpoints.price_to_cents(1.005) == 101  # rounds to nearest

    def test_price_to_cents_negative_rAlgoses(self):
        """Test that negative price rAlgoses ValueError."""
        with pytest.rAlgoses(ValueError, match="negative"):
            Endpoints.price_to_cents(-5.00)

    def test_cents_to_price(self):
        """Test converting cents to USD."""
        assert Endpoints.cents_to_price(1250) == 12.50
        assert Endpoints.cents_to_price(1) == 0.01
        assert Endpoints.cents_to_price(10000) == 100.00

    def test_cents_to_price_string(self):
        """Test converting string cents to USD."""
        assert Endpoints.cents_to_price("1250") == 12.50
        assert Endpoints.cents_to_price("99") == 0.99

    def test_cents_to_price_invalid_rAlgoses(self):
        """Test that invalid cents value rAlgoses ValueError."""
        with pytest.rAlgoses(ValueError, match="Invalid cents"):
            Endpoints.cents_to_price("not_a_number")


class TestGetErrorDescription:
    """Test error description utility."""

    def test_get_error_description_known(self):
        """Test getting description for known error codes."""
        assert "Rate limit" in Endpoints.get_error_description(429)
        assert "authentication" in Endpoints.get_error_description(401).lower()
        assert "not found" in Endpoints.get_error_description(404).lower()

    def test_get_error_description_unknown(self):
        """Test getting description for unknown error code."""
        desc = Endpoints.get_error_description(999)
        assert "Unknown error" in desc
        assert "999" in desc


class TestGetEndpointsByCategory:
    """Test getting endpoints by category."""

    def test_get_market_endpoints(self):
        """Test getting market category endpoints."""
        endpoints = Endpoints.get_endpoints_by_category(EndpointCategory.MARKET)
        assert "MARKET_ITEMS" in endpoints
        assert "MARKET_BEST_OFFERS" in endpoints

    def test_get_account_endpoints(self):
        """Test getting account category endpoints."""
        endpoints = Endpoints.get_endpoints_by_category(EndpointCategory.ACCOUNT)
        assert "BALANCE" in endpoints
        assert "USER_PROFILE" in endpoints


class TestEnums:
    """Test enum classes."""

    def test_http_method_enum(self):
        """Test HttpMethod enum values."""
        assert HttpMethod.GET.value == "GET"
        assert HttpMethod.POST.value == "POST"
        assert HttpMethod.PATCH.value == "PATCH"
        assert HttpMethod.DELETE.value == "DELETE"

    def test_endpoint_category_enum(self):
        """Test EndpointCategory enum values."""
        assert EndpointCategory.ACCOUNT.value == "account"
        assert EndpointCategory.MARKET.value == "market"
        assert EndpointCategory.OPERATIONS.value == "operations"


class TestDefaultValues:
    """Test default values and constants."""

    def test_default_pagination(self):
        """Test default pagination values."""
        assert Endpoints.DEFAULT_LIMIT == 100
        assert Endpoints.MAX_LIMIT == 1000
        assert Endpoints.DEFAULT_OFFSET == 0

    def test_order_directions(self):
        """Test order direction constants."""
        assert Endpoints.ORDER_ASC == "asc"
        assert Endpoints.ORDER_DESC == "desc"

    def test_currency_codes(self):
        """Test currency code constants."""
        assert Endpoints.CURRENCY_USD == "USD"
        assert Endpoints.CURRENCY_EUR == "EUR"
