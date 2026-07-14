"""Unit tests for SteamOracle.

Covers: get_item_price (3-layer cache), get_prices_batch, _parse_price,
throttle, session management, error handling.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.steam_oracle import STEAM_TO_CASH_FACTOR, SteamOracle


@pytest.fixture()
def mock_price_db():
    """Mock the price_db singleton."""
    with patch("src.api.steam_oracle.price_db") as db:
        db.get_latest_price.return_value = None
        db.record_price.return_value = None
        yield db


@pytest.fixture()
def oracle(mock_price_db):
    """Create a SteamOracle with mocked DB."""
    return SteamOracle(api_key="test-key")


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

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_error_response(status: int):
    """Build a mock async context manager for error status."""
    resp = AsyncMock()
    resp.status = status

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
    async def test_memory_cache_hit(self, oracle: SteamOracle):
        """Layer 1: in-memory cache returns instantly."""
        oracle._mem_cache["AK_test"] = (12.50, time.time())
        price = await oracle.get_item_price("AK_test")
        assert price == pytest.approx(12.50)

    @pytest.mark.asyncio
    async def test_memory_cache_expired(self, oracle: SteamOracle, mock_price_db):
        """Expired memory cache falls through to SQLite."""
        oracle._mem_cache["AK_test"] = (12.50, time.time() - 2000)
        mock_price_db.get_latest_price.return_value = 14.00
        price = await oracle.get_item_price("AK_test")
        assert price == pytest.approx(14.00)

    @pytest.mark.asyncio
    async def test_sqlite_cache_hit(self, oracle: SteamOracle, mock_price_db):
        """Layer 2: SQLite cache returns without API call."""
        mock_price_db.get_latest_price.return_value = 25.00
        price = await oracle.get_item_price("AWP_Asiimov")
        assert price == pytest.approx(25.00)
        mock_price_db.get_latest_price.assert_called_once_with(
            "steam:AWP_Asiimov", max_age_seconds=10800
        )

    @pytest.mark.asyncio
    async def test_api_success_median_price(self, oracle: SteamOracle, mock_price_db):
        """Layer 3: valid API response with median_price."""
        api_data = {"success": True, "median_price": "$35.50", "volume": "123"}
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("AWP_Asiimov")
        expected = round(35.50 * STEAM_TO_CASH_FACTOR, 2)
        assert price == pytest.approx(expected)
        mock_price_db.record_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_success_lowest_price_fallback(self, oracle: SteamOracle, mock_price_db):
        """Falls back to lowest_price when median_price absent."""
        api_data = {"success": True, "lowest_price": "$20.00"}
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        expected = round(20.00 * STEAM_TO_CASH_FACTOR, 2)
        assert price == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_api_success_false(self, oracle: SteamOracle):
        """success=false returns 0.0."""
        api_data: dict = {"success": False}
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_api_empty_price_string(self, oracle: SteamOracle):
        """Empty price string returns 0.0."""
        api_data = {"success": True, "median_price": ""}
        handler = MagicMock(return_value=_mock_json_response(200, api_data))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        assert price == 0.0


# =====================================================================
# get_item_price — Error Handling
# =====================================================================


class TestGetItemPriceErrors:
    """Tests for API error responses."""

    @pytest.mark.asyncio
    async def test_429_returns_zero(self, oracle: SteamOracle):
        """429 rate limit returns 0.0 (with backoff sleep)."""
        handler = MagicMock(return_value=_mock_error_response(429))
        oracle._session = _make_mock_session(handler)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            price = await oracle.get_item_price("Item")
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_non_200_returns_zero(self, oracle: SteamOracle):
        """Non-200 status returns 0.0."""
        handler = MagicMock(return_value=_mock_error_response(500))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_timeout_returns_zero(self, oracle: SteamOracle):
        """Timeout returns 0.0."""
        handler = MagicMock(side_effect=asyncio.TimeoutError)
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_network_error_returns_zero(self, oracle: SteamOracle):
        """Connection error returns 0.0."""
        handler = MagicMock(side_effect=Exception("Connection refused"))
        oracle._session = _make_mock_session(handler)

        price = await oracle.get_item_price("Item")
        assert price == 0.0


# =====================================================================
# get_prices_batch
# =====================================================================


class TestGetPricesBatch:
    """Tests for batch price fetching."""

    @pytest.mark.asyncio
    async def test_batch_returns_all(self, oracle: SteamOracle):
        """Batch fetches returns prices for all items."""
        oracle._mem_cache = {
            "Item1": (10.0, time.time()),
            "Item2": (20.0, time.time()),
        }
        result = await oracle.get_prices_batch(["Item1", "Item2"])
        assert result == {"Item1": 10.0, "Item2": 20.0}

    @pytest.mark.asyncio
    async def test_batch_partial_hit(self, oracle: SteamOracle, mock_price_db):
        """Missing items return 0.0 from API."""
        oracle._mem_cache = {"Item1": (10.0, time.time())}
        mock_price_db.get_latest_price.return_value = None

        handler = MagicMock(
            return_value=_mock_json_response(200, {"success": False})
        )
        oracle._session = _make_mock_session(handler)

        result = await oracle.get_prices_batch(["Item1", "Item2"])
        assert result["Item1"] == pytest.approx(10.0)
        assert result["Item2"] == 0.0

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, oracle: SteamOracle):
        """Empty input returns empty dict."""
        result = await oracle.get_prices_batch([])
        assert result == {}


# =====================================================================
# _parse_price (static)
# =====================================================================


class TestParsePrice:
    """Tests for Steam price string parsing."""

    def test_dollar_format(self):
        assert SteamOracle._parse_price("$12.34") == pytest.approx(12.34)

    def test_euro_comma_format(self):
        assert SteamOracle._parse_price("12,34") == pytest.approx(12.34)

    def test_no_currency_symbol(self):
        assert SteamOracle._parse_price("45.67") == pytest.approx(45.67)

    def test_whitespace(self):
        assert SteamOracle._parse_price("  $9.99  ") == pytest.approx(9.99)

    def test_empty_string(self):
        assert SteamOracle._parse_price("") == 0.0

    def test_invalid_string(self):
        assert SteamOracle._parse_price("abc") == 0.0

    def test_non_string_raises(self):
        """Non-string input raises AttributeError (caller's responsibility)."""
        with pytest.raises(AttributeError):
            SteamOracle._parse_price(None)


# =====================================================================
# Session Management
# =====================================================================


class TestSessionManagement:
    """Tests for session lifecycle."""

    @pytest.mark.asyncio
    async def test_session_created_once(self, oracle: SteamOracle):
        """Second call reuses existing session."""
        mock_session = AsyncMock()
        mock_session.closed = False

        with patch("aiohttp.ClientSession", return_value=mock_session):
            s1 = await oracle._get_session()
            s2 = await oracle._get_session()
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_close_session(self, oracle: SteamOracle):
        """close() closes the underlying session."""
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        oracle._session = mock_session

        await oracle.close()
        mock_session.close.assert_called_once()


# =====================================================================
# Steam-to-Cash Factor
# =====================================================================


class TestSteamToCashFactor:
    """Verify the Steam price adjustment factor."""

    def test_factor_is_085(self):
        """Steam prices are reduced by 15% to estimate cash value."""
        assert STEAM_TO_CASH_FACTOR == pytest.approx(0.85)
