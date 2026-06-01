"""Tests for advanced_orders_handler module.

This module tests the AdvancedOrderHandler class for managing
advanced orders with filters (Float, Doppler, Pattern, Sticker).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ConversationHandler

from src.telegram_bot.handlers.advanced_orders_handler import (
    CONFIRMING_ORDER,
    ENTERING_FLOAT_RANGE,
    ENTERING_ITEM_TITLE,
    ENTERING_PRICE,
    SELECTING_ORDER_TYPE,
    AdvancedOrderHandler,
)


class TestAdvancedOrderHandler:
    """Tests for AdvancedOrderHandler class."""

    @pytest.fixture
    def mock_order_manager(self):
        """Create mock order manager."""
        manager = MagicMock()
        
        # Mock create_order to return a result object with success, target_id, message
        result_mock = MagicMock()
        result_mock.success = True
        result_mock.target_id = "target_123"
        result_mock.message = ""
        
        manager.create_order = AsyncMock(return_value=result_mock)
        manager.create_float_order = AsyncMock(return_value={"success": True})
        manager.get_orders = AsyncMock(return_value=[])
        manager.cancel_order = AsyncMock(return_value=True)
        return manager

    @pytest.fixture
    def mock_float_arbitrage(self):
        """Create mock float arbitrage."""
        arb = MagicMock()
        arb.find_opportunities = AsyncMock(return_value=[])
        return arb

    @pytest.fixture
    def handler(self, mock_order_manager, mock_float_arbitrage):
        """Create AdvancedOrderHandler instance."""
        return AdvancedOrderHandler(
            advanced_order_manager=mock_order_manager,
            float_arbitrage=mock_float_arbitrage,
        )

    @pytest.fixture
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        context = MagicMock()
        context.user_data = {}
        context.bot_data = {}
        return context

    def test_init(self, handler, mock_order_manager, mock_float_arbitrage):
        """Test handler initialization."""
        assert handler.order_manager == mock_order_manager
        assert handler.float_arbitrage == mock_float_arbitrage

    def test_init_without_managers(self):
        """Test handler initialization without managers."""
        handler = AdvancedOrderHandler()
        assert handler.order_manager is None
        assert handler.float_arbitrage is None

    @pytest.mark.asyncio
    async def test_show_advanced_orders_menu(self, handler, mock_update, mock_context):
        """Test showing advanced orders menu."""
        result = await handler.show_advanced_orders_menu(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Float Order" in str(call_args) or "расширенных ордеров" in str(call_args)
        assert result == SELECTING_ORDER_TYPE

    @pytest.mark.asyncio
    async def test_handle_order_type_selection_float(self, handler, mock_update, mock_context):
        """Test handling float order type selection."""
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.data = "adv_order_float"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        result = await handler.handle_order_type_selection(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        assert result == ENTERING_ITEM_TITLE

    @pytest.mark.asyncio
    async def test_handle_order_type_selection_doppler(self, handler, mock_update, mock_context):
        """Test handling doppler order type selection."""
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.data = "adv_order_doppler"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        result = await handler.handle_order_type_selection(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_item_title_input(self, handler, mock_update, mock_context):
        """Test handling item title input."""
        mock_update.message.text = "AK-47 | Redline"
        mock_context.user_data["order_type"] = "float"

        result = await handler.handle_item_title(mock_update, mock_context)

        assert mock_context.user_data.get("item_title") == "AK-47 | Redline"
        assert result == ENTERING_FLOAT_RANGE

    @pytest.mark.asyncio
    async def test_handle_float_range_input(self, handler, mock_update, mock_context):
        """Test handling float range input."""
        mock_update.message.text = "0.01 0.07"
        mock_context.user_data["order_type"] = "float"
        mock_context.user_data["item_title"] = "AK-47 | Redline"

        result = await handler.handle_float_range(mock_update, mock_context)

        assert mock_context.user_data.get("float_min") == 0.01
        assert mock_context.user_data.get("float_max") == 0.07
        assert result == ENTERING_PRICE

    @pytest.mark.asyncio
    async def test_handle_float_range_invalid(self, handler, mock_update, mock_context):
        """Test handling invalid float range."""
        mock_update.message.text = "invalid range"
        mock_context.user_data["order_type"] = "float"

        result = await handler.handle_float_range(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        # Should stay on same state for retry
        assert result == ENTERING_FLOAT_RANGE

    @pytest.mark.asyncio
    async def test_handle_price_input(self, handler, mock_update, mock_context):
        """Test handling price input."""
        mock_update.message.text = "25.50"
        mock_context.user_data["order_type"] = "float"
        mock_context.user_data["item_title"] = "AK-47 | Redline"
        mock_context.user_data["float_min"] = 0.01
        mock_context.user_data["float_max"] = 0.07

        result = await handler.handle_price(mock_update, mock_context)

        # Implementation stores price in "max_price" key
        assert mock_context.user_data.get("max_price") == 25.50
        assert result == CONFIRMING_ORDER

    @pytest.mark.asyncio
    async def test_confirm_order(self, handler, mock_update, mock_context, mock_order_manager):
        """Test confirming order creation."""
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.data = "adv_order_confirm"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        mock_context.user_data = {
            "order_type": "float",
            "item_title": "AK-47 | Redline",
            "float_min": 0.01,
            "float_max": 0.07,
            "max_price": 25.50,  # Uses max_price, not price
        }

        result = await handler.handle_confirmation(mock_update, mock_context)

        # Implementation calls create_order, not create_float_order
        mock_order_manager.create_order.assert_called_once()
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_cancel_order_creation(self, handler, mock_update, mock_context):
        """Test canceling order creation."""
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.data = "cancel_order"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        result = await handler.cancel(mock_update, mock_context)

        # cancel() calls edit_message_text, not answer()
        mock_update.callback_query.edit_message_text.assert_called_once()
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_show_active_orders(self, handler, mock_update, mock_context, mock_order_manager):
        """Test showing active orders."""
        mock_order_manager.get_orders.return_value = [
            {"id": 1, "item": "AK-47", "price": 25.0, "type": "float"},
            {"id": 2, "item": "M4A4", "price": 30.0, "type": "doppler"},
        ]

        # Method is called show_my_orders, not show_active_orders
        await handler.show_my_orders(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        # The message contains "Мои активные ордера" in Russian
        assert "активные ордера" in str(call_args)

    @pytest.mark.asyncio
    async def test_show_templates(self, handler, mock_update, mock_context):
        """Test showing order templates."""
        await handler.show_templates(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    def test_get_handlers(self, handler):
        """Test getting conversation handlers."""
        # Method is called get_conversation_handler, not get_handlers
        conv_handler = handler.get_conversation_handler()

        assert isinstance(conv_handler, ConversationHandler)


class TestAdvancedOrderConversationStates:
    """Tests for conversation state constants."""

    def test_state_values(self):
        """Test state values are sequential."""
        states = [
            SELECTING_ORDER_TYPE,
            ENTERING_ITEM_TITLE,
            ENTERING_FLOAT_RANGE,
            ENTERING_PRICE,
            CONFIRMING_ORDER,
        ]

        for i, state in enumerate(states):
            assert state == i
