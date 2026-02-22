"""Tests for auto_sell_handler module.

Tests Telegram commands and callbacks for auto-sell management.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.auto_seller import (
    AutoSeller,
    AutoSellerStats,
    PricingStrategy,
    SaleConfig,
)
from src.telegram_bot.handlers.auto_sell_handler import (
    AutoSellHandler,
    format_auto_sell_notification,
)


@pytest.fixture()
def mock_auto_seller():
    """Create mock AutoSeller instance."""
    seller = MagicMock(spec=AutoSeller)
    seller.config = SaleConfig(
        enabled=True,
        min_margin_percent=4.0,
        target_margin_percent=8.0,
        max_margin_percent=12.0,
        stop_loss_hours=48,
        stop_loss_percent=5.0,
        pricing_strategy=PricingStrategy.UNDERCUT,
    )
    seller._stats = AutoSellerStats()
    seller.scheduled_sales = {}
    return seller


@pytest.fixture()
def handler(mock_auto_seller):
    """Create AutoSellHandler with mocked AutoSeller."""
    return AutoSellHandler(auto_seller=mock_auto_seller)


@pytest.fixture()
def mock_update():
    """Create mock Telegram Update."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture()
def mock_context():
    """Create mock callback context."""
    context = MagicMock()
    context.user_data = {}
    return context


@pytest.fixture()
def mock_query():
    """Create mock callback query."""
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "auto_sell:status"
    return query


class TestAutoSellHandlerInit:
    """Tests for AutoSellHandler initialization."""

    def test_init_without_auto_seller(self):
        """Test initialization without auto_seller."""
        handler = AutoSellHandler()
        assert handler.auto_seller is None

    def test_init_with_auto_seller(self, mock_auto_seller):
        """Test initialization with auto_seller."""
        handler = AutoSellHandler(auto_seller=mock_auto_seller)
        assert handler.auto_seller is mock_auto_seller

    def test_set_auto_seller(self, mock_auto_seller):
        """Test setting auto_seller after init."""
        handler = AutoSellHandler()
        handler.set_auto_seller(mock_auto_seller)
        assert handler.auto_seller is mock_auto_seller


class TestAutoSellCommand:
    """Tests for /auto_sell command."""

    @pytest.mark.asyncio()
    async def test_handle_auto_sell_command_enabled(
        self, handler, mock_update, mock_context, mock_auto_seller
    ):
        """Test command shows enabled status."""
        mock_auto_seller.config.enabled = True

        await handler.handle_auto_sell_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args.kwargs
        assert "✅ Enabled" in call_kwargs.get(
            "text", mock_update.message.reply_text.call_args[0][0]
        )

    @pytest.mark.asyncio()
    async def test_handle_auto_sell_command_disabled(
        self, handler, mock_update, mock_context, mock_auto_seller
    ):
        """Test command shows disabled status."""
        mock_auto_seller.config.enabled = False

        await handler.handle_auto_sell_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        text = call_args.kwargs.get("text", call_args[0][0] if call_args[0] else "")
        assert "❌ Disabled" in text

    @pytest.mark.asyncio()
    async def test_handle_auto_sell_command_no_message(
        self, handler, mock_context, mock_auto_seller
    ):
        """Test command does nothing without message."""
        update = MagicMock()
        update.message = None

        await handler.handle_auto_sell_command(update, mock_context)
        # Should not raise


class TestStatusCallback:
    """Tests for status callback."""

    @pytest.mark.asyncio()
    async def test_show_status(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test status display."""
        mock_auto_seller.get_statistics.return_value = {
            "active_sales": 5,
            "pending": 2,
            "listed": 3,
            "scheduled_count": 10,
            "listed_count": 8,
            "sold_count": 5,
            "failed_count": 1,
            "stop_loss_count": 0,
            "adjustments_count": 15,
            "total_profit": 25.50,
        }

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:status"

        await handler.handle_callback(update, mock_context)

        mock_query.edit_message_text.assert_called_once()
        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "Active Sales" in text
        assert "$25.50" in text

    @pytest.mark.asyncio()
    async def test_show_status_no_auto_seller(self, mock_query, mock_context):
        """Test status with no auto_seller configured."""
        handler = AutoSellHandler()

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:status"

        await handler.handle_callback(update, mock_context)

        mock_query.edit_message_text.assert_called_once()
        text = mock_query.edit_message_text.call_args[0][0]
        assert "not configured" in text


class TestConfigCallback:
    """Tests for config callback."""

    @pytest.mark.asyncio()
    async def test_show_config(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test config display."""
        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:config"

        await handler.handle_callback(update, mock_context)

        mock_query.edit_message_text.assert_called_once()
        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "Configuration" in text
        assert "4.0%" in text  # min_margin_percent
        assert "8.0%" in text  # target_margin_percent


class TestToggleCallback:
    """Tests for toggle callback."""

    @pytest.mark.asyncio()
    async def test_toggle_enabled_to_disabled(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test toggling from enabled to disabled."""
        mock_auto_seller.config.enabled = True

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:toggle"

        await handler.handle_callback(update, mock_context)

        assert mock_auto_seller.config.enabled is False

    @pytest.mark.asyncio()
    async def test_toggle_disabled_to_enabled(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test toggling from disabled to enabled."""
        mock_auto_seller.config.enabled = False

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:toggle"

        await handler.handle_callback(update, mock_context)

        assert mock_auto_seller.config.enabled is True


class TestActiveSalesCallback:
    """Tests for active sales callback."""

    @pytest.mark.asyncio()
    async def test_show_active_sales_empty(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test active sales display when empty."""
        mock_auto_seller.get_active_sales.return_value = []

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:active"

        await handler.handle_callback(update, mock_context)

        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "No active sales" in text

    @pytest.mark.asyncio()
    async def test_show_active_sales_with_items(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test active sales display with items."""
        mock_auto_seller.get_active_sales.return_value = [
            {
                "item_id": "item1",
                "item_name": "AK-47 | Redline",
                "buy_price": 10.0,
                "current_price": 12.0,
                "status": "listed",
                "profit": 2.0,
                "profit_percent": 20.0,
                "listed_at": datetime.now(UTC).isoformat(),
                "adjustments": 0,
            }
        ]

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:active"

        await handler.handle_callback(update, mock_context)

        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "AK-47" in text


class TestCancelSaleCallback:
    """Tests for cancel sale callback."""

    @pytest.mark.asyncio()
    async def test_cancel_sale_success(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test successful sale cancellation."""
        mock_auto_seller.cancel_sale = AsyncMock(return_value=True)

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:cancel:item123"

        await handler.handle_callback(update, mock_context)

        mock_auto_seller.cancel_sale.assert_called_once_with("item123")
        text = mock_query.edit_message_text.call_args[0][0]
        assert "cancelled" in text

    @pytest.mark.asyncio()
    async def test_cancel_sale_failure(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test failed sale cancellation."""
        mock_auto_seller.cancel_sale = AsyncMock(return_value=False)

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:cancel:item123"

        await handler.handle_callback(update, mock_context)

        text = mock_query.edit_message_text.call_args[0][0]
        assert "Failed" in text


class TestCancelMenu:
    """Tests for cancel menu callback."""

    @pytest.mark.asyncio()
    async def test_show_cancel_menu_empty(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test cancel menu when no sales."""
        mock_auto_seller.get_active_sales.return_value = []

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:cancel_menu"

        await handler.handle_callback(update, mock_context)

        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "No active sales to cancel" in text

    @pytest.mark.asyncio()
    async def test_show_cancel_menu_with_items(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test cancel menu with items."""
        mock_auto_seller.get_active_sales.return_value = [
            {
                "item_id": "item1",
                "item_name": "AK-47 | Redline",
                "buy_price": 10.0,
                "current_price": 12.0,
                "status": "listed",
                "profit": 2.0,
                "profit_percent": 20.0,
                "listed_at": datetime.now(UTC).isoformat(),
                "adjustments": 0,
            }
        ]

        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:cancel_menu"

        await handler.handle_callback(update, mock_context)

        # Check keyboard has cancel buttons
        call_kwargs = mock_query.edit_message_text.call_args.kwargs
        assert "reply_markup" in call_kwargs


class TestBackCallback:
    """Tests for back callback."""

    @pytest.mark.asyncio()
    async def test_back_to_main_menu(
        self, handler, mock_query, mock_context, mock_auto_seller
    ):
        """Test returning to main menu."""
        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = "auto_sell:back"

        await handler.handle_callback(update, mock_context)

        mock_query.edit_message_text.assert_called_once()
        text = mock_query.edit_message_text.call_args.kwargs.get(
            "text", mock_query.edit_message_text.call_args[0][0]
        )
        assert "Auto-Sell Management" in text


class TestGetHandlers:
    """Tests for get_handlers method."""

    def test_get_handlers(self, handler):
        """Test handler registration."""
        handlers = handler.get_handlers()

        assert len(handlers) == 2
        # First should be CommandHandler
        assert handlers[0].__class__.__name__ == "CommandHandler"
        # Second should be CallbackQueryHandler
        assert handlers[1].__class__.__name__ == "CallbackQueryHandler"


class TestFormatNotification:
    """Tests for format_auto_sell_notification function."""

    def test_format_listed_notification(self):
        """Test listed notification format."""
        result = format_auto_sell_notification(
            item_name="AK-47 | Redline",
            action="listed",
            price=12.50,
        )

        assert "📤" in result
        assert "Listed" in result
        assert "AK-47 | Redline" in result
        assert "$12.50" in result

    def test_format_sold_notification_with_profit(self):
        """Test sold notification with profit."""
        result = format_auto_sell_notification(
            item_name="M4A4 | Asiimov",
            action="sold",
            price=25.00,
            profit=3.50,
        )

        assert "✅" in result
        assert "Sold" in result
        assert "$25.00" in result
        assert "+$3.50" in result
        assert "📈" in result

    def test_format_sold_notification_with_loss(self):
        """Test sold notification with loss."""
        result = format_auto_sell_notification(
            item_name="AWP | Dragon Lore",
            action="sold",
            price=1000.00,
            profit=-50.00,
        )

        assert "✅" in result
        assert "-$50.00" in result
        assert "📉" in result

    def test_format_stop_loss_notification(self):
        """Test stop loss notification."""
        result = format_auto_sell_notification(
            item_name="Glock-18 | Fade",
            action="stop_loss",
            price=150.00,
            profit=-10.00,
        )

        assert "⚠️" in result
        assert "Stop Loss" in result

    def test_format_cancelled_notification(self):
        """Test cancelled notification."""
        result = format_auto_sell_notification(
            item_name="USP-S | Kill Confirmed",
            action="cancelled",
            price=35.00,
        )

        assert "❌" in result
        assert "Cancelled" in result

    def test_format_adjusted_notification(self):
        """Test price adjusted notification."""
        result = format_auto_sell_notification(
            item_name="Desert Eagle | Blaze",
            action="adjusted",
            price=28.99,
        )

        assert "🔄" in result
        assert "Adjusted" in result


class TestCallbackQueryNone:
    """Tests for edge cases with None values."""

    @pytest.mark.asyncio()
    async def test_handle_callback_no_query(self, handler, mock_context):
        """Test callback with no query."""
        update = MagicMock()
        update.callback_query = None

        result = await handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_handle_callback_no_data(self, handler, mock_query, mock_context):
        """Test callback with no data."""
        update = MagicMock()
        update.callback_query = mock_query
        mock_query.data = None

        result = await handler.handle_callback(update, mock_context)
        assert result is None
