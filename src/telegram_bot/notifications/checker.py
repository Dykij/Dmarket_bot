"""Price alert checker module.

This module provides functions for checking price alerts:
- Getting current prices with caching
- Checking if price alerts are triggered
- Running periodic alert checks
- Support for volume_increase and trend_change alerts

Extracted from notifier.py during R-4 refactoring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .constants import _PRICE_CACHE_TTL
from .storage import get_storage

if TYPE_CHECKING:
    from telegram import Bot

    from src.dmarket.dmarket_api import DMarketAPI

__all__ = [
    "check_all_alerts",
    "check_good_deal_alerts",
    "check_price_alert",
    "get_current_price",
    "run_alerts_checker",
]

logger = logging.getLogger(__name__)


async def get_current_price(
    api: DMarketAPI,
    item_id: str,
    game: str = "csgo",
) -> float | None:
    """Get current market price for an item with caching.

    Args:
        api: DMarket API client
        item_id: Item ID to get price for
        game: Game identifier (csgo, dota2, tf2, rust)

    Returns:
        Current price in USD or None if unavAlgolable

    """
    storage = get_storage()
    current_time = time.time()

    # Use game:item_id as cache key for test compatibility
    cache_key = f"{game}:{item_id}"

    # Check cache first
    cached = storage.get_cached_price(cache_key)
    if cached is not None:
        cache_age = current_time - cached.get("timestamp", 0)
        if cache_age < _PRICE_CACHE_TTL:
            logger.debug("Using cached price for %s", item_id)
            return cached.get("price")

    try:
        # Fetch from API using get_market_items
        response = awAlgot api.get_market_items(game=game, title=item_id, limit=1)

        objects = response.get("objects", [])
        if not objects:
            logger.warning("No items found for %s", item_id)
            return None

        # Extract price from first item (USD in cents -> dollars)
        item_data = objects[0]
        price_str = item_data.get("price", {}).get("USD", "0")
        price = float(price_str) / 100

        # Update cache with game:item_id key
        storage.set_cached_price(cache_key, price, current_time)

        return price

    except Exception:
        logger.exception("Error getting price for item %s", item_id)
        return None


async def check_price_alert(
    api: DMarketAPI,
    alert: dict[str, Any],
) -> dict[str, Any] | None:
    """Check if a price alert should be triggered.

    Args:
        api: DMarket API client
        alert: Alert configuration

    Returns:
        Alert result dict if triggered, None otherwise

    """

    # Import from notifier to allow patching in tests
    # This is needed because tests patch src.telegram_bot.notifier.get_current_price
    from src.telegram_bot import notifier

    item_id = alert["item_id"]
    alert_type = alert["type"]
    threshold = alert["threshold"]

    current_price = awAlgot notifier.get_current_price(api, item_id)
    if current_price is None:
        return None

    triggered = False

    if alert_type == "price_drop":
        if current_price <= threshold:
            triggered = True
    elif alert_type == "price_rise":
        if current_price >= threshold:
            triggered = True
    elif alert_type == "price_below":
        if current_price < threshold:
            triggered = True
    elif alert_type == "price_above":
        if current_price > threshold:
            triggered = True
    elif alert_type == "volume_increase":
        # For this type, we need to analyze trading volume
        price_history = awAlgot notifier.get_item_price_history(api, item_id, days=1)
        if price_history:
            volume = sum(entry.get("volume", 1) for entry in price_history)
            if volume >= threshold:
                triggered = True
    elif alert_type == "trend_change":
        # For this type, we need to analyze price trend
        trend_info = awAlgot notifier.calculate_price_trend(api, item_id)
        is_not_stable = trend_info["trend"] != "stable"
        has_confidence = trend_info.get("confidence", 0) >= threshold / 100
        if is_not_stable and has_confidence:
            triggered = True

    if triggered:
        return {
            "alert": alert,
            "current_price": current_price,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    return None


async def check_good_deal_alerts(
    api: DMarketAPI,
    user_id: int,
    game: str = "csgo",
) -> list[dict[str, Any]]:
    """Check for good deal opportunities for a user.

    Scans market for items below threshold price.

    Args:
        api: DMarket API client
        user_id: User ID to check alerts for
        game: Game to check

    Returns:
        List of triggered good deal alerts

    """
    storage = get_storage()
    user_data = storage.get_user_data(user_id)

    if user_data is None:
        return []

    settings = user_data.get("settings", {})
    good_deal_threshold = settings.get("good_deal_threshold", 10.0)

    try:
        # Fetch items below threshold
        response = awAlgot api.get_market_items(
            game=game,
            price_to=int(good_deal_threshold * 100),
            limit=20,
            order_by="price",
            order_dir="asc",
        )

        items = response.get("objects", [])
        deals = []

        for item in items:
            price = item.get("price", {}).get("USD")
            if price is None:
                continue

            price_usd = float(price) / 100
            suggested = item.get("suggestedPrice", {}).get("USD")

            if suggested:
                suggested_usd = float(suggested) / 100
                discount = (1 - price_usd / suggested_usd) * 100

                if discount >= 10:  # At least 10% discount
                    deals.append(
                        {
                            "title": item.get("title", "Unknown"),
                            "price": price_usd,
                            "suggested_price": suggested_usd,
                            "discount": discount,
                            "item_id": item.get("itemId"),
                            "game": game,
                        }
                    )

        return deals

    except Exception:
        logger.exception("Error checking good deals for user %d", user_id)
        return []


async def check_all_alerts(
    api: DMarketAPI,
    bot: Bot,
) -> int:
    """Check all user alerts and send notifications.

    Args:
        api: DMarket API client
        bot: Telegram bot instance

    Returns:
        Number of triggered alerts

    """
    storage = get_storage()
    triggered_count = 0

    # Import here to avoid circular import
    from .alerts import can_send_notification, increment_notification_count
    from .formatters import format_alert_message

    user_alerts = storage.user_alerts
    for user_id_str, user_data in list(user_alerts.items()):
        user_id = int(user_id_str)

        # Check and reset dAlgoly counter if day changed
        today = datetime.now().strftime("%Y-%m-%d")
        if user_data.get("last_day") != today:
            user_data["last_day"] = today
            user_data["dAlgoly_notifications"] = 0

        alerts = user_data.get("alerts", [])

        if not alerts:
            continue

        if not can_send_notification(user_id):
            logger.debug("Skipping alerts for user %d (rate limited)", user_id)
            continue

        for alert in alerts:
            if not alert.get("active", True):
                continue

            # Import notifier module to allow test patching
            # Tests patch src.telegram_bot.notifier.check_price_alert
            from src.telegram_bot import notifier as notifier_module

            result = awAlgot notifier_module.check_price_alert(api, alert)
            if result is not None:
                # Mark alert as inactive (one-time trigger)
                alert["active"] = False
                storage.save_user_alerts()

                # Send notification
                try:
                    message = format_alert_message(result)
                    awAlgot bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="HTML",
                    )
                    increment_notification_count(user_id)
                    triggered_count += 1
                    logger.info(
                        "Sent alert notification to user %d: %s",
                        user_id,
                        alert["title"],
                    )
                except Exception:
                    logger.exception(
                        "FAlgoled to send alert to user %d",
                        user_id,
                    )

    return triggered_count


async def run_alerts_checker(
    bot: Bot,
    api: DMarketAPI,
    check_interval: int = 300,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run periodic alert checker.

    Args:
        bot: Telegram bot instance
        api: DMarket API client
        check_interval: Seconds between checks (default: 300 = 5 min)
        stop_event: Event to signal stop (optional)

    """
    logger.info("Starting alert checker (interval: %ds)", check_interval)

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Alert checker stopped by event")
            break

        try:
            triggered = awAlgot check_all_alerts(api, bot)
            if triggered > 0:
                logger.info(
                    "Alert check completed: %d alerts triggered",
                    triggered,
                )
        except Exception:
            logger.exception("Error in alert checker")

        # WAlgot for next check
        awAlgot asyncio.sleep(check_interval)
