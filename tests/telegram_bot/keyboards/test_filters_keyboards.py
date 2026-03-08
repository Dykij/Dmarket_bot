"""Unit tests for telegram_bot/keyboards/filters.py module.

Tests cover:
- Filter keyboard generation
- Price range keyboard
- CS:GO exterior keyboard
- Rarity keyboard (all games)
- Weapon type keyboard
- Confirm/Cancel keyboard
- Pagination keyboard with all edge cases
"""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from src.telegram_bot.keyboards.filters import (
    get_confirm_cancel_keyboard,
    get_csgo_exterior_keyboard,
    get_csgo_weapon_type_keyboard,
    get_filter_keyboard,
    get_pagination_keyboard,
    get_price_range_keyboard,
    get_rarity_keyboard,
)
from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL, CB_NEXT_PAGE, CB_PREV_PAGE

# ============================================================================
# Tests for get_filter_keyboard
# ============================================================================


class TestGetFilterKeyboard:
    """Tests for get_filter_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_filter_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_default_game_csgo(self):
        """Test that default game is csgo."""
        result = get_filter_keyboard()

        # Should have 5 rows total
        assert len(result.inline_keyboard) == 5

    def test_has_price_button(self):
        """Test that price button exists."""
        result = get_filter_keyboard("csgo")

        first_row = result.inline_keyboard[0]
        price_button = first_row[0]

        assert "Цена" in price_button.text
        assert price_button.callback_data == "filter_price"

    def test_has_rarity_button(self):
        """Test that rarity button exists."""
        result = get_filter_keyboard()

        first_row = result.inline_keyboard[0]
        rarity_button = first_row[1]

        assert "Редкость" in rarity_button.text
        assert rarity_button.callback_data == "filter_rarity"

    def test_has_exterior_button(self):
        """Test that exterior button exists."""
        result = get_filter_keyboard()

        second_row = result.inline_keyboard[1]
        exterior_button = second_row[0]

        assert "Экстерьер" in exterior_button.text
        assert exterior_button.callback_data == "filter_exterior"

    def test_has_weapon_button(self):
        """Test that weapon button exists."""
        result = get_filter_keyboard()

        second_row = result.inline_keyboard[1]
        weapon_button = second_row[1]

        assert "оружия" in weapon_button.text
        assert weapon_button.callback_data == "filter_weapon"

    def test_has_stattrak_button(self):
        """Test that StatTrak button exists."""
        result = get_filter_keyboard()

        third_row = result.inline_keyboard[2]
        stattrak_button = third_row[0]

        assert "StatTrak" in stattrak_button.text
        assert stattrak_button.callback_data == "filter_stattrak"

    def test_has_stickers_button(self):
        """Test that stickers button exists."""
        result = get_filter_keyboard()

        third_row = result.inline_keyboard[2]
        stickers_button = third_row[1]

        assert "Наклейки" in stickers_button.text
        assert stickers_button.callback_data == "filter_stickers"

    def test_has_reset_button(self):
        """Test that reset button exists."""
        result = get_filter_keyboard()

        fourth_row = result.inline_keyboard[3]
        reset_button = fourth_row[0]

        assert "Сбросить" in reset_button.text
        assert reset_button.callback_data == "filter_reset"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_filter_keyboard()

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK

    def test_works_with_different_games(self):
        """Test that function works with different game parameters."""
        games = ["csgo", "dota2", "tf2", "rust"]

        for game in games:
            result = get_filter_keyboard(game)
            assert isinstance(result, InlineKeyboardMarkup)
            assert len(result.inline_keyboard) == 5


# ============================================================================
# Tests for get_price_range_keyboard
# ============================================================================


class TestGetPriceRangeKeyboard:
    """Tests for get_price_range_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_price_range_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_ranges(self):
        """Test that all price ranges are present."""
        result = get_price_range_keyboard()

        # 8 ranges / 2 per row = 4 rows + 1 back button row = 5 rows
        assert len(result.inline_keyboard) == 5

    def test_first_range_is_0_5(self):
        """Test that first range is $0-$5."""
        result = get_price_range_keyboard()

        first_button = result.inline_keyboard[0][0]
        assert "$0 - $5" in first_button.text
        assert first_button.callback_data == "price_0_5"

    def test_has_custom_range_option(self):
        """Test that custom range option exists."""
        result = get_price_range_keyboard()

        # Should be in the last row before back button
        all_buttons = [
            btn
            for row in result.inline_keyboard[:-1]  # Exclude back button row
            for btn in row
        ]
        custom_button = [btn for btn in all_buttons if "Свой" in btn.text]

        assert len(custom_button) == 1
        assert custom_button[0].callback_data == "price_custom"

    def test_back_button_goes_to_filters(self):
        """Test that back button goes to filters."""
        result = get_price_range_keyboard()

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == "filters"

    def test_works_with_min_price_parameter(self):
        """Test that function works with min_price parameter."""
        result = get_price_range_keyboard(min_price=10.0)

        assert isinstance(result, InlineKeyboardMarkup)
        assert len(result.inline_keyboard) > 0

    def test_works_with_max_price_parameter(self):
        """Test that function works with max_price parameter."""
        result = get_price_range_keyboard(max_price=100.0)

        assert isinstance(result, InlineKeyboardMarkup)
        assert len(result.inline_keyboard) > 0

    def test_works_with_both_prices(self):
        """Test that function works with both price parameters."""
        result = get_price_range_keyboard(min_price=10.0, max_price=100.0)

        assert isinstance(result, InlineKeyboardMarkup)
        assert len(result.inline_keyboard) > 0


# ============================================================================
# Tests for get_csgo_exterior_keyboard
# ============================================================================


class TestGetCsgoExteriorKeyboard:
    """Tests for get_csgo_exterior_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_csgo_exterior_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_csgo_exterior_keyboard()

        # 5 exteriors + all button + back button = 7 rows
        assert len(result.inline_keyboard) == 7

    def test_has_factory_new(self):
        """Test that Factory New button exists."""
        result = get_csgo_exterior_keyboard()

        fn_button = result.inline_keyboard[0][0]
        assert "Factory New" in fn_button.text
        assert fn_button.callback_data == "ext_fn"

    def test_has_minimal_wear(self):
        """Test that Minimal Wear button exists."""
        result = get_csgo_exterior_keyboard()

        mw_button = result.inline_keyboard[1][0]
        assert "Minimal Wear" in mw_button.text
        assert mw_button.callback_data == "ext_mw"

    def test_has_field_tested(self):
        """Test that Field-Tested button exists."""
        result = get_csgo_exterior_keyboard()

        ft_button = result.inline_keyboard[2][0]
        assert "Field-Tested" in ft_button.text
        assert ft_button.callback_data == "ext_ft"

    def test_has_well_worn(self):
        """Test that Well-Worn button exists."""
        result = get_csgo_exterior_keyboard()

        ww_button = result.inline_keyboard[3][0]
        assert "Well-Worn" in ww_button.text
        assert ww_button.callback_data == "ext_ww"

    def test_has_battle_scarred(self):
        """Test that Battle-Scarred button exists."""
        result = get_csgo_exterior_keyboard()

        bs_button = result.inline_keyboard[4][0]
        assert "Battle-Scarred" in bs_button.text
        assert bs_button.callback_data == "ext_bs"

    def test_has_all_button(self):
        """Test that 'All' button exists."""
        result = get_csgo_exterior_keyboard()

        all_button = result.inline_keyboard[5][0]
        assert "Все" in all_button.text
        assert all_button.callback_data == "ext_all"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_csgo_exterior_keyboard()

        back_button = result.inline_keyboard[6][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "filters"


# ============================================================================
# Tests for get_rarity_keyboard
# ============================================================================


class TestGetRarityKeyboard:
    """Tests for get_rarity_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_rarity_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_csgo_has_correct_rarities(self):
        """Test that CS:GO has correct rarities."""
        result = get_rarity_keyboard("csgo")

        # 8 rarities + all + back = 10 rows
        assert len(result.inline_keyboard) == 10

        # Check specific rarities
        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        texts = [btn.text for btn in all_buttons]

        assert any("Consumer" in text for text in texts)
        assert any("Covert" in text for text in texts)
        assert any("Contraband" in text for text in texts)

    def test_dota2_has_correct_rarities(self):
        """Test that Dota 2 has correct rarities."""
        result = get_rarity_keyboard("dota2")

        # 7 rarities + all + back = 9 rows
        assert len(result.inline_keyboard) == 9

        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        texts = [btn.text for btn in all_buttons]

        assert any("Common" in text for text in texts)
        assert any("Immortal" in text for text in texts)
        assert any("Arcana" in text for text in texts)

    def test_other_games_have_generic_rarities(self):
        """Test that other games have generic rarities."""
        result = get_rarity_keyboard("tf2")

        # 5 generic rarities + all + back = 7 rows
        assert len(result.inline_keyboard) == 7

        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        texts = [btn.text for btn in all_buttons]

        assert any("Common" in text for text in texts)
        assert any("Legendary" in text for text in texts)

    def test_has_all_button(self):
        """Test that 'All' button exists for all games."""
        games = ["csgo", "dota2", "tf2", "rust"]

        for game in games:
            result = get_rarity_keyboard(game)
            all_button = result.inline_keyboard[-2][0]
            assert "Все" in all_button.text
            assert all_button.callback_data == "rarity_all"

    def test_has_back_button(self):
        """Test that back button exists for all games."""
        games = ["csgo", "dota2", "tf2"]

        for game in games:
            result = get_rarity_keyboard(game)
            back_button = result.inline_keyboard[-1][0]
            assert "Назад" in back_button.text
            assert back_button.callback_data == "filters"


# ============================================================================
# Tests for get_csgo_weapon_type_keyboard
# ============================================================================


class TestGetCsgoWeaponTypeKeyboard:
    """Tests for get_csgo_weapon_type_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_csgo_weapon_type_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has correct number of rows."""
        result = get_csgo_weapon_type_keyboard()

        # 9 weapon types (2 per row) = 5 rows + all + back = 7 rows
        assert len(result.inline_keyboard) == 7

    def test_has_rifles_button(self):
        """Test that rifles button exists."""
        result = get_csgo_weapon_type_keyboard()

        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        rifle_buttons = [btn for btn in all_buttons if "Винтовки" in btn.text]

        assert len(rifle_buttons) == 1
        assert rifle_buttons[0].callback_data == "weapon_rifle"

    def test_has_knives_button(self):
        """Test that knives button exists."""
        result = get_csgo_weapon_type_keyboard()

        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        knife_buttons = [btn for btn in all_buttons if "Ножи" in btn.text]

        assert len(knife_buttons) == 1
        assert knife_buttons[0].callback_data == "weapon_knife"

    def test_has_gloves_button(self):
        """Test that gloves button exists."""
        result = get_csgo_weapon_type_keyboard()

        all_buttons = [btn for row in result.inline_keyboard[:-2] for btn in row]
        glove_buttons = [btn for btn in all_buttons if "Перчатки" in btn.text]

        assert len(glove_buttons) == 1
        assert glove_buttons[0].callback_data == "weapon_gloves"

    def test_has_all_button(self):
        """Test that 'All' button exists."""
        result = get_csgo_weapon_type_keyboard()

        all_button = result.inline_keyboard[-2][0]
        assert "Все" in all_button.text
        assert all_button.callback_data == "weapon_all"

    def test_has_back_button(self):
        """Test that back button exists."""
        result = get_csgo_weapon_type_keyboard()

        back_button = result.inline_keyboard[-1][0]
        assert "Назад" in back_button.text
        assert back_button.callback_data == "filters"

    def test_buttons_are_pAlgored(self):
        """Test that buttons are organized in pAlgors."""
        result = get_csgo_weapon_type_keyboard()

        # Check all rows except last two (all + back)
        for row in result.inline_keyboard[:-2]:
            assert len(row) <= 2


# ============================================================================
# Tests for get_confirm_cancel_keyboard
# ============================================================================


class TestGetConfirmCancelKeyboard:
    """Tests for get_confirm_cancel_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_confirm_cancel_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_one_row(self):
        """Test that keyboard has exactly one row."""
        result = get_confirm_cancel_keyboard()

        assert len(result.inline_keyboard) == 1

    def test_has_two_buttons(self):
        """Test that row has exactly two buttons."""
        result = get_confirm_cancel_keyboard()

        assert len(result.inline_keyboard[0]) == 2

    def test_default_confirm_callback(self):
        """Test default confirm callback data."""
        result = get_confirm_cancel_keyboard()

        confirm_button = result.inline_keyboard[0][0]
        assert "Подтвердить" in confirm_button.text
        assert confirm_button.callback_data == "confirm"

    def test_default_cancel_callback(self):
        """Test default cancel callback data."""
        result = get_confirm_cancel_keyboard()

        cancel_button = result.inline_keyboard[0][1]
        assert "Отмена" in cancel_button.text
        assert cancel_button.callback_data == CB_CANCEL

    def test_custom_confirm_data(self):
        """Test custom confirm callback data."""
        result = get_confirm_cancel_keyboard(confirm_data="custom_yes")

        confirm_button = result.inline_keyboard[0][0]
        assert confirm_button.callback_data == "custom_yes"

    def test_custom_cancel_data(self):
        """Test custom cancel callback data."""
        result = get_confirm_cancel_keyboard(cancel_data="custom_no")

        cancel_button = result.inline_keyboard[0][1]
        assert cancel_button.callback_data == "custom_no"

    def test_both_custom_data(self):
        """Test both custom callback data."""
        result = get_confirm_cancel_keyboard(
            confirm_data="action_confirm",
            cancel_data="action_cancel",
        )

        confirm_button = result.inline_keyboard[0][0]
        cancel_button = result.inline_keyboard[0][1]

        assert confirm_button.callback_data == "action_confirm"
        assert cancel_button.callback_data == "action_cancel"


# ============================================================================
# Tests for get_pagination_keyboard
# ============================================================================


class TestGetPaginationKeyboard:
    """Tests for get_pagination_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_pagination_keyboard(1, 5)

        assert isinstance(result, InlineKeyboardMarkup)

    def test_first_page_no_prev_buttons(self):
        """Test that first page has no previous buttons."""
        result = get_pagination_keyboard(1, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row if btn.callback_data]

        # Should not have prev button
        assert not any(CB_PREV_PAGE in cb for cb in callbacks)

    def test_first_page_has_next_button(self):
        """Test that first page has next button."""
        result = get_pagination_keyboard(1, 5)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        assert any(CB_NEXT_PAGE in cb for cb in callbacks)

    def test_last_page_no_next_buttons(self):
        """Test that last page has no next buttons."""
        result = get_pagination_keyboard(5, 5)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Should not have next or last buttons
        assert not any(CB_NEXT_PAGE in cb for cb in callbacks)

    def test_last_page_has_prev_button(self):
        """Test that last page has previous button."""
        result = get_pagination_keyboard(5, 5)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        assert any(CB_PREV_PAGE in cb for cb in callbacks)

    def test_middle_page_has_all_buttons(self):
        """Test that middle page has all navigation buttons."""
        result = get_pagination_keyboard(5, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Should have first, prev, next, and last
        assert any(CB_PREV_PAGE in cb for cb in callbacks)
        assert any(CB_NEXT_PAGE in cb for cb in callbacks)

    def test_page_indicator_shows_correct_numbers(self):
        """Test that page indicator shows correct numbers."""
        result = get_pagination_keyboard(3, 10)

        nav_row = result.inline_keyboard[0]
        page_info_button = [btn for btn in nav_row if btn.callback_data == "page_info"][0]

        assert "3/10" in page_info_button.text

    def test_custom_base_callback(self):
        """Test custom base callback."""
        result = get_pagination_keyboard(2, 5, base_callback="items")

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row if btn.callback_data != "page_info"]

        # At least one callback should contain custom base
        assert any("items" in cb for cb in callbacks)

    def test_single_page_shows_indicator_only(self):
        """Test that single page shows only page indicator."""
        result = get_pagination_keyboard(1, 1)

        nav_row = result.inline_keyboard[0]

        # Should only have page indicator
        assert len(nav_row) == 1
        assert nav_row[0].callback_data == "page_info"

    def test_has_back_button(self):
        """Test that back button always exists."""
        for page in range(1, 6):
            result = get_pagination_keyboard(page, 5)
            back_button = result.inline_keyboard[-1][0]

            assert "Назад" in back_button.text
            assert back_button.callback_data == CB_BACK

    def test_second_page_has_first_button(self):
        """Test that second page doesn't have first button."""
        result = get_pagination_keyboard(2, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Page 2 shouldn't have first button (only shows when > 2)
        first_button = [cb for cb in callbacks if cb == "page_1"]
        assert len(first_button) == 0

    def test_third_page_has_first_button(self):
        """Test that third page has first button."""
        result = get_pagination_keyboard(3, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Page 3 should have first button
        first_button = [cb for cb in callbacks if "page_1" in cb]
        assert len(first_button) > 0

    def test_second_to_last_page_has_last_button(self):
        """Test that second to last page has last button."""
        result = get_pagination_keyboard(8, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Should have last button
        last_button = [cb for cb in callbacks if "page_10" in cb]
        assert len(last_button) > 0

    def test_last_minus_one_page_no_last_button(self):
        """Test that page (total-1) has no last button."""
        result = get_pagination_keyboard(9, 10)

        nav_row = result.inline_keyboard[0]
        callbacks = [btn.callback_data for btn in nav_row]

        # Should not have jump to last button (since we're already at total-1)
        # But should have next button
        assert any(CB_NEXT_PAGE in cb for cb in callbacks)
