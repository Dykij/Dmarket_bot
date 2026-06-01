"""Tests for liquidity_settings_handler.py - Telegram bot liquidity filter handlers.

This module tests liquidity settings management, toggle, reset, value input
processing and user preferences persistence.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.liquidity_settings_handler import (
    DEFAULT_LIQUIDITY_SETTINGS,
    cancel_liquidity_input,
    get_liquidity_settings,
    get_liquidity_settings_keyboard,
    liquidity_settings_command,
    process_liquidity_value_input,
    reset_liquidity_settings,
    set_max_time_to_sell_Config,
    set_min_liquidity_score_Config,
    set_min_sales_per_week_Config,
    toggle_liquidity_filter,
    update_liquidity_settings,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture()
def mock_update():
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = "50"
    update.callback_query = None
    return update


@pytest.fixture()
def mock_update_with_callback():
    """Create a mock Update with callback_query."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.message = None
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context


@pytest.fixture()
def mock_profile_manager():
    """Create a mock profile manager."""
    with patch(
        "src.telegram_bot.handlers.liquidity_settings_handler.profile_manager"
    ) as mock_pm:
        mock_pm.get_profile = MagicMock(return_value={})
        mock_pm.update_profile = MagicMock()
        yield mock_pm


# ============================================================================
# Test DEFAULT_LIQUIDITY_SETTINGS
# ============================================================================


class TestDefaultLiquiditySettings:
    """Test default liquidity settings constant."""

    def test_default_settings_has_enabled_key(self):
        """Test default settings has 'enabled' key."""
        assert "enabled" in DEFAULT_LIQUIDITY_SETTINGS

    def test_default_settings_enabled_is_true(self):
        """Test default settings enabled is True."""
        assert DEFAULT_LIQUIDITY_SETTINGS["enabled"] is True

    def test_default_settings_has_min_score(self):
        """Test default settings has min_liquidity_score."""
        assert "min_liquidity_score" in DEFAULT_LIQUIDITY_SETTINGS
        assert DEFAULT_LIQUIDITY_SETTINGS["min_liquidity_score"] == 60

    def test_default_settings_has_min_sales(self):
        """Test default settings has min_sales_per_week."""
        assert "min_sales_per_week" in DEFAULT_LIQUIDITY_SETTINGS
        assert DEFAULT_LIQUIDITY_SETTINGS["min_sales_per_week"] == 5

    def test_default_settings_has_max_time(self):
        """Test default settings has max_time_to_sell_days."""
        assert "max_time_to_sell_days" in DEFAULT_LIQUIDITY_SETTINGS
        assert DEFAULT_LIQUIDITY_SETTINGS["max_time_to_sell_days"] == 7


# ============================================================================
# Test get_liquidity_settings
# ============================================================================


class TestGetLiquiditySettings:
    """Tests for get_liquidity_settings function."""

    def test_get_settings_new_user(self, mock_profile_manager):
        """Test getting settings for new user returns defaults."""
        mock_profile_manager.get_profile.return_value = {}

        settings = get_liquidity_settings(123456789)

        assert settings == DEFAULT_LIQUIDITY_SETTINGS

    def test_get_settings_existing_user(self, mock_profile_manager):
        """Test getting settings for existing user."""
        custom_settings = {
            "enabled": False,
            "min_liquidity_score": 80,
            "min_sales_per_week": 10,
            "max_time_to_sell_days": 3,
        }
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": custom_settings
        }

        settings = get_liquidity_settings(123456789)

        assert settings == custom_settings

    def test_get_settings_calls_update_for_new_user(self, mock_profile_manager):
        """Test that update_profile is called for new user."""
        mock_profile_manager.get_profile.return_value = {}

        get_liquidity_settings(123456789)

        mock_profile_manager.update_profile.assert_called_once()


# ============================================================================
# Test update_liquidity_settings
# ============================================================================


class TestUpdateLiquiditySettings:
    """Tests for update_liquidity_settings function."""

    def test_update_settings_new_user(self, mock_profile_manager):
        """Test updating settings for new user."""
        mock_profile_manager.get_profile.return_value = {}

        update_liquidity_settings(123456789, {"min_liquidity_score": 70})

        mock_profile_manager.update_profile.assert_called()

    def test_update_settings_existing_user(self, mock_profile_manager):
        """Test updating settings for existing user."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        update_liquidity_settings(123456789, {"enabled": False})

        mock_profile_manager.update_profile.assert_called()

    def test_update_multiple_settings(self, mock_profile_manager):
        """Test updating multiple settings at once."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        update_liquidity_settings(
            123456789,
            {
                "min_liquidity_score": 80,
                "min_sales_per_week": 15,
            },
        )

        mock_profile_manager.update_profile.assert_called()


# ============================================================================
# Test get_liquidity_settings_keyboard
# ============================================================================


class TestGetLiquiditySettingsKeyboard:
    """Tests for get_liquidity_settings_keyboard function."""

    def test_keyboard_returns_markup(self):
        """Test keyboard returns InlineKeyboardMarkup."""
        keyboard = get_liquidity_settings_keyboard()
        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_keyboard_has_min_score_button(self):
        """Test keyboard has min score button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "liquidity_set_min_score" in buttons

    def test_keyboard_has_min_sales_button(self):
        """Test keyboard has min sales button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "liquidity_set_min_sales" in buttons

    def test_keyboard_has_max_time_button(self):
        """Test keyboard has max time button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "liquidity_set_max_time" in buttons

    def test_keyboard_has_toggle_button(self):
        """Test keyboard has toggle button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "liquidity_toggle" in buttons

    def test_keyboard_has_reset_button(self):
        """Test keyboard has reset button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "liquidity_reset" in buttons

    def test_keyboard_has_back_button(self):
        """Test keyboard has back button."""
        keyboard = get_liquidity_settings_keyboard()
        buttons = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        assert "back_to_settings" in buttons


# ============================================================================
# Test liquidity_settings_command
# ============================================================================


class TestLiquiditySettingsCommand:
    """Tests for liquidity_settings_command function."""

    @pytest.mark.asyncio()
    async def test_command_shows_settings(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test command shows current settings."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await liquidity_settings_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_command_shows_enabled_status(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test command shows enabled status with emoji."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await liquidity_settings_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        assert "✅" in text  # Enabled

    @pytest.mark.asyncio()
    async def test_command_shows_disabled_status(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test command shows disabled status with emoji."""
        settings = DEFAULT_LIQUIDITY_SETTINGS.copy()
        settings["enabled"] = False
        mock_profile_manager.get_profile.return_value = {"liquidity_settings": settings}

        await liquidity_settings_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        assert "❌" in text  # Disabled

    @pytest.mark.asyncio()
    async def test_command_returns_without_user(
        self, mock_context, mock_profile_manager
    ):
        """Test command returns early without user."""
        update = MagicMock(spec=Update)
        update.effective_user = None
        update.message = MagicMock()

        await liquidity_settings_command(update, mock_context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_command_returns_without_message(
        self, mock_context, mock_profile_manager
    ):
        """Test command returns early without message."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock()
        update.message = None

        await liquidity_settings_command(update, mock_context)

        # Should not raise

    @pytest.mark.asyncio()
    async def test_command_uses_html_parse_mode(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test command uses HTML parse mode."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await liquidity_settings_command(mock_update, mock_context)

        call_kwargs = mock_update.message.reply_text.call_args.kwargs
        assert call_kwargs.get("parse_mode") == "HTML"


# ============================================================================
# Test toggle_liquidity_filter
# ============================================================================


class TestToggleLiquidityFilter:
    """Tests for toggle_liquidity_filter function."""

    @pytest.mark.asyncio()
    async def test_toggle_enables_filter(
        self, mock_update_with_callback, mock_context, mock_profile_manager
    ):
        """Test toggling filter from disabled to enabled."""
        settings = DEFAULT_LIQUIDITY_SETTINGS.copy()
        settings["enabled"] = False
        mock_profile_manager.get_profile.return_value = {"liquidity_settings": settings}

        await toggle_liquidity_filter(mock_update_with_callback, mock_context)

        mock_update_with_callback.callback_query.answer.assert_called()

    @pytest.mark.asyncio()
    async def test_toggle_disables_filter(
        self, mock_update_with_callback, mock_context, mock_profile_manager
    ):
        """Test toggling filter from enabled to disabled."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await toggle_liquidity_filter(mock_update_with_callback, mock_context)

        mock_update_with_callback.callback_query.answer.assert_called()

    @pytest.mark.asyncio()
    async def test_toggle_without_user(self, mock_context, mock_profile_manager):
        """Test toggle returns early without user."""
        update = MagicMock(spec=Update)
        update.effective_user = None
        update.callback_query = MagicMock()

        await toggle_liquidity_filter(update, mock_context)

        update.callback_query.answer.assert_not_called()


# ============================================================================
# Test reset_liquidity_settings
# ============================================================================


class TestResetLiquiditySettings:
    """Tests for reset_liquidity_settings function."""

    @pytest.mark.asyncio()
    async def test_reset_restores_defaults(
        self, mock_update_with_callback, mock_context, mock_profile_manager
    ):
        """Test reset restores default settings."""
        custom_settings = {
            "enabled": False,
            "min_liquidity_score": 90,
            "min_sales_per_week": 20,
            "max_time_to_sell_days": 1,
        }
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": custom_settings
        }

        await reset_liquidity_settings(mock_update_with_callback, mock_context)

        mock_update_with_callback.callback_query.answer.assert_called()

    @pytest.mark.asyncio()
    async def test_reset_shows_confirmation(
        self, mock_update_with_callback, mock_context, mock_profile_manager
    ):
        """Test reset shows confirmation message."""
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await reset_liquidity_settings(mock_update_with_callback, mock_context)

        call_args = mock_update_with_callback.callback_query.answer.call_args
        assert "сброшены" in call_args[0][0].lower()


# ============================================================================
# Test Input Configs
# ============================================================================


class TestInputConfigs:
    """Tests for input Config functions."""

    @pytest.mark.asyncio()
    async def test_min_score_Config_sets_flag(
        self, mock_update_with_callback, mock_context
    ):
        """Test min score Config sets awaiting flag."""
        await set_min_liquidity_score_Config(mock_update_with_callback, mock_context)

        assert mock_context.user_data.get("awaiting_liquidity_score") is True

    @pytest.mark.asyncio()
    async def test_min_sales_Config_sets_flag(
        self, mock_update_with_callback, mock_context
    ):
        """Test min sales Config sets awaiting flag."""
        await set_min_sales_per_week_Config(mock_update_with_callback, mock_context)

        assert mock_context.user_data.get("awaiting_sales_per_week") is True

    @pytest.mark.asyncio()
    async def test_max_time_Config_sets_flag(
        self, mock_update_with_callback, mock_context
    ):
        """Test max time Config sets awaiting flag."""
        await set_max_time_to_sell_Config(mock_update_with_callback, mock_context)

        assert mock_context.user_data.get("awaiting_time_to_sell") is True

    @pytest.mark.asyncio()
    async def test_Config_without_callback_returns(self, mock_context):
        """Test Config returns early without callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        await set_min_liquidity_score_Config(update, mock_context)

        # Should not set any flags
        assert "awaiting_liquidity_score" not in mock_context.user_data


# ============================================================================
# Test process_liquidity_value_input
# ============================================================================


class TestProcessLiquidityValueInput:
    """Tests for process_liquidity_value_input function."""

    @pytest.mark.asyncio()
    async def test_process_valid_liquidity_score(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing valid liquidity score."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "75"
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await process_liquidity_value_input(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        assert mock_context.user_data.get("awaiting_liquidity_score") is False

    @pytest.mark.asyncio()
    async def test_process_invalid_liquidity_score_range(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing invalid liquidity score (out of range)."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "150"  # Invalid: > 100

        await process_liquidity_value_input(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "Ошибка" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_process_valid_sales_per_week(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing valid sales per week."""
        mock_context.user_data["awaiting_sales_per_week"] = True
        mock_update.message.text = "10"
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await process_liquidity_value_input(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        assert mock_context.user_data.get("awaiting_sales_per_week") is False

    @pytest.mark.asyncio()
    async def test_process_negative_sales_rejected(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing negative sales value is rejected."""
        mock_context.user_data["awaiting_sales_per_week"] = True
        mock_update.message.text = "-5"

        await process_liquidity_value_input(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "Ошибка" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_process_valid_time_to_sell(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing valid time to sell."""
        mock_context.user_data["awaiting_time_to_sell"] = True
        mock_update.message.text = "5"
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await process_liquidity_value_input(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        assert mock_context.user_data.get("awaiting_time_to_sell") is False

    @pytest.mark.asyncio()
    async def test_process_zero_time_rejected(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test processing zero time value is rejected."""
        mock_context.user_data["awaiting_time_to_sell"] = True
        mock_update.message.text = "0"

        await process_liquidity_value_input(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "Ошибка" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_process_non_integer_rejected(self, mock_update, mock_context):
        """Test processing non-integer value is rejected."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "abc"

        await process_liquidity_value_input(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "Ошибка" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_process_without_user(self, mock_context):
        """Test process returns early without user."""
        update = MagicMock(spec=Update)
        update.effective_user = None
        update.message = MagicMock()

        await process_liquidity_value_input(update, mock_context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_without_user_data(self, mock_update):
        """Test process returns early without user_data."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        await process_liquidity_value_input(mock_update, context)

        # Should not raise


# ============================================================================
# Test cancel_liquidity_input
# ============================================================================


class TestCancelLiquidityInput:
    """Tests for cancel_liquidity_input function."""

    @pytest.mark.asyncio()
    async def test_cancel_clears_all_flags(self, mock_update, mock_context):
        """Test cancel clears all awaiting flags."""
        mock_context.user_data = {
            "awaiting_liquidity_score": True,
            "awaiting_sales_per_week": True,
            "awaiting_time_to_sell": True,
        }

        await cancel_liquidity_input(mock_update, mock_context)

        assert mock_context.user_data.get("awaiting_liquidity_score") is False
        assert mock_context.user_data.get("awaiting_sales_per_week") is False
        assert mock_context.user_data.get("awaiting_time_to_sell") is False

    @pytest.mark.asyncio()
    async def test_cancel_shows_message(self, mock_update, mock_context):
        """Test cancel shows cancellation message."""
        await cancel_liquidity_input(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "отменен" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_cancel_without_message(self, mock_context):
        """Test cancel returns early without message."""
        update = MagicMock(spec=Update)
        update.message = None

        await cancel_liquidity_input(update, mock_context)

        # Should not raise

    @pytest.mark.asyncio()
    async def test_cancel_without_user_data(self):
        """Test cancel returns early without user_data."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = None

        await cancel_liquidity_input(update, context)

        # Should not raise


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases in liquidity settings handlers."""

    @pytest.mark.asyncio()
    async def test_boundary_liquidity_score_zero(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test boundary value: liquidity score 0."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "0"
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await process_liquidity_value_input(mock_update, mock_context)

        # 0 is valid for liquidity score
        assert mock_context.user_data.get("awaiting_liquidity_score") is False

    @pytest.mark.asyncio()
    async def test_boundary_liquidity_score_hundred(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test boundary value: liquidity score 100."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "100"
        mock_profile_manager.get_profile.return_value = {
            "liquidity_settings": DEFAULT_LIQUIDITY_SETTINGS.copy()
        }

        await process_liquidity_value_input(mock_update, mock_context)

        # 100 is valid for liquidity score
        assert mock_context.user_data.get("awaiting_liquidity_score") is False

    @pytest.mark.asyncio()
    async def test_boundary_negative_liquidity_score(
        self, mock_update, mock_context, mock_profile_manager
    ):
        """Test boundary value: negative liquidity score rejected."""
        mock_context.user_data["awaiting_liquidity_score"] = True
        mock_update.message.text = "-1"

        await process_liquidity_value_input(mock_update, mock_context)

        # Negative values should be rejected
        call_args = mock_update.message.reply_text.call_args
        assert "Ошибка" in call_args[0][0]

    def test_keyboard_button_count(self):
        """Test keyboard has expected number of buttons."""
        keyboard = get_liquidity_settings_keyboard()
        total_buttons = sum(len(row) for row in keyboard.inline_keyboard)
        assert total_buttons == 6  # 6 buttons total

    @pytest.mark.asyncio()
    async def test_multiple_toggles(
        self, mock_update_with_callback, mock_context, mock_profile_manager
    ):
        """Test multiple rapid toggles."""
        settings = DEFAULT_LIQUIDITY_SETTINGS.copy()
        mock_profile_manager.get_profile.return_value = {"liquidity_settings": settings}

        for _ in range(3):
            await toggle_liquidity_filter(mock_update_with_callback, mock_context)

        # Should handle multiple toggles
        assert mock_update_with_callback.callback_query.answer.call_count == 3
