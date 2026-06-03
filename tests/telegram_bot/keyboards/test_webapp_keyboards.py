"""Unit tests for telegram_bot/keyboards/webapp.py module.

Tests cover:
- WebApp keyboard generation
- DMarket WebApp keyboard
- Combined WebApp keyboard
- Payment keyboard
- Login keyboard
- Request contact keyboard
- Request location keyboard
- API key input keyboard
"""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL
from src.telegram_bot.keyboards.webapp import (
    get_api_key_input_keyboard,
    get_combined_web_app_keyboard,
    get_dmarket_webapp_keyboard,
    get_login_keyboard,
    get_payment_keyboard,
    get_request_contact_keyboard,
    get_request_location_keyboard,
    get_webapp_button,
    get_webapp_keyboard,
)

# ============================================================================
# Tests for get_webapp_keyboard
# ============================================================================


class TestGetWebappKeyboard:
    """Tests for get_webapp_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_webapp_keyboard("Test WebApp", "https://example.com")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_one_row(self):
        """Test that keyboard has exactly one row."""
        result = get_webapp_keyboard("Test WebApp", "https://example.com")

        assert len(result.inline_keyboard) == 1

    def test_button_has_correct_text(self):
        """Test that button has the correct text."""
        title = "Open Dashboard"
        result = get_webapp_keyboard(title, "https://example.com")

        button = result.inline_keyboard[0][0]
        assert button.text == title

    def test_button_has_webapp_info(self):
        """Test that button has WebAppInfo with correct URL."""
        url = "https://my-webapp.com/dashboard"
        result = get_webapp_keyboard("Dashboard", url)

        button = result.inline_keyboard[0][0]
        assert button.web_app is not None
        assert button.web_app.url == url

    def test_different_urls_work(self):
        """Test that different URLs work correctly."""
        urls = [
            "https://example.com",
            "https://dmarket.com/app",
            "https://localhost:3000",
        ]

        for url in urls:
            result = get_webapp_keyboard("Test", url)
            button = result.inline_keyboard[0][0]
            assert button.web_app.url == url


# ============================================================================
# Tests for get_dmarket_webapp_keyboard
# ============================================================================


class TestGetDmarketWebappKeyboard:
    """Tests for get_dmarket_webapp_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_dmarket_webapp_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_dmarket_webapp_keyboard()

        # 4 rows: [dmarket webapp], [cs2, dota2], [inventory, balance], [back]
        assert len(result.inline_keyboard) == 4

    def test_dmarket_webapp_button_exists(self):
        """Test that DMarket WebApp button exists."""
        result = get_dmarket_webapp_keyboard()

        first_row = result.inline_keyboard[0]
        dmarket_button = first_row[0]

        assert "DMarket" in dmarket_button.text
        assert dmarket_button.web_app is not None
        assert "dmarket.com" in dmarket_button.web_app.url

    def test_cs2_market_link_exists(self):
        """Test that CS2 market link exists."""
        result = get_dmarket_webapp_keyboard()

        second_row = result.inline_keyboard[1]
        cs2_button = second_row[0]

        assert "CS2" in cs2_button.text or "csgo" in cs2_button.url.lower()
        assert cs2_button.url is not None
        assert "dmarket.com" in cs2_button.url

    def test_dota2_market_link_exists(self):
        """Test that Dota 2 market link exists."""
        result = get_dmarket_webapp_keyboard()

        second_row = result.inline_keyboard[1]
        dota2_button = second_row[1]

        assert "Dota" in dota2_button.text
        assert dota2_button.url is not None
        assert "dota2" in dota2_button.url.lower()

    def test_inventory_link_exists(self):
        """Test that inventory link exists."""
        result = get_dmarket_webapp_keyboard()

        third_row = result.inline_keyboard[2]
        inventory_button = third_row[0]

        assert "Инвентарь" in inventory_button.text
        assert "inventory" in inventory_button.url.lower()

    def test_balance_link_exists(self):
        """Test that balance link exists."""
        result = get_dmarket_webapp_keyboard()

        third_row = result.inline_keyboard[2]
        balance_button = third_row[1]

        assert "Баланс" in balance_button.text
        assert "wallet" in balance_button.url.lower()

    def test_back_button_exists(self):
        """Test that back button exists."""
        result = get_dmarket_webapp_keyboard()

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK


# ============================================================================
# Tests for get_webapp_button
# ============================================================================


class TestGetWebappButton:
    """Tests for get_webapp_button function."""

    def test_returns_inline_keyboard_button(self):
        """Test that function returns InlineKeyboardButton."""
        result = get_webapp_button("https://example.com")

        assert isinstance(result, InlineKeyboardButton)

    def test_default_text(self):
        """Test default button text."""
        result = get_webapp_button("https://example.com")

        assert "Открыть" in result.text

    def test_custom_text(self):
        """Test custom button text."""
        result = get_webapp_button("https://example.com", text="Launch App")

        assert result.text == "Launch App"

    def test_webapp_url_correct(self):
        """Test that WebApp URL is correct."""
        url = "https://my-app.com/page"
        result = get_webapp_button(url)

        assert result.web_app is not None
        assert result.web_app.url == url


# ============================================================================
# Tests for get_combined_web_app_keyboard
# ============================================================================


class TestGetCombinedWebAppKeyboard:
    """Tests for get_combined_web_app_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_combined_web_app_keyboard("https://example.com")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_webapp_button_first(self):
        """Test that WebApp button is first."""
        url = "https://example.com"
        result = get_combined_web_app_keyboard(url)

        first_row = result.inline_keyboard[0]
        webapp_button = first_row[0]

        assert webapp_button.web_app is not None
        assert webapp_button.web_app.url == url

    def test_default_webapp_text(self):
        """Test default WebApp button text."""
        result = get_combined_web_app_keyboard("https://example.com")

        first_row = result.inline_keyboard[0]
        webapp_button = first_row[0]

        assert "Открыть WebApp" in webapp_button.text

    def test_custom_webapp_text(self):
        """Test custom WebApp button text."""
        result = get_combined_web_app_keyboard(
            "https://example.com",
            webapp_text="Launch Dashboard",
        )

        first_row = result.inline_keyboard[0]
        webapp_button = first_row[0]

        assert webapp_button.text == "Launch Dashboard"

    def test_back_button_exists(self):
        """Test that back button exists at the end."""
        result = get_combined_web_app_keyboard("https://example.com")

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK

    def test_additional_buttons_included(self):
        """Test that additional buttons are included."""
        additional = [
            [InlineKeyboardButton(text="Option 1", callback_data="opt1")],
            [InlineKeyboardButton(text="Option 2", callback_data="opt2")],
        ]
        result = get_combined_web_app_keyboard(
            "https://example.com",
            additional_buttons=additional,
        )

        # Should have: webapp + 2 additional + back = 4 rows
        assert len(result.inline_keyboard) == 4

        # Check additional buttons are in the middle
        assert result.inline_keyboard[1][0].text == "Option 1"
        assert result.inline_keyboard[2][0].text == "Option 2"

    def test_no_additional_buttons(self):
        """Test keyboard without additional buttons."""
        result = get_combined_web_app_keyboard("https://example.com")

        # Should have: webapp + back = 2 rows
        assert len(result.inline_keyboard) == 2


# ============================================================================
# Tests for get_payment_keyboard
# ============================================================================


class TestGetPaymentKeyboard:
    """Tests for get_payment_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_payment_keyboard("Pay Now", "test_token")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_one_row(self):
        """Test that keyboard has exactly one row."""
        result = get_payment_keyboard("Pay Now", "test_token")

        assert len(result.inline_keyboard) == 1

    def test_pay_button_text(self):
        """Test that pay button has correct text."""
        title = "Pay $10.00"
        result = get_payment_keyboard(title, "test_token")

        button = result.inline_keyboard[0][0]
        assert button.text == title

    def test_pay_button_is_payment_button(self):
        """Test that button has pay=True."""
        result = get_payment_keyboard("Pay", "test_token")

        button = result.inline_keyboard[0][0]
        assert button.pay is True


# ============================================================================
# Tests for get_login_keyboard
# ============================================================================


class TestGetLoginKeyboard:
    """Tests for get_login_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_login_keyboard("Login", "https://example.com/auth")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_one_row(self):
        """Test that keyboard has exactly one row."""
        result = get_login_keyboard("Login", "https://example.com/auth")

        assert len(result.inline_keyboard) == 1

    def test_login_button_text(self):
        """Test that login button has correct text."""
        title = "Sign In with Telegram"
        result = get_login_keyboard(title, "https://example.com/auth")

        button = result.inline_keyboard[0][0]
        assert button.text == title

    def test_login_url_set(self):
        """Test that login_url is set."""
        result = get_login_keyboard("Login", "https://example.com/auth")

        button = result.inline_keyboard[0][0]
        assert button.login_url is not None
        assert button.login_url.url == "https://example.com/auth"

    def test_forward_text_optional(self):
        """Test that forward_text is optional."""
        result = get_login_keyboard(
            "Login",
            "https://example.com/auth",
            forward_text="Welcome to the app!",
        )

        button = result.inline_keyboard[0][0]
        assert button.login_url.forward_text == "Welcome to the app!"


# ============================================================================
# Tests for get_request_contact_keyboard
# ============================================================================


class TestGetRequestContactKeyboard:
    """Tests for get_request_contact_keyboard function."""

    def test_returns_reply_keyboard_markup(self):
        """Test that function returns ReplyKeyboardMarkup."""
        result = get_request_contact_keyboard()

        assert isinstance(result, ReplyKeyboardMarkup)

    def test_has_two_rows(self):
        """Test that keyboard has two rows."""
        result = get_request_contact_keyboard()

        assert len(result.keyboard) == 2

    def test_default_button_text(self):
        """Test default button text."""
        result = get_request_contact_keyboard()

        button = result.keyboard[0][0]
        assert "контакт" in button.text.lower()

    def test_custom_button_text(self):
        """Test custom button text."""
        result = get_request_contact_keyboard(button_text="Share Phone")

        button = result.keyboard[0][0]
        assert button.text == "Share Phone"

    def test_request_contact_enabled(self):
        """Test that request_contact is enabled."""
        result = get_request_contact_keyboard()

        button = result.keyboard[0][0]
        assert button.request_contact is True

    def test_cancel_button_exists(self):
        """Test that cancel button exists."""
        result = get_request_contact_keyboard()

        cancel_button = result.keyboard[1][0]
        assert "Отмена" in cancel_button.text

    def test_resize_keyboard_enabled(self):
        """Test that resize_keyboard is enabled."""
        result = get_request_contact_keyboard()

        assert result.resize_keyboard is True

    def test_one_time_keyboard_enabled(self):
        """Test that one_time_keyboard is enabled."""
        result = get_request_contact_keyboard()

        assert result.one_time_keyboard is True


# ============================================================================
# Tests for get_request_location_keyboard
# ============================================================================


class TestGetRequestLocationKeyboard:
    """Tests for get_request_location_keyboard function."""

    def test_returns_reply_keyboard_markup(self):
        """Test that function returns ReplyKeyboardMarkup."""
        result = get_request_location_keyboard()

        assert isinstance(result, ReplyKeyboardMarkup)

    def test_has_two_rows(self):
        """Test that keyboard has two rows."""
        result = get_request_location_keyboard()

        assert len(result.keyboard) == 2

    def test_default_button_text(self):
        """Test default button text."""
        result = get_request_location_keyboard()

        button = result.keyboard[0][0]
        assert "геолокацию" in button.text.lower() or "📍" in button.text

    def test_custom_button_text(self):
        """Test custom button text."""
        result = get_request_location_keyboard(button_text="Share Location")

        button = result.keyboard[0][0]
        assert button.text == "Share Location"

    def test_request_location_enabled(self):
        """Test that request_location is enabled."""
        result = get_request_location_keyboard()

        button = result.keyboard[0][0]
        assert button.request_location is True

    def test_cancel_button_exists(self):
        """Test that cancel button exists."""
        result = get_request_location_keyboard()

        cancel_button = result.keyboard[1][0]
        assert "Отмена" in cancel_button.text

    def test_resize_keyboard_enabled(self):
        """Test that resize_keyboard is enabled."""
        result = get_request_location_keyboard()

        assert result.resize_keyboard is True

    def test_one_time_keyboard_enabled(self):
        """Test that one_time_keyboard is enabled."""
        result = get_request_location_keyboard()

        assert result.one_time_keyboard is True


# ============================================================================
# Tests for get_api_key_input_keyboard
# ============================================================================


class TestGetApiKeyInputKeyboard:
    """Tests for get_api_key_input_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_api_key_input_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_api_key_input_keyboard()

        # 4 rows: [paste], [where to find], [help], [cancel]
        assert len(result.inline_keyboard) == 4

    def test_paste_button_exists(self):
        """Test that paste button exists."""
        result = get_api_key_input_keyboard()

        first_row = result.inline_keyboard[0]
        paste_button = first_row[0]

        assert "буфера" in paste_button.text.lower() or "Вставить" in paste_button.text
        assert paste_button.callback_data == "api_paste"

    def test_where_to_find_button_exists(self):
        """Test that 'where to find' button exists with URL."""
        result = get_api_key_input_keyboard()

        second_row = result.inline_keyboard[1]
        where_button = second_row[0]

        assert (
            "ключи" in where_button.text.lower() or "найти" in where_button.text.lower()
        )
        assert where_button.url is not None
        assert "dmarket.com" in where_button.url

    def test_help_button_exists(self):
        """Test that help button exists."""
        result = get_api_key_input_keyboard()

        third_row = result.inline_keyboard[2]
        help_button = third_row[0]

        assert "Инструкция" in help_button.text
        assert help_button.callback_data == "api_help"

    def test_cancel_button_exists(self):
        """Test that cancel button exists."""
        result = get_api_key_input_keyboard()

        last_row = result.inline_keyboard[-1]
        cancel_button = last_row[0]

        assert "Отмена" in cancel_button.text
        assert cancel_button.callback_data == CB_CANCEL
