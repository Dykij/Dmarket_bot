"""Unit tests for CSFloatOracle.

Covers: get_item_price (layered cache), get_sales_history,
get_listings_filtered, scan_low_floats, throttle, session management.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.csfloat_oracle import CSFloatOracle
from src.api.exceptions import RateLimitException


@pytest.fixture()
def mock_price_db():
    """Mock the price_db singleton."""
    with patch("src.api.csfloat_oracle.price_db") as db:
        db.get_state.return_value = None
        db.get_latest_price.return_value = None
        db.record_price.return_value = None
        db.save_state.return_value = None
        yield db


@pytest.fixture()
def oracle(mock_price_db):
    """Create a CSFloatOracle with mocked DB."""
    return CSFloatOracle(api_key="test-key")


def _make_mock_session(get_handler):
    """Build a mock aiohttp session with closed=False and custom get behavior."""
    session = MagicMock()
    session.closed = False
    session.get = get_handler
    return session


def _mock_json_response(status: int, json_data: dict):
    """Build a mock async context manager returning JSON."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    resp.raise_for_status = MagicMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_error_response(status: int, raise_exc: Exception | None = None):
    """Build a mock async context manager for error status."""
    resp = AsyncMock()
    resp.status = status
    resp.raise_for_status = MagicMock(side_effect=raise_exc) if raise_exc else MagicMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# =====================================================================
# get_item_price — Layered Cache
# =====================================================================


class TestGetItemPriceCache:
    """Tests for the 3-layer price lookup."""

    @pytest.mark.asyncio
    async def test_memory_cache_hit(self, oracle: CSFloatOracle):
        """Layer 1: memory cache returns instantly."""
        oracle._mem_cache["AK_test_0"] = (15.50, time.time())
        price = await oracle.get_item_price("AK_test", offset=0)
        assert price == pytest.approx(15.50)

    @pytest.mark.asyncio
    async def test_memory_cache_expired(self, oracle: CSFloatOracle, mock_price_db):
        """Expired memory cache falls through to SQLite layer."""
        oracle._mem_cache["AK_test_0"] = (15.50, time.time() - 2000)
        mock_price_db.get_latest_price.return_value = 16.00
        price = await oracle.get_item_price("AK_test", offset=0)
        assert price == pytest.approx(16.00)

    @pytest.mark.asyncio
    async def test_sqlite_cache_hit(self, oracle: CSFloatOracle, mock_price_db):
        """Layer 2: SQLite cache returns without API call."""
        mock_price_db.get_latest_price.return_value = 20.00
        price = await oracle.get_item_price("AWP_Asiimov", offset=0)
        assert price == pytest.approx(20.00)
        mock_price_db.get_latest_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_returns_valid_price(self, oracle: CSFloatOracle, mock_price_db):
        """Layer 3: live API with valid listing data."""
        api_data = {
            "data": [
                {"price": 1250, "reference": {"predicted_price": 1200}}
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("AK_Redline", offset=0)
        assert price == pytest.approx(12.50)
        mock_price_db.record_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_returns_predicted_price(self, oracle: CSFloatOracle, mock_price_db):
        """Use predicted_price when listed price is zero."""
        api_data = {
            "data": [{"price": 0, "reference": {"predicted_price": 999}}]
        }
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Rare_Item", offset=0)
        assert price == pytest.approx(9.99)

    @pytest.mark.asyncio
    async def test_api_empty_data(self, oracle: CSFloatOracle):
        """Empty data list returns 0.0."""
        api_data: dict = {"data": []}
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Unknown", offset=0)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_api_no_data_key(self, oracle: CSFloatOracle):
        """Missing 'data' key returns 0.0."""
        handler = MagicMock(return_value=_mock_json_response(200, {}))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Missing", offset=0)
        assert price == 0.0


# =====================================================================
# get_item_price — Error Handling
# =====================================================================


class TestGetItemPriceErrors:
    """Tests for API error responses."""

    @pytest.mark.asyncio
    async def test_404_returns_zero(self, oracle: CSFloatOracle):
        """404 means no listing — returns 0.0."""
        handler = MagicMock(return_value=_mock_error_response(404))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("NoItem", offset=0)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self, oracle: CSFloatOracle, mock_price_db):
        """429 raises RateLimitException (wrapped by tenacity RetryError) and doubles delay."""
        handler = MagicMock(return_value=_mock_error_response(429))
        oracle._session = _make_mock_session(handler)

        # The @retry decorator wraps RateLimitException in RetryError after 5 attempts
        # Patch asyncio.sleep to skip the exponential backoff delays
        from tenacity import RetryError
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises((RateLimitException, RetryError)):
                await oracle.get_item_price("Popular", offset=0)

        assert oracle.request_delay > 1.0
        mock_price_db.save_state.assert_called()

    @pytest.mark.asyncio
    async def test_500_returns_zero(self, oracle: CSFloatOracle):
        """500 HTTP error returns 0.0 (after raise_for_status)."""
        handler = MagicMock(
            return_value=_mock_error_response(500, Exception("Internal Server Error"))
        )
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("BadItem", offset=0)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_timeout_returns_zero(self, oracle: CSFloatOracle):
        """Timeout exception returns 0.0."""
        handler = MagicMock(side_effect=asyncio.TimeoutError("Connection timed out"))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("SlowItem", offset=0)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_network_error_returns_zero(self, oracle: CSFloatOracle):
        """Generic connection error returns 0.0."""
        handler = MagicMock(side_effect=Exception("Connection refused"))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Offline", offset=0)
        assert price == 0.0


# =====================================================================
# get_sales_history
# =====================================================================


class TestGetSalesHistory:
    """Tests for CSFloat sales history endpoint."""

    @pytest.mark.asyncio
    async def test_success(self, oracle: CSFloatOracle):
        """Valid sales data parsed correctly."""
        api_data = {
            "data": [
                {"price": 1500, "float_value": 0.15, "sold_at": "2026-01-01"},
                {"price": 1600, "float_value": 0.20, "sold_at": "2026-01-02"},
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("AK_Redline", limit=50)
        assert len(sales) == 2
        assert sales[0]["price"] == pytest.approx(15.00)
        assert sales[1]["float_value"] == 0.20

    @pytest.mark.asyncio
    async def test_429_returns_empty(self, oracle: CSFloatOracle):
        """429 on sales history returns empty list."""
        handler = MagicMock(return_value=_mock_error_response(429))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("Item")
        assert sales == []

    @pytest.mark.asyncio
    async def test_non_200_returns_empty(self, oracle: CSFloatOracle):
        """Non-200 status returns empty list."""
        handler = MagicMock(return_value=_mock_error_response(500))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("Item")
        assert sales == []

    @pytest.mark.asyncio
    async def test_empty_data(self, oracle: CSFloatOracle):
        """Empty data array returns empty list."""
        handler = MagicMock(return_value=_mock_json_response(200, {"data": []}))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("NewItem")
        assert sales == []

    @pytest.mark.asyncio
    async def test_zero_price_filtered(self, oracle: CSFloatOracle):
        """Sales with zero price are filtered out."""
        api_data = {
            "data": [
                {"price": 0, "float_value": 0.1, "sold_at": "2026-01-01"},
                {"price": 2000, "float_value": 0.5, "sold_at": "2026-01-02"},
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("Item")
        assert len(sales) == 1
        assert sales[0]["price"] == pytest.approx(20.00)

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, oracle: CSFloatOracle):
        """Network exception returns empty list."""
        handler = MagicMock(side_effect=Exception("fail"))
        oracle._session = _make_mock_session(handler)

        sales = await oracle.get_sales_history("Item")
        assert sales == []


# =====================================================================
# get_listings_filtered
# =====================================================================


class TestGetListingsFiltered:
    """Tests for filtered listing search."""

    @pytest.mark.asyncio
    async def test_success_with_filters(self, oracle: CSFloatOracle):
        """Filtered listings returned correctly."""
        api_data = {
            "data": [
                {
                    "id": "abc123",
                    "price": 5000,
                    "item": {
                        "float_value": 0.005,
                        "paint_seed": 42,
                        "paint_index": 100,
                        "stickers": ["Katowice 2014"],
                        "collection": "Cobblestone",
                        "rarity": 5,
                        "quality": 4,
                        "is_stattrak": True,
                        "is_souvenir": False,
                        "market_hash_name": "AWP | Dragon Lore",
                    },
                }
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        results = await oracle.get_listings_filtered(
            "AWP_Dragon_Lore", min_float=0.0, max_float=0.01
        )
        assert len(results) == 1
        assert results[0]["price"] == pytest.approx(50.00)
        assert results[0]["is_stattrak"] is True

    @pytest.mark.asyncio
    async def test_429_returns_empty(self, oracle: CSFloatOracle):
        handler = MagicMock(return_value=_mock_error_response(429))
        oracle._session = _make_mock_session(handler)

        results = await oracle.get_listings_filtered("Item")
        assert results == []

    @pytest.mark.asyncio
    async def test_non_200_returns_empty(self, oracle: CSFloatOracle):
        handler = MagicMock(return_value=_mock_error_response(500))
        oracle._session = _make_mock_session(handler)

        results = await oracle.get_listings_filtered("Item")
        assert results == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self, oracle: CSFloatOracle):
        handler = MagicMock(side_effect=Exception("fail"))
        oracle._session = _make_mock_session(handler)

        results = await oracle.get_listings_filtered("Item")
        assert results == []


# =====================================================================
# scan_low_floats
# =====================================================================


class TestScanLowFloats:
    """Tests for ultra-low-float scanner."""

    @pytest.mark.asyncio
    async def test_delegates_to_filtered(self, oracle: CSFloatOracle):
        """scan_low_floats calls get_listings_filtered with correct params."""
        oracle.get_listings_filtered = AsyncMock(return_value=[{"price": 100.0}])
        result = await oracle.scan_low_floats("Item", max_float=0.005, limit=10)
        oracle.get_listings_filtered.assert_called_once_with(
            "Item", max_float=0.005, sort_by="lowest_float", limit=10
        )
        assert len(result) == 1


# =====================================================================
# Session Management
# =====================================================================


class TestSessionManagement:
    """Tests for session lifecycle."""

    @pytest.mark.asyncio
    async def test_session_created_once(self, oracle: CSFloatOracle):
        """Second call reuses existing session."""
        mock_session = AsyncMock()
        mock_session.closed = False

        with patch("aiohttp.ClientSession", return_value=mock_session):
            s1 = await oracle.get_session()
            s2 = await oracle.get_session()
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_close_session(self, oracle: CSFloatOracle):
        """close() closes the underlying session."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        oracle._session = mock_session

        await oracle.close()
        mock_session.close.assert_called_once()


# =====================================================================
# Throttle
# =====================================================================


class TestThrottle:
    """Tests for request throttling."""

    @pytest.mark.asyncio
    async def test_throttle_delay_enforced(self, oracle: CSFloatOracle):
        """Throttle sleeps when requests are too fast."""
        oracle._last_request_time = time.monotonic()
        oracle.request_delay = 0.05

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await oracle._throttle()
            mock_sleep.assert_awaited()

    @pytest.mark.asyncio
    async def test_throttle_no_delay_when_slow(self, oracle: CSFloatOracle):
        """No sleep when enough time has passed."""
        oracle._last_request_time = time.monotonic() - 100
        oracle.request_delay = 1.0

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await oracle._throttle()
            mock_sleep.assert_not_awaited()
