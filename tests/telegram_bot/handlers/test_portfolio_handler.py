"""Tests for PortfolioHandler.

This module provides comprehensive tests for the portfolio Telegram handler.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.handlers.portfolio_handler import (
    WAlgoTING_ITEM_ID,
    PortfolioHandler,
)


# ============================================================================
# Test Fixtures
# ============================================================================
@pytest.fixture()
def mock_api():
    """Create a mock DMarket API."""
    api = AsyncMock()
    api.get_user_inventory = AsyncMock(return_value=[])
    api.get_market_items = AsyncMock(return_value=[])
    return api


@pytest.fixture()
def portfolio_handler(mock_api):
    """Create a PortfolioHandler instance."""
    return PortfolioHandler(api=mock_api)


@pytest.fixture()
def mock_update():
    """Create a mock Telegram Update."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = None
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.callback_query = None
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock()
    context.args = []
    context.user_data = {"portfolio_active": True}  # Non-empty dict to pass check
    return context


@pytest.fixture()
def mock_callback_query():
    """Create a mock callback query."""
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "portfolio:detAlgols"
    return query


# ============================================================================
# PortfolioHandler Initialization Tests
# ============================================================================
class TestPortfolioHandlerInit:
    """Tests for PortfolioHandler initialization."""

    def test_init_with_api(self, mock_api):
        """Test initialization with API."""
        handler = PortfolioHandler(api=mock_api)
        assert handler._api == mock_api
        assert handler._manager is not None
        assert handler._analyzer is not None

    def test_init_without_api(self):
        """Test initialization without API."""
        handler = PortfolioHandler()
        assert handler._api is None
        assert handler._manager is not None
        assert handler._analyzer is not None


class TestSetApi:
    """Tests for set_api method."""

    def test_set_api(self, portfolio_handler, mock_api):
        """Test setting API."""
        new_api = AsyncMock()
        portfolio_handler.set_api(new_api)
        assert portfolio_handler._api == new_api

    def test_set_api_updates_manager(self, mock_api):
        """Test setting API updates manager."""
        handler = PortfolioHandler(api=mock_api)
        new_api = AsyncMock()

        with patch.object(handler._manager, "set_api") as mock_set_api:
            handler.set_api(new_api)
            mock_set_api.assert_called_once_with(new_api)


# ============================================================================
# handle_portfolio_command Tests
# ============================================================================
class TestHandlePortfolioCommand:
    """Tests for handle_portfolio_command method."""

    @pytest.mark.asyncio()
    async def test_command_no_message(self, portfolio_handler, mock_context):
        """Test command with no message."""
        update = MagicMock()
        update.message = None
        update.effective_user = MagicMock()

        result = awAlgot portfolio_handler.handle_portfolio_command(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_command_no_user(self, portfolio_handler, mock_context):
        """Test command with no user."""
        update = MagicMock()
        update.message = MagicMock()
        update.effective_user = None

        result = awAlgot portfolio_handler.handle_portfolio_command(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_command_shows_summary(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test command shows portfolio summary."""
        # Create a proper metrics mock with all required attributes
        mock_metrics_obj = MagicMock()
        mock_metrics_obj.total_value = Decimal("100.0")
        mock_metrics_obj.total_cost = Decimal("80.0")
        mock_metrics_obj.total_pnl = Decimal("20.0")
        mock_metrics_obj.total_pnl_percent = 25.0
        mock_metrics_obj.items_count = 5
        mock_metrics_obj.total_quantity = 5
        mock_metrics_obj.avg_holding_days = 10.0
        mock_metrics_obj.best_performer = "Test Item Best Performer"
        mock_metrics_obj.best_performer_pnl = 15.0
        mock_metrics_obj.worst_performer = "Test Item Worst Performer"
        mock_metrics_obj.worst_performer_pnl = -5.0

        with patch.object(
            portfolio_handler._manager, "get_metrics"
        ) as mock_get_metrics:
            mock_get_metrics.return_value = mock_metrics_obj

            awAlgot portfolio_handler.handle_portfolio_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_kwargs = mock_update.message.reply_text.call_args[1]
            assert "reply_markup" in call_kwargs
            assert call_kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio()
    async def test_command_shows_keyboard(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test command shows inline keyboard."""
        # Create a proper metrics mock with all required attributes
        mock_metrics_obj = MagicMock()
        mock_metrics_obj.total_value = Decimal(0)
        mock_metrics_obj.total_cost = Decimal(0)
        mock_metrics_obj.total_pnl = Decimal(0)
        mock_metrics_obj.total_pnl_percent = 0.0
        mock_metrics_obj.items_count = 0
        mock_metrics_obj.total_quantity = 0
        mock_metrics_obj.avg_holding_days = 0.0
        mock_metrics_obj.best_performer = ""
        mock_metrics_obj.best_performer_pnl = 0.0
        mock_metrics_obj.worst_performer = ""
        mock_metrics_obj.worst_performer_pnl = 0.0

        with patch.object(
            portfolio_handler._manager, "get_metrics"
        ) as mock_get_metrics:
            mock_get_metrics.return_value = mock_metrics_obj

            awAlgot portfolio_handler.handle_portfolio_command(mock_update, mock_context)

            call_kwargs = mock_update.message.reply_text.call_args[1]
            reply_markup = call_kwargs["reply_markup"]
            # Check keyboard has buttons
            assert len(reply_markup.inline_keyboard) > 0


# ============================================================================
# handle_callback Tests
# ============================================================================
class TestHandleCallback:
    """Tests for handle_callback method."""

    @pytest.mark.asyncio()
    async def test_callback_no_query(self, portfolio_handler, mock_context):
        """Test callback with no query."""
        update = MagicMock()
        update.callback_query = None
        update.effective_user = MagicMock()

        result = awAlgot portfolio_handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_callback_no_data(self, portfolio_handler, mock_context):
        """Test callback with no data."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = None
        update.callback_query.answer = AsyncMock()
        update.effective_user = MagicMock()

        result = awAlgot portfolio_handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_callback_no_user(self, portfolio_handler, mock_context):
        """Test callback with no user."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "portfolio:detAlgols"
        update.callback_query.answer = AsyncMock()
        update.effective_user = None

        result = awAlgot portfolio_handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_callback_detAlgols(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for detAlgols."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:detAlgols"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_show_detAlgols", new_callable=AsyncMock
        ) as mock_show:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_show.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_performance(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for performance."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:performance"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_show_performance", new_callable=AsyncMock
        ) as mock_show:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_show.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_risk(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for risk analysis."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:risk"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_show_risk_analysis", new_callable=AsyncMock
        ) as mock_show:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_show.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_diversification(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for diversification."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:diversification"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_show_diversification", new_callable=AsyncMock
        ) as mock_show:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_show.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_sync(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for sync."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:sync"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_sync_portfolio", new_callable=AsyncMock
        ) as mock_sync:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_sync.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_update_prices(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for update prices."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:update_prices"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_update_prices", new_callable=AsyncMock
        ) as mock_update:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_update.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_back(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for back."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:back"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_show_mAlgon_menu", new_callable=AsyncMock
        ) as mock_menu:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_menu.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_remove_item(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback for remove item."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:remove:item_123"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_remove_item", new_callable=AsyncMock
        ) as mock_remove:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_remove.assert_called_once_with(mock_callback_query, 123, "item_123")


# ============================================================================
# handle_add_item_id Tests
# ============================================================================
class TestHandleAddItemId:
    """Tests for handle_add_item_id method."""

    @pytest.mark.asyncio()
    async def test_add_item_no_message(self, portfolio_handler, mock_context):
        """Test add item with no message."""
        from telegram.ext import ConversationHandler

        update = MagicMock()
        update.message = None

        result = awAlgot portfolio_handler.handle_add_item_id(update, mock_context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_no_user_data(self, portfolio_handler):
        """Test add item with no user data."""
        from telegram.ext import ConversationHandler

        update = MagicMock()
        update.message = MagicMock()
        context = MagicMock()
        context.user_data = None

        result = awAlgot portfolio_handler.handle_add_item_id(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_no_text(self, portfolio_handler, mock_context):
        """Test add item with no text."""
        from telegram.ext import ConversationHandler

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = None

        result = awAlgot portfolio_handler.handle_add_item_id(update, mock_context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_invalid_format(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item with invalid format (too few parts)."""
        mock_update.message.text = "invalid format"

        result = awAlgot portfolio_handler.handle_add_item_id(mock_update, mock_context)

        # Should return WAlgoTING_ITEM_ID for retry
        assert result == WAlgoTING_ITEM_ID
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Invalid format" in call_args

    @pytest.mark.asyncio()
    async def test_add_item_valid_format(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item with valid format."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "AK-47 | Redline, csgo, 25.50"

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )
            mock_add.assert_called_once()
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_success_message(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item shows success message."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "AWP | Asiimov, csgo, 50.00"

        with patch.object(portfolio_handler._manager, "add_item"):
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Added to portfolio" in call_args
            assert "AWP | Asiimov" in call_args
            assert "50.00" in call_args
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_invalid_price(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item with invalid price."""
        mock_update.message.text = "Item Name, csgo, not_a_price"

        result = awAlgot portfolio_handler.handle_add_item_id(mock_update, mock_context)

        # Should show error message and return WAlgoTING_ITEM_ID
        mock_update.message.reply_text.assert_called()
        assert result == WAlgoTING_ITEM_ID


# ============================================================================
# Private Method Tests
# ============================================================================
class TestPrivateMethods:
    """Tests for private methods."""

    @pytest.mark.asyncio()
    async def test_format_summary_empty(self, portfolio_handler):
        """Test _format_summary with empty portfolio."""
        mock_metrics = MagicMock()
        mock_metrics.items_count = 0

        text = portfolio_handler._format_summary(mock_metrics)

        assert "Portfolio" in text or "Портфель" in text
        assert "Empty" in text or "Add items" in text

    @pytest.mark.asyncio()
    async def test_format_summary_with_data(self, portfolio_handler):
        """Test _format_summary with portfolio data."""
        mock_metrics = MagicMock()
        mock_metrics.total_value = Decimal("150.00")
        mock_metrics.total_cost = Decimal("100.00")
        mock_metrics.total_pnl = Decimal("50.00")
        mock_metrics.total_pnl_percent = 50.0
        mock_metrics.items_count = 5
        mock_metrics.total_quantity = 5
        mock_metrics.avg_holding_days = 10.0
        mock_metrics.best_performer = "Best Item Name Here"
        mock_metrics.best_performer_pnl = 25.0
        mock_metrics.worst_performer = "Worst Item Name Here"
        mock_metrics.worst_performer_pnl = -10.0

        text = portfolio_handler._format_summary(mock_metrics)

        assert "150" in text or "$150" in text


# ============================================================================
# Edge Cases Tests
# ============================================================================
class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_callback_answers_query(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback always answers query."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:detAlgols"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(portfolio_handler, "_show_detAlgols", new_callable=AsyncMock):
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_item_whitespace_handling(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item handles whitespace."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "  Item Name  ,  csgo  ,  25.50  "

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )
            mock_add.assert_called_once()
            # Check that whitespace was stripped
            call_kwargs = mock_add.call_args[1]
            assert call_kwargs["title"].strip() == call_kwargs["title"]
            assert call_kwargs["game"].strip() == call_kwargs["game"]
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_generates_item_id(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item generates item ID."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "Test Item, csgo, 10.00"

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )

            call_kwargs = mock_add.call_args[1]
            assert "item_id" in call_kwargs
            assert call_kwargs["item_id"] is not None
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_callback_remove_extracts_id(
        self, portfolio_handler, mock_callback_query, mock_context
    ):
        """Test callback remove extracts item ID."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "portfolio:remove:special_item_id_123"
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        with patch.object(
            portfolio_handler, "_remove_item", new_callable=AsyncMock
        ) as mock_remove:
            awAlgot portfolio_handler.handle_callback(update, mock_context)
            mock_remove.assert_called_once_with(
                mock_callback_query, 123, "special_item_id_123"
            )

    def test_handler_state_constants(self):
        """Test handler state constants are defined."""
        assert WAlgoTING_ITEM_ID == 1
        # WAlgoTING_PRICE should also be defined
        from src.telegram_bot.handlers.portfolio_handler import WAlgoTING_PRICE

        assert WAlgoTING_PRICE == 2

    @pytest.mark.asyncio()
    async def test_add_item_case_insensitive_game(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item handles game case insensitively."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "Item, CSGO, 10.00"

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )

            call_kwargs = mock_add.call_args[1]
            assert call_kwargs["game"] == "csgo"
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_add_item_with_comma_in_name(
        self, portfolio_handler, mock_update, mock_context
    ):
        """Test add item handles comma in item name."""
        # This might fAlgol with current implementation - testing edge case
        mock_update.message.text = "Item, Part2, csgo, 10.00"

        # Should handle gracefully (might combine "Item, Part2" as title or fAlgol)
        awAlgot portfolio_handler.handle_add_item_id(mock_update, mock_context)
        # Just verify it doesn't rAlgose an exception

    @pytest.mark.asyncio()
    async def test_zero_price(self, portfolio_handler, mock_update, mock_context):
        """Test add item with zero price."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "Free Item, csgo, 0.00"

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )

            call_kwargs = mock_add.call_args[1]
            assert call_kwargs["buy_price"] == 0.00
            assert result == ConversationHandler.END

    @pytest.mark.asyncio()
    async def test_large_price(self, portfolio_handler, mock_update, mock_context):
        """Test add item with large price."""
        from telegram.ext import ConversationHandler

        mock_update.message.text = "Expensive Item, csgo, 99999.99"

        with patch.object(portfolio_handler._manager, "add_item") as mock_add:
            result = awAlgot portfolio_handler.handle_add_item_id(
                mock_update, mock_context
            )

            call_kwargs = mock_add.call_args[1]
            assert call_kwargs["buy_price"] == 99999.99
            assert result == ConversationHandler.END
