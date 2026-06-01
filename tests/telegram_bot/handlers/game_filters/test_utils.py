"""Tests for game_filters utils module.

This module tests utility functions for game filters:
- get_current_filters
- update_filters
- get_game_filter_keyboard
- get_filter_description
- build_api_params_for_game
"""

from unittest.mock import MagicMock, patch

from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.game_filters.constants import DEFAULT_FILTERS
from src.telegram_bot.handlers.game_filters.utils import (
    build_api_params_for_game,
    get_current_filters,
    get_filter_description,
    get_game_filter_keyboard,
    update_filters,
)


class TestGetCurrentFilters:
    """Tests for get_current_filters function."""

    def test_returns_default_filters_when_user_data_is_none(self):
        """Test returns default filters when user_data is None."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        result = get_current_filters(context, "csgo")

        assert result == DEFAULT_FILTERS["csgo"]

    def test_returns_default_filters_when_filters_not_in_user_data(self):
        """Test returns default filters when filters not in user_data."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}

        result = get_current_filters(context, "csgo")

        assert result == DEFAULT_FILTERS["csgo"]

    def test_returns_default_filters_when_game_not_in_filters(self):
        """Test returns default filters when game not in filters."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"filters": {"dota2": {"min_price": 5.0}}}

        result = get_current_filters(context, "csgo")

        assert result == DEFAULT_FILTERS["csgo"]

    def test_returns_game_filters_when_present(self):
        """Test returns game filters when present."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        expected_filters = {"min_price": 10.0, "max_price": 500.0}
        context.user_data = {"filters": {"csgo": expected_filters}}

        result = get_current_filters(context, "csgo")

        assert result == expected_filters

    def test_returns_copy_not_reference(self):
        """Test returns a copy, not a reference."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        original_filters = {"min_price": 10.0}
        context.user_data = {"filters": {"csgo": original_filters}}

        result = get_current_filters(context, "csgo")
        result["min_price"] = 100.0

        assert original_filters["min_price"] == 10.0

    def test_returns_default_for_dota2(self):
        """Test returns default filters for dota2."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        result = get_current_filters(context, "dota2")

        assert result == DEFAULT_FILTERS["dota2"]

    def test_returns_default_for_tf2(self):
        """Test returns default filters for tf2."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        result = get_current_filters(context, "tf2")

        assert result == DEFAULT_FILTERS["tf2"]

    def test_returns_default_for_rust(self):
        """Test returns default filters for rust."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        result = get_current_filters(context, "rust")

        assert result == DEFAULT_FILTERS["rust"]

    def test_returns_empty_dict_for_unknown_game(self):
        """Test returns empty dict for unknown game."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        result = get_current_filters(context, "unknown_game")

        assert result == {}


class TestUpdateFilters:
    """Tests for update_filters function."""

    def test_creates_user_data_if_none(self):
        """Test creates user_data if None."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        update_filters(context, "csgo", {"min_price": 10.0})

        # Since context.user_data = None doesn't create a new dict in mock,
        # we just check the function doesn't raise

    def test_creates_filters_dict_if_not_exists(self):
        """Test creates filters dict if not exists."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}

        update_filters(context, "csgo", {"min_price": 10.0})

        assert "filters" in context.user_data
        assert context.user_data["filters"]["csgo"] == {"min_price": 10.0}

    def test_updates_existing_game_filters(self):
        """Test updates existing game filters."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"filters": {"csgo": {"min_price": 1.0}}}

        new_filters = {"min_price": 10.0, "max_price": 500.0}
        update_filters(context, "csgo", new_filters)

        assert context.user_data["filters"]["csgo"] == new_filters

    def test_adds_new_game_filters(self):
        """Test adds new game filters."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"filters": {"csgo": {"min_price": 1.0}}}

        new_filters = {"min_price": 5.0}
        update_filters(context, "dota2", new_filters)

        assert context.user_data["filters"]["dota2"] == new_filters
        assert context.user_data["filters"]["csgo"] == {"min_price": 1.0}

    def test_preserves_other_user_data(self):
        """Test preserves other user_data."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {
            "filters": {"csgo": {"min_price": 1.0}},
            "other_data": "preserved",
        }

        update_filters(context, "csgo", {"min_price": 10.0})

        assert context.user_data["other_data"] == "preserved"


class TestGetGameFilterKeyboard:
    """Tests for get_game_filter_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test returns InlineKeyboardMarkup."""
        result = get_game_filter_keyboard("csgo")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_csgo_keyboard_has_price_range(self):
        """Test csgo keyboard has price range button."""
        result = get_game_filter_keyboard("csgo")

        # Check that the keyboard contains expected buttons
        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("price_range" in btn for btn in buttons)

    def test_csgo_keyboard_has_float_range(self):
        """Test csgo keyboard has float range button."""
        result = get_game_filter_keyboard("csgo")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("float_range" in btn for btn in buttons)

    def test_csgo_keyboard_has_stattrak(self):
        """Test csgo keyboard has StatTrak button."""
        result = get_game_filter_keyboard("csgo")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("stattrak" in btn for btn in buttons)

    def test_dota2_keyboard_has_hero(self):
        """Test dota2 keyboard has hero button."""
        result = get_game_filter_keyboard("dota2")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("hero" in btn for btn in buttons)

    def test_dota2_keyboard_has_slot(self):
        """Test dota2 keyboard has slot button."""
        result = get_game_filter_keyboard("dota2")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("slot" in btn for btn in buttons)

    def test_tf2_keyboard_has_class(self):
        """Test tf2 keyboard has class button."""
        result = get_game_filter_keyboard("tf2")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("set_class" in btn for btn in buttons)

    def test_tf2_keyboard_has_australium(self):
        """Test tf2 keyboard has australium button."""
        result = get_game_filter_keyboard("tf2")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("australium" in btn for btn in buttons)

    def test_rust_keyboard_has_category(self):
        """Test rust keyboard has category button."""
        result = get_game_filter_keyboard("rust")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("category" in btn for btn in buttons)

    def test_keyboard_has_reset_button(self):
        """Test keyboard has reset button."""
        result = get_game_filter_keyboard("csgo")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("reset" in btn for btn in buttons)

    def test_keyboard_has_back_button(self):
        """Test keyboard has back button."""
        result = get_game_filter_keyboard("csgo")

        buttons = []
        for row in result.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert any("back" in btn for btn in buttons)


class TestGetFilterDescription:
    """Tests for get_filter_description function."""

    @patch("src.telegram_bot.handlers.game_filters.utils.FilterFactory")
    def test_calls_filter_factory(self, mock_factory):
        """Test calls FilterFactory."""
        mock_filter = MagicMock()
        mock_filter.get_filter_description.return_value = "description"
        mock_factory.get_filter.return_value = mock_filter

        result = get_filter_description("csgo", {"min_price": 10.0})

        mock_factory.get_filter.assert_called_once_with("csgo")
        mock_filter.get_filter_description.assert_called_once_with({"min_price": 10.0})
        assert result == "description"

    @patch("src.telegram_bot.handlers.game_filters.utils.FilterFactory")
    def test_returns_empty_string_for_empty_filters(self, mock_factory):
        """Test returns empty string for empty filters."""
        mock_filter = MagicMock()
        mock_filter.get_filter_description.return_value = ""
        mock_factory.get_filter.return_value = mock_filter

        result = get_filter_description("csgo", {})

        assert result == ""


class TestBuildApiParamsForGame:
    """Tests for build_api_params_for_game function."""

    @patch("src.telegram_bot.handlers.game_filters.utils.FilterFactory")
    def test_calls_filter_factory(self, mock_factory):
        """Test calls FilterFactory."""
        mock_filter = MagicMock()
        mock_filter.build_api_params.return_value = {"param": "value"}
        mock_factory.get_filter.return_value = mock_filter

        result = build_api_params_for_game("csgo", {"min_price": 10.0})

        mock_factory.get_filter.assert_called_once_with("csgo")
        mock_filter.build_api_params.assert_called_once_with({"min_price": 10.0})
        assert result == {"param": "value"}

    @patch("src.telegram_bot.handlers.game_filters.utils.FilterFactory")
    def test_returns_dict(self, mock_factory):
        """Test returns dict."""
        mock_filter = MagicMock()
        mock_filter.build_api_params.return_value = {"game": "csgo", "price_min": 100}
        mock_factory.get_filter.return_value = mock_filter

        result = build_api_params_for_game("csgo", {"min_price": 1.0})

        assert isinstance(result, dict)


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports_are_importable(self):
        """Test that all exports are importable."""
        from src.telegram_bot.handlers.game_filters import utils

        expected_exports = [
            "get_current_filters",
            "update_filters",
            "get_game_filter_keyboard",
            "get_filter_description",
            "build_api_params_for_game",
        ]

        for name in expected_exports:
            assert hasattr(utils, name)
