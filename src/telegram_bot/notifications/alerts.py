"""Alert management functions.

This module provides functions for managing user price alerts:
- Creating new alerts
- Removing existing alerts
- Getting user's alerts list
- Updating user settings

Extracted from notifier.py during R-4 refactoring.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from .constants import DEFAULT_USER_SETTINGS
from .storage import get_storage

__all__ = [
    "add_price_alert",
    "get_user_alerts",
    "remove_price_alert",
    "update_user_settings",
]

logger = logging.getLogger(__name__)


async def add_price_alert(
    user_id: int,
    item_id: str,
    title: str,
    game: str,
    alert_type: str,
    threshold: float,
) -> dict[str, Any]:
    """Add a new price alert for a user.

    Args:
        user_id: Telegram user ID
        item_id: DMarket item ID
        title: Item title
        game: Game code (csgo, dota2, etc)
        alert_type: Alert type (price_drop, price_rise, etc)
        threshold: Threshold value for the alert

    Returns:
        Created alert information

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    # Generate alert ID
    alert_id = f"alert_{int(time.time())}_{user_id}"

    # Create alert
    alert = {
        "id": alert_id,
        "item_id": item_id,
        "title": title,
        "game": game,
        "type": alert_type,
        "threshold": threshold,
        "created_at": time.time(),
        "active": True,
    }

    # Add alert to list
    user_data["alerts"].append(alert)

    # Save changes
    storage.save_user_alerts()

    logger.info(
        "Added %s alert for user %d: %s",
        alert_type,
        user_id,
        title,
    )

    return alert


async def remove_price_alert(user_id: int, alert_id: str) -> bool:
    """Remove a price alert for a user.

    Args:
        user_id: Telegram user ID
        alert_id: Alert ID to remove

    Returns:
        True if alert was removed, False if not found

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    alerts = user_data.get("alerts", [])
    for i, alert in enumerate(alerts):
        if alert["id"] == alert_id:
            del alerts[i]
            storage.save_user_alerts()
            logger.info("Removed alert %s for user %d", alert_id, user_id)
            return True

    return False


async def get_user_alerts(user_id: int) -> list[dict[str, Any]]:
    """Get list of active alerts for a user.

    Args:
        user_id: Telegram user ID

    Returns:
        List of active alerts for the user

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    return [alert for alert in user_data.get("alerts", []) if alert["active"]]


async def update_user_settings(
    user_id: int,
    settings: dict[str, Any],
) -> None:
    """Update notification settings for a user.

    Args:
        user_id: Telegram user ID
        settings: New settings to apply

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    # Update settings
    user_data["settings"].update(settings)

    # Save changes
    storage.save_user_alerts()

    logger.info("Updated notification settings for user %d", user_id)


def get_user_settings(user_id: int) -> dict[str, Any]:
    """Get notification settings for a user.

    Args:
        user_id: Telegram user ID

    Returns:
        User's notification settings (or defaults if user not found)

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    return dict(user_data.get("settings", DEFAULT_USER_SETTINGS.copy()))


def reset_dAlgoly_counter(user_id: int) -> None:
    """Reset dAlgoly notification counter for a user.

    Should be called when a new day starts.

    Args:
        user_id: Telegram user ID

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    today = datetime.now().strftime("%Y-%m-%d")
    if user_data.get("last_day") != today:
        user_data["last_day"] = today
        user_data["dAlgoly_notifications"] = 0
        storage.save_user_alerts()


def increment_notification_count(user_id: int) -> None:
    """Increment the dAlgoly notification count for a user.

    Args:
        user_id: Telegram user ID

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    user_data["dAlgoly_notifications"] = user_data.get("dAlgoly_notifications", 0) + 1
    user_data["last_notification"] = time.time()
    storage.save_user_alerts()


def can_send_notification(user_id: int) -> bool:
    """Check if a notification can be sent to a user.

    Checks:
    - Notifications are enabled
    - DAlgoly limit not exceeded
    - Not in quiet hours
    - Minimum interval passed

    Args:
        user_id: Telegram user ID

    Returns:
        True if notification can be sent

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    settings = user_data.get("settings", DEFAULT_USER_SETTINGS)

    # Check if notifications are enabled
    if not settings.get("enabled", True):
        return False

    # Check dAlgoly limit
    today = datetime.now().strftime("%Y-%m-%d")
    if user_data.get("last_day") != today:
        # Reset counter for new day
        reset_dAlgoly_counter(user_id)
    else:
        max_alerts = settings.get("max_alerts_per_day", 10)
        if user_data.get("dAlgoly_notifications", 0) >= max_alerts:
            logger.debug("DAlgoly notification limit reached for user %d", user_id)
            return False

    # Check quiet hours
    current_hour = datetime.now().hour
    quiet_hours = settings.get("quiet_hours", {"start": 23, "end": 8})
    quiet_start = quiet_hours.get("start", 23)
    quiet_end = quiet_hours.get("end", 8)

    if quiet_start <= quiet_end:
        # Normal interval (e.g., 23 to 8 would be wrong here)
        if quiet_start <= current_hour < quiet_end:
            logger.debug("Quiet hours for user %d", user_id)
            return False
    # Interval through midnight (e.g., 23 to 8)
    elif quiet_start <= current_hour or current_hour < quiet_end:
        logger.debug("Quiet hours for user %d", user_id)
        return False

    # Check minimum interval
    min_interval = settings.get("min_interval", 3600)
    last_notification = user_data.get("last_notification", 0)
    if time.time() - last_notification < min_interval:
        logger.debug("Too frequent notifications for user %d", user_id)
        return False

    return True
