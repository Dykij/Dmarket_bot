import asyncio
from unittest.mock import AsyncMock
import pytest

# Mocking a hypothetical trade flow
# API -> Strategy -> Decision -> Execution

class MockExchange:
    """Mock exchange for integration testing."""
    async def get_ticker(self, symbol):
        """Mock getting ticker data."""
        return {"symbol": symbol, "price": 100.0}

    async def place_order(self, symbol, side, qty):
        """Mock placing an order."""
        return {"id": "123", "symbol": symbol, "side": side, "qty": qty, "status": "filled"}

class Strategy:
    """Simple trading strategy."""
    def decide(self, price):
        """Decide whether to buy or hold based on price."""
        if price < 105.0:
            return "buy"
        return "hold"

@pytest.mark.asyncio
async def test_trade_flow_execution():
    """Test the full trade flow from ticker to execution."""
    exchange = MockExchange()
    exchange.get_ticker = AsyncMock(return_value={"symbol": "BTC/USD", "price": 100.0})
    exchange.place_order = AsyncMock(return_value={"id": "order_1", "status": "filled"})

    strategy = Strategy()

    # 1. Fetch Data
    ticker = await exchange.get_ticker("BTC/USD")
    assert ticker["price"] == 100.0

    # 2. Make Decision
    decision = strategy.decide(ticker["price"])
    assert decision == "buy"

    # 3. Execute
    order = None
    if decision == "buy":
        order = await exchange.place_order("BTC/USD", "buy", 1.0)

    assert order is not None
    assert order["status"] == "filled"
    exchange.place_order.assert_called_once_with("BTC/USD", "buy", 1.0)
