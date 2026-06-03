"""Unit tests for telegram_bot/keyboards/settings.py module.

Tests cover:
- Settings keyboard generation
- Back to settings keyboard
- Create settings keyboard
- Language selection keyboard
- Risk profile keyboard
- Confirm keyboard with custom options
- Game selection keyboard for settings
"""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from src.telegram_bot.keyboards.settings import (
    create_confirm_keyboard,
    create_game_selection_keyboard,
    create_settings_keyboard,
    get_back_to_settings_keyboard,
    get_language_keyboard,
    get_risk_profile_keyboard,
    get_settings_keyboard,
)
from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL, CB_GAME_PREFIX


class TestGetSettingsKeyboard:
    """Tests for get_settings_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = get_settings_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        result = get_settings_keyboard()
        assert len(result.inline_keyboard) == 4

    def test_has_language_button(self):
        result = get_settings_keyboard()
        lang_button = result.inline_keyboard[0][0]
        assert "Язык" in lang_button.text
        assert lang_button.callback_data == "settings_language"

    def test_has_back_button(self):
        result = get_settings_keyboard()
        back_button = result.inline_keyboard[3][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK


class TestGetLanguageKeyboard:
    """Tests for get_language_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = get_language_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_russian_language(self):
        result = get_language_keyboard()
        ru_button = result.inline_keyboard[0][0]
        assert "Русский" in ru_button.text
        assert ru_button.callback_data == "lang_ru"

    def test_current_language_is_marked(self):
        result = get_language_keyboard(current_language="en")
        en_button = result.inline_keyboard[1][0]
        assert "✓" in en_button.text


class TestGetRiskProfileKeyboard:
    """Tests for get_risk_profile_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = get_risk_profile_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_low_risk_profile(self):
        result = get_risk_profile_keyboard()
        low_button = result.inline_keyboard[0][0]
        assert "Низкий" in low_button.text

    def test_current_profile_is_marked(self):
        result = get_risk_profile_keyboard(current_risk="high")
        high_button = result.inline_keyboard[2][0]
        assert "✓" in high_button.text


class TestCreateConfirmKeyboard:
    """Tests for create_confirm_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = create_confirm_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_custom_parameters(self):
        result = create_confirm_keyboard(
            confirm_text="Accept",
            cancel_text="Decline",
            confirm_data="accept_action",
            cancel_data="decline_action",
        )
        confirm_button = result.inline_keyboard[0][0]
        cancel_button = result.inline_keyboard[0][1]
        assert confirm_button.text == "Accept"
        assert cancel_button.text == "Decline"
        assert confirm_button.callback_data == "accept_action"
        assert cancel_button.callback_data == "decline_action"


class TestCreateGameSelectionKeyboard:
    """Tests for create_game_selection_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = create_game_selection_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_cs2_button(self):
        result = create_game_selection_keyboard()
        all_buttons = [btn for row in result.inline_keyboard[:-1] for btn in row]
        cs2_buttons = [btn for btn in all_buttons if "CS" in btn.text]
        assert len(cs2_buttons) >= 1
        assert any(btn.callback_data == f"{CB_GAME_PREFIX}csgo" for btn in cs2_buttons)


class TestCreateSettingsKeyboard:
    """Tests for create_settings_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = create_settings_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_settings_buttons(self):
        result = create_settings_keyboard()
        assert len(result.inline_keyboard) > 0


class TestGetBackToSettingsKeyboard:
    """Tests for get_back_to_settings_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        result = get_back_to_settings_keyboard()
        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_back_button(self):
        result = get_back_to_settings_keyboard()
        assert len(result.inline_keyboard) > 0
        # Back button should be present
        all_buttons = [btn for row in result.inline_keyboard for btn in row]
        assert any("Назад" in btn.text or "назад" in btn.text.lower() for btn in all_buttons)


class TestCancelCallback:
    """Tests for CB_CANCEL constant usage."""

    def test_cancel_callback_is_string(self):
        assert isinstance(CB_CANCEL, str)

    def test_cancel_callback_not_empty(self):
        assert len(CB_CANCEL) > 0
