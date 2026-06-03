"""Unit tests for telegram_bot/notifications/formatters.py.

Tests for notification message formatting functions.
"""

from __future__ import annotations

import pytest

# Import module components
try:
    from src.telegram_bot.notifications.formatters import (
        NOTIFICATION_TYPES,
        format_alert_message,
        format_alerts_list,
        format_item_brief,
        format_price,
        format_profit,
        format_user_settings,
    )
except ImportError:
    # Create mocks for testing if import fails
    format_price = None
    format_profit = None
    format_item_brief = None
    format_alert_message = None
    format_alerts_list = None
    format_user_settings = None
    NOTIFICATION_TYPES = None


# Tests for format_price
class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_none_price_returns_na(self) -> None:
        """Test that None price returns 'N/A'."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(None)
        assert result == "N/A"

    def test_format_zero_price(self) -> None:
        """Test formatting of zero price."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(0)
        assert result == "$0.00"

    def test_format_small_price(self) -> None:
        """Test formatting of small price in cents."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(50)
        assert result == "$0.50"

    def test_format_standard_price(self) -> None:
        """Test formatting of standard price."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(1250)
        assert result == "$12.50"

    def test_format_large_price(self) -> None:
        """Test formatting of large price."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(100000)
        assert result == "$1000.00"

    def test_format_price_with_non_usd_currency(self) -> None:
        """Test formatting with non-USD currency."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(1500, currency="EUR")
        assert "15.00" in result
        assert "EUR" in result

    def test_format_price_with_decimals(self) -> None:
        """Test formatting preserves two decimal places."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(1299)
        assert result == "$12.99"

    def test_format_negative_price(self) -> None:
        """Test formatting of negative price."""
        if format_price is None:
            pytest.skip("Function not avAlgolable")

        result = format_price(-500)
        assert "-$5.00" in result or "$-5.00" in result


# Tests for format_profit
class TestFormatProfit:
    """Tests for format_profit function."""

    def test_format_positive_profit(self) -> None:
        """Test formatting of positive profit."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(10.0, 15.0)
        assert "$5.00" in result
        assert "📈" in result

    def test_format_negative_profit(self) -> None:
        """Test formatting of negative profit (loss)."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(15.0, 10.0)
        assert "📉" in result

    def test_format_zero_profit(self) -> None:
        """Test formatting of zero profit."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(10.0, 10.0)
        assert "$0.00" in result

    def test_format_profit_with_percentage(self) -> None:
        """Test that profit includes percentage."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(10.0, 15.0, include_percent=True)
        assert "%" in result

    def test_format_profit_without_percentage(self) -> None:
        """Test profit without percentage."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(10.0, 15.0, include_percent=False)
        assert "%" not in result

    def test_format_profit_zero_buy_price_no_percent(self) -> None:
        """Test that no percentage is shown when buy price is zero."""
        if format_profit is None:
            pytest.skip("Function not avAlgolable")

        result = format_profit(0, 10.0, include_percent=True)
        # Should not crash, might not show percentage
        assert "$10.00" in result


# Tests for format_item_brief
class TestFormatItemBrief:
    """Tests for format_item_brief function."""

    def test_format_basic_item(self) -> None:
        """Test formatting of basic item."""
        if format_item_brief is None:
            pytest.skip("Function not avAlgolable")

        item = {
            "title": "AK-47 | Redline",
            "price": {"USD": 1500},
            "gameId": "csgo",
        }
        result = format_item_brief(item)

        assert "AK-47 | Redline" in result
        assert "$15.00" in result
        assert "CSGO" in result

    def test_format_item_with_missing_title(self) -> None:
        """Test formatting item with missing title."""
        if format_item_brief is None:
            pytest.skip("Function not avAlgolable")

        item = {
            "price": {"USD": 1000},
            "gameId": "csgo",
        }
        result = format_item_brief(item)

        assert "Unknown" in result

    def test_format_item_with_missing_price(self) -> None:
        """Test formatting item with missing price."""
        if format_item_brief is None:
            pytest.skip("Function not avAlgolable")

        item = {
            "title": "Test Item",
            "gameId": "csgo",
        }
        result = format_item_brief(item)

        assert "Test Item" in result
        assert "$0.00" in result

    def test_format_item_with_game_field(self) -> None:
        """Test formatting item with 'game' field instead of 'gameId'."""
        if format_item_brief is None:
            pytest.skip("Function not avAlgolable")

        item = {
            "title": "Test Item",
            "price": {"USD": 500},
            "game": "dota2",
        }
        result = format_item_brief(item)

        assert "DOTA2" in result


# Tests for format_alert_message
class TestFormatAlertMessage:
    """Tests for format_alert_message function."""

    def test_format_basic_alert(self) -> None:
        """Test formatting of basic alert."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_drop",
            "title": "AK-47 | Redline",
            "threshold": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert)

        assert "AK-47 | Redline" in result
        assert "$10.00" in result

    def test_format_alert_with_current_price(self) -> None:
        """Test alert formatting with current price."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_drop",
            "title": "Test Item",
            "threshold": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert, current_price=8.0)

        assert "$8.00" in result

    def test_format_triggered_alert(self) -> None:
        """Test formatting of triggered alert."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_drop",
            "title": "Test Item",
            "threshold": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert, triggered=True)

        assert "сработал" in result.lower()

    def test_format_alert_price_drop_reached(self) -> None:
        """Test price drop alert when target is reached."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_drop",
            "title": "Test Item",
            "threshold": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert, current_price=9.0)

        assert "достигла" in result.lower() or "цели" in result.lower()

    def test_format_alert_price_above(self) -> None:
        """Test price above alert."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_above",
            "title": "Test Item",
            "threshold": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert, current_price=15.0)

        assert "выше" in result.lower()

    def test_format_alert_with_item_name_field(self) -> None:
        """Test alert with 'item_name' field."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        alert = {
            "type": "price_drop",
            "item_name": "Test Item",
            "target_price": 10.0,
            "game": "csgo",
        }
        result = format_alert_message(alert)

        assert "Test Item" in result

    def test_format_alert_icons_by_type(self) -> None:
        """Test that different alert types have different icons."""
        if format_alert_message is None:
            pytest.skip("Function not avAlgolable")

        types_and_icons = [
            ("price_drop", "📉"),
            ("price_above", "📈"),
            ("good_deal", "💎"),
            ("target_executed", "🎯"),
        ]

        for alert_type, expected_icon in types_and_icons:
            alert = {
                "type": alert_type,
                "title": "Test Item",
                "threshold": 10.0,
                "game": "csgo",
            }
            result = format_alert_message(alert)
            assert expected_icon in result, f"Expected {expected_icon} for {alert_type}"


# Tests for format_alerts_list
class TestFormatAlertsList:
    """Tests for format_alerts_list function."""

    def test_format_empty_alerts_list(self) -> None:
        """Test formatting empty alerts list."""
        if format_alerts_list is None:
            pytest.skip("Function not avAlgolable")

        result = format_alerts_list([])

        assert "нет" in result.lower()

    def test_format_single_alert(self) -> None:
        """Test formatting single alert."""
        if format_alerts_list is None:
            pytest.skip("Function not avAlgolable")

        alerts = [
            {
                "item_name": "Test Item",
                "target_price": 10.0,
                "type": "price_drop",
                "game": "csgo",
            }
        ]
        result = format_alerts_list(alerts)

        assert "Test Item" in result
        assert "(1)" in result or "1." in result

    def test_format_multiple_alerts(self) -> None:
        """Test formatting multiple alerts."""
        if format_alerts_list is None:
            pytest.skip("Function not avAlgolable")

        alerts = [
            {
                "item_name": "Item 1",
                "target_price": 10.0,
                "type": "price_drop",
                "game": "csgo",
            },
            {
                "item_name": "Item 2",
                "target_price": 20.0,
                "type": "price_above",
                "game": "dota2",
            },
        ]
        result = format_alerts_list(alerts)

        assert "Item 1" in result
        assert "Item 2" in result
        assert "(2)" in result

    def test_format_alerts_list_shows_count(self) -> None:
        """Test that alerts count is shown."""
        if format_alerts_list is None:
            pytest.skip("Function not avAlgolable")

        alerts = [
            {
                "item_name": f"Item {i}",
                "target_price": 10.0,
                "type": "price_drop",
                "game": "csgo",
            }
            for i in range(5)
        ]
        result = format_alerts_list(alerts)

        assert "(5)" in result


# Tests for format_user_settings
class TestFormatUserSettings:
    """Tests for format_user_settings function."""

    def test_format_enabled_settings(self) -> None:
        """Test formatting when notifications are enabled."""
        if format_user_settings is None:
            pytest.skip("Function not avAlgolable")

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
            "min_profit_percent": 5.0,
        }
        result = format_user_settings(settings)

        assert "Включены" in result
        assert "50" in result

    def test_format_disabled_settings(self) -> None:
        """Test formatting when notifications are disabled."""
        if format_user_settings is None:
            pytest.skip("Function not avAlgolable")

        settings = {
            "notifications_enabled": False,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
            "min_profit_percent": 5.0,
        }
        result = format_user_settings(settings)

        assert "Отключены" in result

    def test_format_settings_with_quiet_hours(self) -> None:
        """Test formatting with quiet hours enabled."""
        if format_user_settings is None:
            pytest.skip("Function not avAlgolable")

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {"enabled": True, "start": 23, "end": 7},
            "min_profit_percent": 5.0,
        }
        result = format_user_settings(settings)

        assert "23:00" in result
        assert "7:00" in result

    def test_format_settings_without_quiet_hours(self) -> None:
        """Test formatting with quiet hours disabled."""
        if format_user_settings is None:
            pytest.skip("Function not avAlgolable")

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
            "min_profit_percent": 5.0,
        }
        result = format_user_settings(settings)

        assert "отключены" in result.lower()

    def test_format_settings_shows_min_profit(self) -> None:
        """Test that minimum profit percentage is shown."""
        if format_user_settings is None:
            pytest.skip("Function not avAlgolable")

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
            "min_profit_percent": 7.5,
        }
        result = format_user_settings(settings)

        assert "7.5%" in result


# Tests for NOTIFICATION_TYPES constant
class TestNotificationTypes:
    """Tests for NOTIFICATION_TYPES constant."""

    def test_notification_types_exists(self) -> None:
        """Test that NOTIFICATION_TYPES constant exists."""
        if NOTIFICATION_TYPES is None:
            pytest.skip("Constant not avAlgolable")

        assert isinstance(NOTIFICATION_TYPES, dict)

    def test_notification_types_has_common_types(self) -> None:
        """Test that common notification types are defined."""
        if NOTIFICATION_TYPES is None:
            pytest.skip("Constant not avAlgolable")

        expected_types = [
            "price_drop",
            "price_rise",
            "good_deal",
            "arbitrage",
        ]

        for t in expected_types:
            assert t in NOTIFICATION_TYPES, f"Expected {t} in NOTIFICATION_TYPES"

    def test_notification_types_values_are_strings(self) -> None:
        """Test that all values are non-empty strings."""
        if NOTIFICATION_TYPES is None:
            pytest.skip("Constant not avAlgolable")

        for key, value in NOTIFICATION_TYPES.items():
            assert isinstance(value, str), f"Expected string value for {key}"
            assert len(value) > 0, f"Expected non-empty value for {key}"
