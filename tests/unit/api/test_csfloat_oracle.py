"""Unit tests for CSFloatOracle (src/api/csfloat_oracle.py)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.exceptions import RateLimitException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int = 200, json_data: dict | None = None):
    """Create a mock aiohttp response used as async context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    # async context-manager protocol
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _listing(price_cents: int = 1500, predicted_cents: int = 0) -> dict:
    """Single CSFloat listing dict."""
    entry: dict = {"price": price_cents}
    if predicted_cents:
        entry["reference"] = {"predicted_price": predicted_cents}
    return entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _mock_price_db():
    """Patch the price_db singleton used by csfloat_oracle."""
    with patch("src.api.csfloat_oracle.price_db") as mock_db:
        mock_db.get_latest_price.return_value = None
        mock_db.get_state.return_value = None
        mock_db.record_price = MagicMock()
        mock_db.save_state = MagicMock()
        yield mock_db


@pytest.fixture()
def _oracle(_mock_price_db):
    """Return a fresh CSFloatOracle with mocked DB."""
    from src.api.csfloat_oracle import CSFloatOracle

    return CSFloatOracle(api_key="test_key")


@pytest.fixture()
def _mock_session(_oracle):
    """Attach a mock HTTP session to the oracle."""
    session = AsyncMock()
    session.closed = False
    session.get = MagicMock()
    session.close = AsyncMock()
    _oracle._session = session
    return session


# ---------------------------------------------------------------------------
# Tests — get_item_price
# ---------------------------------------------------------------------------

class TestGetItemPrice:
    """Tests for CSFloatOracle.get_item_price."""

    @pytest.mark.asyncio()
    async def test_success(self, _oracle, _mock_session):
        """Happy path: API returns listing data with price in cents."""
        _mock_session.get.return_value = _make_response(
            200, {"data": [_listing(price_cents=1500)]}
        )
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 15.0

    @pytest.mark.asyncio()
    async def test_success_with_predicted(self, _oracle, _mock_session):
        """When listed price is zero, fall back to predicted_price."""
        _mock_session.get.return_value = _make_response(
            200, {"data": [_listing(price_cents=0, predicted_cents=1200)]}
        )
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 12.0

    @pytest.mark.asyncio()
    async def test_not_found(self, _oracle, _mock_session):
        """404 response → 0.0."""
        _mock_session.get.return_value = _make_response(404)
        price = await _oracle.get_item_price("Nonexistent Item")
        assert price == 0.0

    @pytest.mark.asyncio()
    async def test_rate_limit(self, _oracle, _mock_session, _mock_price_db):
        """429 → delay increased, RateLimitException raised (wrapped in RetryError by tenacity)."""
        _mock_session.get.return_value = _make_response(429)
        original_delay = _oracle.request_delay

        with pytest.raises((RateLimitException, Exception)):
            await _oracle.get_item_price("AK-47 | Redline (FT)")

        # tenacity wraps the final RateLimitException in RetryError
        assert _oracle.request_delay >= original_delay * 2.0
        _mock_price_db.save_state.assert_called()

    @pytest.mark.asyncio()
    async def test_cached_memory(self, _oracle, _mock_session):
        """Memory cache hit (within 15 min TTL) → no HTTP call."""
        _oracle._mem_cache["AK-47 | Redline (FT)_0"] = (15.0, time.time())
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 15.0
        _mock_session.get.assert_not_called()

    @pytest.mark.asyncio()
    async def test_cached_db(self, _oracle, _mock_session, _mock_price_db):
        """SQLite cache hit → no HTTP call."""
        _mock_price_db.get_latest_price.return_value = 14.5
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 14.5
        _mock_session.get.assert_not_called()

    @pytest.mark.asyncio()
    async def test_empty_data(self, _oracle, _mock_session):
        """API returns empty data list → 0.0."""
        _mock_session.get.return_value = _make_response(200, {"data": []})
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 0.0

    @pytest.mark.asyncio()
    async def test_generic_exception(self, _oracle, _mock_session):
        """Unexpected error → 0.0 (graceful degradation)."""
        _mock_session.get.side_effect = Exception("network boom")
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 0.0


# ---------------------------------------------------------------------------
# Tests — get_sales_history
# ---------------------------------------------------------------------------

class TestGetSalesHistory:
    """Tests for CSFloatOracle.get_sales_history."""

    @pytest.mark.asyncio()
    async def test_success(self, _oracle, _mock_session):
        """Valid history response → list of price/float_value/date dicts."""
        _mock_session.get.return_value = _make_response(200, {
            "data": [
                {"price": 1500, "float_value": 0.015, "sold_at": "2026-01-01"},
                {"price": 1600, "float_value": 0.022, "sold_at": "2026-01-02"},
            ]
        })
        sales = await _oracle.get_sales_history("AK-47 | Redline (FT)")
        assert len(sales) == 2
        assert sales[0]["price"] == 15.0
        assert sales[0]["float_value"] == 0.015
        assert sales[1]["date"] == "2026-01-02"

    @pytest.mark.asyncio()
    async def test_rate_limit(self, _oracle, _mock_session):
        """429 on history → empty list (no exception propagation)."""
        _mock_session.get.return_value = _make_response(429)
        sales = await _oracle.get_sales_history("AK-47 | Redline (FT)")
        assert sales == []

    @pytest.mark.asyncio()
    async def test_non_200(self, _oracle, _mock_session):
        """Non-200, non-429 → empty list."""
        _mock_session.get.return_value = _make_response(500)
        sales = await _oracle.get_sales_history("AK-47 | Redline (FT)")
        assert sales == []

    @pytest.mark.asyncio()
    async def test_zero_price_skipped(self, _oracle, _mock_session):
        """Entries with price=0 are filtered out."""
        _mock_session.get.return_value = _make_response(200, {
            "data": [
                {"price": 0, "float_value": 0.01, "sold_at": "2026-01-01"},
                {"price": 1500, "float_value": 0.02, "sold_at": "2026-01-02"},
            ]
        })
        sales = await _oracle.get_sales_history("AK-47 | Redline (FT)")
        assert len(sales) == 1
        assert sales[0]["price"] == 15.0


# ---------------------------------------------------------------------------
# Tests — get_listings_filtered
# ---------------------------------------------------------------------------

class TestGetListingsFiltered:
    """Tests for CSFloatOracle.get_listings_filtered."""

    @pytest.mark.asyncio()
    async def test_success(self, _oracle, _mock_session):
        """Filtered listings returned with all fields parsed."""
        _mock_session.get.return_value = _make_response(200, {
            "data": [{
                "id": "lst_001",
                "price": 2000,
                "item": {
                    "float_value": 0.005,
                    "paint_seed": 42,
                    "paint_index": 567,
                    "stickers": ["Katowice 2014"],
                    "collection": "Cobblestone",
                    "rarity": 6,
                    "quality": 3,
                    "is_stattrak": True,
                    "is_souvenir": False,
                    "market_hash_name": "AK-47 | Redline (FT)",
                },
            }]
        })
        results = await _oracle.get_listings_filtered(
            "AK-47 | Redline (FT)", max_float=0.01, paint_seed=42
        )
        assert len(results) == 1
        r = results[0]
        assert r["price"] == 20.0
        assert r["float_value"] == 0.005
        assert r["paint_seed"] == 42
        assert r["is_stattrak"] is True
        assert r["listing_id"] == "lst_001"

    @pytest.mark.asyncio()
    async def test_429(self, _oracle, _mock_session):
        """429 → empty list (no crash)."""
        _mock_session.get.return_value = _make_response(429)
        results = await _oracle.get_listings_filtered("AK-47 | Redline (FT)")
        assert results == []

    @pytest.mark.asyncio()
    async def test_non_200(self, _oracle, _mock_session):
        """Non-200 → empty list."""
        _mock_session.get.return_value = _make_response(500)
        results = await _oracle.get_listings_filtered("AK-47 | Redline (FT)")
        assert results == []


# ---------------------------------------------------------------------------
# Tests — scan_low_floats
# ---------------------------------------------------------------------------

class TestScanLowFloats:
    """Tests for CSFloatOracle.scan_low_floats."""

    @pytest.mark.asyncio()
    async def test_delegates_to_filtered(self, _oracle):
        """scan_low_floats calls get_listings_filtered with correct params."""
        expected = [{"price": 10.0, "float_value": 0.003}]
        with patch.object(
            _oracle, "get_listings_filtered", new_callable=AsyncMock, return_value=expected
        ) as mock_filt:
            result = await _oracle.scan_low_floats("AK-47 | Redline (FT)", max_float=0.01, limit=20)
            mock_filt.assert_called_once_with(
                "AK-47 | Redline (FT)",
                max_float=0.01,
                sort_by="lowest_float",
                limit=20,
            )
            assert result == expected


# ---------------------------------------------------------------------------
# Tests — throttle
# ---------------------------------------------------------------------------

class TestThrottle:
    """Tests for CSFloatOracle._throttle."""

    @pytest.mark.asyncio()
    async def test_respects_delay(self, _oracle):
        """Second call within delay window is throttled."""
        _oracle.request_delay = 0.05
        _oracle._last_request_time = time.monotonic()
        start = time.monotonic()
        await _oracle._throttle()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.03  # at least some sleep happened


# ---------------------------------------------------------------------------
# Tests — close
# ---------------------------------------------------------------------------

class TestClose:
    """Tests for CSFloatOracle.close."""

    @pytest.mark.asyncio()
    async def test_close_session(self, _oracle):
        """close() closes the underlying aiohttp session."""
        session = AsyncMock()
        session.closed = False
        session.close = AsyncMock()
        _oracle._session = session
        await _oracle.close()
        session.close.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_close_no_session(self, _oracle):
        """close() is safe when no session exists."""
        _oracle._session = None
        await _oracle.close()  # should not raise
