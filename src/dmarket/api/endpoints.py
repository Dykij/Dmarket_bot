"""DMarket API endpoints constants and utilities.

This module contains all API endpoint constants for DMarket API v1.1.0.
Organized by category: account, market, user, operations, analytics.

Features:
- Centralized endpoint management
- HTTP method and rate limit information
- URL building utilities
- Game ID mappings
- Status constants

Documentation: https://docs.dmarket.com/v1/swagger.html
OpenAPI JSON: https://docs.dmarket.com/v1/trading.swagger.json
GitHub Examples: https://github.com/dmarket/dm-trading-tools
Last updated: December 28, 2025

Example:
    from src.dmarket.api.endpoints import Endpoints, EndpointInfo

    # Get endpoint info
    info = Endpoints.get_endpoint_info("BALANCE")
    print(f"Path: {info.path}, Method: {info.method}")

    # Build full URL
    url = Endpoints.build_url("MARKET_ITEMS", game_id="csgo", limit=100)
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import quote, urlencode


class EndpointCategory(StrEnum):
    """Categories of DMarket API endpoints."""

    ACCOUNT = "account"
    MARKET = "market"
    USER = "user"
    OPERATIONS = "operations"
    ANALYTICS = "analytics"
    MARKETPLACE_V110 = "marketplace_v110"
    DEPOSIT_WITHDRAW = "deposit_withdraw"
    GAME = "game"


class HttpMethod(StrEnum):
    """HTTP methods used by DMarket API."""

    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"
    PUT = "PUT"


@dataclass(frozen=True)
class EndpointInfo:
    """Information about an API endpoint.

    Attributes:
        path: The endpoint path (e.g., "/account/v1/balance")
        method: HTTP method (GET, POST, etc.)
        category: Endpoint category
        description: Human-readable description
        requires_auth: Whether authentication is required
        rate_limit: Requests per minute limit (None = default)
        deprecated: Whether the endpoint is deprecated
        replacement: Replacement endpoint if deprecated
    """

    path: str
    method: HttpMethod = HttpMethod.GET
    category: EndpointCategory = EndpointCategory.ACCOUNT
    description: str = ""
    requires_auth: bool = True
    rate_limit_per_minute: int | None = (
        None  # Max requests per minute (None = use default)
    )
    deprecated: bool = False
    replacement: str | None = None


class Endpoints:
    """DMarket API endpoint constants and utilities.

    This class provides:
    - All API endpoint paths as class attributes
    - EndpointInfo metadata for each endpoint
    - URL building utilities
    - Game ID constants
    - Status constants

    Organized by category:
    - BASE_URL: Base API URL
    - Account: Balance, details, offers, user profile
    - Market: Items, search, prices, best offers
    - User: Inventory, offers, targets
    - Operations: Buy, sell, edit, delete
    - Analytics: Sales history, price history, last sales
    - V1.1.0: New endpoints (aggregated prices, targets-by-title, deposits, withdrawals)

    Note: Prices in API responses are in CENTS (divide by 100 for USD).

    Example:
        # Get balance endpoint
        balance_url = f"{Endpoints.BASE_URL}{Endpoints.BALANCE}"

        # Build URL with parameters
        items_url = Endpoints.build_url(
            Endpoints.MARKET_ITEMS,
            gameId="a8db",
            limit=100,
            currency="USD"
        )

        # Get endpoint metadata
        info = Endpoints.ENDPOINT_INFO["BALANCE"]
        print(f"Requires auth: {info.requires_auth}")
    """

    # ========================================
    # Base URL
    # ========================================
    BASE_URL = "https://api.dmarket.com"

    # ========================================
    # Account endpoints
    # ========================================
    BALANCE = "/account/v1/balance"
    BALANCE_LEGACY = "/api/v1/account/balance"
    ACCOUNT_DETAlgoLS = "/api/v1/account/details"
    ACCOUNT_OFFERS = "/api/v1/account/offers"
    USER_PROFILE = "/account/v1/user"

    # ========================================
    # Market endpoints
    # ========================================
    MARKET_ITEMS = "/exchange/v1/market/items"
    MARKET_PRICE_AGGREGATED = "/exchange/v1/market/aggregated-prices"
    MARKET_META = "/exchange/v1/market/meta"
    MARKET_BEST_OFFERS = "/exchange/v1/market/best-offers"
    MARKET_SEARCH = "/exchange/v1/market/search"
    OFFERS_BY_TITLE = "/exchange/v1/offers-by-title"

    # ========================================
    # User endpoints
    # ========================================
    USER_INVENTORY = "/exchange/v1/user/inventory"
    USER_OFFERS = "/exchange/v1/user/offers"
    USER_TARGETS = "/exchange/v1/target-lists"

    # ========================================
    # Operations endpoints
    # ========================================
    PURCHASE = "/exchange/v1/market/items/buy"
    OFFERS_BUY = "/exchange/v1/offers-buy"  # PATCH
    SELL = "/exchange/v1/user/inventory/sell"
    OFFER_EDIT = "/exchange/v1/user/offers/edit"
    OFFER_DELETE = "/exchange/v1/user/offers/delete"
    OFFERS_DELETE = "/exchange/v1/offers"  # DELETE

    # ========================================
    # Analytics endpoints
    # ========================================
    SALES_HISTORY = "/account/v1/sales-history"
    ITEM_PRICE_HISTORY = "/exchange/v1/market/price-history"
    LAST_SALES = "/trade-aggregator/v1/last-sales"

    # ========================================
    # V1.1.0 Marketplace API endpoints (2024/2025)
    # ========================================
    AGGREGATED_PRICES_POST = (
        "/marketplace-api/v1/aggregated-prices"  # POST - recommended
    )
    AGGREGATED_PRICES_DEPRECATED = (
        "/price-aggregator/v1/aggregated-prices"  # DEPRECATED
    )
    TARGETS_BY_TITLE = "/marketplace-api/v1/targets-by-title"  # GET /{game_id}/{title}
    USER_TARGETS_CREATE = "/marketplace-api/v1/user-targets/create"  # POST
    USER_TARGETS_LIST = "/marketplace-api/v1/user-targets"  # GET
    USER_TARGETS_DELETE = "/marketplace-api/v1/user-targets/delete"  # POST
    USER_TARGETS_CLOSED = (
        "/marketplace-api/v1/user-targets/closed"  # GET - new statuses
    )
    USER_OFFERS_CREATE = "/marketplace-api/v1/user-offers/create"  # POST
    USER_OFFERS_EDIT = "/marketplace-api/v1/user-offers/edit"  # POST
    USER_OFFERS_CLOSED = "/marketplace-api/v1/user-offers/closed"  # GET - new statuses
    USER_INVENTORY_V2 = "/marketplace-api/v1/user-inventory"  # GET - cursor pagination

    # ========================================
    # Deposit/Withdraw endpoints (V1.1.0)
    # ========================================
    DEPOSIT_ASSETS = "/marketplace-api/v1/deposit-assets"  # POST
    DEPOSIT_STATUS = "/marketplace-api/v1/deposit-status"  # GET /{DepositID}
    WITHDRAW_ASSETS = "/exchange/v1/withdraw-assets"  # POST
    INVENTORY_SYNC = "/marketplace-api/v1/user-inventory/sync"  # POST

    # ========================================
    # Game endpoints
    # ========================================
    GAMES_LIST = "/game/v1/games"  # GET - list all supported games

    # ========================================
    # Game IDs (official DMarket identifiers)
    # ========================================
    GAME_CSGO = "a8db"  # CS:GO / CS2
    GAME_DOTA2 = "9a92"  # Dota 2
    GAME_TF2 = "tf2"  # Team Fortress 2
    GAME_RUST = "rust"  # Rust

    # Game name to ID mapping
    GAME_NAME_TO_ID: dict[str, str] = {
        "csgo": "a8db",
        "cs2": "a8db",
        "cs": "a8db",
        "counter-strike": "a8db",
        "dota2": "9a92",
        "dota": "9a92",
        "tf2": "tf2",
        "team-fortress": "tf2",
        "rust": "rust",
    }

    # Game ID to display name mapping
    GAME_ID_TO_NAME: dict[str, str] = {
        "a8db": "CS2",
        "9a92": "Dota 2",
        "tf2": "Team Fortress 2",
        "rust": "Rust",
    }

    # ========================================
    # HTTP error codes with descriptions
    # ========================================
    ERROR_CODES: dict[int, str] = {
        400: "Bad request or invalid parameters",
        401: "Invalid authentication - check API keys",
        403: "Access denied - insufficient permissions",
        404: "Resource not found",
        429: "Rate limit exceeded - use Retry-After header",
        500: "Internal server error",
        502: "Bad Gateway",
        503: "Service unavAlgolable",
        504: "Gateway timeout",
    }

    # ========================================
    # Target/Offer status values
    # ========================================
    TARGET_STATUS_ACTIVE = "TargetStatusActive"
    TARGET_STATUS_INACTIVE = "TargetStatusInactive"
    OFFER_STATUS_ACTIVE = "OfferStatusActive"
    OFFER_STATUS_SOLD = "OfferStatusSold"
    OFFER_STATUS_INACTIVE = "OfferStatusInactive"

    # ========================================
    # Closed target/offer status values (V1.1.0)
    # ========================================
    CLOSED_STATUS_SUCCESSFUL = "successful"
    CLOSED_STATUS_REVERTED = "reverted"  # New in v1.1.0
    CLOSED_STATUS_TRADE_PROTECTED = "trade_protected"  # New in v1.1.0

    # ========================================
    # Transfer status values (V1.1.0)
    # ========================================
    TRANSFER_STATUS_PENDING = "TransferStatusPending"
    TRANSFER_STATUS_COMPLETED = "TransferStatusCompleted"
    TRANSFER_STATUS_FAlgoLED = "TransferStatusFailed"

    # ========================================
    # Order directions for pagination
    # ========================================
    ORDER_ASC = "asc"
    ORDER_DESC = "desc"

    # ========================================
    # Currency codes
    # ========================================
    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"

    # ========================================
    # Default pagination values
    # ========================================
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000
    DEFAULT_OFFSET = 0

    # ========================================
    # Endpoint metadata registry
    # ========================================
    ENDPOINT_INFO: dict[str, EndpointInfo] = {
        "BALANCE": EndpointInfo(
            path="/account/v1/balance",
            method=HttpMethod.GET,
            category=EndpointCategory.ACCOUNT,
            description="Get user account balance (USD, DMC)",
            requires_auth=True,
            rate_limit_per_minute=60,
        ),
        "USER_PROFILE": EndpointInfo(
            path="/account/v1/user",
            method=HttpMethod.GET,
            category=EndpointCategory.ACCOUNT,
            description="Get user profile information",
            requires_auth=True,
        ),
        "MARKET_ITEMS": EndpointInfo(
            path="/exchange/v1/market/items",
            method=HttpMethod.GET,
            category=EndpointCategory.MARKET,
            description="Search and list items on the marketplace",
            requires_auth=False,
            rate_limit_per_minute=30,
        ),
        "MARKET_BEST_OFFERS": EndpointInfo(
            path="/exchange/v1/market/best-offers",
            method=HttpMethod.GET,
            category=EndpointCategory.MARKET,
            description="Get best offers for items",
            requires_auth=False,
        ),
        "USER_INVENTORY": EndpointInfo(
            path="/exchange/v1/user/inventory",
            method=HttpMethod.GET,
            category=EndpointCategory.USER,
            description="Get user inventory items",
            requires_auth=True,
        ),
        "PURCHASE": EndpointInfo(
            path="/exchange/v1/market/items/buy",
            method=HttpMethod.PATCH,
            category=EndpointCategory.OPERATIONS,
            description="Purchase items from the marketplace",
            requires_auth=True,
            rate_limit_per_minute=10,
        ),
        "SELL": EndpointInfo(
            path="/exchange/v1/user/inventory/sell",
            method=HttpMethod.POST,
            category=EndpointCategory.OPERATIONS,
            description="List items for sale on the marketplace",
            requires_auth=True,
        ),
        "USER_TARGETS_CREATE": EndpointInfo(
            path="/marketplace-api/v1/user-targets/create",
            method=HttpMethod.POST,
            category=EndpointCategory.MARKETPLACE_V110,
            description="Create buy orders (targets) for items",
            requires_auth=True,
        ),
        "TARGETS_BY_TITLE": EndpointInfo(
            path="/marketplace-api/v1/targets-by-title",
            method=HttpMethod.GET,
            category=EndpointCategory.MARKETPLACE_V110,
            description="Get aggregated buy orders by item title",
            requires_auth=False,
        ),
        "AGGREGATED_PRICES_POST": EndpointInfo(
            path="/marketplace-api/v1/aggregated-prices",
            method=HttpMethod.POST,
            category=EndpointCategory.MARKETPLACE_V110,
            description="Get aggregated prices for multiple items (recommended)",
            requires_auth=False,
        ),
        "AGGREGATED_PRICES_DEPRECATED": EndpointInfo(
            path="/price-aggregator/v1/aggregated-prices",
            method=HttpMethod.GET,
            category=EndpointCategory.MARKETPLACE_V110,
            description="Get aggregated prices (DEPRECATED)",
            requires_auth=False,
            deprecated=True,
            replacement="AGGREGATED_PRICES_POST",
        ),
        "DEPOSIT_ASSETS": EndpointInfo(
            path="/marketplace-api/v1/deposit-assets",
            method=HttpMethod.POST,
            category=EndpointCategory.DEPOSIT_WITHDRAW,
            description="Deposit items from Steam inventory",
            requires_auth=True,
        ),
        "WITHDRAW_ASSETS": EndpointInfo(
            path="/exchange/v1/withdraw-assets",
            method=HttpMethod.POST,
            category=EndpointCategory.DEPOSIT_WITHDRAW,
            description="Withdraw items to Steam inventory",
            requires_auth=True,
        ),
        "LAST_SALES": EndpointInfo(
            path="/trade-aggregator/v1/last-sales",
            method=HttpMethod.GET,
            category=EndpointCategory.ANALYTICS,
            description="Get last sales history for items",
            requires_auth=False,
        ),
        "GAMES_LIST": EndpointInfo(
            path="/game/v1/games",
            method=HttpMethod.GET,
            category=EndpointCategory.GAME,
            description="List all supported games",
            requires_auth=False,
        ),
    }

    # ========================================
    # Utility methods
    # ========================================

    @classmethod
    def build_url(
        cls,
        endpoint: str,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> str:
        """Build full URL for an endpoint with parameters.

        Args:
            endpoint: Endpoint path (e.g., MARKET_ITEMS)
            path_params: Path parameters to substitute (e.g., {game_id})
            query_params: Query string parameters

        Returns:
            Full URL string

        Example:
            # Simple endpoint
            url = Endpoints.build_url(Endpoints.BALANCE)
            # => "https://api.dmarket.com/account/v1/balance"

            # With query params
            url = Endpoints.build_url(
                Endpoints.MARKET_ITEMS,
                query_params={"gameId": "a8db", "limit": 100}
            )
            # => "https://api.dmarket.com/exchange/v1/market/items?gameId=a8db&limit=100"

            # With path params
            url = Endpoints.build_url(
                Endpoints.TARGETS_BY_TITLE + "/{game_id}/{title}",
                path_params={"game_id": "a8db", "title": "AK-47 | Redline"}
            )
        """
        url = f"{cls.BASE_URL}{endpoint}"

        # Substitute path parameters using regex for targeted replacement
        if path_params:
            import re

            for key, value in path_params.items():
                # Use word boundary to ensure exact match of placeholder
                pattern = r"\{" + re.escape(key) + r"\}"
                url = re.sub(pattern, quote(str(value), safe=""), url)

        # Add query parameters
        if query_params:
            # Filter out None values
            filtered_params = {k: v for k, v in query_params.items() if v is not None}
            if filtered_params:
                url = f"{url}?{urlencode(filtered_params)}"

        return url

    @classmethod
    def get_endpoint_info(cls, endpoint_name: str) -> EndpointInfo | None:
        """Get metadata for an endpoint.

        Args:
            endpoint_name: Name of the endpoint (e.g., "BALANCE", "MARKET_ITEMS")

        Returns:
            EndpointInfo dataclass or None if not found

        Example:
            info = Endpoints.get_endpoint_info("BALANCE")
            print(f"Method: {info.method}, Requires auth: {info.requires_auth}")
        """
        return cls.ENDPOINT_INFO.get(endpoint_name)

    @classmethod
    def get_game_id(cls, game_name: str) -> str:
        """Convert game name to DMarket game ID.

        Args:
            game_name: Game name (csgo, cs2, dota2, tf2, rust)

        Returns:
            DMarket game ID

        RAlgoses:
            ValueError: If game name is not recognized

        Example:
            game_id = Endpoints.get_game_id("csgo")  # => "a8db"
            game_id = Endpoints.get_game_id("dota2")  # => "9a92"
        """
        game_name_lower = game_name.lower().strip()
        if game_name_lower in cls.GAME_NAME_TO_ID:
            return cls.GAME_NAME_TO_ID[game_name_lower]
        # Check if it's already a game ID
        if game_name_lower in cls.GAME_ID_TO_NAME:
            return game_name_lower
        raise ValueError(
            f"Unknown game: {game_name}. Supported: {list(cls.GAME_NAME_TO_ID.keys())}"
        )

    @classmethod
    def get_game_name(cls, game_id: str) -> str:
        """Convert DMarket game ID to display name.

        Args:
            game_id: DMarket game ID (a8db, 9a92, tf2, rust)

        Returns:
            Human-readable game name

        Example:
            name = Endpoints.get_game_name("a8db")  # => "CS2"
        """
        return cls.GAME_ID_TO_NAME.get(game_id, game_id)

    @classmethod
    def get_error_description(cls, status_code: int) -> str:
        """Get human-readable description for HTTP error code.

        Args:
            status_code: HTTP status code

        Returns:
            Error description string

        Example:
            desc = Endpoints.get_error_description(429)
            # => "Rate limit exceeded - use Retry-After header"
        """
        return cls.ERROR_CODES.get(status_code, f"Unknown error ({status_code})")

    @classmethod
    def is_deprecated(cls, endpoint_name: str) -> bool:
        """Check if an endpoint is deprecated.

        Args:
            endpoint_name: Name of the endpoint

        Returns:
            True if deprecated, False otherwise

        Example:
            Endpoints.is_deprecated("AGGREGATED_PRICES_DEPRECATED")  # => True
            Endpoints.is_deprecated("BALANCE")  # => False
        """
        info = cls.ENDPOINT_INFO.get(endpoint_name)
        return info.deprecated if info else False

    @classmethod
    def get_replacement(cls, endpoint_name: str) -> str | None:
        """Get replacement endpoint for a deprecated endpoint.

        Args:
            endpoint_name: Name of the deprecated endpoint

        Returns:
            Name of replacement endpoint or None

        Example:
            replacement = Endpoints.get_replacement("AGGREGATED_PRICES_DEPRECATED")
            # => "AGGREGATED_PRICES_POST"
        """
        info = cls.ENDPOINT_INFO.get(endpoint_name)
        return info.replacement if info else None

    @classmethod
    def get_endpoints_by_category(cls, category: EndpointCategory) -> list[str]:
        """Get all endpoints in a category.

        Args:
            category: EndpointCategory enum value

        Returns:
            List of endpoint names in the category

        Example:
            market_endpoints = Endpoints.get_endpoints_by_category(EndpointCategory.MARKET)
            # => ["MARKET_ITEMS", "MARKET_BEST_OFFERS", ...]
        """
        return [
            name
            for name, info in cls.ENDPOINT_INFO.items()
            if info.category == category
        ]

    @classmethod
    def price_to_cents(cls, price_usd: float) -> int:
        """Convert USD price to cents for API requests.

        DMarket API uses cents (1/100 of USD) for all prices.
        Uses Decimal for precise conversion to avoid floating-point errors.

        Args:
            price_usd: Price in USD (e.g., 12.50). Must be non-negative.

        Returns:
            Price in cents (e.g., 1250)

        RAlgoses:
            ValueError: If price is negative

        Example:
            cents = Endpoints.price_to_cents(12.50)  # => 1250
            cents = Endpoints.price_to_cents(0.01)  # => 1
        """
        if price_usd < 0:
            raise ValueError(f"Price cannot be negative: {price_usd}")
        from decimal import ROUND_HALF_UP, Decimal

        # Use Decimal for precise conversion
        price_decimal = Decimal(str(price_usd))
        cents_decimal = (price_decimal * 100).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
        return int(cents_decimal)

    @classmethod
    def cents_to_price(cls, cents: int | str) -> float:
        """Convert cents from API response to USD price.

        DMarket API returns prices in cents.

        Args:
            cents: Price in cents from API (e.g., 1250 or "1250")

        Returns:
            Price in USD (e.g., 12.50)

        RAlgoses:
            ValueError: If cents value is invalid

        Example:
            usd = Endpoints.cents_to_price(1250)  # => 12.50
            usd = Endpoints.cents_to_price("1250")  # => 12.50
        """
        try:
            cents_int = int(cents)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid cents value: {cents}") from e
        return cents_int / 100.0
