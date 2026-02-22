"""Alert management for smart notifications."""

import logging
import uuid
from datetime import datetime
from typing import Any

from src.telegram_bot.smart_notifications.preferences import (
    get_active_alerts,
    get_user_preferences,
    register_user,
    save_user_preferences,
)

logger = logging.getLogger(__name__)


async def create_alert(
    user_id: int,
    alert_type: str,
    item_id: str | None = None,
    item_name: str | None = None,
    game: str = "csgo",
    conditions: dict[str, Any] | None = None,
    one_time: bool = False,
) -> str:
    """Create a new alert for a user.

    Args:
        user_id: Telegram user ID
        alert_type: Type of alert (price_alert, trend_alert, etc.)
        item_id: Optional DMarket item ID
        item_name: Optional item name
        game: Game code (csgo, dota2, tf2, rust)
        conditions: Dictionary of alert conditions
        one_time: Whether the alert should trigger only once

    Returns:
        Alert ID
    """
    active_alerts = get_active_alerts()
    user_preferences = get_user_preferences()
    user_id_str = str(user_id)

    # Register if not already registered
    if user_id_str not in user_preferences:
        await register_user(user_id)

    # Generate alert ID
    alert_id = str(uuid.uuid4())

    # Create alert data
    alert_data = {
        "id": alert_id,
        "user_id": user_id_str,
        "type": alert_type,
        "item_id": item_id,
        "item_name": item_name,
        "game": game,
        "conditions": conditions or {},
        "one_time": one_time,
        "created_at": datetime.now().timestamp(),
        "last_triggered": None,
        "trigger_count": 0,
        "active": True,
    }

    # Add to active alerts
    if user_id_str not in active_alerts:
        active_alerts[user_id_str] = []

    active_alerts[user_id_str].append(alert_data)

    save_user_preferences()
    logger.info(
        f"Created {alert_type} alert for user {user_id} on {item_name or 'market conditions'}"
    )

    return alert_id


async def deactivate_alert(user_id: int, alert_id: str) -> bool:
    """Deactivate an alert for a user.

    Args:
        user_id: Telegram user ID
        alert_id: Alert ID to deactivate

    Returns:
        True if successful, False otherwise
    """
    active_alerts = get_active_alerts()
    user_id_str = str(user_id)

    if user_id_str not in active_alerts:
        return False

    for alert in active_alerts[user_id_str]:
        if alert["id"] == alert_id:
            alert["active"] = False
            save_user_preferences()
            logger.debug(f"Deactivated alert {alert_id} for user {user_id}")
            return True

    return False


async def get_user_alerts(user_id: int) -> list[dict[str, Any]]:
    """Get a user's active alerts.

    Args:
        user_id: Telegram user ID

    Returns:
        List of active alerts
    """
    active_alerts = get_active_alerts()
    user_id_str = str(user_id)

    if user_id_str not in active_alerts:
        return []

    return [alert for alert in active_alerts[user_id_str] if alert["active"]]
