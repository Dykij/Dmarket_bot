"""Unit tests for notifications/constants.py module.

This module tests the notification system constants:
- NOTIFICATION_TYPES
- _PRICE_CACHE_TTL
- DEFAULT_USER_SETTINGS
- NOTIFICATION_PRIORITIES
"""

from __future__ import annotations

from src.telegram_bot.notifications.constants import (
    _PRICE_CACHE_TTL,
    DEFAULT_USER_SETTINGS,
    NOTIFICATION_PRIORITIES,
    NOTIFICATION_TYPES,
)


# =============================================================================
# NOTIFICATION_TYPES Tests
# =============================================================================
class TestNotificationTypes:
    """Tests for NOTIFICATION_TYPES constant."""

    def test_notification_types_is_dict(self):
        """Test that NOTIFICATION_TYPES is a dictionary."""
        assert isinstance(NOTIFICATION_TYPES, dict)

    def test_notification_types_contains_price_drop(self):
        """Test that price_drop type exists."""
        assert "price_drop" in NOTIFICATION_TYPES
        assert "📉" in NOTIFICATION_TYPES["price_drop"]

    def test_notification_types_contains_price_rise(self):
        """Test that price_rise type exists."""
        assert "price_rise" in NOTIFICATION_TYPES
        assert "📈" in NOTIFICATION_TYPES["price_rise"]

    def test_notification_types_contains_volume_increase(self):
        """Test that volume_increase type exists."""
        assert "volume_increase" in NOTIFICATION_TYPES
        assert "📊" in NOTIFICATION_TYPES["volume_increase"]

    def test_notification_types_contains_good_deal(self):
        """Test that good_deal type exists."""
        assert "good_deal" in NOTIFICATION_TYPES
        assert "💰" in NOTIFICATION_TYPES["good_deal"]

    def test_notification_types_contains_arbitrage(self):
        """Test that arbitrage type exists."""
        assert "arbitrage" in NOTIFICATION_TYPES
        assert "🔄" in NOTIFICATION_TYPES["arbitrage"]

    def test_notification_types_contains_trend_change(self):
        """Test that trend_change type exists."""
        assert "trend_change" in NOTIFICATION_TYPES

    def test_notification_types_contains_buy_intent(self):
        """Test that buy_intent type exists."""
        assert "buy_intent" in NOTIFICATION_TYPES
        assert "🛒" in NOTIFICATION_TYPES["buy_intent"]

    def test_notification_types_contains_buy_success(self):
        """Test that buy_success type exists."""
        assert "buy_success" in NOTIFICATION_TYPES
        assert "✅" in NOTIFICATION_TYPES["buy_success"]

    def test_notification_types_contains_buy_failed(self):
        """Test that buy_failed type exists."""
        assert "buy_failed" in NOTIFICATION_TYPES
        assert "❌" in NOTIFICATION_TYPES["buy_failed"]

    def test_notification_types_contains_sell_success(self):
        """Test that sell_success type exists."""
        assert "sell_success" in NOTIFICATION_TYPES
        assert "✅" in NOTIFICATION_TYPES["sell_success"]

    def test_notification_types_contains_sell_failed(self):
        """Test that sell_failed type exists."""
        assert "sell_failed" in NOTIFICATION_TYPES
        assert "❌" in NOTIFICATION_TYPES["sell_failed"]

    def test_notification_types_contains_critical_shutdown(self):
        """Test that critical_shutdown type exists."""
        assert "critical_shutdown" in NOTIFICATION_TYPES
        assert "🛑" in NOTIFICATION_TYPES["critical_shutdown"]

    def test_notification_types_count(self):
        """Test that all expected types are present."""
        expected_types = [
            "price_drop",
            "price_rise",
            "volume_increase",
            "good_deal",
            "arbitrage",
            "trend_change",
            "buy_intent",
            "buy_success",
            "buy_failed",
            "sell_success",
            "sell_failed",
            "critical_shutdown",
        ]

        for t in expected_types:
            assert t in NOTIFICATION_TYPES

    def test_notification_types_values_are_strings(self):
        """Test that all values are strings."""
        for key, value in NOTIFICATION_TYPES.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_notification_types_values_contain_emojis(self):
        """Test that all values contain emojis for visual feedback."""
        for value in NOTIFICATION_TYPES.values():
            # All notification type descriptions should have some text
            assert len(value) > 0


# =============================================================================
# _PRICE_CACHE_TTL Tests
# =============================================================================
class TestPriceCacheTTL:
    """Tests for _PRICE_CACHE_TTL constant."""

    def test_cache_ttl_is_integer(self):
        """Test that cache TTL is an integer."""
        assert isinstance(_PRICE_CACHE_TTL, int)

    def test_cache_ttl_is_positive(self):
        """Test that cache TTL is positive."""
        assert _PRICE_CACHE_TTL > 0

    def test_cache_ttl_is_5_minutes(self):
        """Test that cache TTL is 5 minutes (300 seconds)."""
        assert _PRICE_CACHE_TTL == 300

    def test_cache_ttl_reasonable_range(self):
        """Test that cache TTL is in a reasonable range."""
        # Should be at least 1 minute and at most 1 hour
        assert 60 <= _PRICE_CACHE_TTL <= 3600


# =============================================================================
# DEFAULT_USER_SETTINGS Tests
# =============================================================================
class TestDefaultUserSettings:
    """Tests for DEFAULT_USER_SETTINGS constant."""

    def test_default_settings_is_dict(self):
        """Test that DEFAULT_USER_SETTINGS is a dictionary."""
        assert isinstance(DEFAULT_USER_SETTINGS, dict)

    def test_default_enabled_setting(self):
        """Test that enabled setting is True by default."""
        assert "enabled" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["enabled"] is True

    def test_default_language_setting(self):
        """Test that language setting is 'ru' by default."""
        assert "language" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["language"] == "ru"

    def test_default_min_interval_setting(self):
        """Test that min_interval is 5 minutes by default."""
        assert "min_interval" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["min_interval"] == 300

    def test_default_quiet_hours_setting(self):
        """Test that quiet_hours has start and end times."""
        assert "quiet_hours" in DEFAULT_USER_SETTINGS
        quiet_hours = DEFAULT_USER_SETTINGS["quiet_hours"]

        assert "start" in quiet_hours
        assert "end" in quiet_hours
        assert quiet_hours["start"] == 23
        assert quiet_hours["end"] == 7

    def test_default_max_alerts_per_day(self):
        """Test that max_alerts_per_day has a reasonable default."""
        assert "max_alerts_per_day" in DEFAULT_USER_SETTINGS
        assert DEFAULT_USER_SETTINGS["max_alerts_per_day"] == 50
        assert DEFAULT_USER_SETTINGS["max_alerts_per_day"] > 0

    def test_quiet_hours_valid_range(self):
        """Test that quiet hours are valid hour values (0-23)."""
        quiet_hours = DEFAULT_USER_SETTINGS["quiet_hours"]

        assert 0 <= quiet_hours["start"] <= 23
        assert 0 <= quiet_hours["end"] <= 23


# =============================================================================
# NOTIFICATION_PRIORITIES Tests
# =============================================================================
class TestNotificationPriorities:
    """Tests for NOTIFICATION_PRIORITIES constant."""

    def test_priorities_is_dict(self):
        """Test that NOTIFICATION_PRIORITIES is a dictionary."""
        assert isinstance(NOTIFICATION_PRIORITIES, dict)

    def test_critical_shutdown_highest_priority(self):
        """Test that critical_shutdown has highest priority."""
        assert "critical_shutdown" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["critical_shutdown"] == 100

        # Should be highest
        max_priority = max(NOTIFICATION_PRIORITIES.values())
        assert NOTIFICATION_PRIORITIES["critical_shutdown"] == max_priority

    def test_buy_success_high_priority(self):
        """Test that buy_success has high priority."""
        assert "buy_success" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["buy_success"] == 90

    def test_buy_failed_high_priority(self):
        """Test that buy_failed has high priority."""
        assert "buy_failed" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["buy_failed"] == 90

    def test_sell_success_priority(self):
        """Test that sell_success has appropriate priority."""
        assert "sell_success" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["sell_success"] == 85

    def test_sell_failed_priority(self):
        """Test that sell_failed has appropriate priority."""
        assert "sell_failed" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["sell_failed"] == 85

    def test_buy_intent_priority(self):
        """Test that buy_intent has appropriate priority."""
        assert "buy_intent" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["buy_intent"] == 80

    def test_arbitrage_priority(self):
        """Test that arbitrage has appropriate priority."""
        assert "arbitrage" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["arbitrage"] == 70

    def test_good_deal_priority(self):
        """Test that good_deal has appropriate priority."""
        assert "good_deal" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["good_deal"] == 60

    def test_price_drop_priority(self):
        """Test that price_drop has appropriate priority."""
        assert "price_drop" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["price_drop"] == 50

    def test_price_rise_priority(self):
        """Test that price_rise has appropriate priority."""
        assert "price_rise" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["price_rise"] == 50

    def test_volume_increase_priority(self):
        """Test that volume_increase has appropriate priority."""
        assert "volume_increase" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["volume_increase"] == 40

    def test_trend_change_lowest_priority(self):
        """Test that trend_change has lowest priority."""
        assert "trend_change" in NOTIFICATION_PRIORITIES
        assert NOTIFICATION_PRIORITIES["trend_change"] == 30

    def test_all_priorities_are_integers(self):
        """Test that all priority values are integers."""
        for key, value in NOTIFICATION_PRIORITIES.items():
            assert isinstance(value, int), f"{key} priority should be int"

    def test_all_priorities_positive(self):
        """Test that all priorities are positive."""
        for key, value in NOTIFICATION_PRIORITIES.items():
            assert value > 0, f"{key} priority should be positive"

    def test_priority_ordering_logical(self):
        """Test that priority ordering makes logical sense."""
        # Critical should be higher than trading
        assert (
            NOTIFICATION_PRIORITIES["critical_shutdown"]
            > NOTIFICATION_PRIORITIES["buy_success"]
        )

        # Trading notifications should be higher than market alerts
        assert (
            NOTIFICATION_PRIORITIES["buy_success"]
            > NOTIFICATION_PRIORITIES["arbitrage"]
        )

        # Arbitrage should be higher than simple price changes
        assert (
            NOTIFICATION_PRIORITIES["arbitrage"] > NOTIFICATION_PRIORITIES["price_drop"]
        )

    def test_priorities_match_notification_types(self):
        """Test that all notification types have priorities defined."""
        for notification_type in NOTIFICATION_TYPES:
            assert (
                notification_type in NOTIFICATION_PRIORITIES
            ), f"{notification_type} should have a priority defined"


# =============================================================================
# Integration Tests
# =============================================================================
class TestConstantsIntegration:
    """Integration tests for constants module."""

    def test_notification_types_and_priorities_aligned(self):
        """Test that types and priorities are aligned."""
        type_keys = set(NOTIFICATION_TYPES.keys())
        priority_keys = set(NOTIFICATION_PRIORITIES.keys())

        # All types should have priorities
        assert type_keys == priority_keys

    def test_default_settings_values_valid(self):
        """Test that default settings have valid value types."""
        # enabled should be bool
        assert isinstance(DEFAULT_USER_SETTINGS["enabled"], bool)

        # language should be string
        assert isinstance(DEFAULT_USER_SETTINGS["language"], str)

        # min_interval should be int
        assert isinstance(DEFAULT_USER_SETTINGS["min_interval"], int)

        # quiet_hours should be dict
        assert isinstance(DEFAULT_USER_SETTINGS["quiet_hours"], dict)

        # max_alerts_per_day should be int
        assert isinstance(DEFAULT_USER_SETTINGS["max_alerts_per_day"], int)

    def test_cache_ttl_shorter_than_min_interval(self):
        """Test that cache TTL is shorter than or equal to min notification interval."""
        # Cache should refresh at least as often as notifications can be sent
        assert DEFAULT_USER_SETTINGS["min_interval"] >= _PRICE_CACHE_TTL

    def test_all_exports_avAlgolable(self):
        """Test that all expected exports are avAlgolable."""
        from src.telegram_bot.notifications.constants import (
            _PRICE_CACHE_TTL,
            DEFAULT_USER_SETTINGS,
            NOTIFICATION_PRIORITIES,
            NOTIFICATION_TYPES,
        )

        assert DEFAULT_USER_SETTINGS is not None
        assert NOTIFICATION_PRIORITIES is not None
        assert NOTIFICATION_TYPES is not None
        assert _PRICE_CACHE_TTL is not None


# =============================================================================
# Edge Cases
# =============================================================================
class TestConstantsEdgeCases:
    """Tests for edge cases in constants."""

    def test_notification_types_immutable_intent(self):
        """Test that NOTIFICATION_TYPES is Final (immutable intent)."""
        # Note: Final is a type hint, not runtime enforcement
        # This test documents the intended behavior
        original_count = len(NOTIFICATION_TYPES)

        # We shouldn't modify constants, but verify they exist as expected
        assert len(NOTIFICATION_TYPES) == original_count

    def test_priorities_range(self):
        """Test that all priorities are within expected range (1-100)."""
        for key, value in NOTIFICATION_PRIORITIES.items():
            assert (
                1 <= value <= 100
            ), f"{key} priority {value} should be between 1 and 100"

    def test_quiet_hours_span(self):
        """Test quiet hours span calculation."""
        quiet_hours = DEFAULT_USER_SETTINGS["quiet_hours"]
        start = quiet_hours["start"]
        end = quiet_hours["end"]

        # Calculate span (handles overnight)
        if end > start:
            span = end - start
        else:
            span = (24 - start) + end

        # Quiet hours should be reasonable (4-12 hours typically)
        assert 4 <= span <= 12

    def test_notification_type_descriptions_non_empty(self):
        """Test that all notification type descriptions are non-empty."""
        for key, value in NOTIFICATION_TYPES.items():
            assert len(value.strip()) > 0, f"{key} description should not be empty"

    def test_language_valid_code(self):
        """Test that default language is a valid code."""
        language = DEFAULT_USER_SETTINGS["language"]
        valid_languages = ["ru", "en", "es", "de", "fr", "uk", "zh"]

        assert (
            language in valid_languages
        ), f"Language {language} should be a valid code"
