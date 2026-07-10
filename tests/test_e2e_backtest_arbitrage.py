import pytest
import asyncio
from typing import Dict, Any

from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
from src.analytics.rare_valuation import RareValuationEngine
from src.analytics.stickers_evaluator import StickerEvaluator

class MockCSFloatOracle:
    async def get_item_price(self, title: str) -> float:
        # Mock prices for backtesting based on title
        mock_db = {
            "AK-47 | Redline (Field-Tested)": 15.00,
            "AWP | Asiimov (Field-Tested)": 65.00,
            "M4A1-S | Printstream (Minimal Wear)": 120.00,
            "Desert Eagle | Blaze (Factory New)": 250.00
        }
        return mock_db.get(title, 0.0)

class BacktestBroker:
    def __init__(self):
        self.balance = 1000.0
        self.inventory = []
        self.trades_executed = 0
        self.rejected_trades = 0
        
    def execute_trade(self, title: str, buy_price: float, expected_sell: float, margin: float):
        if self.balance >= buy_price:
            self.balance -= buy_price
            self.inventory.append({"title": title, "buy_price": buy_price, "target_sell": expected_sell})
            self.trades_executed += 1
        else:
            self.rejected_trades += 1


@pytest.mark.asyncio
async def test_sniping_bot_backtrader_logic():
    """
    E2E Backtesting simulation representing the Quantitative Arbitrage Engine.
    Examines multiple market conditions and verifies the bot enforces the strict >5% margin rule.
    """
    broker = BacktestBroker()
    oracle = MockCSFloatOracle()
    valuation = RareValuationEngine()
    stickers = StickerEvaluator()

    min_profit_margin = 0.05
    fee_markup = 0.05

    # Mock items observed on DMarket
    market_items = [
        {"title": "AK-47 | Redline (Field-Tested)", "dmarket_price": 12.00, "attrs": {}},      # Should pass (CSFloat: $15.00, EV: $12 -> 15. 12 -> 15 is 25% gross. 5% fee)
        {"title": "AWP | Asiimov (Field-Tested)", "dmarket_price": 63.00, "attrs": {}},        # Should fail (CSFloat: $65.00. Too close, margin < 5% after fees)
        {"title": "M4A1-S | Printstream (Minimal Wear)", "dmarket_price": 105.00, "attrs": {}}, # Should pass (CSFloat: $120.00)
        {"title": "Desert Eagle | Blaze (Factory New)", "dmarket_price": 245.00, "attrs": {}}   # Should fail (Gross margin very small)
    ]

    for item in market_items:
        title = item["title"]
        base_price = item["dmarket_price"]

        # 1. EV Calculation
        ev = valuation.estimate_market_value(base_price, item["attrs"])
        sticker_ev = stickers.calculate_added_value([])
        total_ev = ev + sticker_ev

        # 2. Oracle Validation
        oracle_price = await oracle.get_item_price(title)
        
        target_sell_price = oracle_price if oracle_price > 0 else total_ev

        # 3. Validation Logic
        try:
            net_margin = validate_arbitrage_profit(
                buy_price=base_price,
                expected_sell_price=target_sell_price,
                fee_markup=fee_markup,
                min_profit_margin=min_profit_margin
            )
            broker.execute_trade(title, base_price, target_sell_price, net_margin)
        except PriceValidationError:
            broker.rejected_trades += 1

    # Assertions based on Backtrader verification
    assert broker.trades_executed == 2, f"Expected 2 successful trades, got {broker.trades_executed}"
    assert broker.rejected_trades == 2, f"Expected 2 rejected trades, got {broker.rejected_trades}"
    assert broker.balance == 1000.0 - 12.00 - 105.00, "Balance should reflect 2 purchased items."

    # Validate inventory matches expectations
    bought_titles = [i["title"] for i in broker.inventory]
    assert "AK-47 | Redline (Field-Tested)" in bought_titles
    assert "M4A1-S | Printstream (Minimal Wear)" in bought_titles
    assert "AWP | Asiimov (Field-Tested)" not in bought_titles
    assert "Desert Eagle | Blaze (Factory New)" not in bought_titles
