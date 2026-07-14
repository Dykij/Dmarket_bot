"""Unit tests for SteamOracle (src/api/steam_oracle.py)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int = 200, json_data: dict | None = None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _mock_price_db():
    with patch("src.api.steam_oracle.price_db") as mock_db:
        mock_db.get_latest_price.return_value = None
        mock_db.record_price = MagicMock()
        yield mock_db


@pytest.fixture()
def _oracle(_mock_price_db):
    from src.api.steam_oracle import SteamOracle
    return SteamOracle(api_key="")


@pytest.fixture()
def _mock_session(_oracle):
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
    """Tests for SteamOracle.get_item_price."""

    @pytest.mark.asyncio()
    async def test_success(self, _oracle, _mock_session, _mock_price_db):
        """Median price $12.34 → adjusted to 12.34 * 0.85 = 10.49."""
        _mock_session.get.return_value = _make_response(200, {
            "success": True,
            "median_price": "$12.34",
        })
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == round(12.34 * 0.85, 2)
        _mock_price_db.record_price.assert_called_once()

    @pytest.mark.asyncio()
    async def test_success_lowest_price(self, _oracle, _mock_session):
        """Falls back to lowest_price when median_price absent."""
        _mock_session.get.return_value = _make_response(200, {
            "success": True,
            "lowest_price": "$10.00",
        })
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == round(10.0 * 0.85, 2)

    @pytest.mark.asyncio()
    async def test_not_found(self, _oracle, _mock_session):
        """success=false → 0.0."""
        _mock_session.get.return_value = _make_response(200, {
            "success": False,
        })
        price = await _oracle.get_item_price("Nonexistent")
        assert price == 0.0

    @pytest.mark.asyncio()
    async def test_rate_limit(self, _oracle, _mock_session):
        """429 → backs off ~5s, returns 0.0."""
        _mock_session.get.return_value = _make_response(429)
        start = time.monotonic()
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        elapsed = time.monotonic() - start
        assert price == 0.0
        assert elapsed >= 4.0  # ~5s backoff

    @pytest.mark.asyncio()
    async def test_non_200(self, _oracle, _mock_session):
        """Non-200 → 0.0."""
        _mock_session.get.return_value = _make_response(500)
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 0.0

    @pytest.mark.asyncio()
    async def test_empty_median(self, _oracle, _mock_session):
        """Empty median_price string → 0.0."""
        _mock_session.get.return_value = _make_response(200, {
            "success": True,
            "median_price": "",
        })
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 0.0

    @pytest.mark.asyncio()
    async def test_cached_memory(self, _oracle, _mock_session):
        """Memory cache hit → no HTTP call."""
        _oracle._mem_cache["AK-47 | Redline (FT)"] = (10.49, time.time())
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 10.49
        _mock_session.get.assert_not_called()

    @pytest.mark.asyncio()
    async def test_cached_db(self, _oracle, _mock_session, _mock_price_db):
        """SQLite cache hit → no HTTP call."""
        _mock_price_db.get_latest_price.return_value = 9.99
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 9.99
        _mock_session.get.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — price adjustment
# ---------------------------------------------------------------------------

class TestPriceAdjustment:
    """Verify STEAM_TO_CASH_FACTOR is applied correctly."""

    @pytest.mark.parametrize("raw,expected", [
        ("$10.00", 8.5),
        ("$100.00", 85.0),
        ("$0.50", 0.42),
        ("12,34", 10.49),
    ])
    @pytest.mark.asyncio()
    async def test_adjustment(self, _oracle, _mock_session, raw, expected):
        _mock_session.get.return_value = _make_response(200, {
            "success": True,
            "median_price": raw,
        })
        price = await _oracle.get_item_price("Test Item")
        assert price == round(expected, 2)


# ---------------------------------------------------------------------------
# Tests — _parse_price
# ---------------------------------------------------------------------------

class TestParsePrice:
    """Tests for SteamOracle._parse_price static method."""

    def test_dollar_format(self):
        from src.api.steam_oracle import SteamOracle
        assert SteamOracle._parse_price("$12.34") == 12.34

    def test_comma_format(self):
        from src.api.steam_oracle import SteamOracle
        assert SteamOracle._parse_price("12,34") == 12.34

    def test_no_symbol(self):
        from src.api.steam_oracle import SteamOracle
        assert SteamOracle._parse_price("5.50") == 5.5

    def test_invalid(self):
        from src.api.steam_oracle import SteamOracle
        assert SteamOracle._parse_price("abc") == 0.0

    def test_empty(self):
        from src.api.steam_oracle import SteamOracle
        assert SteamOracle._parse_price("") == 0.0


# ---------------------------------------------------------------------------
# Tests — get_prices_batch
# ---------------------------------------------------------------------------

class TestGetPricesBatch:
    """Tests for SteamOracle.get_prices_batch."""

    @pytest.mark.asyncio()
    async def test_batch(self, _oracle, _mock_session):
        """Batch fetches prices sequentially."""
        _mock_session.get.return_value = _make_response(200, {
            "success": True,
            "median_price": "$10.00",
        })
        result = await _oracle.get_prices_batch(["Item A", "Item B"])
        assert "Item A" in result
        assert "Item B" in result


# ---------------------------------------------------------------------------
# Tests — close
# ---------------------------------------------------------------------------

class TestClose:
    @pytest.mark.asyncio()
    async def test_close_session(self, _oracle):
        session = AsyncMock()
        session.closed = False
        session.close = AsyncMock()
        _oracle._session = session
        await _oracle.close()
        session.close.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_close_no_session(self, _oracle):
        _oracle._session = None
        await _oracle.close()
