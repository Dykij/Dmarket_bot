"""Notifications package for DMarket Telegram Bot.

This package provides a comprehensive notification system including:
- Price alerts with various trigger types
- Trading notifications (buy/sell success/failure)
- Alert storage and persistence
- Telegram command handlers for alert management
- Notification digests (grouping and batching)

Modules:
    constants: Notification types, priorities, and default settings
    storage: AlertStorage singleton for persistent alert data
    alerts: Alert management functions (add, remove, get, update)
    checker: Price checking and alert monitoring
    trading: Trading notification functions
    formatters: Message formatting utilities
    handlers: Telegram command and callback handlers
    digest: Notification digest system for spam reduction

Usage:
    from src.telegram_bot.notifications import (
        # Alert management
        add_price_alert,
        remove_price_alert,
        get_user_alerts,
        update_user_settings,
        get_user_settings,

        # Price checking
        check_price_alert,
        check_all_alerts,
        run_alerts_checker,

        # Trading notifications
        send_buy_intent_notification,
        send_buy_success_notification,
        send_sell_success_notification,

        # Notification digests
        NotificationDigest,
        Notification,
        NotificationCategory,
        NotificationPriority,

        # Handler registration
        register_notification_handlers,
    )
"""

from __future__ import annotations

# Alert management
from .alerts import (
    add_price_alert,
    can_send_notification,
    get_user_alerts,
    get_user_settings,
    increment_notification_count,
    remove_price_alert,
    reset_daily_counter,
    update_user_settings,
)

# Price checking
from .checker import (
    check_all_alerts,
    check_good_deal_alerts,
    check_price_alert,
    get_current_price,
    run_alerts_checker,
)

# Constants
from .constants import DEFAULT_USER_SETTINGS, NOTIFICATION_PRIORITIES, NOTIFICATION_TYPES

# Digest system
from .digest import Notification, NotificationCategory, NotificationDigest, NotificationPriority

# Formatters
from .formatters import (
    format_alert_message,
    format_alerts_list,
    format_item_brief,
    format_price,
    format_profit,
    format_user_settings,
)

# Handlers
from .handlers import (
    create_alert_command,
    handle_alert_callback,
    handle_buy_cancel_callback,
    list_alerts_command,
    register_notification_handlers,
    remove_alert_command,
    settings_command,
)

# Storage
from .storage import AlertStorage, get_storage, load_user_alerts, save_user_alerts

# Trading notifications
from .trading import (
    send_arbitrage_opportunity,
    send_buy_failed_notification,
    send_buy_intent_notification,
    send_buy_success_notification,
    send_crash_notification,
    send_critical_shutdown_notification,
    send_sell_success_notification,
)

__all__ = [
    "DEFAULT_USER_SETTINGS",
    "NOTIFICATION_PRIORITIES",
    # Constants
    "NOTIFICATION_TYPES",
    # Storage
    "AlertStorage",
    # Digest system
    "Notification",
    "NotificationCategory",
    "NotificationDigest",
    "NotificationPriority",
    # Alert management
    "add_price_alert",
    "can_send_notification",
    "check_all_alerts",
    "check_good_deal_alerts",
    "check_price_alert",
    "create_alert_command",
    "format_alert_message",
    "format_alerts_list",
    "format_item_brief",
    # Formatters
    "format_price",
    "format_profit",
    "format_user_settings",
    # Price checking
    "get_current_price",
    "get_storage",
    "get_user_alerts",
    "get_user_settings",
    "handle_alert_callback",
    # Handlers
    "handle_buy_cancel_callback",
    "increment_notification_count",
    "list_alerts_command",
    "load_user_alerts",
    "register_notification_handlers",
    "remove_alert_command",
    "remove_price_alert",
    "reset_daily_counter",
    "run_alerts_checker",
    "save_user_alerts",
    "send_arbitrage_opportunity",
    "send_buy_failed_notification",
    # Trading notifications
    "send_buy_intent_notification",
    "send_buy_success_notification",
    "send_crash_notification",
    "send_critical_shutdown_notification",
    "send_sell_success_notification",
    "settings_command",
    "update_user_settings",
]
