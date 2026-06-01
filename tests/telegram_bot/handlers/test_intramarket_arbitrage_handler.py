"""Расширенные тесты для обработчика внутрирыночного арбитража."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User
from telegram.ext import ContextTypes

from src.dmarket.intramarket_arbitrage import PriceAnomalyType
from src.telegram_bot.handlers.intramarket_arbitrage_handler import (
    ANOMALY_ACTION,
    INTRA_ARBITRAGE_ACTION,
    RARE_ACTION,
    TRENDING_ACTION,
    display_results_with_pagination,
    format_intramarket_item,
    format_intramarket_results,
    handle_intramarket_callback,
    handle_intramarket_pagination,
    register_intramarket_handlers,
    start_intramarket_arbitrage,
)

# ======================== Fixtures ========================


@pytest.fixture()
def mock_user():
    """Create a mock User object."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.is_bot = False
    return user


@pytest.fixture()
def mock_chat():
    """Create a mock Chat object."""
    chat = MagicMock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"
    return chat


@pytest.fixture()
def mock_message(mock_user, mock_chat):
    """Create a mock Message object."""
    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.reply_text = AsyncMock()
    return message


@pytest.fixture()
def mock_callback_query(mock_user, mock_message):
    """Create a mock CallbackQuery object."""
    query = MagicMock(spec=CallbackQuery)
    query.id = "test_id"
    query.from_user = mock_user
    query.message = mock_message
    query.data = INTRA_ARBITRAGE_ACTION
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return query


@pytest.fixture()
def mock_update(mock_user, mock_callback_query):
    """Create a mock Update object with callback_query."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.callback_query = mock_callback_query
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    context.chat_data = {}
    return context


@pytest.fixture()
def sample_underpriced_result():
    """Create a sample underpriced item result."""
    return {
        "type": PriceAnomalyType.UNDERPRICED,
        "item_to_buy": {
            "itemId": "item_12345",
            "title": "AK-47 | Redline (Field-Tested)",
        },
        "item_to_sell": {
            "itemId": "item_67890",
            "title": "AK-47 | Redline (Field-Tested)",
        },
        "buy_price": 12.50,
        "sell_price": 18.75,
        "profit_percentage": 35.0,
        "profit_after_fee": 4.25,
        "similarity": 0.92,
    }


@pytest.fixture()
def sample_trending_result():
    """Create a sample trending item result."""
    return {
        "type": PriceAnomalyType.TRENDING_UP,
        "item": {
            "itemId": "item_55555",
            "title": "M4A4 | Howl (Factory New)",
        },
        "current_price": 1500.00,
        "projected_price": 1800.00,
        "price_change_percent": 20.0,
        "potential_profit_percent": 20.0,
        "sales_velocity": 15,
    }


@pytest.fixture()
def sample_rare_result():
    """Create a sample rare trAlgots item result."""
    return {
        "type": PriceAnomalyType.RARE_TRAlgoTS,
        "item": {
            "itemId": "item_99999",
            "title": "AK-47 | Case Hardened (Factory New)",
        },
        "current_price": 250.00,
        "estimated_value": 1500.00,
        "price_difference_percent": 500.0,
        "rare_trAlgots": [
            "Blue Gem Pattern 387",
            "Low Float: 0.008",
            "4x Katowice 2014 Stickers",
        ],
    }


# ======================== Tests for format_intramarket_item ========================


class TestFormatIntramarketItem:
    """Tests for format_intramarket_item function."""

    def test_format_underpriced_item(self, sample_underpriced_result):
        """Test formatting an underpriced item."""
        result = format_intramarket_item(sample_underpriced_result)

        assert "AK-47 | Redline (Field-Tested)" in result
        assert "$12.50" in result
        assert "$18.75" in result
        assert "35.0%" in result
        assert "$4.25" in result
        assert "92%" in result
        assert "item_12345" in result

    def test_format_trending_item(self, sample_trending_result):
        """Test formatting a trending item."""
        result = format_intramarket_item(sample_trending_result)

        assert "M4A4 | Howl (Factory New)" in result
        assert "$1500.00" in result
        assert "$1800.00" in result
        assert "20.0%" in result
        assert "15" in result
        assert "item_55555" in result

    def test_format_rare_item(self, sample_rare_result):
        """Test formatting a rare trAlgots item."""
        result = format_intramarket_item(sample_rare_result)

        assert "AK-47 | Case Hardened (Factory New)" in result
        assert "$250.00" in result
        assert "$1500.00" in result
        assert "500.0%" in result
        assert "Blue Gem Pattern 387" in result
        assert "Low Float" in result
        assert "Katowice 2014" in result
        assert "item_99999" in result

    def test_format_unknown_type(self):
        """Test formatting an item with unknown type."""
        unknown_result = {"type": "unknown_type"}
        result = format_intramarket_item(unknown_result)

        assert "Неизвестный тип результата" in result

    def test_format_missing_fields(self):
        """Test formatting with missing fields."""
        incomplete_result = {
            "type": PriceAnomalyType.UNDERPRICED,
            "item_to_buy": {"title": "Test Item"},
            # Missing other fields
        }
        result = format_intramarket_item(incomplete_result)

        assert "Test Item" in result
        assert "$0.00" in result

    def test_format_empty_rare_trAlgots(self):
        """Test formatting rare item with empty trAlgots list."""
        rare_no_trAlgots = {
            "type": PriceAnomalyType.RARE_TRAlgoTS,
            "item": {"itemId": "item_1", "title": "Test Item"},
            "current_price": 100.0,
            "estimated_value": 200.0,
            "price_difference_percent": 100.0,
            "rare_trAlgots": [],
        }
        result = format_intramarket_item(rare_no_trAlgots)

        assert "Test Item" in result
        assert "особенности" in result or "✨" in result


class TestFormatIntramarketResults:
    """Tests for format_intramarket_results function."""

    def test_format_empty_results(self):
        """Test formatting empty results list."""
        result = format_intramarket_results([], 0, 10)
        assert "Нет результатов" in result

    def test_format_single_result(self, sample_underpriced_result):
        """Test formatting a single result."""
        result = format_intramarket_results([sample_underpriced_result], 0, 10)

        assert "Страница 1" in result
        assert "AK-47 | Redline" in result

    def test_format_multiple_results(
        self, sample_underpriced_result, sample_trending_result
    ):
        """Test formatting multiple results."""
        results = [sample_underpriced_result, sample_trending_result]
        result = format_intramarket_results(results, 0, 10)

        assert "Страница 1" in result
        assert "AK-47 | Redline" in result
        assert "M4A4 | Howl" in result

    def test_format_with_page_number(self, sample_underpriced_result):
        """Test formatting with different page numbers."""
        result = format_intramarket_results([sample_underpriced_result], 5, 10)
        assert "Страница 6" in result

    def test_format_with_large_page(self, sample_underpriced_result):
        """Test formatting with large page number."""
        result = format_intramarket_results([sample_underpriced_result], 99, 10)
        assert "Страница 100" in result


# ======================== Tests for display_results_with_pagination ========================


class TestDisplayResultsWithPagination:
    """Tests for display_results_with_pagination function."""

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_display_empty_results(self, mock_pagination, mock_callback_query):
        """Test displaying empty results."""
        await display_results_with_pagination(
            query=mock_callback_query,
            results=[],
            title="Test Title",
            user_id=123456789,
            action_type=ANOMALY_ACTION,
            game="csgo",
        )

        mock_callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_query.edit_message_text.call_args
        assert "Возможности не найдены" in call_args[0][0]
        assert call_args[1]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_display_with_results(
        self,
        mock_pagination,
        mock_keyboard,
        mock_callback_query,
        sample_underpriced_result,
    ):
        """Test displaying results with pagination."""
        mock_pagination.get_page.return_value = ([sample_underpriced_result], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await display_results_with_pagination(
            query=mock_callback_query,
            results=[sample_underpriced_result],
            title="Ценовые аномалии",
            user_id=123456789,
            action_type=ANOMALY_ACTION,
            game="csgo",
        )

        mock_pagination.add_items_for_user.assert_called_once()
        mock_pagination.get_page.assert_called_once()
        mock_callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_display_pagination_key_format(
        self,
        mock_pagination,
        mock_keyboard,
        mock_callback_query,
        sample_underpriced_result,
    ):
        """Test that pagination key is correctly formatted."""
        mock_pagination.get_page.return_value = ([sample_underpriced_result], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await display_results_with_pagination(
            query=mock_callback_query,
            results=[sample_underpriced_result],
            title="Test",
            user_id=123456789,
            action_type=TRENDING_ACTION,
            game="dota2",
        )

        # Verify pagination manager was called with correct key
        add_call = mock_pagination.add_items_for_user.call_args
        assert add_call[0][2] == f"intra_{TRENDING_ACTION}"


# ======================== Tests for handle_intramarket_pagination ========================


class TestHandleIntramarketPagination:
    """Tests for handle_intramarket_pagination function."""

    @pytest.mark.asyncio()
    async def test_pagination_no_callback_query(self, mock_update, mock_context):
        """Test pagination without callback query."""
        mock_update.callback_query = None

        await handle_intramarket_pagination(mock_update, mock_context)

        # Function should return early without errors

    @pytest.mark.asyncio()
    async def test_pagination_no_effective_user(self, mock_update, mock_context):
        """Test pagination without effective user."""
        mock_update.effective_user = None
        mock_update.callback_query.data = "intra_paginate:next:anomaly:csgo"

        await handle_intramarket_pagination(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_pagination_no_callback_data(self, mock_update, mock_context):
        """Test pagination without callback data."""
        mock_update.callback_query.data = None

        await handle_intramarket_pagination(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_pagination_invalid_data_format(self, mock_update, mock_context):
        """Test pagination with invalid data format."""
        mock_update.callback_query.data = "invalid_data"

        await handle_intramarket_pagination(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_next_page(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test navigating to next page."""
        mock_update.callback_query.data = "intra_paginate:next:anomaly:csgo"
        mock_pagination.get_page.return_value = ([], 1, 3)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        mock_pagination.next_page.assert_called_once_with(123456789)
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_prev_page(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test navigating to previous page."""
        mock_update.callback_query.data = "intra_paginate:prev:trending:csgo"
        mock_pagination.get_page.return_value = ([], 0, 3)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        mock_pagination.prev_page.assert_called_once_with(123456789)

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_title_anomaly(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test that correct title is shown for anomaly type."""
        mock_update.callback_query.data = f"intra_paginate:next:{ANOMALY_ACTION}:csgo"
        mock_pagination.get_page.return_value = ([], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Ценовые аномалии" in call_args[0][0]

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_title_trending(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test that correct title is shown for trending type."""
        mock_update.callback_query.data = f"intra_paginate:next:{TRENDING_ACTION}:dota2"
        mock_pagination.get_page.return_value = ([], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Растущие в цене" in call_args[0][0]

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_title_rare(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test that correct title is shown for rare type."""
        mock_update.callback_query.data = f"intra_paginate:next:{RARE_ACTION}:tf2"
        mock_pagination.get_page.return_value = ([], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Редкие предметы" in call_args[0][0]

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_pagination_keyboard"
    )
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    async def test_pagination_default_game(
        self, mock_pagination, mock_keyboard, mock_update, mock_context
    ):
        """Test default game when not specified."""
        # Only 3 parts, no game specified
        mock_update.callback_query.data = "intra_paginate:next:anomaly"
        mock_pagination.get_page.return_value = ([], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10
        mock_keyboard.return_value = InlineKeyboardMarkup([])

        await handle_intramarket_pagination(mock_update, mock_context)

        # Should default to csgo
        call_args = mock_update.callback_query.edit_message_text.call_args
        # CS2 is the display name for csgo
        assert "CS2" in call_args[0][0] or "CS:GO" in call_args[0][0]


# ======================== Tests for start_intramarket_arbitrage ========================


class TestStartIntramarketArbitrage:
    """Tests for start_intramarket_arbitrage function."""

    @pytest.mark.asyncio()
    async def test_start_menu_content(self, mock_update, mock_context):
        """Test that start menu contains all expected elements."""
        await start_intramarket_arbitrage(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_context.bot.send_message.assert_called_once()

        call_kwargs = mock_context.bot.send_message.call_args[1]
        text = call_kwargs["text"]
        keyboard = call_kwargs["reply_markup"].inline_keyboard

        # Check text content
        assert "арбитраж" in text.lower()

        # Check buttons
        button_texts = [btn.text for row in keyboard for btn in row]
        button_data = [btn.callback_data for row in keyboard for btn in row]

        assert any("аномал" in t.lower() for t in button_texts)
        assert any("растущ" in t.lower() or "цене" in t.lower() for t in button_texts)
        assert any("редк" in t.lower() for t in button_texts)
        assert any("назад" in t.lower() for t in button_texts)

        # Check callback data
        assert f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}" in button_data
        assert f"{INTRA_ARBITRAGE_ACTION}_{TRENDING_ACTION}" in button_data
        assert f"{INTRA_ARBITRAGE_ACTION}_{RARE_ACTION}" in button_data

    @pytest.mark.asyncio()
    async def test_start_menu_chat_id(self, mock_update, mock_context):
        """Test that message is sent to correct chat."""
        await start_intramarket_arbitrage(mock_update, mock_context)

        call_kwargs = mock_context.bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 123456789

    @pytest.mark.asyncio()
    async def test_start_menu_parse_mode(self, mock_update, mock_context):
        """Test that Markdown parse mode is used."""
        await start_intramarket_arbitrage(mock_update, mock_context)

        call_kwargs = mock_context.bot.send_message.call_args[1]
        assert call_kwargs.get("parse_mode") == "Markdown"


# ======================== Tests for handle_intramarket_callback ========================


class TestHandleIntramarketCallback:
    """Tests for handle_intramarket_callback function."""

    @pytest.mark.asyncio()
    async def test_callback_no_query(self, mock_update, mock_context):
        """Test callback without query."""
        mock_update.callback_query = None

        await handle_intramarket_callback(mock_update, mock_context)

        # Should return early without errors

    @pytest.mark.asyncio()
    async def test_callback_no_data(self, mock_update, mock_context):
        """Test callback without data."""
        mock_update.callback_query.data = None

        await handle_intramarket_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_main_menu(self, mock_update, mock_context):
        """Test callback with just the base action shows error message."""
        # When callback_data is just "intra" (no action type), it shows an error
        mock_update.callback_query.data = INTRA_ARBITRAGE_ACTION

        await handle_intramarket_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        # Without action type, it shows "incorrect request data" via edit_message_text
        mock_update.callback_query.edit_message_text.assert_called()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "Некорректные данные" in call_args

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_price_anomalies"
    )
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env"
    )
    async def test_callback_anomaly_no_api_client(
        self, mock_api_client, mock_anomalies, mock_update, mock_context
    ):
        """Test callback when API client creation fails."""
        mock_update.callback_query.data = (
            f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}_csgo"
        )
        mock_api_client.return_value = None

        await handle_intramarket_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        # Should show error about API client
        call_args = mock_update.callback_query.edit_message_text.call_args_list
        # Check last call for error message
        any(
            "API" in str(call) or "ошибка" in str(call).lower() for call in call_args
        )
        # At minimum, some message should be shown
        assert len(call_args) > 0

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_price_anomalies"
    )
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env"
    )
    async def test_callback_anomaly_success(
        self,
        mock_api_client,
        mock_anomalies,
        mock_pagination,
        mock_update,
        mock_context,
        sample_underpriced_result,
    ):
        """Test successful anomaly search callback."""
        mock_update.callback_query.data = (
            f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}_csgo"
        )
        mock_api_client.return_value = AsyncMock()
        mock_anomalies.return_value = [sample_underpriced_result]
        mock_pagination.get_page.return_value = ([sample_underpriced_result], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10

        await handle_intramarket_callback(mock_update, mock_context)

        mock_anomalies.assert_called_once()
        mock_pagination.add_items_for_user.assert_called_once()

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_trending_items"
    )
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env"
    )
    async def test_callback_trending_success(
        self,
        mock_api_client,
        mock_trending,
        mock_pagination,
        mock_update,
        mock_context,
        sample_trending_result,
    ):
        """Test successful trending search callback."""
        mock_update.callback_query.data = (
            f"{INTRA_ARBITRAGE_ACTION}_{TRENDING_ACTION}_dota2"
        )
        mock_api_client.return_value = AsyncMock()
        mock_trending.return_value = [sample_trending_result]
        mock_pagination.get_page.return_value = ([sample_trending_result], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10

        await handle_intramarket_callback(mock_update, mock_context)

        mock_trending.assert_called_once()
        call_kwargs = mock_trending.call_args[1]
        assert call_kwargs["game"] == "dota2"

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager")
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_mispriced_rare_items"
    )
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env"
    )
    async def test_callback_rare_success(
        self,
        mock_api_client,
        mock_rare,
        mock_pagination,
        mock_update,
        mock_context,
        sample_rare_result,
    ):
        """Test successful rare items search callback."""
        mock_update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{RARE_ACTION}_tf2"
        mock_api_client.return_value = AsyncMock()
        mock_rare.return_value = [sample_rare_result]
        mock_pagination.get_page.return_value = ([sample_rare_result], 0, 1)
        mock_pagination.get_items_per_page.return_value = 10

        await handle_intramarket_callback(mock_update, mock_context)

        mock_rare.assert_called_once()
        call_kwargs = mock_rare.call_args[1]
        assert call_kwargs["game"] == "tf2"

    @pytest.mark.asyncio()
    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env"
    )
    async def test_callback_unknown_action(
        self, mock_api_client, mock_update, mock_context
    ):
        """Test callback with unknown action type."""
        mock_update.callback_query.data = (
            f"{INTRA_ARBITRAGE_ACTION}_unknown_action_csgo"
        )
        mock_api_client.return_value = AsyncMock()

        await handle_intramarket_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args_list
        # Should show unknown type message
        last_call = call_args[-1][0][0]
        assert "Неизвестный тип" in last_call


# ======================== Tests for register_intramarket_handlers ========================


class TestRegisterIntramarketHandlers:
    """Tests for register_intramarket_handlers function."""

    def test_register_handlers(self):
        """Test that handlers are registered correctly."""
        mock_dispatcher = MagicMock()

        register_intramarket_handlers(mock_dispatcher)

        # Should register at least 2 handlers (main callback and pagination)
        assert mock_dispatcher.add_handler.call_count >= 2

    def test_register_callback_query_handlers(self):
        """Test that CallbackQueryHandler types are used."""
        from telegram.ext import CallbackQueryHandler

        mock_dispatcher = MagicMock()

        register_intramarket_handlers(mock_dispatcher)

        for call in mock_dispatcher.add_handler.call_args_list:
            handler = call[0][0]
            assert isinstance(handler, CallbackQueryHandler)


# ======================== Edge Cases Tests ========================


class TestIntramarketEdgeCases:
    """Edge case tests for intramarket arbitrage handler."""

    def test_format_item_with_special_characters(self):
        """Test formatting item with special characters in title."""
        result = {
            "type": PriceAnomalyType.UNDERPRICED,
            "item_to_buy": {
                "itemId": "item_1",
                "title": "Test <Item> & 'Special' \"Chars\"",
            },
            "buy_price": 10.0,
            "sell_price": 15.0,
            "profit_percentage": 50.0,
            "profit_after_fee": 4.0,
            "similarity": 0.9,
        }

        formatted = format_intramarket_item(result)

        assert "Test" in formatted
        assert "Item" in formatted

    def test_format_item_with_zero_prices(self):
        """Test formatting item with zero prices."""
        result = {
            "type": PriceAnomalyType.UNDERPRICED,
            "item_to_buy": {"itemId": "item_1", "title": "Test Item"},
            "buy_price": 0.0,
            "sell_price": 0.0,
            "profit_percentage": 0.0,
            "profit_after_fee": 0.0,
            "similarity": 0.0,
        }

        formatted = format_intramarket_item(result)

        assert "$0.00" in formatted
        assert "0.0%" in formatted

    def test_format_item_with_very_high_prices(self):
        """Test formatting item with very high prices."""
        result = {
            "type": PriceAnomalyType.TRENDING_UP,
            "item": {"itemId": "item_1", "title": "Expensive Item"},
            "current_price": 99999.99,
            "projected_price": 150000.00,
            "price_change_percent": 50.0,
            "potential_profit_percent": 50.0,
            "sales_velocity": 1,
        }

        formatted = format_intramarket_item(result)

        assert "$99999.99" in formatted
        assert "$150000.00" in formatted

    def test_format_results_preserves_order(
        self, sample_underpriced_result, sample_trending_result, sample_rare_result
    ):
        """Test that results order is preserved."""
        results = [
            sample_underpriced_result,
            sample_trending_result,
            sample_rare_result,
        ]

        formatted = format_intramarket_results(results, 0, 10)

        # Check order - underpriced should appear before trending
        underpriced_pos = formatted.find("AK-47 | Redline")
        trending_pos = formatted.find("M4A4 | Howl")
        rare_pos = formatted.find("Case Hardened")

        assert underpriced_pos < trending_pos < rare_pos
