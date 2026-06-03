"""Tests for telegram_bot.notifications.formatters module.

This module tests notification message formatting functions:
- format_price
- format_profit
- format_item_brief
- format_alert_message
- format_alerts_list
- format_user_settings
- NOTIFICATION_TYPES constant
"""

from __future__ import annotations

# =============================================================================
# Test format_price function
# =============================================================================


class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_price_usd(self) -> None:
        """Test formatting price in USD."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(1250)

        assert result == "$12.50"

    def test_format_price_zero(self) -> None:
        """Test formatting zero price."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(0)

        assert result == "$0.00"

    def test_format_price_none(self) -> None:
        """Test formatting None price."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(None)

        assert result == "N/A"

    def test_format_price_large(self) -> None:
        """Test formatting large price."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(100000)

        assert result == "$1000.00"

    def test_format_price_fractional(self) -> None:
        """Test formatting fractional price."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(1)

        assert result == "$0.01"

    def test_format_price_other_currency(self) -> None:
        """Test formatting price in other currency."""
        from src.telegram_bot.notifications.formatters import format_price

        result = format_price(1000, currency="EUR")

        assert result == "10.00 EUR"


# =============================================================================
# Test format_profit function
# =============================================================================


class TestFormatProfit:
    """Tests for format_profit function."""

    def test_format_profit_positive(self) -> None:
        """Test formatting positive profit."""
        from src.telegram_bot.notifications.formatters import format_profit

        result = format_profit(buy_price=10.0, sell_price=15.0)

        assert "📈" in result
        assert "$5.00" in result
        assert "+50.0%" in result

    def test_format_profit_negative(self) -> None:
        """Test formatting negative profit (loss)."""
        from src.telegram_bot.notifications.formatters import format_profit

        result = format_profit(buy_price=20.0, sell_price=15.0)

        assert "📉" in result
        assert "-$5.00" in result or "$-5.00" in result

    def test_format_profit_zero(self) -> None:
        """Test formatting zero profit."""
        from src.telegram_bot.notifications.formatters import format_profit

        result = format_profit(buy_price=10.0, sell_price=10.0)

        assert "$0.00" in result

    def test_format_profit_without_percent(self) -> None:
        """Test formatting profit without percentage."""
        from src.telegram_bot.notifications.formatters import format_profit

        result = format_profit(buy_price=10.0, sell_price=15.0, include_percent=False)

        assert "%" not in result

    def test_format_profit_zero_buy_price(self) -> None:
        """Test formatting profit with zero buy price."""
        from src.telegram_bot.notifications.formatters import format_profit

        # Should not divide by zero
        result = format_profit(buy_price=0, sell_price=10.0, include_percent=True)

        assert "$10.00" in result


# =============================================================================
# Test format_item_brief function
# =============================================================================


class TestFormatItemBrief:
    """Tests for format_item_brief function."""

    def test_format_item_brief_basic(self) -> None:
        """Test basic item brief formatting."""
        from src.telegram_bot.notifications.formatters import format_item_brief

        item = {
            "title": "AK-47 | Redline",
            "price": {"USD": 1500},
            "gameId": "csgo",
        }

        result = format_item_brief(item)

        assert "AK-47 | Redline" in result
        assert "$15.00" in result
        assert "CSGO" in result

    def test_format_item_brief_missing_title(self) -> None:
        """Test item brief with missing title."""
        from src.telegram_bot.notifications.formatters import format_item_brief

        item = {
            "price": {"USD": 1000},
            "gameId": "csgo",
        }

        result = format_item_brief(item)

        assert "Unknown" in result

    def test_format_item_brief_missing_price(self) -> None:
        """Test item brief with missing price."""
        from src.telegram_bot.notifications.formatters import format_item_brief

        item = {
            "title": "Test Item",
            "gameId": "dota2",
        }

        result = format_item_brief(item)

        assert "$0.00" in result

    def test_format_item_brief_game_fallback(self) -> None:
        """Test item brief with game key fallback."""
        from src.telegram_bot.notifications.formatters import format_item_brief

        item = {
            "title": "Test",
            "price": {"USD": 500},
            "game": "tf2",  # Uses 'game' instead of 'gameId'
        }

        result = format_item_brief(item)

        assert "TF2" in result


# =============================================================================
# Test format_alert_message function
# =============================================================================


class TestFormatAlertMessage:
    """Tests for format_alert_message function."""

    def test_format_alert_message_basic(self) -> None:
        """Test basic alert message formatting."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_drop",
            "title": "Test Item",
            "target_price": 10.0,
            "game": "csgo",
        }

        result = format_alert_message(alert, current_price=8.0)

        assert "Test Item" in result
        assert "$8.00" in result
        assert "📉" in result or "📦" in result  # Price drop icon or item icon

    def test_format_alert_message_triggered(self) -> None:
        """Test triggered alert message."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_drop",
            "item_name": "AK-47",
            "target_price": 15.0,
            "game": "csgo",
        }

        result = format_alert_message(alert, current_price=12.0, triggered=True)

        assert "сработал" in result.lower() or "trigger" in result.lower()

    def test_format_alert_message_price_above(self) -> None:
        """Test price_above alert message."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_above",
            "title": "Item",
            "target_price": 10.0,
            "game": "csgo",
        }

        result = format_alert_message(alert, current_price=15.0)

        assert "📈" in result or "$15.00" in result

    def test_format_alert_message_good_deal(self) -> None:
        """Test good_deal alert message."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "good_deal",
            "title": "BargAlgon Item",
            "threshold": 5.0,
            "game": "dota2",
        }

        result = format_alert_message(alert)

        assert "BargAlgon Item" in result

    def test_format_alert_message_no_current_price(self) -> None:
        """Test alert message without current price."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_drop",
            "title": "Item",
            "target_price": 10.0,
            "game": "csgo",
        }

        result = format_alert_message(alert)

        assert "Item" in result
        assert "$10.00" in result

    def test_format_alert_message_uses_item_name_fallback(self) -> None:
        """Test that alert message uses item_name when title is missing."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_drop",
            "item_name": "Fallback Name",
            "game": "csgo",
        }

        result = format_alert_message(alert)

        assert "Fallback Name" in result

    def test_format_alert_message_uses_threshold_fallback(self) -> None:
        """Test that alert message uses threshold when target_price is missing."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        alert = {
            "type": "price_drop",
            "title": "Item",
            "threshold": 25.0,
            "game": "csgo",
        }

        result = format_alert_message(alert)

        assert "$25.00" in result


# =============================================================================
# Test format_alerts_list function
# =============================================================================


class TestFormatAlertsList:
    """Tests for format_alerts_list function."""

    def test_format_alerts_list_empty(self) -> None:
        """Test formatting empty alerts list."""
        from src.telegram_bot.notifications.formatters import format_alerts_list

        result = format_alerts_list([])

        assert "нет" in result.lower() or "no" in result.lower()

    def test_format_alerts_list_single(self) -> None:
        """Test formatting single alert."""
        from src.telegram_bot.notifications.formatters import format_alerts_list

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
        assert "$10.00" in result
        assert "1" in result  # Numbered list

    def test_format_alerts_list_multiple(self) -> None:
        """Test formatting multiple alerts."""
        from src.telegram_bot.notifications.formatters import format_alerts_list

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
        assert "(2)" in result or "2." in result


# =============================================================================
# Test format_user_settings function
# =============================================================================


class TestFormatUserSettings:
    """Tests for format_user_settings function."""

    def test_format_user_settings_enabled(self) -> None:
        """Test formatting enabled settings."""
        from src.telegram_bot.notifications.formatters import format_user_settings

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
            "min_profit_percent": 5.0,
        }

        result = format_user_settings(settings)

        assert "✅" in result or "Включены" in result
        assert "50" in result

    def test_format_user_settings_disabled(self) -> None:
        """Test formatting disabled settings."""
        from src.telegram_bot.notifications.formatters import format_user_settings

        settings = {
            "notifications_enabled": False,
            "daily_limit": 50,
            "quiet_hours": {"enabled": False},
        }

        result = format_user_settings(settings)

        assert "❌" in result or "Отключены" in result

    def test_format_user_settings_with_quiet_hours(self) -> None:
        """Test formatting settings with quiet hours enabled."""
        from src.telegram_bot.notifications.formatters import format_user_settings

        settings = {
            "notifications_enabled": True,
            "daily_limit": 50,
            "quiet_hours": {
                "enabled": True,
                "start": 23,
                "end": 7,
            },
        }

        result = format_user_settings(settings)

        assert "23:00" in result
        assert "7:00" in result


# =============================================================================
# Test NOTIFICATION_TYPES constant
# =============================================================================


class TestNotificationTypes:
    """Tests for NOTIFICATION_TYPES constant."""

    def test_notification_types_exists(self) -> None:
        """Test NOTIFICATION_TYPES constant exists."""
        from src.telegram_bot.notifications.formatters import NOTIFICATION_TYPES

        assert isinstance(NOTIFICATION_TYPES, dict)

    def test_notification_types_has_price_drop(self) -> None:
        """Test NOTIFICATION_TYPES has price_drop."""
        from src.telegram_bot.notifications.formatters import NOTIFICATION_TYPES

        assert "price_drop" in NOTIFICATION_TYPES

    def test_notification_types_has_price_rise(self) -> None:
        """Test NOTIFICATION_TYPES has price_rise."""
        from src.telegram_bot.notifications.formatters import NOTIFICATION_TYPES

        assert "price_rise" in NOTIFICATION_TYPES

    def test_notification_types_has_buy_success(self) -> None:
        """Test NOTIFICATION_TYPES has buy_success."""
        from src.telegram_bot.notifications.formatters import NOTIFICATION_TYPES

        assert "buy_success" in NOTIFICATION_TYPES

    def test_notification_types_values_are_strings(self) -> None:
        """Test all NOTIFICATION_TYPES values are strings."""
        from src.telegram_bot.notifications.formatters import NOTIFICATION_TYPES

        for key, value in NOTIFICATION_TYPES.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


# =============================================================================
# Module exports test
# =============================================================================


class TestFormattersModuleExports:
    """Tests for module exports."""

    def test_module_exports_format_price(self) -> None:
        """Test format_price is exported."""
        from src.telegram_bot.notifications.formatters import format_price

        assert callable(format_price)

    def test_module_exports_format_profit(self) -> None:
        """Test format_profit is exported."""
        from src.telegram_bot.notifications.formatters import format_profit

        assert callable(format_profit)

    def test_module_exports_format_item_brief(self) -> None:
        """Test format_item_brief is exported."""
        from src.telegram_bot.notifications.formatters import format_item_brief

        assert callable(format_item_brief)

    def test_module_exports_format_alert_message(self) -> None:
        """Test format_alert_message is exported."""
        from src.telegram_bot.notifications.formatters import format_alert_message

        assert callable(format_alert_message)

    def test_all_exports(self) -> None:
        """Test __all__ exports correct functions."""
        from src.telegram_bot.notifications import formatters

        expected = [
            "format_alert_message",
            "format_item_brief",
            "format_price",
            "format_profit",
        ]

        for name in expected:
            assert hasattr(formatters, name)
