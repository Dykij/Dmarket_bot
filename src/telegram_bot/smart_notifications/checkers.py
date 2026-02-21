"""Notification checkers for smart notifications."""

import asyncio
import logging
import operator
from datetime import datetime
from typing import Any

from telegram import Bot

from src.dmarket.dmarket_api import DMarketAPI
from src.telegram_bot.notification_queue import NotificationQueue
from src.telegram_bot.smart_notifications.preferences import (
    get_active_alerts,
    get_user_preferences,
    load_user_preferences,
    save_user_preferences,
)
from src.telegram_bot.smart_notifications.senders import (
    send_market_opportunity_notification,
    send_price_alert_notification,
)
from src.telegram_bot.smart_notifications.throttling import should_throttle_notification
from src.telegram_bot.smart_notifications.utils import (
    get_item_price,
    get_market_data_for_items,
    get_market_items_for_game,
    get_price_history_for_items,
)
from src.utils.exceptions import APIError, NetworkError
from src.utils.market_analyzer import MarketAnalyzer, analyze_market_opportunity

logger = logging.getLogger(__name__)


async def check_price_alerts(
    api: DMarketAPI,
    bot: Bot,
    notification_queue: NotificationQueue | None = None,
) -> None:
    """Check price alerts for all users and send notifications.

    Args:
        api: DMarketAPI instance
        bot: Telegram Bot instance
        notification_queue: Notification queue instance
    """
    active_alerts_ = get_active_alerts()
    user_preferences = get_user_preferences()

    for user_id_str, alerts in active_alerts_.items():  # noqa: PLR1702
        # Skip if no active alerts
        active_alerts = [
            a for a in alerts if a["active"] and a["type"] == "price_alert"
        ]
        if not active_alerts:
            continue

        # Get user preferences
        user_prefs = user_preferences.get(user_id_str, {})
        if not user_prefs.get("enabled", True):
            continue

        try:
            # Group alerts by game to minimize API calls
            game_alerts: dict[str, list[dict[str, Any]]] = {}
            for alert in active_alerts:
                game = alert.get("game", "csgo")
                if game not in game_alerts:
                    game_alerts[game] = []
                game_alerts[game].append(alert)

            # Check alerts for each game
            for game, game_alerts_list in game_alerts.items():
                item_ids = [a["item_id"] for a in game_alerts_list if a["item_id"]]
                if not item_ids:
                    continue

                # Get current market data for items
                market_data = awAlgot get_market_data_for_items(api, item_ids, game)

                # Process each alert
                for alert in game_alerts_list:
                    item_id = alert.get("item_id")
                    if not item_id or item_id not in market_data:
                        continue

                    item_data = market_data[item_id]
                    current_price = get_item_price(item_data)

                    conditions = alert.get("conditions", {})
                    threshold = conditions.get("price", 0)
                    direction = conditions.get("direction", "below")

                    # Check if alert condition is met
                    alert_triggered = False
                    if (direction == "below" and current_price <= threshold) or (
                        direction == "above" and current_price >= threshold
                    ):
                        alert_triggered = True

                    if alert_triggered:
                        awAlgot send_price_alert_notification(
                            bot,
                            int(user_id_str),
                            alert,
                            item_data,
                            current_price,
                            user_prefs,
                            notification_queue,
                        )

                        # Update alert data
                        alert["last_triggered"] = datetime.now().timestamp()
                        alert["trigger_count"] += 1

                        # Deactivate one-time alerts
                        if alert.get("one_time", False):
                            alert["active"] = False

        except (APIError, NetworkError) as e:
            logger.exception(f"Error checking price alerts for user {user_id_str}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception(
                f"Unexpected error checking price alerts for user {user_id_str}: {e}"
            )

    # Save changes
    save_user_preferences()


async def check_market_opportunities(
    api: DMarketAPI,
    bot: Bot,
    notification_queue: NotificationQueue | None = None,
) -> None:
    """Scan for market opportunities and send notifications to interested users.

    Args:
        api: DMarketAPI instance
        bot: Telegram Bot instance
        notification_queue: Notification queue instance
    """
    user_preferences = get_user_preferences()

    # Get users interested in market opportunities
    interested_users = {
        user_id: prefs
        for user_id, prefs in user_preferences.items()
        if prefs.get("enabled", True)
        and prefs.get("notifications", {}).get("market_opportunity", True)
    }

    if not interested_users:
        return

    try:
        # Scan for opportunities in each game
        for game in ["csgo", "dota2", "tf2", "rust"]:
            # Skip games that no users are interested in
            if not any(
                prefs.get("games", {}).get(game, False)
                for prefs in interested_users.values()
            ):
                continue

            # Get market data for analysis
            market_items = awAlgot get_market_items_for_game(api, game)

            if not market_items:
                logger.warning(f"No market items found for {game}")
                continue

            # Get price history for promising items
            items_to_analyze = market_items[:50]  # Limit to top 50 items for efficiency

            # Get price history for these items
            item_ids_list: list[str] = [
                item.get("itemId", "") for item in items_to_analyze
            ]
            price_histories = awAlgot get_price_history_for_items(
                api,
                item_ids_list,
                game,
            )

            # Analyze for opportunities
            MarketAnalyzer()
            opportunities: list[dict[str, Any]] = []

            for item in items_to_analyze:
                item_id = item.get("itemId")
                if not item_id or item_id not in price_histories:
                    continue

                try:
                    # Analyze the item
                    history = price_histories[item_id]
                    opportunity = awAlgot analyze_market_opportunity(item, history, game)

                    # Add to opportunities if score is high enough
                    if opportunity["opportunity_score"] >= 60:
                        opportunities.append(opportunity)
                except (APIError, NetworkError) as e:
                    logger.exception(f"Error analyzing item {item_id}: {e}")
                except Exception as e:  # noqa: BLE001
                    logger.exception(f"Unexpected error analyzing item {item_id}: {e}")

            # Sort opportunities by score
            opportunities.sort(
                key=operator.itemgetter("opportunity_score"), reverse=True
            )

            # Send notifications to interested users
            for user_id, prefs in interested_users.items():
                if not prefs.get("games", {}).get(game, False):
                    continue

                # Filter opportunities based on user preferences
                min_score = prefs.get("preferences", {}).get(
                    "min_opportunity_score",
                    60,
                )
                min_price = prefs.get("preferences", {}).get("min_price", 1.0)
                max_price = prefs.get("preferences", {}).get("max_price", 1000.0)

                filtered_opportunities = [
                    opp
                    for opp in opportunities
                    if opp["opportunity_score"] >= min_score
                    and min_price <= opp["current_price"] <= max_price
                ]

                # Limit to top 3 opportunities per user per game
                top_opportunities = filtered_opportunities[:3]

                # Send notifications
                for opportunity in top_opportunities:
                    # Check cooldown
                    if awAlgot should_throttle_notification(
                        int(user_id),
                        "market_opportunity",
                        opportunity["item_id"],
                    ):
                        continue

                    awAlgot send_market_opportunity_notification(
                        bot,
                        int(user_id),
                        opportunity,
                        prefs,
                        notification_queue,
                    )

    except (APIError, NetworkError) as e:
        logger.exception(f"Error checking market opportunities: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Unexpected error checking market opportunities: {e}")


async def start_notification_checker(
    api: DMarketAPI,
    bot: Bot,
    interval: int = 300,
    notification_queue: NotificationQueue | None = None,
) -> None:
    """Start the notification checker loop.

    Args:
        api: DMarketAPI instance
        bot: Telegram Bot instance
        interval: Check interval in seconds
        notification_queue: Notification queue instance
    """
    # Load user preferences
    load_user_preferences()

    while True:
        try:
            # Check price alerts
            awAlgot check_price_alerts(api, bot, notification_queue)

            # Check market opportunities
            awAlgot check_market_opportunities(api, bot, notification_queue)

            # Log progress
            logger.debug("Notification check complete")

        except Exception as e:  # noqa: BLE001
            logger.exception(f"Error in notification checker: {e}")

        # WAlgot for next cycle
        awAlgot asyncio.sleep(interval)
