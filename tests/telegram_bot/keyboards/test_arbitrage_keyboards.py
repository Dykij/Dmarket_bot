"""Unit tests for telegram_bot/keyboards/arbitrage.py module.

Tests cover:
- Arbitrage keyboard generation
- Modern arbitrage keyboard
- Auto-arbitrage keyboard
- Create arbitrage keyboard with options
- Back to arbitrage keyboard
- Marketplace comparison keyboard
- Game selection keyboard
- Market analysis keyboard
"""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from src.telegram_bot.keyboards.arbitrage import (
    create_arbitrage_keyboard,
    create_market_analysis_keyboard,
    get_arbitrage_keyboard,
    get_auto_arbitrage_keyboard,
    get_back_to_arbitrage_keyboard,
    get_game_selection_keyboard,
    get_marketplace_comparison_keyboard,
    get_modern_arbitrage_keyboard,
)
from src.telegram_bot.keyboards.utils import CB_BACK, CB_GAME_PREFIX

# ============================================================================
# Tests for get_arbitrage_keyboard
# ============================================================================


class TestGetArbitrageKeyboard:
    """Tests for get_arbitrage_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_arbitrage_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_arbitrage_keyboard()

        # 4 rows: [scan, game], [levels, settings], [auto], [back]
        assert len(result.inline_keyboard) == 4

    def test_has_scan_button(self):
        """Test that scan button exists."""
        result = get_arbitrage_keyboard()

        scan_button = result.inline_keyboard[0][0]
        assert "Сканировать" in scan_button.text
        assert scan_button.callback_data == "arb_scan"

    def test_has_game_button(self):
        """Test that game selection button exists."""
        result = get_arbitrage_keyboard()

        game_button = result.inline_keyboard[0][1]
        assert "игры" in game_button.text.lower()
        assert game_button.callback_data == "arb_game"

    def test_has_levels_button(self):
        """Test that levels button exists."""
        result = get_arbitrage_keyboard()

        levels_button = result.inline_keyboard[1][0]
        assert "Уровни" in levels_button.text
        assert levels_button.callback_data == "arb_levels"

    def test_has_settings_button(self):
        """Test that settings button exists."""
        result = get_arbitrage_keyboard()

        settings_button = result.inline_keyboard[1][1]
        assert "НастSwarmки" in settings_button.text
        assert settings_button.callback_data == "arb_settings"

    def test_has_auto_arbitrage_button(self):
        """Test that auto-arbitrage button exists."""
        result = get_arbitrage_keyboard()

        auto_button = result.inline_keyboard[2][0]
        assert "Авто" in auto_button.text
        assert auto_button.callback_data == "arb_auto"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_arbitrage_keyboard()

        back_button = result.inline_keyboard[3][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK


# ============================================================================
# Tests for get_modern_arbitrage_keyboard
# ============================================================================


class TestGetModernArbitrageKeyboard:
    """Tests for get_modern_arbitrage_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_modern_arbitrage_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_modern_arbitrage_keyboard()

        # 9 rows total (including Waxpeer P2P button and new rows)
        assert len(result.inline_keyboard) == 9

    def test_has_simple_menu_button(self):
        """Test that simple menu button exists."""
        result = get_modern_arbitrage_keyboard()

        simple_button = result.inline_keyboard[0][0]
        assert "Упрощенное меню" in simple_button.text
        assert simple_button.callback_data == "simple_menu"

    def test_has_quick_scan_button(self):
        """Test that quick scan button exists."""
        result = get_modern_arbitrage_keyboard()

        # Row 2 (index 2) has quick and deep scan
        quick_button = result.inline_keyboard[2][0]
        assert "Быстрый" in quick_button.text
        assert quick_button.callback_data == "arb_quick"

    def test_has_deep_scan_button(self):
        """Test that deep scan button exists."""
        result = get_modern_arbitrage_keyboard()

        deep_button = result.inline_keyboard[2][1]
        assert "Глубокий" in deep_button.text
        assert deep_button.callback_data == "arb_deep"

    def test_has_market_analysis_button(self):
        """Test that market analysis button exists."""
        result = get_modern_arbitrage_keyboard()

        # Row 3 (index 3) has analysis and multilevel scan
        analysis_button = result.inline_keyboard[3][0]
        assert "Анализ" in analysis_button.text
        assert analysis_button.callback_data == "arb_market_analysis"

    def test_has_multilevel_scan_button(self):
        """Test that multilevel scan button exists."""
        result = get_modern_arbitrage_keyboard()

        scanner_button = result.inline_keyboard[3][1]
        assert "Многоуровневый" in scanner_button.text
        assert scanner_button.callback_data == "scanner"

    def test_has_enhanced_scanner_button(self):
        """Test that enhanced scanner button exists."""
        result = get_modern_arbitrage_keyboard()

        # Row 5 (index 5) has enhanced scanner and stats
        enhanced_button = result.inline_keyboard[5][0]
        assert "Enhanced" in enhanced_button.text
        assert enhanced_button.callback_data == "enhanced_scanner_menu"

    def test_has_stats_button(self):
        """Test that stats button exists."""
        result = get_modern_arbitrage_keyboard()

        stats_button = result.inline_keyboard[5][1]
        assert "Статистика" in stats_button.text
        assert stats_button.callback_data == "arb_stats"

    def test_has_target_button(self):
        """Test that create target button exists."""
        result = get_modern_arbitrage_keyboard()

        # Row 6 (index 6) has target and compare
        target_button = result.inline_keyboard[6][0]
        assert "таргет" in target_button.text.lower()
        assert target_button.callback_data == "arb_target"

    def test_has_compare_button(self):
        """Test that compare marketplaces button exists."""
        result = get_modern_arbitrage_keyboard()

        compare_button = result.inline_keyboard[6][1]
        assert "Сравнить" in compare_button.text
        assert compare_button.callback_data == "arb_compare"

    def test_has_main_menu_button(self):
        """Test that main menu button exists."""
        result = get_modern_arbitrage_keyboard()

        # MAlgon menu is now at index 8 (last row)
        main_button = result.inline_keyboard[8][0]
        assert "Главное" in main_button.text
        assert main_button.callback_data == "main_menu"


# ============================================================================
# Tests for get_auto_arbitrage_keyboard
# ============================================================================


class TestGetAutoArbitrageKeyboard:
    """Tests for get_auto_arbitrage_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_auto_arbitrage_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_auto_arbitrage_keyboard()

        # 4 rows: [start, stop], [settings, status], [history], [back]
        assert len(result.inline_keyboard) == 4

    def test_has_start_button(self):
        """Test that start button exists."""
        result = get_auto_arbitrage_keyboard()

        start_button = result.inline_keyboard[0][0]
        assert "Запустить" in start_button.text
        assert start_button.callback_data == "auto_arb_start"

    def test_has_stop_button(self):
        """Test that stop button exists."""
        result = get_auto_arbitrage_keyboard()

        stop_button = result.inline_keyboard[0][1]
        assert "Остановить" in stop_button.text
        assert stop_button.callback_data == "auto_arb_stop"

    def test_has_settings_button(self):
        """Test that settings button exists."""
        result = get_auto_arbitrage_keyboard()

        settings_button = result.inline_keyboard[1][0]
        assert "НастSwarmки" in settings_button.text
        assert settings_button.callback_data == "auto_arb_settings"

    def test_has_status_button(self):
        """Test that status button exists."""
        result = get_auto_arbitrage_keyboard()

        status_button = result.inline_keyboard[1][1]
        assert "Статус" in status_button.text
        assert status_button.callback_data == "auto_arb_status"

    def test_has_history_button(self):
        """Test that history button exists."""
        result = get_auto_arbitrage_keyboard()

        history_button = result.inline_keyboard[2][0]
        assert "История" in history_button.text
        assert history_button.callback_data == "auto_arb_history"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_auto_arbitrage_keyboard()

        back_button = result.inline_keyboard[3][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "arbitrage"


# ============================================================================
# Tests for create_arbitrage_keyboard
# ============================================================================


class TestCreateArbitrageKeyboard:
    """Tests for create_arbitrage_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = create_arbitrage_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_default_includes_auto_and_analysis(self):
        """Test that default configuration includes auto and analysis."""
        result = create_arbitrage_keyboard()

        all_callbacks = [btn.callback_data for row in result.inline_keyboard for btn in row]

        assert "arb_auto" in all_callbacks
        assert "arb_analysis" in all_callbacks

    def test_exclude_auto(self):
        """Test excluding auto-arbitrage button."""
        result = create_arbitrage_keyboard(include_auto=False)

        all_callbacks = [btn.callback_data for row in result.inline_keyboard for btn in row]

        assert "arb_auto" not in all_callbacks

    def test_exclude_analysis(self):
        """Test excluding analysis button."""
        result = create_arbitrage_keyboard(include_analysis=False)

        all_callbacks = [btn.callback_data for row in result.inline_keyboard for btn in row]

        assert "arb_analysis" not in all_callbacks

    def test_exclude_both(self):
        """Test excluding both auto and analysis."""
        result = create_arbitrage_keyboard(include_auto=False, include_analysis=False)

        # Should have: [scan, game], [back]
        assert len(result.inline_keyboard) == 2

        all_callbacks = [btn.callback_data for row in result.inline_keyboard for btn in row]

        assert "arb_auto" not in all_callbacks
        assert "arb_analysis" not in all_callbacks

    def test_always_has_scan_button(self):
        """Test that scan button is always present."""
        configs = [
            {},
            {"include_auto": False},
            {"include_analysis": False},
            {"include_auto": False, "include_analysis": False},
        ]

        for config in configs:
            result = create_arbitrage_keyboard(**config)
            all_callbacks = [btn.callback_data for row in result.inline_keyboard for btn in row]
            assert "arb_scan" in all_callbacks

    def test_always_has_back_button(self):
        """Test that back button is always present."""
        configs = [
            {},
            {"include_auto": False},
            {"include_analysis": False},
            {"include_auto": False, "include_analysis": False},
        ]

        for config in configs:
            result = create_arbitrage_keyboard(**config)
            back_button = result.inline_keyboard[-1][0]
            assert back_button.callback_data == CB_BACK


# ============================================================================
# Tests for get_back_to_arbitrage_keyboard
# ============================================================================


class TestGetBackToArbitrageKeyboard:
    """Tests for get_back_to_arbitrage_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_back_to_arbitrage_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_one_row(self):
        """Test that keyboard has exactly one row."""
        result = get_back_to_arbitrage_keyboard()

        assert len(result.inline_keyboard) == 1

    def test_has_one_button(self):
        """Test that row has exactly one button."""
        result = get_back_to_arbitrage_keyboard()

        assert len(result.inline_keyboard[0]) == 1

    def test_button_text(self):
        """Test button text."""
        result = get_back_to_arbitrage_keyboard()

        button = result.inline_keyboard[0][0]
        assert "арбитражу" in button.text.lower()

    def test_button_callback(self):
        """Test button callback data."""
        result = get_back_to_arbitrage_keyboard()

        button = result.inline_keyboard[0][0]
        assert button.callback_data == "arbitrage"


# ============================================================================
# Tests for get_marketplace_comparison_keyboard
# ============================================================================


class TestGetMarketplaceComparisonKeyboard:
    """Tests for get_marketplace_comparison_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_marketplace_comparison_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_marketplace_comparison_keyboard()

        # 3 rows: [steam, buff], [refresh], [back]
        assert len(result.inline_keyboard) == 3

    def test_has_steam_comparison_button(self):
        """Test that Steam comparison button exists."""
        result = get_marketplace_comparison_keyboard()

        steam_button = result.inline_keyboard[0][0]
        assert "Steam" in steam_button.text
        assert steam_button.callback_data == "cmp_steam"

    def test_has_buff_comparison_button(self):
        """Test that Buff comparison button exists."""
        result = get_marketplace_comparison_keyboard()

        buff_button = result.inline_keyboard[0][1]
        assert "Buff" in buff_button.text
        assert buff_button.callback_data == "cmp_buff"

    def test_has_refresh_button(self):
        """Test that refresh button exists."""
        result = get_marketplace_comparison_keyboard()

        refresh_button = result.inline_keyboard[1][0]
        assert "Обновить" in refresh_button.text
        assert refresh_button.callback_data == "cmp_refresh"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_marketplace_comparison_keyboard()

        back_button = result.inline_keyboard[2][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "arbitrage"


# ============================================================================
# Tests for get_game_selection_keyboard
# ============================================================================


class TestGetGameSelectionKeyboard:
    """Tests for get_game_selection_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_game_selection_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_game_selection_keyboard()

        back_button = result.inline_keyboard[-1][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "arbitrage"

    def test_game_buttons_use_game_prefix(self):
        """Test that game buttons use correct prefix."""
        result = get_game_selection_keyboard()

        # Get all game buttons (exclude back button)
        game_buttons = [btn for row in result.inline_keyboard[:-1] for btn in row]

        # All should have game prefix
        for button in game_buttons:
            assert button.callback_data.startswith(CB_GAME_PREFIX)

    def test_has_cs2_button(self):
        """Test that CS2/CSGO button exists."""
        result = get_game_selection_keyboard()

        all_buttons = [btn for row in result.inline_keyboard[:-1] for btn in row]
        cs2_buttons = [btn for btn in all_buttons if "CS2" in btn.text or "CS:GO" in btn.text]

        assert len(cs2_buttons) == 1
        assert cs2_buttons[0].callback_data == f"{CB_GAME_PREFIX}csgo"

    def test_has_dota2_button(self):
        """Test that Dota 2 button exists."""
        result = get_game_selection_keyboard()

        all_buttons = [btn for row in result.inline_keyboard[:-1] for btn in row]
        dota_buttons = [btn for btn in all_buttons if "Dota" in btn.text]

        assert len(dota_buttons) == 1
        assert dota_buttons[0].callback_data == f"{CB_GAME_PREFIX}dota2"

    def test_buttons_are_pAlgored(self):
        """Test that game buttons are organized in pAlgors."""
        result = get_game_selection_keyboard()

        # Check all rows except last (back button)
        for row in result.inline_keyboard[:-1]:
            assert len(row) <= 2


# ============================================================================
# Tests for create_market_analysis_keyboard
# ============================================================================


class TestCreateMarketAnalysisKeyboard:
    """Tests for create_market_analysis_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = create_market_analysis_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = create_market_analysis_keyboard()

        # 4 rows: [trends, vol], [top, drop], [rec], [back]
        assert len(result.inline_keyboard) == 4

    def test_has_trends_button(self):
        """Test that trends button exists."""
        result = create_market_analysis_keyboard()

        trends_button = result.inline_keyboard[0][0]
        assert "Тренды" in trends_button.text
        assert trends_button.callback_data == "analysis_trends"

    def test_has_volatility_button(self):
        """Test that volatility button exists."""
        result = create_market_analysis_keyboard()

        vol_button = result.inline_keyboard[0][1]
        assert "Волатильность" in vol_button.text
        assert vol_button.callback_data == "analysis_vol"

    def test_has_top_sales_button(self):
        """Test that top sales button exists."""
        result = create_market_analysis_keyboard()

        top_button = result.inline_keyboard[1][0]
        assert "Топ" in top_button.text
        assert top_button.callback_data == "analysis_top"

    def test_has_dropping_button(self):
        """Test that dropping prices button exists."""
        result = create_market_analysis_keyboard()

        drop_button = result.inline_keyboard[1][1]
        assert "Падающие" in drop_button.text
        assert drop_button.callback_data == "analysis_drop"

    def test_has_recommendations_button(self):
        """Test that recommendations button exists."""
        result = create_market_analysis_keyboard()

        rec_button = result.inline_keyboard[2][0]
        assert "Рекомендации" in rec_button.text
        assert rec_button.callback_data == "analysis_rec"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = create_market_analysis_keyboard()

        back_button = result.inline_keyboard[3][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "arbitrage"
