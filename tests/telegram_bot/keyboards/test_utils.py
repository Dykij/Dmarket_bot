"""Тесты для модуля keyboards/utils.

Проверяет вспомогательные функции для работы с клавиатурами.
"""

from telegram import ForceReply, InlineKeyboardButton, ReplyKeyboardRemove

from src.telegram_bot.keyboards.utils import (
    CB_BACK,
    CB_CANCEL,
    CB_GAME_PREFIX,
    CB_HELP,
    CB_NEXT_PAGE,
    CB_PREV_PAGE,
    CB_SETTINGS,
    GAMES,
    build_menu,
    extract_callback_data,
    force_reply,
    remove_keyboard,
)


class TestConstants:
    """Тесты констант callback_data."""

    def test_cb_cancel_constant(self):
        """Тест константы CB_CANCEL."""
        assert CB_CANCEL == "cancel"

    def test_cb_back_constant(self):
        """Тест константы CB_BACK."""
        assert CB_BACK == "back"

    def test_cb_next_page_constant(self):
        """Тест константы CB_NEXT_PAGE."""
        assert CB_NEXT_PAGE == "next_page"

    def test_cb_prev_page_constant(self):
        """Тест константы CB_PREV_PAGE."""
        assert CB_PREV_PAGE == "prev_page"

    def test_cb_game_prefix_constant(self):
        """Тест константы CB_GAME_PREFIX."""
        assert CB_GAME_PREFIX == "game_"

    def test_cb_help_constant(self):
        """Тест константы CB_HELP."""
        assert CB_HELP == "help"

    def test_cb_settings_constant(self):
        """Тест константы CB_SETTINGS."""
        assert CB_SETTINGS == "settings"

    def test_games_constant_exists(self):
        """Тест наличия константы GAMES."""
        assert GAMES is not None
        assert isinstance(GAMES, dict)

    def test_games_has_csgo(self):
        """Тест что GAMES содержит CS:GO."""
        assert "csgo" in GAMES

    def test_games_has_dota2(self):
        """Тест что GAMES содержит Dota 2."""
        assert "dota2" in GAMES


class TestForceReply:
    """Тесты функции force_reply."""

    def test_force_reply_returns_force_reply_object(self):
        """Тест что функция возвращает ForceReply объект."""
        result = force_reply()
        assert isinstance(result, ForceReply)

    def test_force_reply_is_selective(self):
        """Тест что ForceReply имеет selective=True."""
        result = force_reply()
        assert result.selective is True

    def test_force_reply_multiple_calls(self):
        """Тест что каждый вызов возвращает новый объект."""
        result1 = force_reply()
        result2 = force_reply()
        assert result1 is not result2


class TestRemoveKeyboard:
    """Тесты функции remove_keyboard."""

    def test_remove_keyboard_returns_remove_keyboard_object(self):
        """Тест что функция возвращает ReplyKeyboardRemove объект."""
        result = remove_keyboard()
        assert isinstance(result, ReplyKeyboardRemove)

    def test_remove_keyboard_multiple_calls(self):
        """Тест что каждый вызов возвращает новый объект."""
        result1 = remove_keyboard()
        result2 = remove_keyboard()
        assert result1 is not result2


class TestExtractCallbackData:
    """Тесты функции extract_callback_data."""

    def test_extract_with_matching_prefix(self):
        """Тест извлечения данных с совпадающим префиксом."""
        result = extract_callback_data("game_csgo", "game_")
        assert result == "csgo"

    def test_extract_with_no_prefix_match(self):
        """Тест когда префикс не совпадает."""
        result = extract_callback_data("csgo", "game_")
        assert result == "csgo"

    def test_extract_empty_string(self):
        """Тест извлечения из пустой строки."""
        result = extract_callback_data("", "game_")
        assert result == ""

    def test_extract_only_prefix(self):
        """Тест когда callback_data содержит только префикс."""
        result = extract_callback_data("game_", "game_")
        assert result == ""

    def test_extract_with_complex_data(self):
        """Тест извлечения сложных данных."""
        result = extract_callback_data("action_buy_item_123", "action_")
        assert result == "buy_item_123"

    def test_extract_with_multiple_underscores(self):
        """Тест с несколькими подчеркиваниями."""
        result = extract_callback_data("prefix_data_with_underscores", "prefix_")
        assert result == "data_with_underscores"

    def test_extract_case_sensitive(self):
        """Тест что извлечение чувствительно к регистру."""
        result = extract_callback_data("Game_csgo", "game_")
        assert result == "Game_csgo"  # Префикс не совпал


class TestBuildMenu:
    """Тесты функции build_menu."""

    def test_build_menu_with_two_columns(self):
        """Тест построения меню с двумя колонками."""
        buttons = [
            InlineKeyboardButton("1", callback_data="1"),
            InlineKeyboardButton("2", callback_data="2"),
            InlineKeyboardButton("3", callback_data="3"),
            InlineKeyboardButton("4", callback_data="4"),
        ]
        result = build_menu(buttons, n_cols=2)
        assert len(result) == 2
        assert len(result[0]) == 2
        assert len(result[1]) == 2

    def test_build_menu_with_one_column(self):
        """Тест построения меню с одной колонкой."""
        buttons = [
            InlineKeyboardButton("1", callback_data="1"),
            InlineKeyboardButton("2", callback_data="2"),
        ]
        result = build_menu(buttons, n_cols=1)
        assert len(result) == 2
        assert len(result[0]) == 1
        assert len(result[1]) == 1

    def test_build_menu_with_three_columns(self):
        """Тест построения меню с тремя колонками."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(6)]
        result = build_menu(buttons, n_cols=3)
        assert len(result) == 2
        assert len(result[0]) == 3
        assert len(result[1]) == 3

    def test_build_menu_with_uneven_buttons(self):
        """Тест построения меню с неровным количеством кнопок."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(5)]
        result = build_menu(buttons, n_cols=2)
        assert len(result) == 3
        assert len(result[0]) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 1

    def test_build_menu_with_header(self):
        """Тест построения меню с header кнопками."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4)]
        header = [InlineKeyboardButton("Header", callback_data="header")]
        result = build_menu(buttons, n_cols=2, header_buttons=header)
        assert len(result) == 3
        assert len(result[0]) == 1  # Header
        assert result[0][0].text == "Header"

    def test_build_menu_with_footer(self):
        """Тест построения меню с footer кнопками."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4)]
        footer = [InlineKeyboardButton("Footer", callback_data="footer")]
        result = build_menu(buttons, n_cols=2, footer_buttons=footer)
        assert len(result) == 3
        assert len(result[-1]) == 1  # Footer
        assert result[-1][0].text == "Footer"

    def test_build_menu_with_header_and_footer(self):
        """Тест построения меню с header и footer."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4)]
        header = [InlineKeyboardButton("Header", callback_data="header")]
        footer = [InlineKeyboardButton("Footer", callback_data="footer")]
        result = build_menu(
            buttons, n_cols=2, header_buttons=header, footer_buttons=footer
        )
        assert len(result) == 4
        assert result[0][0].text == "Header"
        assert result[-1][0].text == "Footer"

    def test_build_menu_empty_buttons(self):
        """Тест построения меню с пустым списком кнопок."""
        result = build_menu([], n_cols=2)
        assert len(result) == 0

    def test_build_menu_single_button(self):
        """Тест построения меню с одной кнопкой."""
        buttons = [InlineKeyboardButton("Single", callback_data="single")]
        result = build_menu(buttons, n_cols=2)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_build_menu_multiple_header_buttons(self):
        """Тест построения меню с несколькими header кнопками."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4)]
        header = [
            InlineKeyboardButton("H1", callback_data="h1"),
            InlineKeyboardButton("H2", callback_data="h2"),
        ]
        result = build_menu(buttons, n_cols=2, header_buttons=header)
        assert len(result[0]) == 2
        assert result[0][0].text == "H1"
        assert result[0][1].text == "H2"

    def test_build_menu_multiple_footer_buttons(self):
        """Тест построения меню с несколькими footer кнопками."""
        buttons = [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(4)]
        footer = [
            InlineKeyboardButton("F1", callback_data="f1"),
            InlineKeyboardButton("F2", callback_data="f2"),
        ]
        result = build_menu(buttons, n_cols=2, footer_buttons=footer)
        assert len(result[-1]) == 2
        assert result[-1][0].text == "F1"
        assert result[-1][1].text == "F2"


class TestButtonCreation:
    """Тесты создания кнопок через build_menu."""

    def test_buttons_preserve_text(self):
        """Тест что текст кнопок сохраняется."""
        buttons = [
            InlineKeyboardButton("Button 1", callback_data="1"),
            InlineKeyboardButton("Button 2", callback_data="2"),
        ]
        result = build_menu(buttons, n_cols=1)
        assert result[0][0].text == "Button 1"
        assert result[1][0].text == "Button 2"

    def test_buttons_preserve_callback_data(self):
        """Тест что callback_data кнопок сохраняется."""
        buttons = [
            InlineKeyboardButton("Button 1", callback_data="callback_1"),
            InlineKeyboardButton("Button 2", callback_data="callback_2"),
        ]
        result = build_menu(buttons, n_cols=1)
        assert result[0][0].callback_data == "callback_1"
        assert result[1][0].callback_data == "callback_2"

    def test_buttons_order_preserved(self):
        """Тест что порядок кнопок сохраняется."""
        buttons = [
            InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 7)
        ]
        result = build_menu(buttons, n_cols=3)
        # Проверяем порядок в первой строке
        assert result[0][0].text == "1"
        assert result[0][1].text == "2"
        assert result[0][2].text == "3"
        # Проверяем порядок во втоSwarm строке
        assert result[1][0].text == "4"
        assert result[1][1].text == "5"
        assert result[1][2].text == "6"
