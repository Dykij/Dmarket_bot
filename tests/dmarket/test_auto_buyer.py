"""Tests for auto_buyer module.

This module tests the AutoBuyer class for automatic item purchases.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.auto_buyer import AutoBuyConfig, AutoBuyer, PurchaseResult


class TestAutoBuyConfig:
    """Tests for AutoBuyConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AutoBuyConfig()

        assert config.enabled is False
        assert config.min_discount_percent == 30.0
        assert config.max_price_usd == 100.0
        assert config.check_sales_history is True
        assert config.check_trade_lock is True
        assert config.max_trade_lock_hours == 168
        assert config.dry_run is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = AutoBuyConfig(
            enabled=True,
            min_discount_percent=20.0,
            max_price_usd=500.0,
            check_sales_history=False,
            dry_run=False,
        )

        assert config.enabled is True
        assert config.min_discount_percent == 20.0
        assert config.max_price_usd == 500.0
        assert config.check_sales_history is False
        assert config.dry_run is False


class TestPurchaseResult:
    """Tests for PurchaseResult class."""

    def test_successful_result(self):
        """Test successful purchase result."""
        result = PurchaseResult(
            success=True,
            item_id="item123",
            item_title="AK-47 | Redline",
            price_usd=25.50,
            message="Purchase successful",
            order_id="order456",
        )

        assert result.success is True
        assert result.item_id == "item123"
        assert result.item_title == "AK-47 | Redline"
        assert result.price_usd == 25.50
        assert result.order_id == "order456"
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

    def test_fAlgoled_result(self):
        """Test fAlgoled purchase result."""
        result = PurchaseResult(
            success=False,
            item_id="item123",
            item_title="M4A4 | Howl",
            price_usd=1000.0,
            message="Purchase fAlgoled",
            error="Insufficient balance",
        )

        assert result.success is False
        assert result.error == "Insufficient balance"
        assert result.order_id is None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = PurchaseResult(
            success=True,
            item_id="item123",
            item_title="Test Item",
            price_usd=10.0,
            message="Success",
            order_id="order456",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["item_id"] == "item123"
        assert result_dict["order_id"] == "order456"
        assert "timestamp" in result_dict


class TestAutoBuyer:
    """Tests for AutoBuyer class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_balance = AsyncMock(return_value={"usd": 10000})  # $100 in cents
        api.buy_item = AsyncMock(return_value={"success": True, "orderId": "order123"})
        api.get_sales_history = AsyncMock(return_value={"Sales": []})
        return api

    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence."""
        persistence = MagicMock()
        persistence.save_purchase = AsyncMock()
        persistence.get_purchases = AsyncMock(return_value=[])
        return persistence

    @pytest.fixture
    def auto_buyer(self, mock_api, mock_persistence):
        """Create AutoBuyer instance."""
        buyer = AutoBuyer(
            api_client=mock_api,
            config=AutoBuyConfig(enabled=True, dry_run=True),
        )
        buyer.set_trading_persistence(mock_persistence)
        return buyer

    def test_init(self, auto_buyer, mock_api):
        """Test initialization."""
        assert auto_buyer.api == mock_api
        assert auto_buyer.config.enabled is True
        assert auto_buyer.config.dry_run is True

    def test_set_trading_persistence(self, mock_api, mock_persistence):
        """Test setting trading persistence."""
        buyer = AutoBuyer(api_client=mock_api)
        assert buyer._trading_persistence is None

        buyer.set_trading_persistence(mock_persistence)
        assert buyer._trading_persistence == mock_persistence

    def test_set_auto_seller(self, auto_buyer):
        """Test linking auto seller."""
        mock_seller = MagicMock()
        auto_buyer.set_auto_seller(mock_seller)
        assert auto_buyer._auto_seller == mock_seller

    @pytest.mark.asyncio
    async def test_buy_item_dry_run(self, auto_buyer, mock_api):
        """Test buying item in dry run mode."""
        result = awAlgot auto_buyer.buy_item("item123", price_usd=25.50)

        assert result.success is True
        assert "DRY_RUN" in result.message
        mock_api.buy_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_item_records_history(self, auto_buyer):
        """Test that purchases are recorded in history."""
        awAlgot auto_buyer.buy_item("item123", price_usd=25.50)

        assert len(auto_buyer.purchase_history) == 1
        assert auto_buyer.purchase_history[0].item_id == "item123"

    @pytest.mark.asyncio
    async def test_should_auto_buy_price_too_high(self, auto_buyer):
        """Test should_auto_buy rejects high price."""
        item = {
            "itemId": "item123",
            "title": "Dragon Lore",
            "price": {"USD": "500000"},  # $5000
        }

        should_buy, reason = awAlgot auto_buyer.should_auto_buy(item)

        assert should_buy is False
        assert "price" in reason.lower() or "max" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_auto_buy_low_discount(self, auto_buyer):
        """Test should_auto_buy rejects low discount."""
        item = {
            "itemId": "item123",
            "title": "AK-47 | Redline",
            "price": {"USD": "2550"},
            "suggestedPrice": {"USD": "2600"},  # Only ~2% discount
        }

        should_buy, reason = awAlgot auto_buyer.should_auto_buy(item)

        assert should_buy is False
        assert "discount" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_auto_buy_success(self, auto_buyer):
        """Test should_auto_buy accepts good item."""
        item = {
            "itemId": "item123",
            "title": "AK-47 | Redline",
            "price": {"USD": "1500"},  # $15
            "suggestedPrice": {"USD": "2500"},  # $25 - 40% discount
        }

        should_buy, reason = awAlgot auto_buyer.should_auto_buy(item)

        assert should_buy is True

    @pytest.mark.asyncio
    async def test_process_opportunity(self, auto_buyer, mock_api):
        """Test processing arbitrage opportunity."""
        opportunity = {
            "itemId": "item123",
            "title": "AK-47 | Redline",
            "price": {"USD": "1500"},
            "suggestedPrice": {"USD": "2500"},
            "profit_percent": 40.0,
        }

        result = awAlgot auto_buyer.process_opportunity(opportunity)

        assert result is not None
        assert result.success is True

    def test_get_purchase_stats_empty(self, auto_buyer):
        """Test getting purchase statistics when empty."""
        stats = auto_buyer.get_purchase_stats()

        assert stats["total_purchases"] == 0
        assert stats["successful"] == 0
        assert stats["fAlgoled"] == 0
        assert stats["total_spent_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_get_purchase_stats_with_history(self, auto_buyer):
        """Test getting purchase statistics with history."""
        awAlgot auto_buyer.buy_item("item1", price_usd=10.0)
        awAlgot auto_buyer.buy_item("item2", price_usd=20.0)

        stats = auto_buyer.get_purchase_stats()

        assert stats["total_purchases"] == 2
        assert stats["successful"] == 2
        assert stats["total_spent_usd"] == 30.0

    def test_clear_history(self, auto_buyer):
        """Test clearing purchase history."""
        auto_buyer.purchase_history.append(
            PurchaseResult(
                success=True,
                item_id="test",
                item_title="Test",
                price_usd=10.0,
                message="Test",
            )
        )

        auto_buyer.clear_history()

        assert len(auto_buyer.purchase_history) == 0

    @pytest.mark.asyncio
    async def test_insufficient_balance_real_mode(self, mock_api, mock_persistence):
        """Test handling insufficient balance in real mode."""
        mock_api.get_balance = AsyncMock(return_value={"usd": 500})  # $5 in cents

        auto_buyer = AutoBuyer(
            api_client=mock_api,
            config=AutoBuyConfig(enabled=True, dry_run=False),
        )
        auto_buyer.set_trading_persistence(mock_persistence)

        result = awAlgot auto_buyer.buy_item("item123", price_usd=25.50)

        assert result.success is False
        assert "balance" in result.error.lower() or "insufficient" in result.error.lower()
