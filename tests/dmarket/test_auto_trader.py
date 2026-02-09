"""Tests for auto_trader module.

This module tests the AutoTrader class and related components
for automatic trading functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.auto_trader import (
    AutoTrader,
    RiskConfig,
    TradeResult,
)


class TestRiskConfig:
    """Tests for RiskConfig class."""

    def test_init(self):
        """Test RiskConfig initialization."""
        config = RiskConfig(
            level="medium",
            max_trades=5,
            max_price=50.0,
            min_profit=0.5,
            balance=100.0,
        )

        assert config.level == "medium"
        assert config.max_trades == 5
        assert config.max_price == 50.0
        assert config.min_profit == 0.5
        assert config.balance == 100.0

    def test_from_level_low(self):
        """Test low risk configuration."""
        config = RiskConfig.from_level(
            level="low",
            max_trades=10,
            max_price=100.0,
            min_profit=0.5,
            balance=100.0,
        )

        assert config.level == "low"
        assert config.max_trades <= 2  # Low risk limits trades
        assert config.max_price <= 20.0  # Low risk limits price
        assert config.min_profit >= 1.0  # Low risk requires higher profit

    def test_from_level_medium(self):
        """Test medium risk configuration."""
        config = RiskConfig.from_level(
            level="medium",
            max_trades=10,
            max_price=100.0,
            min_profit=0.3,
            balance=100.0,
        )

        assert config.level == "medium"
        assert config.max_trades <= 5
        assert config.max_price <= 50.0
        # Medium level keeps original min_profit value
        assert config.min_profit == 0.3

    def test_from_level_high(self):
        """Test high risk configuration."""
        config = RiskConfig.from_level(
            level="high",
            max_trades=10,
            max_price=100.0,
            min_profit=0.3,
            balance=100.0,
        )

        assert config.level == "high"
        # High risk keeps original values or slightly reduced


class TestTradeResult:
    """Tests for TradeResult class."""

    def test_init(self):
        """Test TradeResult initialization."""
        result = TradeResult()

        assert result.purchases == 0
        assert result.sales == 0
        assert result.total_profit == 0.0
        assert result.trades_count == 0
        assert result.remaining_balance == 0.0

    def test_add_purchase(self):
        """Test recording a purchase."""
        result = TradeResult()
        result.remaining_balance = 100.0

        result.add_purchase(25.0)

        assert result.purchases == 1
        assert result.remaining_balance == 75.0

    def test_add_sale(self):
        """Test recording a sale."""
        result = TradeResult()

        result.add_sale(5.0)
        result.add_sale(3.0)

        assert result.sales == 2
        assert result.total_profit == 8.0

    def test_increment_trades(self):
        """Test incrementing trade counter."""
        result = TradeResult()

        result.increment_trades()
        result.increment_trades()

        assert result.trades_count == 2

    def test_to_tuple(self):
        """Test conversion to tuple."""
        result = TradeResult()
        result.purchases = 5
        result.sales = 3
        result.total_profit = 15.50

        tuple_result = result.to_tuple()

        assert tuple_result == (5, 3, 15.50)


class TestAutoTrader:
    """Tests for AutoTrader class."""

    @pytest.fixture
    def mock_scanner(self):
        """Create mock ArbitrageScanner."""
        scanner = MagicMock()
        scanner.min_profit = 0.5
        scanner.max_price = 50.0
        scanner.max_trades = 10
        scanner.check_user_balance = AsyncMock(return_value={"balance": 100.0})
        scanner.get_api_client = AsyncMock(return_value=MagicMock())
        return scanner

    @pytest.fixture
    def auto_trader(self, mock_scanner):
        """Create AutoTrader with mocked scanner."""
        return AutoTrader(scanner=mock_scanner)

    def test_init(self, auto_trader, mock_scanner):
        """Test AutoTrader initialization."""
        assert auto_trader is not None
        assert auto_trader.scanner == mock_scanner

    @pytest.mark.asyncio
    async def test_auto_trade_items_empty_input(self, auto_trader):
        """Test auto trading with empty items."""
        result = await auto_trader.auto_trade_items(items_by_game={})

        assert result == (0, 0, 0.0)

    @pytest.mark.asyncio
    async def test_auto_trade_items_insufficient_balance(self, auto_trader, mock_scanner):
        """Test auto trading with insufficient balance."""
        mock_scanner.check_user_balance = AsyncMock(return_value={"balance": 0.0})

        result = await auto_trader.auto_trade_items(
            items_by_game={"csgo": [{"item": "test"}]}
        )

        assert result == (0, 0, 0.0)

    @pytest.mark.asyncio
    async def test_auto_trade_with_risk_level(self, auto_trader, mock_scanner):
        """Test auto trading with different risk levels."""
        mock_scanner.check_user_balance = AsyncMock(return_value={"balance": 100.0})

        # Low risk should use conservative settings
        result = await auto_trader.auto_trade_items(
            items_by_game={},
            risk_level="low"
        )

        # With empty items, should return zeros
        assert result == (0, 0, 0.0)

    def test_has_sufficient_balance(self, auto_trader):
        """Test balance sufficiency check."""
        # Sufficient balance (needs has_funds=True)
        assert auto_trader._has_sufficient_balance({"balance": 100.0, "has_funds": True}) is True

        # Insufficient balance
        assert auto_trader._has_sufficient_balance({"balance": 0.0, "has_funds": False}) is False

        # has_funds False even with balance
        assert auto_trader._has_sufficient_balance({"balance": 100.0, "has_funds": False}) is False

    def test_setup_trader(self, auto_trader):
        """Test trader setup with config."""
        config = RiskConfig(
            level="medium",
            max_trades=5,
            max_price=50.0,
            min_profit=0.5,
            balance=100.0,
        )
        mock_api = MagicMock()

        trader = auto_trader._setup_trader(config, mock_api)

        assert trader is not None

    def test_prepare_items_for_trading(self, auto_trader):
        """Test preparing items from multiple games."""
        items_by_game = {
            "csgo": [{"name": "Item 1", "profit": 5.0}, {"name": "Item 2", "profit": 10.0}],
            "dota2": [{"name": "Item 3", "profit": 7.0}],
        }

        prepared = auto_trader._prepare_items_for_trading(items_by_game)

        assert len(prepared) == 3
        # Should be sorted by profit (highest first)
        assert prepared[0]["profit"] == 10.0

    def test_prepare_items_adds_game(self, auto_trader):
        """Test that game code is added to each item."""
        items_by_game = {
            "csgo": [{"name": "Item 1"}],
        }

        prepared = auto_trader._prepare_items_for_trading(items_by_game)

        assert prepared[0]["game"] == "csgo"

    def test_should_continue_trading(self, auto_trader):
        """Test trading continuation logic."""
        config = RiskConfig(
            level="medium",
            max_trades=5,
            max_price=50.0,
            min_profit=0.5,
            balance=100.0,
        )
        result = TradeResult()
        result.remaining_balance = 50.0

        # Should continue with remaining balance and trades
        assert auto_trader._should_continue_trading(result, config) is True

        # Exhaust trades
        result.trades_count = 5
        assert auto_trader._should_continue_trading(result, config) is False

    def test_is_price_acceptable(self, auto_trader):
        """Test price acceptance check."""
        # Acceptable price - item exists with same price
        item = {"price": 30.0, "title": "Test Item"}
        assert auto_trader._is_price_acceptable(item, 30.0, "Test Item") is True

        # Price increased too much
        item = {"price": 50.0, "title": "Test Item"}
        assert auto_trader._is_price_acceptable(item, 30.0, "Test Item") is False

        # Item not found
        assert auto_trader._is_price_acceptable(None, 30.0, "Test Item") is False
