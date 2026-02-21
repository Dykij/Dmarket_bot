"""Unit tests for telegram_bot/keyboards/alerts.py module.

Tests cover:
- Alert keyboard generation
- Alert type selection keyboard
- Alert actions keyboard
- Price alerts list keyboard with pagination
- Alert notification settings keyboard
"""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from src.telegram_bot.keyboards.alerts import (
    create_price_alerts_keyboard,
    get_alert_actions_keyboard,
    get_alert_keyboard,
    get_alert_notification_settings_keyboard,
    get_alert_type_keyboard,
)
from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL

# ============================================================================
# Tests for get_alert_keyboard
# ============================================================================


class TestGetAlertKeyboard:
    """Tests for get_alert_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_alert_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_alert_keyboard()

        # 4 rows: [create, list], [active, history], [settings], [back]
        assert len(result.inline_keyboard) == 4

    def test_create_alert_button_exists(self):
        """Test that 'Create alert' button exists with correct callback."""
        result = get_alert_keyboard()

        first_row = result.inline_keyboard[0]
        create_button = first_row[0]

        assert "Создать алерт" in create_button.text
        assert create_button.callback_data == "alert_create"

    def test_my_alerts_button_exists(self):
        """Test that 'My alerts' button exists with correct callback."""
        result = get_alert_keyboard()

        first_row = result.inline_keyboard[0]
        list_button = first_row[1]

        assert "Мои алерты" in list_button.text
        assert list_button.callback_data == "alert_list"

    def test_active_alerts_button_exists(self):
        """Test that 'Active' button exists with correct callback."""
        result = get_alert_keyboard()

        second_row = result.inline_keyboard[1]
        active_button = second_row[0]

        assert "Активные" in active_button.text
        assert active_button.callback_data == "alert_active"

    def test_history_button_exists(self):
        """Test that 'History' button exists with correct callback."""
        result = get_alert_keyboard()

        second_row = result.inline_keyboard[1]
        history_button = second_row[1]

        assert "История" in history_button.text
        assert history_button.callback_data == "alert_history"

    def test_settings_button_exists(self):
        """Test that 'Settings' button exists with correct callback."""
        result = get_alert_keyboard()

        third_row = result.inline_keyboard[2]
        settings_button = third_row[0]

        assert "НастSwarmки" in settings_button.text
        assert settings_button.callback_data == "alert_settings"

    def test_back_button_exists(self):
        """Test that 'Back' button exists with correct callback."""
        result = get_alert_keyboard()

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK


# ============================================================================
# Tests for get_alert_type_keyboard
# ============================================================================


class TestGetAlertTypeKeyboard:
    """Tests for get_alert_type_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_alert_type_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_alert_type_keyboard()

        # 4 rows: [below, above], [target, percent], [new item], [cancel]
        assert len(result.inline_keyboard) == 4

    def test_price_below_button_exists(self):
        """Test that 'Price below' button exists with correct callback."""
        result = get_alert_type_keyboard()

        first_row = result.inline_keyboard[0]
        below_button = first_row[0]

        assert "ниже" in below_button.text.lower()
        assert below_button.callback_data == "alert_type_below"

    def test_price_above_button_exists(self):
        """Test that 'Price above' button exists with correct callback."""
        result = get_alert_type_keyboard()

        first_row = result.inline_keyboard[0]
        above_button = first_row[1]

        assert "выше" in above_button.text.lower()
        assert above_button.callback_data == "alert_type_above"

    def test_target_price_button_exists(self):
        """Test that 'Target price' button exists with correct callback."""
        result = get_alert_type_keyboard()

        second_row = result.inline_keyboard[1]
        target_button = second_row[0]

        assert "Целевая" in target_button.text
        assert target_button.callback_data == "alert_type_target"

    def test_percent_change_button_exists(self):
        """Test that 'Percent change' button exists with correct callback."""
        result = get_alert_type_keyboard()

        second_row = result.inline_keyboard[1]
        percent_button = second_row[1]

        assert "%" in percent_button.text
        assert percent_button.callback_data == "alert_type_percent"

    def test_new_item_button_exists(self):
        """Test that 'New item' button exists with correct callback."""
        result = get_alert_type_keyboard()

        third_row = result.inline_keyboard[2]
        new_item_button = third_row[0]

        assert "Новый предмет" in new_item_button.text
        assert new_item_button.callback_data == "alert_type_new_item"

    def test_cancel_button_exists(self):
        """Test that 'Cancel' button exists with correct callback."""
        result = get_alert_type_keyboard()

        last_row = result.inline_keyboard[-1]
        cancel_button = last_row[0]

        assert "Отмена" in cancel_button.text
        assert cancel_button.callback_data == CB_CANCEL


# ============================================================================
# Tests for get_alert_actions_keyboard
# ============================================================================


class TestGetAlertActionsKeyboard:
    """Tests for get_alert_actions_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_alert_actions_keyboard("test_alert_123")

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_alert_actions_keyboard("test_alert_123")

        # 3 rows: [edit, delete], [pause, stats], [back]
        assert len(result.inline_keyboard) == 3

    def test_edit_button_contAlgons_alert_id(self):
        """Test that 'Edit' button contAlgons the alert ID in callback."""
        alert_id = "alert_456"
        result = get_alert_actions_keyboard(alert_id)

        first_row = result.inline_keyboard[0]
        edit_button = first_row[0]

        assert "Изменить" in edit_button.text
        assert f"alert_edit_{alert_id}" == edit_button.callback_data

    def test_delete_button_contAlgons_alert_id(self):
        """Test that 'Delete' button contAlgons the alert ID in callback."""
        alert_id = "alert_789"
        result = get_alert_actions_keyboard(alert_id)

        first_row = result.inline_keyboard[0]
        delete_button = first_row[1]

        assert "Удалить" in delete_button.text
        assert f"alert_delete_{alert_id}" == delete_button.callback_data

    def test_pause_button_contAlgons_alert_id(self):
        """Test that 'Pause' button contAlgons the alert ID in callback."""
        alert_id = "my_alert"
        result = get_alert_actions_keyboard(alert_id)

        second_row = result.inline_keyboard[1]
        pause_button = second_row[0]

        assert "Приостановить" in pause_button.text
        assert f"alert_pause_{alert_id}" == pause_button.callback_data

    def test_stats_button_contAlgons_alert_id(self):
        """Test that 'Stats' button contAlgons the alert ID in callback."""
        alert_id = "stats_alert"
        result = get_alert_actions_keyboard(alert_id)

        second_row = result.inline_keyboard[1]
        stats_button = second_row[1]

        assert "Статистика" in stats_button.text
        assert f"alert_stats_{alert_id}" == stats_button.callback_data

    def test_back_button_goes_to_alert_list(self):
        """Test that 'Back' button goes to alert list."""
        result = get_alert_actions_keyboard("any_alert")

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == "alert_list"


# ============================================================================
# Tests for create_price_alerts_keyboard
# ============================================================================


class TestCreatePriceAlertsKeyboard:
    """Tests for create_price_alerts_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = create_price_alerts_keyboard([])

        assert isinstance(result, InlineKeyboardMarkup)

    def test_empty_alerts_list_has_create_button(self):
        """Test that empty list still shows create button."""
        result = create_price_alerts_keyboard([])

        # Should have at least create and back buttons
        all_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert any("Создать" in text for text in all_texts)

    def test_single_alert_displayed(self):
        """Test that single alert is displayed correctly."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "AK-47 Redline",
                "target_price": 25.50,
                "type": "below",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        # Find the alert button
        alert_buttons = [
            btn
            for row in result.inline_keyboard
            for btn in row
            if btn.callback_data and btn.callback_data.startswith("alert_view_")
        ]
        assert len(alert_buttons) == 1
        assert alert_buttons[0].callback_data == "alert_view_alert1"

    def test_alert_shows_item_name(self):
        """Test that alert button shows truncated item name."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "AK-47 | Redline (Field-Tested)",
                "target_price": 25.50,
                "type": "below",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        # Item name truncated to 25 chars
        assert "AK-47" in alert_button.text

    def test_alert_shows_price(self):
        """Test that alert button shows price."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "AWP",
                "target_price": 100.00,
                "type": "below",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        assert "$100.00" in alert_button.text

    def test_alert_type_emoji_below(self):
        """Test that 'below' type shows down arrow emoji."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "Item",
                "target_price": 10.0,
                "type": "below",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        assert "📉" in alert_button.text

    def test_alert_type_emoji_above(self):
        """Test that 'above' type shows up arrow emoji."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "Item",
                "target_price": 10.0,
                "type": "above",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        assert "📈" in alert_button.text

    def test_active_alert_shows_green_status(self):
        """Test that active alert shows green status emoji."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "Item",
                "target_price": 10.0,
                "type": "below",
                "active": True,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        assert "🟢" in alert_button.text

    def test_inactive_alert_shows_red_status(self):
        """Test that inactive alert shows red status emoji."""
        alerts = [
            {
                "id": "alert1",
                "item_name": "Item",
                "target_price": 10.0,
                "type": "below",
                "active": False,
            }
        ]
        result = create_price_alerts_keyboard(alerts)

        alert_button = result.inline_keyboard[0][0]
        assert "🔴" in alert_button.text

    def test_pagination_with_many_alerts(self):
        """Test that pagination appears with many alerts."""
        alerts = [
            {
                "id": f"alert_{i}",
                "item_name": f"Item {i}",
                "target_price": 10.0 + i,
                "type": "below",
                "active": True,
            }
            for i in range(10)
        ]
        result = create_price_alerts_keyboard(alerts, page=1, page_size=5)

        # Find pagination buttons
        all_callbacks = [
            btn.callback_data
            for row in result.inline_keyboard
            for btn in row
            if btn.callback_data
        ]
        assert any("alerts_page_" in cb for cb in all_callbacks)

    def test_first_page_no_previous_button(self):
        """Test that first page has no previous button."""
        alerts = [
            {
                "id": f"alert_{i}",
                "item_name": f"Item {i}",
                "target_price": 10.0,
                "type": "below",
                "active": True,
            }
            for i in range(10)
        ]
        result = create_price_alerts_keyboard(alerts, page=1, page_size=5)

        # Check for previous page button (should not exist)
        all_callbacks = [
            btn.callback_data
            for row in result.inline_keyboard
            for btn in row
            if btn.callback_data
        ]
        assert "alerts_page_0" not in all_callbacks

    def test_last_page_no_next_button(self):
        """Test that last page has no next button."""
        alerts = [
            {
                "id": f"alert_{i}",
                "item_name": f"Item {i}",
                "target_price": 10.0,
                "type": "below",
                "active": True,
            }
            for i in range(10)
        ]
        result = create_price_alerts_keyboard(alerts, page=2, page_size=5)

        # Check for next page button (should not exist)
        all_callbacks = [
            btn.callback_data
            for row in result.inline_keyboard
            for btn in row
            if btn.callback_data
        ]
        assert "alerts_page_3" not in all_callbacks

    def test_middle_page_has_both_navigation_buttons(self):
        """Test that middle page has both prev and next buttons."""
        alerts = [
            {
                "id": f"alert_{i}",
                "item_name": f"Item {i}",
                "target_price": 10.0,
                "type": "below",
                "active": True,
            }
            for i in range(15)
        ]
        result = create_price_alerts_keyboard(alerts, page=2, page_size=5)

        all_callbacks = [
            btn.callback_data
            for row in result.inline_keyboard
            for btn in row
            if btn.callback_data
        ]
        # Should have page 1 (prev) and page 3 (next)
        assert "alerts_page_1" in all_callbacks
        assert "alerts_page_3" in all_callbacks

    def test_delete_all_button_exists(self):
        """Test that 'Delete all' button exists."""
        result = create_price_alerts_keyboard([])

        all_texts = [btn.text for row in result.inline_keyboard for btn in row]
        assert any("Удалить все" in text for text in all_texts)

    def test_back_button_exists(self):
        """Test that 'Back' button exists."""
        result = create_price_alerts_keyboard([])

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == CB_BACK


# ============================================================================
# Tests for get_alert_notification_settings_keyboard
# ============================================================================


class TestGetAlertNotificationSettingsKeyboard:
    """Tests for get_alert_notification_settings_keyboard function."""

    def test_returns_inline_keyboard_markup(self):
        """Test that function returns InlineKeyboardMarkup."""
        result = get_alert_notification_settings_keyboard()

        assert isinstance(result, InlineKeyboardMarkup)

    def test_has_correct_number_of_rows(self):
        """Test that keyboard has the expected number of rows."""
        result = get_alert_notification_settings_keyboard()

        # 4 rows: [push, telegram], [emAlgol, sound], [quiet hours], [back]
        assert len(result.inline_keyboard) == 4

    def test_default_settings_push_enabled(self):
        """Test that push is enabled by default."""
        result = get_alert_notification_settings_keyboard()

        first_row = result.inline_keyboard[0]
        push_button = first_row[0]

        assert "Push" in push_button.text
        assert "✅" in push_button.text

    def test_default_settings_telegram_enabled(self):
        """Test that telegram is enabled by default."""
        result = get_alert_notification_settings_keyboard()

        first_row = result.inline_keyboard[0]
        telegram_button = first_row[1]

        assert "Telegram" in telegram_button.text
        assert "✅" in telegram_button.text

    def test_default_settings_emAlgol_disabled(self):
        """Test that emAlgol is disabled by default."""
        result = get_alert_notification_settings_keyboard()

        second_row = result.inline_keyboard[1]
        emAlgol_button = second_row[0]

        assert "EmAlgol" in emAlgol_button.text
        assert "❌" in emAlgol_button.text

    def test_default_settings_sound_enabled(self):
        """Test that sound is enabled by default."""
        result = get_alert_notification_settings_keyboard()

        second_row = result.inline_keyboard[1]
        sound_button = second_row[1]

        assert "Звук" in sound_button.text
        assert "✅" in sound_button.text

    def test_custom_settings_push_disabled(self):
        """Test custom settings with push disabled."""
        settings = {"push": False, "telegram": True, "emAlgol": False, "sound": True}
        result = get_alert_notification_settings_keyboard(settings)

        first_row = result.inline_keyboard[0]
        push_button = first_row[0]

        assert "❌" in push_button.text

    def test_custom_settings_emAlgol_enabled(self):
        """Test custom settings with emAlgol enabled."""
        settings = {"push": True, "telegram": True, "emAlgol": True, "sound": True}
        result = get_alert_notification_settings_keyboard(settings)

        second_row = result.inline_keyboard[1]
        emAlgol_button = second_row[0]

        assert "✅" in emAlgol_button.text

    def test_quiet_hours_button_exists(self):
        """Test that 'Quiet hours' button exists."""
        result = get_alert_notification_settings_keyboard()

        third_row = result.inline_keyboard[2]
        quiet_hours_button = third_row[0]

        assert "тишины" in quiet_hours_button.text.lower()
        assert quiet_hours_button.callback_data == "alert_setting_quiet_hours"

    def test_push_callback_data(self):
        """Test push button callback data."""
        result = get_alert_notification_settings_keyboard()

        first_row = result.inline_keyboard[0]
        push_button = first_row[0]

        assert push_button.callback_data == "alert_setting_push"

    def test_telegram_callback_data(self):
        """Test telegram button callback data."""
        result = get_alert_notification_settings_keyboard()

        first_row = result.inline_keyboard[0]
        telegram_button = first_row[1]

        assert telegram_button.callback_data == "alert_setting_telegram"

    def test_back_button_goes_to_alerts(self):
        """Test that 'Back' button goes to alerts."""
        result = get_alert_notification_settings_keyboard()

        last_row = result.inline_keyboard[-1]
        back_button = last_row[0]

        assert "Назад" in back_button.text
        assert back_button.callback_data == "alerts"
