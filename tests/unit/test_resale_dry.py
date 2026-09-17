import pytest
from unittest.mock import patch, MagicMock

from src.core.target_sniping.resale_dry import _ResaleDryMixin
from src.db.price_history import price_db

class TestResaleDryMixin(_ResaleDryMixin):
    pass

@pytest.mark.asyncio
async def test_dry_simulate_sales_skip():
    mixin = TestResaleDryMixin()
    
    with patch('src.core.target_sniping.resale_dry.random.random', return_value=0.50):
        with patch.object(price_db, 'get_virtual_inventory', return_value=[{"id": 1, "market_price": 100, "buy_price": 100, "sell_price": 105, "hash_name": "Test"}]) as mock_get_inv:
            with patch.object(price_db, 'record_virtual_sale') as mock_record_sale:
                await mixin._dry_simulate_sales()
                
                assert mock_get_inv.called
                assert not mock_record_sale.called

@pytest.mark.asyncio
async def test_dry_simulate_sales_sell():
    mixin = TestResaleDryMixin()
    
    with patch('src.core.target_sniping.resale_dry.random.random', return_value=0.10):
        with patch.object(price_db, 'get_virtual_inventory', return_value=[{"id": 1, "buy_price": 100, "sell_price": 105, "hash_name": "Test"}]) as mock_get_inv:
            with patch.object(price_db, 'record_virtual_sale') as mock_record_sale:
                with patch.object(price_db, 'set_funds_hold') as mock_set_funds:
                    with patch('src.core.target_sniping.resale_dry.get_sell_fee_rate', return_value=0.05):
                        
                        await mixin._dry_simulate_sales()
                        
                        assert mock_get_inv.called
                        assert mock_record_sale.called
                        mock_record_sale.assert_called_with(1, 105, 5.25)
                        assert mock_set_funds.called
