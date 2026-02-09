"""Throttling logic for smart notifications."""

import logging
import time
from datetime import datetime

from src.telegram_bot.smart_notifications.constants import DEFAULT_COOLDOWN
from src.telegram_bot.smart_notifications.preferences import (
    get_user_preferences,
    save_user_preferences,
)

logger = logging.getLogger(__name__)


async def should_throttle_notification(
    user_id: int,
    notification_type: str,
    item_id: str | None = None,
) -> bool:
    """Check if a notification should be throttled based on previous notifications.

    Args:
        user_id: Telegram user ID
        notification_type: Type of notification
        item_id: Optional item ID

    Returns:
        True if notification should be throttled, False otherwise
    """
    user_preferences = get_user_preferences()
    user_id_str = str(user_id)

    # Get user preferences
    prefs = user_preferences.get(user_id_str, {})
    frequency = prefs.get("frequency", "normal")

    # Get history key
    history_key = f"{notification_type}:{item_id}" if item_id else notification_type

    # Get cooldown period based on frequency
    base_cooldown = DEFAULT_COOLDOWN.get(notification_type, 3600)
    cooldown: float = float(base_cooldown)

    if frequency == "low":
        cooldown *= 2
    elif frequency == "high":
        cooldown /= 2

    # Check quiet hours
    now = datetime.now()
    quiet_hours = prefs.get("quiet_hours", {"start": 23, "end": 8})

    if quiet_hours["start"] <= now.hour < quiet_hours["end"]:
        return True  # Don't notify during quiet hours

    # Check last notification time
    last_notifications = prefs.get("last_notification", {})
    last_time = float(last_notifications.get(history_key, 0))

    return time.time() - last_time < cooldown  # Throttle notification


async def record_notification(
    user_id: int,
    notification_type: str,
    item_id: str | None = None,
) -> None:
    """Record that a notification was sent to a user.

    Args:
        user_id: Telegram user ID
        notification_type: Type of notification
        item_id: Optional item ID
    """
    user_preferences = get_user_preferences()
    user_id_str = str(user_id)

    if user_id_str not in user_preferences:
        return

    # Get history key
    history_key = f"{notification_type}:{item_id}" if item_id else notification_type

    # Update last notification time
    if "last_notification" not in user_preferences[user_id_str]:
        user_preferences[user_id_str]["last_notification"] = {}

    user_preferences[user_id_str]["last_notification"][history_key] = time.time()

    # Save changes
    save_user_preferences()
