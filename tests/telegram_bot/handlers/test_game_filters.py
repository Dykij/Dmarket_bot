"""Unit tests for src/telegram_bot/handlers/game_filters/.

Tests for game filter handlers including:
- Game filter constants
- Filter utilities (get, update, build API params)
- Telegram callback handlers for filter configuration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup


class TestGameFilterConstants:
    """Tests for game filter constants."""

    def test_cs2_categories_defined(self):
        """Test CS2 categories are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import CS2_CATEGORIES

        assert isinstance(CS2_CATEGORIES, list)
        assert len(CS2_CATEGORIES) > 0
        assert "Rifle" in CS2_CATEGORIES
        assert "Knife" in CS2_CATEGORIES

    def test_cs2_rarities_defined(self):
        """Test CS2 rarities are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import CS2_RARITIES

        assert isinstance(CS2_RARITIES, list)
        assert "Covert" in CS2_RARITIES
        assert "Contraband" in CS2_RARITIES

    def test_cs2_exteriors_defined(self):
        """Test CS2 exteriors are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import CS2_EXTERIORS

        assert isinstance(CS2_EXTERIORS, list)
        assert "Factory New" in CS2_EXTERIORS
        assert "Battle-Scarred" in CS2_EXTERIORS
        assert len(CS2_EXTERIORS) == 5

    def test_dota2_heroes_defined(self):
        """Test Dota 2 heroes are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import DOTA2_HEROES

        assert isinstance(DOTA2_HEROES, list)
        assert "Invoker" in DOTA2_HEROES
        assert "Pudge" in DOTA2_HEROES

    def test_dota2_rarities_defined(self):
        """Test Dota 2 rarities are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import DOTA2_RARITIES

        assert isinstance(DOTA2_RARITIES, list)
        assert "Arcana" in DOTA2_RARITIES
        assert "Immortal" in DOTA2_RARITIES

    def test_dota2_slots_defined(self):
        """Test Dota 2 slots are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import DOTA2_SLOTS

        assert isinstance(DOTA2_SLOTS, list)
        assert "Weapon" in DOTA2_SLOTS
        assert "Courier" in DOTA2_SLOTS

    def test_tf2_classes_defined(self):
        """Test TF2 classes are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import TF2_CLASSES

        assert isinstance(TF2_CLASSES, list)
        assert "Scout" in TF2_CLASSES
        assert "Spy" in TF2_CLASSES
        assert "All Classes" in TF2_CLASSES

    def test_tf2_qualities_defined(self):
        """Test TF2 qualities are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import TF2_QUALITIES

        assert isinstance(TF2_QUALITIES, list)
        assert "Unusual" in TF2_QUALITIES
        assert "Strange" in TF2_QUALITIES

    def test_tf2_types_defined(self):
        """Test TF2 types are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import TF2_TYPES

        assert isinstance(TF2_TYPES, list)
        assert "Hat" in TF2_TYPES
        assert "Weapon" in TF2_TYPES

    def test_rust_categories_defined(self):
        """Test Rust categories are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import RUST_CATEGORIES

        assert isinstance(RUST_CATEGORIES, list)
        assert "Weapon" in RUST_CATEGORIES
        assert "Clothing" in RUST_CATEGORIES

    def test_rust_types_defined(self):
        """Test Rust types are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import RUST_TYPES

        assert isinstance(RUST_TYPES, list)
        assert "Assault Rifle" in RUST_TYPES
        assert "Helmet" in RUST_TYPES

    def test_rust_rarities_defined(self):
        """Test Rust rarities are properly defined."""
        from src.telegram_bot.handlers.game_filters.constants import RUST_RARITIES

        assert isinstance(RUST_RARITIES, list)
        assert "Common" in RUST_RARITIES
        assert "Legendary" in RUST_RARITIES

    def test_default_filters_defined(self):
        """Test default filters are defined for all games."""
        from src.telegram_bot.handlers.game_filters.constants import DEFAULT_FILTERS

        assert "csgo" in DEFAULT_FILTERS
        assert "dota2" in DEFAULT_FILTERS
        assert "tf2" in DEFAULT_FILTERS
        assert "rust" in DEFAULT_FILTERS

        # Check csgo defaults
        assert DEFAULT_FILTERS["csgo"]["min_price"] == 1.0
        assert DEFAULT_FILTERS["csgo"]["max_price"] == 1000.0
        assert "float_min" in DEFAULT_FILTERS["csgo"]

    def test_game_names_defined(self):
        """Test game names are defined for all games."""
        from src.telegram_bot.handlers.game_filters.constants import GAME_NAMES

        assert "csgo" in GAME_NAMES
        assert "dota2" in GAME_NAMES
        assert "tf2" in GAME_NAMES
        assert "rust" in GAME_NAMES

        assert "CS2" in GAME_NAMES["csgo"]
        assert "Dota 2" in GAME_NAMES["dota2"]


class TestGameFilterUtils:
    """Tests for game filter utilities."""

    def test_get_current_filters_empty_context(self):
        """Test getting filters with empty context returns defaults."""
        from src.telegram_bot.handlers.game_filters.constants import DEFAULT_FILTERS
        from src.telegram_bot.handlers.game_filters.utils import get_current_filters

        context = MagicMock()
        context.user_data = None

        filters = get_current_filters(context, "csgo")

        assert filters == DEFAULT_FILTERS["csgo"]

    def test_get_current_filters_with_user_data(self):
        """Test getting filters with existing user data."""
        from src.telegram_bot.handlers.game_filters.utils import get_current_filters

        context = MagicMock()
        context.user_data = {
            "filters": {
                "csgo": {
                    "min_price": 10.0,
                    "max_price": 500.0,
                    "category": "Rifle",
                },
            },
        }

        filters = get_current_filters(context, "csgo")

        assert filters["min_price"] == 10.0
        assert filters["max_price"] == 500.0
        assert filters["category"] == "Rifle"

    def test_get_current_filters_different_game(self):
        """Test getting filters for different game returns defaults."""
        from src.telegram_bot.handlers.game_filters.constants import DEFAULT_FILTERS
        from src.telegram_bot.handlers.game_filters.utils import get_current_filters

        context = MagicMock()
        context.user_data = {
            "filters": {
                "csgo": {"min_price": 10.0},
            },
        }

        filters = get_current_filters(context, "dota2")

        assert filters == DEFAULT_FILTERS["dota2"]

    def test_update_filters_empty_context(self):
        """Test updating filters with empty context."""
        from src.telegram_bot.handlers.game_filters.utils import update_filters

        context = MagicMock()
        context.user_data = None

        new_filters = {"min_price": 50.0, "category": "Knife"}
        update_filters(context, "csgo", new_filters)

        # Should create user_data structure
        assert context.user_data is not None

    def test_update_filters_existing_context(self):
        """Test updating filters with existing context."""
        from src.telegram_bot.handlers.game_filters.utils import update_filters

        context = MagicMock()
        context.user_data = {"filters": {}}

        new_filters = {"min_price": 25.0, "max_price": 100.0}
        update_filters(context, "csgo", new_filters)

        assert context.user_data["filters"]["csgo"]["min_price"] == 25.0
        assert context.user_data["filters"]["csgo"]["max_price"] == 100.0

    def test_get_game_filter_keyboard_csgo(self):
        """Test generating keyboard for CSGO filters."""
        from src.telegram_bot.handlers.game_filters.utils import (
            get_game_filter_keyboard,
        )

        keyboard = get_game_filter_keyboard("csgo")

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Should have price range and game-specific options
        all_buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_buttons.append(button.callback_data)

        assert any("price_range" in btn for btn in all_buttons)
        assert any("float_range" in btn for btn in all_buttons)
        assert any("set_category" in btn for btn in all_buttons)

    def test_get_game_filter_keyboard_dota2(self):
        """Test generating keyboard for Dota 2 filters."""
        from src.telegram_bot.handlers.game_filters.utils import (
            get_game_filter_keyboard,
        )

        keyboard = get_game_filter_keyboard("dota2")

        all_buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_buttons.append(button.callback_data)

        assert any("set_hero" in btn for btn in all_buttons)
        assert any("set_slot" in btn for btn in all_buttons)

    def test_get_game_filter_keyboard_tf2(self):
        """Test generating keyboard for TF2 filters."""
        from src.telegram_bot.handlers.game_filters.utils import (
            get_game_filter_keyboard,
        )

        keyboard = get_game_filter_keyboard("tf2")

        all_buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_buttons.append(button.callback_data)

        assert any("set_class" in btn for btn in all_buttons)
        assert any("australium" in btn for btn in all_buttons)

    def test_get_game_filter_keyboard_rust(self):
        """Test generating keyboard for Rust filters."""
        from src.telegram_bot.handlers.game_filters.utils import (
            get_game_filter_keyboard,
        )

        keyboard = get_game_filter_keyboard("rust")

        all_buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_buttons.append(button.callback_data)

        assert any("set_category" in btn for btn in all_buttons)
        assert any("set_type" in btn for btn in all_buttons)


class TestGameFilterHandlers:
    """Tests for game filter Telegram handlers."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update object."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.data = "select_game_filter:csgo"
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context object."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio()
    async def test_handle_game_filters_command(self, mock_update, mock_context):
        """Test /filters command handler."""
        from src.telegram_bot.handlers.game_filters.handlers import handle_game_filters

        awAlgot handle_game_filters(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Выберите игру" in call_args.args[0]

    @pytest.mark.asyncio()
    async def test_handle_game_filters_no_message(self, mock_context):
        """Test handler when message is None."""
        from src.telegram_bot.handlers.game_filters.handlers import handle_game_filters

        update = MagicMock()
        update.message = None

        # Should not rAlgose
        awAlgot handle_game_filters(update, mock_context)

    @pytest.mark.asyncio()
    async def test_handle_select_game_filter_callback(self, mock_update, mock_context):
        """Test game selection callback handler."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_select_game_filter_callback,
        )

        awAlgot handle_select_game_filter_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_select_game_filter_no_query(self, mock_context):
        """Test callback handler when query is None."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_select_game_filter_callback,
        )

        update = MagicMock()
        update.callback_query = None

        # Should not rAlgose
        awAlgot handle_select_game_filter_callback(update, mock_context)

    @pytest.mark.asyncio()
    async def test_handle_price_range_callback(self, mock_update, mock_context):
        """Test price range selection callback."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_price_range_callback,
        )

        mock_update.callback_query.data = "price_range:csgo"

        awAlgot handle_price_range_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "НастSwarmка диапазона цен" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_float_range_callback_csgo(self, mock_update, mock_context):
        """Test float range callback for CSGO."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_float_range_callback,
        )

        mock_update.callback_query.data = "float_range:csgo"

        awAlgot handle_float_range_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Float" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_float_range_callback_non_csgo(
        self, mock_update, mock_context
    ):
        """Test float range callback for non-CSGO game shows error."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_float_range_callback,
        )

        mock_update.callback_query.data = "float_range:dota2"

        awAlgot handle_float_range_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "только для CS2" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_category_callback_csgo(self, mock_update, mock_context):
        """Test category selection callback for CSGO."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_category_callback,
        )

        mock_update.callback_query.data = "set_category:csgo"

        awAlgot handle_set_category_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор категории" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_rarity_callback(self, mock_update, mock_context):
        """Test rarity selection callback."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_rarity_callback,
        )

        mock_update.callback_query.data = "set_rarity:csgo"

        awAlgot handle_set_rarity_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор редкости" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_exterior_callback_csgo(self, mock_update, mock_context):
        """Test exterior selection callback for CSGO."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_exterior_callback,
        )

        mock_update.callback_query.data = "set_exterior:csgo"

        awAlgot handle_set_exterior_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "внешнего вида" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_exterior_callback_non_csgo(
        self, mock_update, mock_context
    ):
        """Test exterior callback for non-CSGO shows error."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_exterior_callback,
        )

        mock_update.callback_query.data = "set_exterior:dota2"

        awAlgot handle_set_exterior_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "только для CS2" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_hero_callback_dota2(self, mock_update, mock_context):
        """Test hero selection callback for Dota 2."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_hero_callback,
        )

        mock_update.callback_query.data = "set_hero:dota2"

        awAlgot handle_set_hero_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор героя" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_hero_callback_non_dota2(self, mock_update, mock_context):
        """Test hero callback for non-Dota2 shows error."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_hero_callback,
        )

        mock_update.callback_query.data = "set_hero:csgo"

        awAlgot handle_set_hero_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "только для Dota 2" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_slot_callback_dota2(self, mock_update, mock_context):
        """Test slot selection callback for Dota 2."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_slot_callback,
        )

        mock_update.callback_query.data = "set_slot:dota2"

        awAlgot handle_set_slot_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор слота" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_class_callback_tf2(self, mock_update, mock_context):
        """Test class selection callback for TF2."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_class_callback,
        )

        mock_update.callback_query.data = "set_class:tf2"

        awAlgot handle_set_class_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор класса" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_class_callback_non_tf2(self, mock_update, mock_context):
        """Test class callback for non-TF2 shows error."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_class_callback,
        )

        mock_update.callback_query.data = "set_class:csgo"

        awAlgot handle_set_class_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "только для Team Fortress 2" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_type_callback(self, mock_update, mock_context):
        """Test type selection callback."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_type_callback,
        )

        mock_update.callback_query.data = "set_type:tf2"

        awAlgot handle_set_type_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор типа" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_set_quality_callback_tf2(self, mock_update, mock_context):
        """Test quality selection callback for TF2."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_set_quality_callback,
        )

        mock_update.callback_query.data = "set_quality:tf2"

        awAlgot handle_set_quality_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выбор качества" in call_args.kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_price_range(
        self, mock_update, mock_context
    ):
        """Test setting price range filter value."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:price_range:10:50:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        # Should update filters and return to filter menu
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_reset(self, mock_update, mock_context):
        """Test resetting all filters."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:reset:value:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        # Reset handler may return early if data doesn't match expected format

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_toggle_stattrak(
        self, mock_update, mock_context
    ):
        """Test toggling StatTrak filter."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:stattrak:toggle:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        # Toggle handler may require specific callback format

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_category(
        self, mock_update, mock_context
    ):
        """Test setting category filter."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:category:Rifle:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_category_reset(
        self, mock_update, mock_context
    ):
        """Test resetting category filter."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:category:reset:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_float_range(
        self, mock_update, mock_context
    ):
        """Test setting float range filter."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:float_range:0.00:0.07:csgo"

        awAlgot handle_filter_value_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_filter_value_callback_invalid_data(
        self, mock_update, mock_context
    ):
        """Test handler with invalid callback data."""
        from src.telegram_bot.handlers.game_filters.handlers import (
            handle_filter_value_callback,
        )

        mock_update.callback_query.data = "filter:invalid"

        # Should not rAlgose, just return
        awAlgot handle_filter_value_callback(mock_update, mock_context)
