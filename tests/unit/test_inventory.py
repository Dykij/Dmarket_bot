import pytest
import time
from unittest.mock import patch
from src.core.target_sniping.inventory import _InventoryMixin
from src.db.price_history import price_db

class DummyInventory(_InventoryMixin):
    pass

@pytest.mark.asyncio
async def test_skip_if_locked_not_known():
    inv = DummyInventory()
    with patch.object(price_db, "is_known_item", return_value=False) as mock_is_known:
        result = await inv._skip_if_locked("item123", "AK-47")
        assert result is False
        mock_is_known.assert_called_once_with("item123")

@pytest.mark.asyncio
async def test_skip_if_locked_reverted():
    inv = DummyInventory()
    with patch.object(price_db, "is_known_item", return_value=True) as mock_is_known, \
         patch.object(price_db, "get_asset_status", return_value={"status": "reverted"}) as mock_get_status:
        result = await inv._skip_if_locked("item123", "AK-47")
        assert result is True
        mock_is_known.assert_called_once_with("item123")
        mock_get_status.assert_called_once_with("item123")

@pytest.mark.asyncio
async def test_skip_if_locked_trade_protected_active():
    inv = DummyInventory()
    with patch.object(price_db, "is_known_item", return_value=True), \
         patch.object(price_db, "get_asset_status", return_value={"status": "trade_protected", "finalization_time": time.time() + 1000}):
        result = await inv._skip_if_locked("item123", "AK-47")
        assert result is True

@pytest.mark.asyncio
async def test_skip_if_locked_trade_protected_expired():
    inv = DummyInventory()
    with patch.object(price_db, "is_known_item", return_value=True), \
         patch.object(price_db, "get_asset_status", return_value={"status": "trade_protected", "finalization_time": time.time() - 1000}):
        result = await inv._skip_if_locked("item123", "AK-47")
        assert result is False

