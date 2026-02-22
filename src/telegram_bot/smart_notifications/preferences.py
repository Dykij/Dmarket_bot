"""User preferences management for smart notifications."""

import json
import logging
from datetime import datetime
from typing import Any

from src.telegram_bot.smart_notifications.constants import (
    DATA_DIR,
    DEFAULT_USER_PREFERENCES,
    SMART_ALERTS_FILE,
)

logger = logging.getLogger(__name__)

# In-memory storage
_user_preferences: dict[str, dict[str, Any]] = {}
_active_alerts: dict[str, list[dict[str, Any]]] = {}


def get_user_preferences() -> dict[str, dict[str, Any]]:
    """Get all user preferences."""
    return _user_preferences


def get_active_alerts() -> dict[str, list[dict[str, Any]]]:
    """Get all active alerts."""
    return _active_alerts


def load_user_preferences() -> None:
    """Load user notification preferences from storage."""
    global _user_preferences, _active_alerts

    try:
        if SMART_ALERTS_FILE.exists():
            with open(SMART_ALERTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _user_preferences = data.get("user_preferences", {})
                _active_alerts = data.get("active_alerts", {})
                logger.info(
                    f"Loaded preferences for {len(_user_preferences)} users "
                    f"and {len(_active_alerts)} alerts"
                )
    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"Error loading user preferences: {e}")
        _user_preferences = {}
        _active_alerts = {}


def save_user_preferences() -> None:
    """Save user notification preferences to storage."""
    try:
        # Ensure directory exists
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)

        with open(SMART_ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "user_preferences": _user_preferences,
                    "active_alerts": _active_alerts,
                    "updated_at": datetime.now().timestamp(),
                },
                f,
                indent=2,
            )
        logger.debug("User preferences saved successfully")
    except OSError as e:
        logger.exception(f"Error saving user preferences: {e}")


async def register_user(user_id: int, chat_id: int | None = None) -> None:
    """Register a user for notifications with default settings.

    Args:
        user_id: Telegram user ID
        chat_id: Optional chat ID (defaults to user_id)
    """
    global _user_preferences

    user_id_str = str(user_id)
    chat_id = chat_id if chat_id is not None else user_id

    if user_id_str not in _user_preferences:
        _user_preferences[user_id_str] = {
            **DEFAULT_USER_PREFERENCES,
            "chat_id": chat_id,
            "registered_at": datetime.now().timestamp(),
        }
        save_user_preferences()
        logger.info(f"User {user_id} registered for notifications")


async def update_user_preferences(
    user_id: int,
    preferences: dict[str, Any],
) -> None:
    """Update a user's notification preferences.

    Args:
        user_id: Telegram user ID
        preferences: Dictionary of preference updates
    """
    global _user_preferences

    user_id_str = str(user_id)

    # Register if not already registered
    if user_id_str not in _user_preferences:
        await register_user(user_id)

    # Update preferences
    for key, value in preferences.items():
        if key in _user_preferences[user_id_str]:
            if isinstance(_user_preferences[user_id_str][key], dict) and isinstance(
                value,
                dict,
            ):
                # Merge dictionaries for nested settings
                _user_preferences[user_id_str][key].update(value)
            else:
                # Direct assignment for simple values
                _user_preferences[user_id_str][key] = value

    save_user_preferences()
    logger.debug(f"Updated preferences for user {user_id}")


def get_user_prefs(user_id: int) -> dict[str, Any]:
    """Get preferences for a specific user.

    Args:
        user_id: Telegram user ID

    Returns:
        User preferences dictionary or empty dict if not found
    """
    return _user_preferences.get(str(user_id), {})
