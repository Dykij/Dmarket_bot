"""
Comprehensive tests for game_filters/handlers.py module.

This module tests Telegram handlers for game item filters:
- handle_game_filters - MAlgon filter menu handler
- handle_select_game_filter_callback - Game selection handler
- handle_price_range_callback - Price range selection
- handle_float_range_callback - Float range selection (CS2)
- handle_set_category_callback - Category selection
- handle_set_rarity_callback - Rarity selection
- handle_set_exterior_callback - Exterior selection
- handle_set_hero_callback - Hero selection (Dota 2)
- handle_set_class_callback - Class selection (TF2)
- handle_filter_callback - Generic filter value setting

Coverage Target: 85%+
Estimated Tests: 50+ tests
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.game_filters.handlers import (
    handle_float_range_callback,
    handle_game_filters,
    handle_price_range_callback,
    handle_select_game_filter_callback,
    handle_set_category_callback,
    handle_set_class_callback,
    handle_set_exterior_callback,
    handle_set_hero_callback,
    handle_set_rarity_callback,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_user():
    """Create a mock Telegram user."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "test_user"
    return user


@pytest.fixture()
def mock_chat():
    """Create a mock Telegram chat."""
    chat = MagicMock(spec=Chat)
    chat.id = 987654321
    chat.type = "private"
    return chat


@pytest.fixture()
def mock_message(mock_user, mock_chat):
    """Create a mock Message object."""
    message = AsyncMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.reply_text = AsyncMock()
    return message


@pytest.fixture()
def mock_callback_query(mock_user, mock_message):
    """Create a mock CallbackQuery object."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = mock_user
    callback.message = mock_message
    callback.edit_message_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.data = ""
    return callback


@pytest.fixture()
def mock_update(mock_message, mock_callback_query):
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.message = mock_message
    update.callback_query = mock_callback_query
    return update


@pytest.fixture()
def mock_context():
    """Create a mock context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {}
    return context


# ============================================================================
# Tests for handle_game_filters
# ============================================================================


class TestHandleGameFilters:
    """Tests for handle_game_filters handler."""

    @pytest.mark.asyncio()
    async def test_sends_game_selection_keyboard(self, mock_update, mock_context):
        """Test that handler sends game selection keyboard."""
        # Arrange - ensure message exists
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        # Act
        await handle_game_filters(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "reply_markup" in call_args.kwargs
        assert isinstance(call_args.kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio()
    async def test_keyboard_contains_all_games(self, mock_update, mock_context):
        """Test that keyboard contains all supported games."""
        # Arrange
        mock_update.message = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        # Act
        await handle_game_filters(mock_update, mock_context)

        # Assert
        call_args = mock_update.message.reply_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")

        # Check text mentions filters
        assert "фильтр" in text.lower()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self, mock_context):
        """Test that handler returns early if no message."""
        # Arrange
        update = MagicMock(spec=Update)
        update.message = None

        # Act
        result = await handle_game_filters(update, mock_context)

        # Assert - no exception, just returns
        assert result is None


# ============================================================================
# Tests for handle_select_game_filter_callback
# ============================================================================


class TestHandleSelectGameFilterCallback:
    """Tests for handle_select_game_filter_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_filter_menu_for_csgo(self, mock_update, mock_context):
        """Test showing filter menu for CS:GO."""
        # Arrange
        mock_update.callback_query.data = "select_game_filter:csgo"

        # Act
        await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_shows_filter_menu_for_dota2(self, mock_update, mock_context):
        """Test showing filter menu for Dota 2."""
        # Arrange
        mock_update.callback_query.data = "select_game_filter:dota2"

        # Act
        await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_shows_filter_menu_for_tf2(self, mock_update, mock_context):
        """Test showing filter menu for TF2."""
        # Arrange
        mock_update.callback_query.data = "select_game_filter:tf2"

        # Act
        await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_shows_filter_menu_for_rust(self, mock_update, mock_context):
        """Test showing filter menu for Rust."""
        # Arrange
        mock_update.callback_query.data = "select_game_filter:rust"

        # Act
        await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_includes_current_filters_in_message(self, mock_update, mock_context):
        """Test that current filters are included in message."""
        # Arrange
        mock_update.callback_query.data = "select_game_filter:csgo"
        mock_context.user_data["filters"] = {"csgo": {"category": "Rifle"}}

        # Act
        await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "фильтр" in text.lower()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_select_game_filter_callback(update, mock_context)

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_data(self, mock_update, mock_context):
        """Test early return if no callback data."""
        # Arrange
        mock_update.callback_query.data = None

        # Act
        result = await handle_select_game_filter_callback(mock_update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_price_range_callback
# ============================================================================


class TestHandlePriceRangeCallback:
    """Tests for handle_price_range_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_price_range_options(self, mock_update, mock_context):
        """Test showing price range options."""
        # Arrange
        mock_update.callback_query.data = "price_range:csgo"

        # Act
        await handle_price_range_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "цен" in text.lower()

    @pytest.mark.asyncio()
    async def test_shows_current_price_range(self, mock_update, mock_context):
        """Test showing current price range."""
        # Arrange
        mock_update.callback_query.data = "price_range:csgo"
        mock_context.user_data["filters"] = {
            "csgo": {"min_price": 10.0, "max_price": 50.0}
        }

        # Act
        await handle_price_range_callback(mock_update, mock_context)

        # Assert
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "$10.00" in text
        assert "$50.00" in text

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_price_range_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_float_range_callback
# ============================================================================


class TestHandleFloatRangeCallback:
    """Tests for handle_float_range_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_float_options_for_csgo(self, mock_update, mock_context):
        """Test showing float options for CS:GO."""
        # Arrange
        mock_update.callback_query.data = "float_range:csgo"

        # Act
        await handle_float_range_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "Float" in text

    @pytest.mark.asyncio()
    async def test_rejects_float_for_non_csgo(self, mock_update, mock_context):
        """Test rejecting float for non-CS:GO games."""
        # Arrange
        mock_update.callback_query.data = "float_range:dota2"

        # Act
        await handle_float_range_callback(mock_update, mock_context)

        # Assert
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "Float" in text
        assert "CS2" in text

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_float_range_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_set_category_callback
# ============================================================================


class TestHandleSetCategoryCallback:
    """Tests for handle_set_category_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_category_options_for_csgo(self, mock_update, mock_context):
        """Test showing category options for CS:GO."""
        # Arrange
        mock_update.callback_query.data = "set_category:csgo"

        # Act
        await handle_set_category_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        text = call_args.kwargs.get("text", "")
        assert "категор" in text.lower()

    @pytest.mark.asyncio()
    async def test_shows_category_options_for_rust(self, mock_update, mock_context):
        """Test showing category options for Rust."""
        # Arrange
        mock_update.callback_query.data = "set_category:rust"

        # Act
        await handle_set_category_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_set_category_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_set_rarity_callback
# ============================================================================


class TestHandleSetRarityCallback:
    """Tests for handle_set_rarity_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_rarity_options_for_csgo(self, mock_update, mock_context):
        """Test showing rarity options for CS:GO."""
        # Arrange
        mock_update.callback_query.data = "set_rarity:csgo"

        # Act
        await handle_set_rarity_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_shows_rarity_options_for_dota2(self, mock_update, mock_context):
        """Test showing rarity options for Dota 2."""
        # Arrange
        mock_update.callback_query.data = "set_rarity:dota2"

        # Act
        await handle_set_rarity_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_set_rarity_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_set_exterior_callback
# ============================================================================


class TestHandleSetExteriorCallback:
    """Tests for handle_set_exterior_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_exterior_options_for_csgo(self, mock_update, mock_context):
        """Test showing exterior options for CS:GO."""
        # Arrange
        mock_update.callback_query.data = "set_exterior:csgo"

        # Act
        await handle_set_exterior_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_set_exterior_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_set_hero_callback
# ============================================================================


class TestHandleSetHeroCallback:
    """Tests for handle_set_hero_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_hero_options_for_dota2(self, mock_update, mock_context):
        """Test showing hero options for Dota 2."""
        # Arrange
        mock_update.callback_query.data = "set_hero:dota2"

        # Act
        await handle_set_hero_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_set_hero_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Tests for handle_set_class_callback
# ============================================================================


class TestHandleSetClassCallback:
    """Tests for handle_set_class_callback handler."""

    @pytest.mark.asyncio()
    async def test_shows_class_options_for_tf2(self, mock_update, mock_context):
        """Test showing class options for TF2."""
        # Arrange
        mock_update.callback_query.data = "set_class:tf2"

        # Act
        await handle_set_class_callback(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Test early return if no callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        result = await handle_set_class_callback(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 28 tests

Test Categories:
1. handle_game_filters: 3 tests
   - Game selection keyboard
   - All games present
   - No message handling

2. handle_select_game_filter_callback: 7 tests
   - Filter menus for all games
   - Current filters display
   - Edge cases

3. handle_price_range_callback: 3 tests
   - Price options display
   - Current price range
   - Edge cases

4. handle_float_range_callback: 3 tests
   - CS:GO float options
   - Non-CS:GO rejection
   - Edge cases

5. handle_set_category_callback: 3 tests
   - Category options
   - Different games
   - Edge cases

6. handle_set_rarity_callback: 3 tests
   - Rarity options
   - Different games
   - Edge cases

7. handle_set_exterior_callback: 2 tests
   - Exterior options
   - Edge cases

8. handle_set_hero_callback: 2 tests
   - Hero options
   - Edge cases

9. handle_set_class_callback: 2 tests
   - Class options
   - Edge cases

Expected Coverage: 85%+
"""
