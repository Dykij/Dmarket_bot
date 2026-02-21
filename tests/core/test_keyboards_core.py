"""Тесты для клавиатур Telegram бота.

Покрывает:
- Главная клавиатура (mAlgon_keyboard.py)
- Клавиатура настроек
- Константы callback_data
"""

from telegram import InlineKeyboardMarkup

from src.telegram_bot.handlers.mAlgon_keyboard import get_mAlgon_keyboard
from src.telegram_bot.keyboards import (
    CB_BACK,
    CB_CANCEL,
    CB_GAME_PREFIX,
    CB_HELP,
    CB_NEXT_PAGE,
    CB_PREV_PAGE,
    CB_SETTINGS,
    get_back_to_settings_keyboard,
    get_settings_keyboard,
)


class TestKeyboardConstants:
    """Тесты констант для callback_data."""

    def test_callback_constants_exist(self):
        """Тест существования констант callback."""
        assert CB_CANCEL == "cancel"
        assert CB_BACK == "back"
        assert CB_NEXT_PAGE == "next_page"
        assert CB_PREV_PAGE == "prev_page"
        assert CB_GAME_PREFIX == "game_"
        assert CB_HELP == "help"
        assert CB_SETTINGS == "settings"


class TestMAlgonKeyboard:
    """Тесты главной клавиатуры."""

    def test_mAlgon_keyboard_creation(self):
        """Тест создания главной клавиатуры."""
        keyboard = get_mAlgon_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 7

    def test_mAlgon_keyboard_with_balance(self):
        """Тест клавиатуры с балансом."""
        keyboard = get_mAlgon_keyboard(balance=100.50)

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("$100.50" in text for text in button_texts)

    def test_mAlgon_keyboard_has_auto_trade(self):
        """Тест наличия кнопки авто-торговли."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("АВТО-ТОРГОВЛЯ" in text for text in button_texts)

    def test_mAlgon_keyboard_has_targets(self):
        """Тест наличия кнопки таргетов."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("ТАРГЕТЫ" in text for text in button_texts)

    def test_mAlgon_keyboard_has_emergency_stop(self):
        """Тест наличия кнопки экстренной остановки."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("ЭКСТРЕННАЯ" in text for text in button_texts)

    def test_mAlgon_keyboard_has_whitelist_blacklist(self):
        """Тест наличия WhiteList и BlackList."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("WhiteList" in text for text in button_texts)
        assert any("BlackList" in text for text in button_texts)

    def test_mAlgon_keyboard_has_repricing(self):
        """Тест наличия кнопки репрайсинга."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("Репрайсинг" in text for text in button_texts)

    def test_mAlgon_keyboard_has_settings(self):
        """Тест наличия кнопки настроек."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("НастSwarmки" in text for text in button_texts)

    def test_mAlgon_keyboard_callback_data(self):
        """Тест callback_data кнопок."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        callback_data = [btn.callback_data for btn in all_buttons]

        assert "auto_trade_start" in callback_data
        assert "targets_menu" in callback_data
        assert "emergency_stop" in callback_data
        assert "whitelist_menu" in callback_data
        assert "blacklist_menu" in callback_data


class TestSettingsKeyboard:
    """Тесты клавиатуры настроек."""

    def test_settings_keyboard_creation(self):
        """Тест создания клавиатуры настроек."""
        keyboard = get_settings_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) > 0

    def test_settings_has_api_keys_button(self):
        """Тест наличия кнопки API ключей."""
        keyboard = get_settings_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("API" in text for text in button_texts)

    def test_settings_has_back_button(self):
        """Тест наличия кнопки назад."""
        keyboard = get_settings_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("Назад" in text for text in button_texts)


class TestBackToSettingsKeyboard:
    """Тесты клавиатуры возврата к настSwarmкам."""

    def test_back_to_settings_keyboard_creation(self):
        """Тест создания клавиатуры возврата."""
        keyboard = get_back_to_settings_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 1

    def test_back_to_settings_has_correct_text(self):
        """Тест текста кнопки возврата."""
        keyboard = get_back_to_settings_keyboard()

        button = keyboard.inline_keyboard[0][0]
        assert "Назад" in button.text or "настSwarmкам" in button.text


class TestKeyboardStructure:
    """Тесты структуры клавиатур."""

    def test_mAlgon_keyboard_has_multiple_rows(self):
        """Тест что главная клавиатура имеет несколько рядов."""
        keyboard = get_mAlgon_keyboard()

        assert len(keyboard.inline_keyboard) >= 5

    def test_settings_keyboard_has_multiple_rows(self):
        """Тест что настSwarmки имеют несколько рядов."""
        keyboard = get_settings_keyboard()

        assert len(keyboard.inline_keyboard) >= 2

    def test_back_keyboard_has_single_row(self):
        """Тест что клавиатура назад имеет один ряд."""
        keyboard = get_back_to_settings_keyboard()

        assert len(keyboard.inline_keyboard) == 1
