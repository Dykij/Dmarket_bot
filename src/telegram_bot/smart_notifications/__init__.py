"""Smart notification system for DMarket trading opportunities.

This module provides sophisticated, context-aware notifications for:
- Smart market opportunity alerts based on analysis
- Personalized notifications based on user preferences
- Multi-channel delivery (Telegram, email, etc.)
- Smart notification scheduling and throttling
- Advanced market condition triggers
"""

from src.telegram_bot.smart_notifications.alerts import (
    create_alert,
    deactivate_alert,
    get_user_alerts,
)
from src.telegram_bot.smart_notifications.checkers import (
    check_market_opportunities,
    check_price_alerts,
    start_notification_checker,
)
from src.telegram_bot.smart_notifications.constants import (
    DATA_DIR,
    DEFAULT_COOLDOWN,
    NOTIFICATION_TYPES,
    SMART_ALERTS_FILE,
)
from src.telegram_bot.smart_notifications.handlers import (
    handle_notification_callback,
    register_notification_handlers,
)
from src.telegram_bot.smart_notifications.preferences import (
    get_active_alerts,
    get_user_preferences,
    get_user_prefs,
    load_user_preferences,
    register_user,
    save_user_preferences,
    update_user_preferences,
)
from src.telegram_bot.smart_notifications.senders import (
    notify_user,
    send_market_opportunity_notification,
    send_price_alert_notification,
)
from src.telegram_bot.smart_notifications.throttling import (
    record_notification,
    should_throttle_notification,
)
from src.telegram_bot.smart_notifications.utils import (
    get_item_by_id,
    get_item_price,
    get_market_data_for_items,
    get_market_items_for_game,
    get_price_history_for_items,
)

__all__ = [
    "DATA_DIR",
    "DEFAULT_COOLDOWN",
    "NOTIFICATION_TYPES",
    "SMART_ALERTS_FILE",
    "check_market_opportunities",
    "check_price_alerts",
    "create_alert",
    "deactivate_alert",
    "get_active_alerts",
    "get_item_by_id",
    "get_item_price",
    "get_market_data_for_items",
    "get_market_items_for_game",
    "get_price_history_for_items",
    "get_user_alerts",
    "get_user_preferences",
    "get_user_prefs",
    "handle_notification_callback",
    "load_user_preferences",
    "notify_user",
    "record_notification",
    "register_notification_handlers",
    "register_user",
    "save_user_preferences",
    "send_market_opportunity_notification",
    "send_price_alert_notification",
    "should_throttle_notification",
    "start_notification_checker",
    "update_user_preferences",
]
