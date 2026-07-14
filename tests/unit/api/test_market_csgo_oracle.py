"""Unit tests for MarketCsgoOracle (src/api/market_csgo_oracle.py)."""

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
    with patch("src.api.market_csgo_oracle.price_db") as mock_db:
        mock_db.record_price = MagicMock()
        yield mock_db


@pytest.fixture()
def _oracle(_mock_price_db):
    from src.api.market_csgo_oracle import MarketCsgoOracle
    return MarketCsgoOracle()


@pytest.fixture()
def _mock_session(_oracle):
    session = AsyncMock()
    session.closed = False
    session.get = MagicMock()
    session.close = AsyncMock()
    _oracle._session = session
    return session


# ---------------------------------------------------------------------------
# Tests — load_items
# ---------------------------------------------------------------------------

class TestLoadItems:
    """Tests for MarketCsgoOracle.load_items."""

    @pytest.mark.asyncio()
    async def test_load_success(self, _oracle, _mock_session, _mock_price_db):
        """Items loaded with price string '30.546' and volume '442'."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "AK-47 | Redline (FT)", "price": "30.546", "volume": "442"},
                {"market_hash_name": "AWP | Asiimov (FT)", "price": "45.123", "volume": "120"},
            ]
        })
        count = await _oracle.load_items()
        assert count == 2
        assert _oracle._items_cache["AK-47 | Redline (FT)"]["price"] == 30.546
        assert _oracle._items_cache["AK-47 | Redline (FT)"]["volume"] == 442
        assert _oracle._items_cache["AWP | Asiimov (FT)"]["price"] == 45.123
        _mock_price_db.record_price.assert_called()

    @pytest.mark.asyncio()
    async def test_load_non_200(self, _oracle, _mock_session):
        """Non-200 → 0 items."""
        _mock_session.get.return_value = _make_response(500)
        count = await _oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio()
    async def test_load_cached(self, _oracle, _mock_session):
        """Cache hit → no HTTP call."""
        _oracle._items_cache = {"X": {"price": 1.0, "volume": 1}}
        _oracle._items_cache_ts = time.time()
        count = await _oracle.load_items()
        assert count == 1
        _mock_session.get.assert_not_called()

    @pytest.mark.asyncio()
    async def test_empty_name_skipped(self, _oracle, _mock_session):
        """Items with empty market_hash_name are skipped."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "", "price": "10", "volume": "5"},
                {"market_hash_name": "Valid", "price": "20", "volume": "10"},
            ]
        })
        count = await _oracle.load_items()
        assert count == 1

    @pytest.mark.asyncio()
    async def test_invalid_price_skipped(self, _oracle, _mock_session):
        """Items with non-numeric price are skipped."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "Bad", "price": "abc", "volume": "5"},
                {"market_hash_name": "Good", "price": "10.5", "volume": "5"},
            ]
        })
        count = await _oracle.load_items()
        assert count == 1
        assert "Good" in _oracle._items_cache


# ---------------------------------------------------------------------------
# Tests — get_item_price
# ---------------------------------------------------------------------------

class TestGetItemPrice:
    @pytest.mark.asyncio()
    async def test_found(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "AK-47 | Redline (FT)", "price": "30.546", "volume": "442"},
            ]
        })
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 30.546

    @pytest.mark.asyncio()
    async def test_not_found(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {"items": []})
        price = await _oracle.get_item_price("Nonexistent")
        assert price == 0.0


# ---------------------------------------------------------------------------
# Tests — get_item_volume
# ---------------------------------------------------------------------------

class TestGetItemVolume:
    @pytest.mark.asyncio()
    async def test_found(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "AK-47 | Redline (FT)", "price": "30.546", "volume": "442"},
            ]
        })
        vol = await _oracle.get_item_volume("AK-47 | Redline (FT)")
        assert vol == 442

    @pytest.mark.asyncio()
    async def test_not_found(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {"items": []})
        vol = await _oracle.get_item_volume("Nonexistent")
        assert vol == 0


# ---------------------------------------------------------------------------
# Tests — get_prices_batch
# ---------------------------------------------------------------------------

class TestGetPricesBatch:
    @pytest.mark.asyncio()
    async def test_batch(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"market_hash_name": "A", "price": "10", "volume": "5"},
                {"market_hash_name": "B", "price": "20", "volume": "10"},
            ]
        })
        result = await _oracle.get_prices_batch(["A", "B", "C"])
        assert result == {"A": 10.0, "B": 20.0}


# ---------------------------------------------------------------------------
# Tests — close
# ---------------------------------------------------------------------------

class TestClose:
    @pytest.mark.asyncio()
    async def test_close(self, _oracle):
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
