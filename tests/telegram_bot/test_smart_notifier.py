"""Tests for telegram_bot smart_notifier module (facade)."""

import warnings


class TestSmartNotifierImports:
    """Tests for smart_notifier imports and deprecation warnings."""

    def test_deprecation_warning_on_import(self):
        """Test that importing smart_notifier emits deprecation warning."""
        # Clear any cached import
        import importlib
        import sys

        # Remove module and its parent from cache to force re-import
        modules_to_remove = [
            key for key in sys.modules.keys()
            if "smart_notifier" in key
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Import the module - this should trigger deprecation warning
            import src.telegram_bot.smart_notifier  # noqa: F401
            importlib.reload(src.telegram_bot.smart_notifier)

            # Verify deprecation warning was issued
            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1, f"Expected deprecation warning, got: {[str(w.message) for w in w]}"

    def test_exports_constants(self):
        """Test that module exports required constants."""
        from src.telegram_bot.smart_notifier import (
            DATA_DIR,
            DEFAULT_COOLDOWN,
            NOTIFICATION_TYPES,
            SMART_ALERTS_FILE,
        )

        assert DATA_DIR is not None
        assert DEFAULT_COOLDOWN is not None
        assert NOTIFICATION_TYPES is not None
        assert SMART_ALERTS_FILE is not None

    def test_exports_preference_functions(self):
        """Test that module exports preference functions."""
        from src.telegram_bot.smart_notifier import (
            get_user_preferences,
            load_user_preferences,
            register_user,
            save_user_preferences,
            update_user_preferences,
        )

        assert callable(load_user_preferences)
        assert callable(save_user_preferences)
        assert callable(register_user)
        assert callable(update_user_preferences)
        assert callable(get_user_preferences)

    def test_exports_alert_functions(self):
        """Test that module exports alert functions."""
        from src.telegram_bot.smart_notifier import (
            create_alert,
            deactivate_alert,
            get_active_alerts,
            get_user_alerts,
        )

        assert callable(create_alert)
        assert callable(deactivate_alert)
        assert callable(get_user_alerts)
        assert callable(get_active_alerts)

    def test_exports_checker_functions(self):
        """Test that module exports checker functions."""
        from src.telegram_bot.smart_notifier import (
            check_market_opportunities,
            check_price_alerts,
        )

        assert callable(check_price_alerts)
        assert callable(check_market_opportunities)

    def test_exports_throttling_functions(self):
        """Test that module exports throttling functions."""
        from src.telegram_bot.smart_notifier import (
            record_notification,
            should_throttle_notification,
        )

        assert callable(should_throttle_notification)
        assert callable(record_notification)

    def test_exports_sender_functions(self):
        """Test that module exports sender functions."""
        from src.telegram_bot.smart_notifier import (
            notify_user,
            send_market_opportunity_notification,
            send_price_alert_notification,
        )

        assert callable(send_price_alert_notification)
        assert callable(send_market_opportunity_notification)
        assert callable(notify_user)

    def test_exports_handler_functions(self):
        """Test that module exports handler functions."""
        from src.telegram_bot.smart_notifier import (
            handle_notification_callback,
            register_notification_handlers,
        )

        assert callable(handle_notification_callback)
        assert callable(register_notification_handlers)

    def test_exports_utility_functions(self):
        """Test that module exports utility functions."""
        from src.telegram_bot.smart_notifier import (
            get_item_by_id,
            get_item_price,
            get_market_data_for_items,
            get_market_items_for_game,
            get_price_history_for_items,
        )

        assert callable(get_market_data_for_items)
        assert callable(get_item_by_id)
        assert callable(get_market_items_for_game)
        assert callable(get_price_history_for_items)
        assert callable(get_item_price)

    def test_exports_main_function(self):
        """Test that module exports main function."""
        from src.telegram_bot.smart_notifier import start_notification_checker

        assert callable(start_notification_checker)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from src.telegram_bot import smart_notifier

        expected_exports = [
            "DATA_DIR",
            "DEFAULT_COOLDOWN",
            "NOTIFICATION_TYPES",
            "SMART_ALERTS_FILE",
            "load_user_preferences",
            "save_user_preferences",
            "register_user",
            "update_user_preferences",
            "create_alert",
            "deactivate_alert",
            "get_user_alerts",
            "check_price_alerts",
            "check_market_opportunities",
            "should_throttle_notification",
            "record_notification",
            "send_price_alert_notification",
            "send_market_opportunity_notification",
            "notify_user",
            "handle_notification_callback",
            "register_notification_handlers",
            "get_market_data_for_items",
            "get_item_by_id",
            "get_market_items_for_game",
            "get_price_history_for_items",
            "get_item_price",
            "start_notification_checker",
        ]

        for export in expected_exports:
            assert export in smart_notifier.__all__, f"{export} not in __all__"


class TestSmartNotifierFunctionality:
    """Tests for smart_notifier actual functionality."""

    def test_get_user_preferences_returns_dict(self):
        """Test that get_user_preferences returns a dict."""
        from src.telegram_bot.smart_notifier import get_user_preferences

        result = get_user_preferences()
        assert isinstance(result, dict)

    def test_get_active_alerts_returns_dict(self):
        """Test that get_active_alerts returns a dict."""
        from src.telegram_bot.smart_notifier import get_active_alerts

        result = get_active_alerts()
        assert isinstance(result, dict)

    def test_notification_types_structure(self):
        """Test NOTIFICATION_TYPES has expected structure."""
        from src.telegram_bot.smart_notifier import NOTIFICATION_TYPES

        assert isinstance(NOTIFICATION_TYPES, (dict, list, set))

    def test_default_cooldown_is_positive(self):
        """Test DEFAULT_COOLDOWN is a positive value or dict with positive values."""
        from src.telegram_bot.smart_notifier import DEFAULT_COOLDOWN

        if isinstance(DEFAULT_COOLDOWN, (int, float)):
            assert DEFAULT_COOLDOWN > 0
        elif isinstance(DEFAULT_COOLDOWN, dict):
            # DEFAULT_COOLDOWN is a dict with cooldown values per notification type
            assert len(DEFAULT_COOLDOWN) > 0
            for value in DEFAULT_COOLDOWN.values():
                assert value > 0
        else:
            assert DEFAULT_COOLDOWN is not None
