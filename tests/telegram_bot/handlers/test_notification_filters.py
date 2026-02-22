"""Unit tests for src/telegram_bot/handlers/notification_filters_handler.py.

Tests for notification filters including:
- NotificationFilters class
- User filter management
- Filter condition checking
- Telegram handlers for filter configuration
"""


class TestNotificationFiltersConstants:
    """Tests for notification filter constants."""

    def test_supported_games_defined(self):
        """Test supported games are properly defined."""
        from src.telegram_bot.handlers.notification_filters_handler import SUPPORTED_GAMES

        assert isinstance(SUPPORTED_GAMES, dict)
        assert "csgo" in SUPPORTED_GAMES
        assert "dota2" in SUPPORTED_GAMES
        assert "tf2" in SUPPORTED_GAMES
        assert "rust" in SUPPORTED_GAMES

    def test_arbitrage_levels_defined(self):
        """Test arbitrage levels are properly defined."""
        from src.telegram_bot.handlers.notification_filters_handler import ARBITRAGE_LEVELS

        assert isinstance(ARBITRAGE_LEVELS, dict)
        assert "boost" in ARBITRAGE_LEVELS
        assert "standard" in ARBITRAGE_LEVELS
        assert "medium" in ARBITRAGE_LEVELS
        assert "advanced" in ARBITRAGE_LEVELS
        assert "pro" in ARBITRAGE_LEVELS

    def test_notification_types_defined(self):
        """Test notification types are properly defined."""
        from src.telegram_bot.handlers.notification_filters_handler import NOTIFICATION_TYPES

        assert isinstance(NOTIFICATION_TYPES, dict)
        assert "arbitrage" in NOTIFICATION_TYPES
        assert "target_filled" in NOTIFICATION_TYPES
        assert "price_alert" in NOTIFICATION_TYPES
        assert "market_trend" in NOTIFICATION_TYPES


class TestNotificationFiltersClass:
    """Tests for NotificationFilters class."""

    def test_init(self):
        """Test NotificationFilters initialization."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        assert filters._filters == {}

    def test_get_user_filters_new_user(self):
        """Test getting filters for new user returns defaults."""
        from src.telegram_bot.handlers.notification_filters_handler import (
            ARBITRAGE_LEVELS,
            NOTIFICATION_TYPES,
            SUPPORTED_GAMES,
            NotificationFilters,
        )

        filters = NotificationFilters()
        user_filters = filters.get_user_filters(123456)

        assert "games" in user_filters
        assert set(user_filters["games"]) == set(SUPPORTED_GAMES.keys())
        assert user_filters["min_profit_percent"] == 5.0
        assert set(user_filters["levels"]) == set(ARBITRAGE_LEVELS.keys())
        assert set(user_filters["notification_types"]) == set(NOTIFICATION_TYPES.keys())
        assert user_filters["enabled"] is True

    def test_get_user_filters_existing_user(self):
        """Test getting filters for existing user returns their filters."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        # Set custom filters
        filters._filters[123456] = {
            "games": ["csgo"],
            "min_profit_percent": 10.0,
            "levels": ["pro"],
            "notification_types": ["arbitrage"],
            "enabled": True,
        }

        user_filters = filters.get_user_filters(123456)

        assert user_filters["games"] == ["csgo"]
        assert user_filters["min_profit_percent"] == 10.0
        assert user_filters["levels"] == ["pro"]

    def test_get_user_filters_returns_copy(self):
        """Test getting filters returns a copy, not reference."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        user_filters_1 = filters.get_user_filters(123456)
        user_filters_2 = filters.get_user_filters(123456)

        # Modify one
        user_filters_1["games"] = ["csgo"]

        # Original should be unchanged
        assert len(user_filters_2["games"]) > 1

    def test_update_user_filters_new_user(self):
        """Test updating filters for new user."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        new_settings = {"min_profit_percent": 15.0}
        filters.update_user_filters(123456, new_settings)

        user_filters = filters.get_user_filters(123456)
        assert user_filters["min_profit_percent"] == 15.0

    def test_update_user_filters_existing_user(self):
        """Test updating filters for existing user."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        # Initial filters
        filters.get_user_filters(123456)

        # Update
        filters.update_user_filters(123456, {"games": ["csgo", "dota2"]})

        user_filters = filters.get_user_filters(123456)
        assert user_filters["games"] == ["csgo", "dota2"]
        # Other settings should remain
        assert "min_profit_percent" in user_filters

    def test_reset_user_filters(self):
        """Test resetting user filters to defaults."""
        from src.telegram_bot.handlers.notification_filters_handler import (
            SUPPORTED_GAMES,
            NotificationFilters,
        )

        filters = NotificationFilters()

        # Set custom filters
        filters.update_user_filters(
            123456,
            {
                "games": ["csgo"],
                "min_profit_percent": 20.0,
            },
        )

        # Reset
        filters.reset_user_filters(123456)

        user_filters = filters.get_user_filters(123456)
        assert set(user_filters["games"]) == set(SUPPORTED_GAMES.keys())
        assert user_filters["min_profit_percent"] == 5.0


class TestNotificationFiltersShouldNotify:
    """Tests for should_notify method."""

    def test_should_notify_all_conditions_met(self):
        """Test notification sent when all conditions met."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is True

    def test_should_notify_disabled_filters(self):
        """Test notification not sent when filters disabled."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"enabled": False})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_should_notify_game_not_selected(self):
        """Test notification not sent when game not in filter."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"games": ["dota2"]})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_should_notify_profit_too_low(self):
        """Test notification not sent when profit below minimum."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"min_profit_percent": 15.0})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_should_notify_level_not_selected(self):
        """Test notification not sent when level not in filter."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"levels": ["pro", "advanced"]})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="boost",
            notification_type="arbitrage",
        )

        assert result is False

    def test_should_notify_type_not_selected(self):
        """Test notification not sent when type not in filter."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"notification_types": ["arbitrage"]})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="price_drop",
        )

        assert result is False


class TestNotificationFiltersDefaultFilters:
    """Tests for default filter values."""

    def test_default_filters_structure(self):
        """Test default filters have correct structure."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        defaults = filters._get_default_filters()

        assert "games" in defaults
        assert "min_profit_percent" in defaults
        assert "levels" in defaults
        assert "notification_types" in defaults
        assert "enabled" in defaults

    def test_default_filters_values(self):
        """Test default filter values are correct."""
        from src.telegram_bot.handlers.notification_filters_handler import (
            ARBITRAGE_LEVELS,
            NOTIFICATION_TYPES,
            SUPPORTED_GAMES,
            NotificationFilters,
        )

        filters = NotificationFilters()
        defaults = filters._get_default_filters()

        # All games enabled by default
        assert len(defaults["games"]) == len(SUPPORTED_GAMES)

        # All levels enabled by default
        assert len(defaults["levels"]) == len(ARBITRAGE_LEVELS)

        # All notification types enabled by default
        assert len(defaults["notification_types"]) == len(NOTIFICATION_TYPES)

        # Default profit threshold
        assert defaults["min_profit_percent"] == 5.0

        # Enabled by default
        assert defaults["enabled"] is True


class TestNotificationFiltersEdgeCases:
    """Tests for edge cases in notification filtering."""

    def test_empty_games_list(self):
        """Test with empty games list."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"games": []})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_empty_levels_list(self):
        """Test with empty levels list."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"levels": []})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_zero_profit_threshold(self):
        """Test with zero profit threshold."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()
        filters.update_user_filters(123456, {"min_profit_percent": 0})

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=0.5,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is True

    def test_negative_profit(self):
        """Test with negative profit value."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        result = filters.should_notify(
            user_id=123456,
            game="csgo",
            profit_percent=-5.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_unknown_game(self):
        """Test with unknown game."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        result = filters.should_notify(
            user_id=123456,
            game="unknown_game",
            profit_percent=10.0,
            level="standard",
            notification_type="arbitrage",
        )

        assert result is False

    def test_multiple_users_isolation(self):
        """Test that filters for different users are isolated."""
        from src.telegram_bot.handlers.notification_filters_handler import NotificationFilters

        filters = NotificationFilters()

        # User 1 - only csgo
        filters.update_user_filters(111, {"games": ["csgo"]})

        # User 2 - only dota2
        filters.update_user_filters(222, {"games": ["dota2"]})

        # User 1 should get csgo notification
        assert filters.should_notify(111, "csgo", 10.0, "standard", "arbitrage") is True
        assert filters.should_notify(111, "dota2", 10.0, "standard", "arbitrage") is False

        # User 2 should get dota2 notification
        assert filters.should_notify(222, "csgo", 10.0, "standard", "arbitrage") is False
        assert filters.should_notify(222, "dota2", 10.0, "standard", "arbitrage") is True
