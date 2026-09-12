import asyncio
import pytest
import time
from unittest.mock import MagicMock, patch

from src.core.target_sniping.filter import _FilterMixin

class DummySniper(_FilterMixin):
    def __init__(self):
        self._sales_cache = {}
        self._prev_agg_prices = {}
        self.buy_budget = 1000.0

@pytest.mark.asyncio
async def test_evaluate_candidate_blocks_event_loop():
    class DummyConfig:
        MIN_BID_ASK_COUNT = 1
        MIN_DISCOUNT = 0
        MIN_PRICE_USD = 1.0
        KELLY_FRACTION = 0.5
        KELLY_FLOOR_PCT = 1.0
        OFI_KELLY_BOOST = 0.0
        MAX_POSITION_RISK_PCT = 10.0
        MAX_SNIPING_PRICE_USD = 100.0
        KELLY_ENABLED = False
        REQUIRE_ACTIVE_BUY_ORDERS = False
        
    import src.core.target_sniping.filter as filter_mod
    filter_mod.Config = DummyConfig
    filter_mod.run_microstructure_pipeline = MagicMock(return_value=MagicMock(passes=True))
    filter_mod.check_bait_detection = MagicMock(return_value={"pass": True})
    
    sniper = DummySniper()
    sniper._skip_if_locked = MagicMock(return_value=False)
    
    loop = asyncio.get_running_loop()
    counter = 0
    async def bg_task():
        nonlocal counter
        while True:
            await asyncio.sleep(0.01)
            counter += 1
            
    bg = asyncio.create_task(bg_task())
    start_time = loop.time()
    
    mock_item = {
        "title": "Test Item",
        "priceCents": 500,
        "offerId": "123",
        "discount": 10
    }
    
    def slow_get_recent_prices(*args, **kwargs):
        print("slow_get_recent_prices CALLED!")
        time.sleep(0.5)
        return []

    with patch("src.core.target_sniping.filter.price_db") as mock_price_db:
        mock_price_db.get_recent_prices.side_effect = slow_get_recent_prices
        mock_price_db.has_target_been_placed.return_value = False
        mock_price_db.is_crashing.return_value = False
        mock_price_db.detect_wash_trading.return_value = False
        mock_price_db.get_low_fee_rate.return_value = 0.05
        
        try:
            await sniper._evaluate_candidate(
                item=mock_item,
                game_id="a8db",
                agg_prices={"Test Item": {
                    "best_ask": 10.00,
                    "best_bid": 9.00,
                    "ask_count": 2,
                    "bid_count": 2
                }},
                bulk_fees={"Test Item": 0.05},
                current_balance=1000.0,
                current_margin=0.1
            )
        except Exception as e:
            if not isinstance(e, AttributeError): pass
            import traceback; traceback.print_exc()
            pass
            
    elapsed = loop.time() - start_time
    bg.cancel()
    
    print(f"\n--- TEST RESULT ---")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Counter: {counter}")
    print(f"-------------------\n")
