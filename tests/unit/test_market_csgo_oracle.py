"""Unit tests for MarketCsgoOracle.

Covers: load_items (cache + API), get_item_price, get_item_volume,
get_prices_batch, get_stats, session management.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.market_csgo_oracle import MarketCsgoOracle


@pytest.fixture()
def mock_price_db():
    """Mock the price_db singleton."""
    with patch("src.api.market_csgo_oracle.price_db") as db:
        db.record_price.return_value = None
        yield db


@pytest.fixture()
def oracle(mock_price_db):
    """Create a MarketCsgoOracle with mocked DB."""
    return MarketCsgoOracle()


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


def _sample_items():
    """Sample Market.CSGO API response."""
    return {
        "items": [
            {"market_hash_name": "AK-47 | Redline", "volume": "442", "price": "30.546"},
            {"market_hash_name": "AWP | Asiimov", "volume": "100", "price": "50.00"},
            {"market_hash_name": "Empty Item", "volume": "0", "price": "0"},
        ]
    }


# =====================================================================
# load_items
# =====================================================================


class TestLoadItems:
    """Tests for bulk item loading from Market.CSGO API."""

    @pytest.mark.asyncio
    async def test_load_success(self, oracle: MarketCsgoOracle, mock_price_db):
        """Valid API response populates cache correctly."""
        handler = MagicMock(return_value=_mock_json_response(200, _sample_items()))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 3
        assert oracle._items_cache["AK-47 | Redline"]["price"] == pytest.approx(30.546)
        assert oracle._items_cache["AK-47 | Redline"]["volume"] == 442

    @pytest.mark.asyncio
    async def test_load_persists_to_sqlite(self, oracle: MarketCsgoOracle, mock_price_db):
        """Loaded items are persisted to SQLite."""
        handler = MagicMock(return_value=_mock_json_response(200, _sample_items()))
        oracle._session = _make_mock_session(handler)

        await oracle.load_items()
        assert mock_price_db.record_price.call_count == 3

    @pytest.mark.asyncio
    async def test_load_cache_hit(self, oracle: MarketCsgoOracle):
        """Second call within TTL returns cached count."""
        oracle._items_cache = {"Item": {"price": 10.0, "volume": 5}}
        oracle._items_cache_ts = time.time()

        count = await oracle.load_items()
        assert count == 1

    @pytest.mark.asyncio
    async def test_load_cache_expired(self, oracle: MarketCsgoOracle, mock_price_db):
        """Expired cache triggers fresh API call."""
        oracle._items_cache = {"Old": {"price": 1.0, "volume": 1}}
        oracle._items_cache_ts = time.time() - 2000

        handler = MagicMock(return_value=_mock_json_response(200, _sample_items()))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 3
        assert "Old" not in oracle._items_cache

    @pytest.mark.asyncio
    async def test_load_non_200_returns_zero(self, oracle: MarketCsgoOracle):
        """Non-200 status returns 0."""
        handler = MagicMock(return_value=_mock_error_response(500))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_429_returns_zero(self, oracle: MarketCsgoOracle):
        """429 rate limit returns 0."""
        handler = MagicMock(return_value=_mock_error_response(429))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_empty_items(self, oracle: MarketCsgoOracle):
        """Empty items list returns 0."""
        handler = MagicMock(return_value=_mock_json_response(200, {"items": []}))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_missing_items_key(self, oracle: MarketCsgoOracle):
        """Missing 'items' key returns 0."""
        handler = MagicMock(return_value=_mock_json_response(200, {}))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_exception_returns_zero(self, oracle: MarketCsgoOracle):
        """Network exception returns 0."""
        handler = MagicMock(side_effect=Exception("Connection failed"))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_skips_empty_names(self, oracle: MarketCsgoOracle, mock_price_db):
        """Items with empty market_hash_name are skipped."""
        data = {"items": [{"market_hash_name": "", "volume": "5", "price": "10.0"}]}
        handler = MagicMock(return_value=_mock_json_response(200, data))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_skips_invalid_price(self, oracle: MarketCsgoOracle, mock_price_db):
        """Items with non-numeric price are skipped."""
        data = {
            "items": [
                {"market_hash_name": "Bad", "volume": "5", "price": "not_a_number"}
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, data))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_skips_invalid_volume(self, oracle: MarketCsgoOracle, mock_price_db):
        """Items with non-numeric volume are skipped."""
        data = {
            "items": [
                {"market_hash_name": "Bad", "volume": "NaN", "price": "10.0"}
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, data))
        oracle._session = _make_mock_session(handler)

        count = await oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_load_string_prices_parsed(self, oracle: MarketCsgoOracle, mock_price_db):
        """String price/volume values are correctly parsed."""
        data = {
            "items": [
                {"market_hash_name": "Item", "volume": "42", "price": "15.75"}
            ]
        }
        handler = MagicMock(return_value=_mock_json_response(200, data))
        oracle._session = _make_mock_session(handler)

        await oracle.load_items()
        assert oracle._items_cache["Item"]["price"] == pytest.approx(15.75)
        assert oracle._items_cache["Item"]["volume"] == 42


# =====================================================================
# get_item_price / get_item_volume
# =====================================================================


class TestSingleItemAccessors:
    """Tests for single-item lookups."""

    @pytest.mark.asyncio
    async def test_get_price_exists(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {"Item": {"price": 30.55, "volume": 100}}
        oracle._items_cache_ts = time.time()
        assert await oracle.get_item_price("Item") == pytest.approx(30.55)

    @pytest.mark.asyncio
    async def test_get_price_missing(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {}
        oracle._items_cache_ts = time.time()
        assert await oracle.get_item_price("NoSuch") == 0.0

    @pytest.mark.asyncio
    async def test_get_volume_exists(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {"Item": {"price": 10.0, "volume": 442}}
        oracle._items_cache_ts = time.time()
        assert await oracle.get_item_volume("Item") == 442

    @pytest.mark.asyncio
    async def test_get_volume_missing(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {}
        oracle._items_cache_ts = time.time()
        assert await oracle.get_item_volume("NoSuch") == 0


# =====================================================================
# get_prices_batch
# =====================================================================


class TestGetPricesBatch:
    """Tests for batch price fetching."""

    @pytest.mark.asyncio
    async def test_batch_partial_match(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {
            "A": {"price": 10.0, "volume": 1},
            "B": {"price": 20.0, "volume": 2},
        }
        oracle._items_cache_ts = time.time()

        result = await oracle.get_prices_batch(["A", "C"])
        assert result == {"A": 10.0}
        assert "C" not in result

    @pytest.mark.asyncio
    async def test_batch_empty_input(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {"A": {"price": 10.0, "volume": 1}}
        oracle._items_cache_ts = time.time()

        result = await oracle.get_prices_batch([])
        assert result == {}


# =====================================================================
# get_stats
# =====================================================================


class TestGetStats:
    """Tests for oracle statistics."""

    def test_stats_with_cache(self, oracle: MarketCsgoOracle):
        oracle._items_cache = {"A": {}, "B": {}, "C": {}}
        oracle._items_cache_ts = time.time() - 5

        stats = oracle.get_stats()
        assert stats["items_cached"] == 3
        assert stats["cache_age_sec"] is not None
        assert stats["cache_age_sec"] >= 5.0

    def test_stats_empty_cache(self, oracle: MarketCsgoOracle):
        stats = oracle.get_stats()
        assert stats["items_cached"] == 0
        assert stats["cache_age_sec"] is None


# =====================================================================
# Session Management
# =====================================================================


class TestSessionManagement:
    """Tests for session lifecycle."""

    @pytest.mark.asyncio
    async def test_session_created_once(self, oracle: MarketCsgoOracle):
        mock_session = AsyncMock()
        mock_session.closed = False

        with patch("aiohttp.ClientSession", return_value=mock_session):
            s1 = await oracle._get_session()
            s2 = await oracle._get_session()
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_close_session(self, oracle: MarketCsgoOracle):
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        oracle._session = mock_session

        await oracle.close()
        mock_session.close.assert_called_once()
