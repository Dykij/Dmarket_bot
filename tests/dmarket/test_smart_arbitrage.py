"""Tests for smart_arbitrage module.

This module tests the SmartArbitrageEngine class for intelligent
arbitrage opportunity detection and execution.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.smart_arbitrage import SmartArbitrageEngine, SmartLimits, SmartOpportunity


class TestSmartArbitrageEngine:
    """Tests for SmartArbitrageEngine class."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_balance = AsyncMock(return_value={"balance": 100.0})
        api.get_market_items = AsyncMock(return_value={"objects": []})
        api.__aenter__ = AsyncMock(return_value=api)
        api.__aexit__ = AsyncMock(return_value=None)
        return api

    @pytest.fixture()
    def smart_arb(self, mock_api):
        """Create SmartArbitrageEngine instance."""
        return SmartArbitrageEngine(api_client=mock_api)

    def test_init(self, smart_arb, mock_api):
        """Test SmartArbitrageEngine initialization."""
        assert smart_arb.api_client == mock_api
        assert smart_arb.is_running is False

    def test_check_balance_safety(self, smart_arb):
        """Test balance safety check."""
        result, message = smart_arb.check_balance_safety()
        assert isinstance(result, bool)
        assert isinstance(message, str)

    @pytest.mark.asyncio()
    async def test_find_smart_opportunities(self, smart_arb, mock_api):
        """Test finding smart opportunities."""
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "itemId": "item1",
                        "title": "Test Item",
                        "price": {"USD": "1000"},
                        "suggestedPrice": {"USD": "1200"},
                    }
                ]
            }
        )

        opportunities = await smart_arb.find_smart_opportunities(game="csgo")
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio()
    async def test_find_smart_opportunities_empty_market(self, smart_arb, mock_api):
        """Test finding opportunities in empty market."""
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        opportunities = await smart_arb.find_smart_opportunities(game="csgo")
        assert opportunities == []

    @pytest.mark.asyncio()
    async def test_get_current_balance(self, smart_arb, mock_api):
        """Test getting current balance."""
        mock_api.get_balance = AsyncMock(return_value={"balance": 150.0})
        balance = await smart_arb.get_current_balance()
        # Balance may be cached or fetched
        assert isinstance(balance, (int, float))

    @pytest.mark.asyncio()
    async def test_calculate_adaptive_limits(self, smart_arb, mock_api):
        """Test calculating adaptive limits."""
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})
        limits = await smart_arb.calculate_adaptive_limits()
        assert isinstance(limits, SmartLimits)

    @pytest.mark.asyncio()
    async def test_get_strategy_description(self, smart_arb, mock_api):
        """Test getting strategy description."""
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})
        description = await smart_arb.get_strategy_description()
        assert isinstance(description, str)

    def test_is_running_property(self, smart_arb):
        """Test is_running property."""
        assert smart_arb.is_running is False

    def test_stop_smart_mode(self, smart_arb):
        """Test stopping smart mode."""
        # Should not raise any errors when not running
        smart_arb.stop_smart_mode()
        assert smart_arb.is_running is False


class TestSmartLimits:
    """Tests for SmartLimits dataclass."""

    def test_smart_limits_creation(self):
        """Test SmartLimits creation."""
        limits = SmartLimits(
            max_buy_price=50.0,
            min_roi=10.0,
            inventory_limit=5,
            max_same_items=2,
            usable_balance=90.0,
            reserve=10.0,
            diversification_factor=0.3,
        )
        assert limits.max_buy_price == 50.0
        assert limits.min_roi == 10.0
        assert limits.inventory_limit == 5
        assert limits.reserve == 10.0


class TestSmartOpportunity:
    """Tests for SmartOpportunity dataclass."""

    def test_smart_opportunity_creation(self):
        """Test SmartOpportunity creation."""
        opp = SmartOpportunity(
            item_id="item123",
            title="Test Item",
            buy_price=10.0,
            sell_price=12.0,
            profit=1.5,
            profit_percent=15.0,
            game="csgo",
        )
        assert opp.item_id == "item123"
        assert opp.title == "Test Item"
        assert opp.buy_price == 10.0
        assert opp.sell_price == 12.0
        assert opp.profit == 1.5
        assert opp.profit_percent == 15.0
        assert opp.game == "csgo"
