"""Fixtures for integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.database import DatabaseManager


@pytest.fixture(autouse=True)
def reset_circuit_breakers_for_integration() -> Generator[None, None, None]:
    """Reset all circuit breakers before and after each integration test.

    This ensures tests are isolated from circuit breaker state.
    autouse=True means this runs automatically for all tests in this directory.
    """
    try:
        from src.utils.api_circuit_breaker import reset_all_circuit_breakers

        # Reset before test
        reset_all_circuit_breakers()
    except ImportError:
        pass

    yield

    try:
        from src.utils.api_circuit_breaker import reset_all_circuit_breakers

        # Reset after test
        reset_all_circuit_breakers()
    except ImportError:
        pass


@pytest_asyncio.fixture
async def test_database() -> AsyncGenerator[DatabaseManager, None]:
    """Create test database instance."""
    from src.utils.database import DatabaseManager

    # Use in-memory SQLite for tests
    db_url = "sqlite:///:memory:"
    db = DatabaseManager(db_url)

    await db.init_database()

    yield db

    await db.close()


@pytest_asyncio.fixture
async def mock_dmarket_api() -> DMarketAPI:
    """Create DMarketAPI instance for mocking."""
    from src.dmarket.dmarket_api import DMarketAPI

    return DMarketAPI(
        public_key="test_public_key",
        secret_key="test_secret_key",
        api_url="https://api.dmarket.com",
    )


@pytest.fixture()
def mock_market_items_response() -> dict[str, Any]:
    """Mock response for market items."""
    return {
        "cursor": "next_page_cursor",
        "objects": [
            {
                "itemId": "item_001",
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"USD": "1250"},
                "suggestedPrice": {"USD": "1350"},
                "imageUrl": "https://example.com/image.png",
                "extra": {
                    "category": "Rifle",
                    "exterior": "Field-Tested",
                    "rarity": "Classified",
                    "popularity": 0.85,
                },
            },
            {
                "itemId": "item_002",
                "title": "AWP | Asiimov (Field-Tested)",
                "price": {"USD": "8500"},
                "suggestedPrice": {"USD": "9200"},
                "imageUrl": "https://example.com/image2.png",
                "extra": {
                    "category": "Sniper Rifle",
                    "exterior": "Field-Tested",
                    "rarity": "Covert",
                    "popularity": 0.92,
                },
            },
        ],
        "total": 2,
    }


@pytest.fixture()
def mock_balance_response() -> dict[str, str]:
    """Mock response for balance."""
    return {
        "usd": "10000",  # $100.00
        "usdAvAlgolableToWithdraw": "9500",
        "dmc": "5000",
        "dmcAvAlgolableToWithdraw": "4500",
    }


@pytest.fixture()
def mock_aggregated_prices_response() -> dict[str, Any]:
    """Mock response for aggregated prices."""
    return {
        "aggregatedPrices": [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "orderBestPrice": "1200",
                "orderCount": 15,
                "offerBestPrice": "1250",
                "offerCount": 23,
            }
        ],
        "nextCursor": "",
    }


@pytest.fixture()
def mock_sales_history_response() -> dict[str, Any]:
    """Mock response for sales history."""
    return {
        "sales": [
            {"price": "1250", "date": 1699876543, "txOperationType": "Offer"},
            {"price": "1240", "date": 1699876443, "txOperationType": "Target"},
            {"price": "1260", "date": 1699876343, "txOperationType": "Offer"},
        ]
    }


@pytest.fixture()
def mock_rate_limit_error() -> httpx.Response:
    """Mock 429 rate limit error response."""
    return httpx.Response(
        status_code=429,
        headers={"Retry-After": "60"},
        json={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
            }
        },
    )


@pytest.fixture()
def mock_api_error() -> httpx.Response:
    """Mock 500 server error response."""
    return httpx.Response(
        status_code=500,
        json={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            }
        },
    )


@pytest.fixture()
def mock_network_error() -> Exception:
    """Mock network error."""
    return httpx.ConnectError("Connection failed")
