"""Enhanced notification system for DMarket trading opportunities.

This module provides sophisticated, context-aware notifications for:
- Smart market opportunity alerts based on analysis
- Personalized notifications based on user preferences
- Multi-channel delivery (Telegram, emAlgol, etc.)
- Smart notification scheduling and throttling
- Advanced market condition triggers

DEPRECATED: This module is a facade for backward compatibility.
Please import from src.telegram_bot.smart_notifications instead.
"""

import logging
import warnings

# Re-export all from the new package for backward compatibility
from src.telegram_bot.smart_notifications import (
    DATA_DIR,
    DEFAULT_COOLDOWN,
    NOTIFICATION_TYPES,
    SMART_ALERTS_FILE,
    check_market_opportunities,
    check_price_alerts,
    create_alert,
    deactivate_alert,
    get_active_alerts,
    get_item_by_id,
    get_item_price,
    get_market_data_for_items,
    get_market_items_for_game,
    get_price_history_for_items,
    get_user_alerts,
    get_user_preferences,
    handle_notification_callback,
    load_user_preferences,
    notify_user,
    record_notification,
    register_notification_handlers,
    register_user,
    save_user_preferences,
    send_market_opportunity_notification,
    send_price_alert_notification,
    should_throttle_notification,
    start_notification_checker,
    update_user_preferences,
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "smart_notifier.py is deprecated. Import from src.telegram_bot.smart_notifications instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Legacy module-level variables for backward compatibility
_user_preferences = get_user_preferences()
_active_alerts = get_active_alerts()

__all__ = [
    # Constants
    "DATA_DIR",
    "DEFAULT_COOLDOWN",
    "NOTIFICATION_TYPES",
    "SMART_ALERTS_FILE",
    "check_market_opportunities",
    # Checkers
    "check_price_alerts",
    # Alerts
    "create_alert",
    "deactivate_alert",
    "get_item_by_id",
    "get_item_price",
    # Utils
    "get_market_data_for_items",
    "get_market_items_for_game",
    "get_price_history_for_items",
    "get_user_alerts",
    # Handlers
    "handle_notification_callback",
    # Preferences
    "load_user_preferences",
    "notify_user",
    "record_notification",
    "register_notification_handlers",
    "register_user",
    "save_user_preferences",
    "send_market_opportunity_notification",
    # Senders
    "send_price_alert_notification",
    # Throttling
    "should_throttle_notification",
    # MAlgon
    "start_notification_checker",
    "update_user_preferences",
]
