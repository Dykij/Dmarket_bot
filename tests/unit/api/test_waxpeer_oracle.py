"""Unit tests for WaxpeerOracle (src/api/waxpeer_oracle.py)."""

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
    with patch("src.api.waxpeer_oracle.price_db") as mock_db:
        mock_db.record_price = MagicMock()
        yield mock_db


@pytest.fixture()
def _oracle(_mock_price_db):
    from src.api.waxpeer_oracle import WaxpeerOracle
    return WaxpeerOracle()


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
    """Tests for WaxpeerOracle.load_items."""

    @pytest.mark.asyncio()
    async def test_load_success(self, _oracle, _mock_session, _mock_price_db):
        """Items loaded: mills→USD conversion (31848 → $31.848)."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"name": "AK-47 | Redline (FT)", "min": 31848, "count": 388, "steam_price": 29626},
                {"name": "AWP | Asiimov (FT)", "min": 45000, "count": 120, "steam_price": 42000},
            ]
        })
        count = await _oracle.load_items()
        assert count == 2
        assert _oracle._items_cache["AK-47 | Redline (FT)"]["price"] == 31.848
        assert _oracle._items_cache["AK-47 | Redline (FT)"]["volume"] == 388
        assert _oracle._items_cache["AWP | Asiimov (FT)"]["price"] == 45.0

    @pytest.mark.asyncio()
    async def test_load_steam_price(self, _oracle, _mock_session):
        """Steam reference price also converted from mills."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"name": "Test Item", "min": 10000, "count": 50, "steam_price": 12000},
            ]
        })
        await _oracle.load_items()
        assert _oracle._items_cache["Test Item"]["steam_price"] == 12.0

    @pytest.mark.asyncio()
    async def test_load_non_200(self, _oracle, _mock_session):
        """Non-200 → 0 items loaded."""
        _mock_session.get.return_value = _make_response(500)
        count = await _oracle.load_items()
        assert count == 0

    @pytest.mark.asyncio()
    async def test_load_cached(self, _oracle, _mock_session):
        """Cache hit → no HTTP call."""
        _oracle._items_cache = {"Test": {"price": 1.0, "volume": 1, "steam_price": 1.0}}
        _oracle._items_cache_ts = time.time()
        count = await _oracle.load_items()
        assert count == 1
        _mock_session.get.assert_not_called()

    @pytest.mark.asyncio()
    async def test_empty_name_skipped(self, _oracle, _mock_session):
        """Items with empty name are skipped."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"name": "", "min": 1000, "count": 10, "steam_price": 1000},
                {"name": "Valid Item", "min": 2000, "count": 20, "steam_price": 2000},
            ]
        })
        count = await _oracle.load_items()
        assert count == 1
        assert "Valid Item" in _oracle._items_cache


# ---------------------------------------------------------------------------
# Tests — get_item_price
# ---------------------------------------------------------------------------

class TestGetItemPrice:
    """Tests for WaxpeerOracle.get_item_price."""

    @pytest.mark.asyncio()
    async def test_found(self, _oracle, _mock_session):
        """Item found → price returned."""
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"name": "AK-47 | Redline (FT)", "min": 31848, "count": 100, "steam_price": 30000},
            ]
        })
        price = await _oracle.get_item_price("AK-47 | Redline (FT)")
        assert price == 31.848

    @pytest.mark.asyncio()
    async def test_not_found(self, _oracle, _mock_session):
        """Item not in cache → 0.0."""
        _mock_session.get.return_value = _make_response(200, {"items": []})
        price = await _oracle.get_item_price("Nonexistent")
        assert price == 0.0


# ---------------------------------------------------------------------------
# Tests — price conversion
# ---------------------------------------------------------------------------

class TestPriceConversion:
    """Verify mills → USD conversion (divide by 1000)."""

    @pytest.mark.parametrize("mills,usd", [
        (31848, 31.848),
        (1000, 1.0),
        (0, 0.0),
        (500, 0.5),
    ])
    @pytest.mark.asyncio()
    async def test_conversion(self, _oracle, _mock_session, mills, usd):
        _mock_session.get.return_value = _make_response(200, {
            "items": [
                {"name": "Test", "min": mills, "count": 10, "steam_price": 0},
            ]
        })
        await _oracle.load_items()
        assert _oracle._items_cache["Test"]["price"] == pytest.approx(usd)


# ---------------------------------------------------------------------------
# Tests — get_item_volume / get_item_steam_price
# ---------------------------------------------------------------------------

class TestAccessors:
    @pytest.mark.asyncio()
    async def test_get_volume(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {
            "items": [{"name": "X", "min": 1000, "count": 42, "steam_price": 0}],
        })
        vol = await _oracle.get_item_volume("X")
        assert vol == 42

    @pytest.mark.asyncio()
    async def test_get_steam_price(self, _oracle, _mock_session):
        _mock_session.get.return_value = _make_response(200, {
            "items": [{"name": "X", "min": 1000, "count": 10, "steam_price": 5000}],
        })
        sp = await _oracle.get_item_steam_price("X")
        assert sp == 5.0


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
