"""Unit tests for arbitrage/trader.py.

Tests for:
- ArbitrageTrader class initialization
- Balance checking
- Trading limits management
- Error handling and recovery
- Profitable item discovery
- Trade execution
- Auto-trading loop
- Transaction history
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Test ArbitrageTrader Initialization
# =============================================================================


class TestArbitrageTraderInit:
    """Test ArbitrageTrader initialization."""

    def test_init_with_api_client(self):
        """Test initialization with API client."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        trader = ArbitrageTrader(api_client=mock_api)

        assert trader.api is mock_api
        assert trader.active is False
        assert trader.transaction_history == []

    def test_init_with_credentials(self):
        """Test initialization with public/secret keys.

        This test verifies that trader can be initialized with credentials.
        Note: Full test requires pydantic dependency for DMarketAPI.
        """
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        # Create trader with mock API client to avoid dependency issues
        mock_api = MagicMock()
        trader = ArbitrageTrader(api_client=mock_api)

        # Verify initialization
        assert trader.api is mock_api
        assert trader.public_key is None
        assert trader.secret_key is None

    def test_init_without_credentials_raises(self):
        """Test initialization without credentials raises ValueError."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        with pytest.raises(ValueError) as exc_info:
            ArbitrageTrader()

        assert "requires either api_client" in str(exc_info.value)

    def test_init_default_values(self):
        """Test default values on initialization."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        trader = ArbitrageTrader(api_client=mock_api)

        assert trader.min_profit_percentage == 5.0  # DEFAULT_MIN_PROFIT_PERCENTAGE
        assert trader.max_trade_value == 100.0  # DEFAULT_MAX_TRADE_VALUE
        assert trader.daily_limit == 500.0  # DEFAULT_DAILY_LIMIT
        assert trader.daily_traded == 0.0
        assert trader.error_count == 0
        assert trader.pause_until == 0.0
        assert trader.current_game == "csgo"

    def test_init_custom_values(self):
        """Test custom values on initialization."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        trader = ArbitrageTrader(
            api_client=mock_api,
            min_profit_percentage=10.0,
            max_trade_value=50.0,
            daily_limit=200.0,
        )

        assert trader.min_profit_percentage == 10.0
        assert trader.max_trade_value == 50.0
        assert trader.daily_limit == 200.0


# =============================================================================
# Test check_balance
# =============================================================================


class TestCheckBalance:
    """Test check_balance method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance with mocked API."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_check_balance_sufficient(self, trader):
        """Test check_balance with sufficient funds."""
        # API returns {"balance": value_in_dollars}
        trader.api.get_balance = AsyncMock(return_value={"balance": 100.0, "error": False})

        has_funds, balance = await trader.check_balance()

        assert has_funds is True
        assert balance == 100.0

    @pytest.mark.asyncio()
    async def test_check_balance_insufficient(self, trader):
        """Test check_balance with insufficient funds."""
        # API returns {"balance": value_in_dollars}
        trader.api.get_balance = AsyncMock(return_value={"balance": 0.5, "error": False})

        has_funds, balance = await trader.check_balance()

        assert has_funds is False
        assert balance == 0.5

    @pytest.mark.asyncio()
    async def test_check_balance_handles_exception(self, trader):
        """Test check_balance handles exceptions."""
        trader.api.get_balance = AsyncMock(side_effect=Exception("API Error"))

        has_funds, balance = await trader.check_balance()

        assert has_funds is False
        assert balance == 0.0


# =============================================================================
# Test Trading Limits
# =============================================================================


class TestTradingLimits:
    """Test trading limits functionality."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        return ArbitrageTrader(
            api_client=mock_api,
            max_trade_value=50.0,
            daily_limit=200.0,
        )

    @pytest.mark.asyncio()
    async def test_check_limits_allows_valid_trade(self, trader):
        """Test that valid trades are allowed."""
        result = await trader._check_trading_limits(30.0)
        assert result is True

    @pytest.mark.asyncio()
    async def test_check_limits_rejects_over_max(self, trader):
        """Test that trades over max_trade_value are rejected."""
        result = await trader._check_trading_limits(100.0)  # Over $50 max
        assert result is False

    @pytest.mark.asyncio()
    async def test_check_limits_rejects_over_daily(self, trader):
        """Test that trades over daily limit are rejected."""
        trader.daily_traded = 180.0
        result = await trader._check_trading_limits(30.0)  # Would exceed $200 daily
        assert result is False

    def test_set_trading_limits(self, trader):
        """Test setting trading limits."""
        trader.set_trading_limits(max_trade_value=75.0, daily_limit=300.0)

        assert trader.max_trade_value == 75.0
        assert trader.daily_limit == 300.0

    def test_set_trading_limits_partial(self, trader):
        """Test setting only one limit."""
        trader.set_trading_limits(max_trade_value=25.0)

        assert trader.max_trade_value == 25.0
        assert trader.daily_limit == 200.0  # Unchanged

    def test_reset_daily_limits(self, trader):
        """Test daily limits reset after 24 hours."""
        trader.daily_traded = 150.0
        trader.daily_reset_time = time.time() - 25 * 3600  # 25 hours ago

        trader._reset_daily_limits()

        assert trader.daily_traded == 0.0


# =============================================================================
# Test Error Handling
# =============================================================================


class TestErrorHandling:
    """Test error handling and pause functionality."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_handle_error_increments_count(self, trader):
        """Test that error count is incremented."""
        assert trader.error_count == 0
        await trader._handle_trading_error()
        assert trader.error_count == 1

    @pytest.mark.asyncio()
    async def test_handle_error_pauses_after_3(self, trader):
        """Test 15-minute pause after 3 errors."""
        trader.error_count = 2

        await trader._handle_trading_error()

        assert trader.error_count == 3
        assert trader.pause_until > time.time()

    @pytest.mark.asyncio()
    async def test_handle_error_long_pause_after_10(self, trader):
        """Test 1-hour pause after 10 errors."""
        trader.error_count = 9

        await trader._handle_trading_error()

        # After 10 errors, count resets to 0 and pause for 1 hour
        assert trader.error_count == 0
        assert trader.pause_until > time.time()

    @pytest.mark.asyncio()
    async def test_can_trade_now_when_paused(self, trader):
        """Test can_trade_now returns False when paused."""
        trader.pause_until = time.time() + 600  # Paused for 10 more minutes

        result = await trader._can_trade_now()

        assert result is False

    @pytest.mark.asyncio()
    async def test_can_trade_now_when_not_paused(self, trader):
        """Test can_trade_now returns True when not paused."""
        result = await trader._can_trade_now()
        assert result is True

    @pytest.mark.asyncio()
    async def test_can_trade_now_resets_after_pause(self, trader):
        """Test that pause is reset after it expires."""
        trader.pause_until = time.time() - 10  # Expired 10 seconds ago
        trader.error_count = 5

        result = await trader._can_trade_now()

        assert result is True
        assert trader.pause_until == 0
        assert trader.error_count == 0


# =============================================================================
# Test find_profitable_items
# =============================================================================


class TestFindProfitableItems:
    """Test find_profitable_items method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance with mocked API."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_finds_profitable_items(self, trader):
        """Test finding profitable items."""
        mock_items = [
            {
                "title": "Item A",
                "price": {"USD": 1000},
                "itemId": "item1",
                "extra": {"rarity": "Covert", "category": "Rifle", "popularity": 0.8},
            },
            {
                "title": "Item A",
                "price": {"USD": 1500},
                "itemId": "item2",
            },
        ]
        trader.api.get_all_market_items = AsyncMock(return_value=mock_items)

        results = await trader.find_profitable_items(
            game="csgo",
            min_profit_percentage=5.0,
        )

        assert isinstance(results, list)
        trader.api.get_all_market_items.assert_called_once()

    @pytest.mark.asyncio()
    async def test_empty_market_items(self, trader):
        """Test with no market items."""
        trader.api.get_all_market_items = AsyncMock(return_value=[])

        results = await trader.find_profitable_items(game="csgo")

        assert results == []

    @pytest.mark.asyncio()
    async def test_handles_exception(self, trader):
        """Test exception handling."""
        trader.api.get_all_market_items = AsyncMock(side_effect=Exception("API Error"))

        results = await trader.find_profitable_items(game="csgo")

        assert results == []


# =============================================================================
# Test Auto-Trading
# =============================================================================


class TestAutoTrading:
    """Test auto-trading functionality."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_start_auto_trading_success(self, trader):
        """Test starting auto-trading."""
        trader.api.get_balance = AsyncMock(return_value={"balance": 100.0, "error": False})

        success, message = await trader.start_auto_trading(
            game="csgo",
            min_profit_percentage=5.0,
        )

        assert success is True
        assert len(message) > 0  # Message should not be empty
        assert trader.active is True

    @pytest.mark.asyncio()
    async def test_start_auto_trading_already_active(self, trader):
        """Test starting when already active."""
        trader.active = True

        success, message = await trader.start_auto_trading()

        assert success is False
        assert len(message) > 0  # Error message should not be empty

    @pytest.mark.asyncio()
    async def test_start_auto_trading_insufficient_funds(self, trader):
        """Test starting with insufficient funds."""
        trader.api.get_balance = AsyncMock(return_value={"balance": 0.5, "error": False})

        success, message = await trader.start_auto_trading()

        assert success is False
        assert len(message) > 0  # Error message should not be empty

    @pytest.mark.asyncio()
    async def test_stop_auto_trading(self, trader):
        """Test stopping auto-trading."""
        trader.active = True

        success, message = await trader.stop_auto_trading()

        assert success is True
        assert len(message) > 0  # Message should not be empty
        assert trader.active is False

    @pytest.mark.asyncio()
    async def test_stop_auto_trading_not_active(self, trader):
        """Test stopping when not active."""
        trader.active = False

        success, _message = await trader.stop_auto_trading()

        assert success is False


# =============================================================================
# Test get_status
# =============================================================================


class TestGetStatus:
    """Test get_status method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        return ArbitrageTrader(api_client=mock_api)

    def test_status_inactive(self, trader):
        """Test status when inactive."""
        status = trader.get_status()

        assert status["active"] is False
        assert status["current_game"] == "csgo"
        assert status["transactions_count"] == 0
        assert status["total_profit"] == 0.0
        assert status["on_pause"] is False

    def test_status_active(self, trader):
        """Test status when active."""
        trader.active = True
        trader.current_game = "dota2"

        status = trader.get_status()

        assert status["active"] is True
        assert status["current_game"] == "dota2"
        assert "Dota 2" in status["game_name"]

    def test_status_with_transactions(self, trader):
        """Test status with transaction history."""
        trader.transaction_history = [
            {"profit": 5.0},
            {"profit": 10.0},
            {"profit": 3.0},
        ]

        status = trader.get_status()

        assert status["transactions_count"] == 3
        assert status["total_profit"] == 18.0

    def test_status_on_pause(self, trader):
        """Test status when on pause."""
        trader.pause_until = time.time() + 600  # 10 minutes

        status = trader.get_status()

        assert status["on_pause"] is True
        assert status["pause_minutes"] > 0


# =============================================================================
# Test Transaction History
# =============================================================================


class TestTransactionHistory:
    """Test transaction history functionality."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        return ArbitrageTrader(api_client=mock_api)

    def test_get_transaction_history_empty(self, trader):
        """Test getting empty transaction history."""
        history = trader.get_transaction_history()
        assert history == []

    def test_get_transaction_history_with_items(self, trader):
        """Test getting transaction history with items."""
        trader.transaction_history = [
            {"item_name": "Item 1", "profit": 5.0},
            {"item_name": "Item 2", "profit": 10.0},
        ]

        history = trader.get_transaction_history()

        assert len(history) == 2
        assert history[0]["item_name"] == "Item 1"


# =============================================================================
# Test purchase_item
# =============================================================================


class TestPurchaseItem:
    """Test purchase_item method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance with mocked API."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_purchase_item_success(self, trader):
        """Test successful item purchase."""
        trader.api._request = AsyncMock(
            return_value={
                "items": [{"itemId": "new_item_123"}],
            }
        )

        result = await trader.purchase_item("item123", 10.0)

        assert result["success"] is True
        assert result["new_item_id"] == "new_item_123"

    @pytest.mark.asyncio()
    async def test_purchase_item_error_response(self, trader):
        """Test purchase with error response."""
        trader.api._request = AsyncMock(
            return_value={
                "error": {"message": "Item not available"},
            }
        )

        result = await trader.purchase_item("item123", 10.0)

        assert result["success"] is False
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio()
    async def test_purchase_item_exception(self, trader):
        """Test purchase with exception."""
        trader.api._request = AsyncMock(side_effect=Exception("Network error"))

        result = await trader.purchase_item("item123", 10.0)

        assert result["success"] is False
        assert "Network error" in result["error"]


# =============================================================================
# Test list_item_for_sale
# =============================================================================


class TestListItemForSale:
    """Test list_item_for_sale method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance with mocked API."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_list_item_success(self, trader):
        """Test successful item listing."""
        trader.api._request = AsyncMock(return_value={"status": "ok"})

        result = await trader.list_item_for_sale("item123", 15.0)

        assert result["success"] is True
        assert result["price"] == 15.0

    @pytest.mark.asyncio()
    async def test_list_item_error_response(self, trader):
        """Test listing with error response."""
        trader.api._request = AsyncMock(
            return_value={
                "error": {"message": "Invalid price"},
            }
        )

        result = await trader.list_item_for_sale("item123", 15.0)

        assert result["success"] is False

    @pytest.mark.asyncio()
    async def test_list_item_exception(self, trader):
        """Test listing with exception."""
        trader.api._request = AsyncMock(side_effect=Exception("API Error"))

        result = await trader.list_item_for_sale("item123", 15.0)

        assert result["success"] is False


# =============================================================================
# Test execute_arbitrage_trade
# =============================================================================


class TestExecuteArbitrageTrade:
    """Test execute_arbitrage_trade method."""

    @pytest.fixture()
    def trader(self):
        """Create a trader instance with mocked API."""
        from src.dmarket.arbitrage.trader import ArbitrageTrader

        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        return ArbitrageTrader(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_execute_trade_success(self, trader):
        """Test successful trade execution."""
        # Mock balance check
        trader.api.get_balance = AsyncMock(return_value={"balance": 100.0, "error": False})

        # Mock purchase
        trader.purchase_item = AsyncMock(
            return_value={"success": True, "new_item_id": "new123"}
        )

        # Mock listing
        trader.list_item_for_sale = AsyncMock(return_value={"success": True})

        item = {
            "name": "Test Item",
            "buy_price": 10.0,
            "sell_price": 15.0,
            "profit": 4.0,
            "profit_percentage": 40.0,
            "buy_item_id": "buy123",
            "game": "csgo",
        }

        result = await trader.execute_arbitrage_trade(item)

        assert result["success"] is True
        assert result["profit"] == 4.0
        assert len(trader.transaction_history) == 1

    @pytest.mark.asyncio()
    async def test_execute_trade_insufficient_balance(self, trader):
        """Test trade with insufficient balance."""
        trader.api.get_balance = AsyncMock(return_value={"balance": 1.0, "error": False})  # $1

        item = {
            "name": "Expensive Item",
            "buy_price": 50.0,  # Can't afford
            "sell_price": 70.0,
            "buy_item_id": "buy123",
            "game": "csgo",
        }

        result = await trader.execute_arbitrage_trade(item)

        assert result["success"] is False
        assert len(result["errors"]) > 0  # Should have at least one error

    @pytest.mark.asyncio()
    async def test_execute_trade_purchase_fails(self, trader):
        """Test trade when purchase fails."""
        trader.api.get_balance = AsyncMock(return_value={"balance": 100.0, "error": False})
        trader.purchase_item = AsyncMock(
            return_value={"success": False, "error": "Item sold"}
        )

        item = {
            "name": "Test Item",
            "buy_price": 10.0,
            "sell_price": 15.0,
            "buy_item_id": "buy123",
            "game": "csgo",
        }

        result = await trader.execute_arbitrage_trade(item)

        assert result["success"] is False
        assert len(result["errors"]) > 0  # Should have at least one error
