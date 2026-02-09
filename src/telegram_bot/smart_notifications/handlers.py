"""Callback handlers for smart notifications."""

import asyncio
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from src.telegram_bot.smart_notifications.alerts import create_alert, deactivate_alert
from src.telegram_bot.smart_notifications.checkers import start_notification_checker
from src.telegram_bot.smart_notifications.utils import get_item_by_id, get_item_price

logger = logging.getLogger(__name__)


async def handle_notification_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle callback queries from notification buttons.

    Args:
        update: Update object
        context: ContextTypes.DEFAULT_TYPE object
    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    # Safely get message text
    msg_text = ""
    if query.message and hasattr(query.message, "text"):
        msg_text = str(query.message.text) if query.message.text else ""

    if query.data.startswith("disable_alert:"):
        alert_id = query.data.split(":", 1)[1]
        success = await deactivate_alert(query.from_user.id, alert_id)

        if success:
            await query.edit_message_text(
                text=f"{msg_text}\n\n✅ Alert has been disabled.",
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await query.edit_message_reply_markup(reply_markup=None)

    elif query.data.startswith("track_item:"):
        parts = query.data.split(":", 2)
        item_id = parts[1]
        game = parts[2] if len(parts) > 2 else "csgo"

        # Create price alert for the item
        api = context.bot_data.get("dmarket_api")

        if not api:
            await query.edit_message_text(
                text=f"{msg_text}\n\n❌ Could not create alert: API not available.",
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:
            # Get current item data
            item_data: dict[str, Any] | None = await get_item_by_id(api, item_id, game)

            if not item_data:
                await query.edit_message_text(
                    text=f"{msg_text}\n\n❌ Could not create alert: Item not found.",
                    reply_markup=None,
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            item_name = item_data.get("title", "Unknown item")
            current_price = get_item_price(item_data)

            # Create price alerts for both directions
            await create_alert(
                query.from_user.id,
                "price_alert",
                item_id=item_id,
                item_name=item_name,
                game=game,
                conditions={
                    "price": current_price * 0.9,  # 10% below current price
                    "direction": "below",
                },
            )

            await create_alert(
                query.from_user.id,
                "price_alert",
                item_id=item_id,
                item_name=item_name,
                game=game,
                conditions={
                    "price": current_price * 1.1,  # 10% above current price
                    "direction": "above",
                },
            )

            # Update message
            keyboard = [
                [
                    InlineKeyboardButton(
                        "View on DMarket",
                        url=f"https://dmarket.com/ingame-items/{game}/skin/{item_id}",
                    ),
                ],
                [
                    InlineKeyboardButton("View Alerts", callback_data="view_alerts"),
                ],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text=f"{msg_text}\n\n✅ Alerts created for price changes.",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )

            logger.info(
                "Created price alerts for user %s on item %s",
                query.from_user.id,
                item_name,
            )

        except Exception as e:  # noqa: BLE001
            logger.exception(
                "Error creating alert for user %s on item %s: %s",
                query.from_user.id,
                item_id,
                e,
            )

            await query.edit_message_text(
                text=f"{msg_text}\n\n❌ Error creating alert: {e!s}",
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN,
            )


def register_notification_handlers(
    application: Application,  # type: ignore[type-arg]
) -> None:
    """Register notification handlers with the application.

    Args:
        application: Application instance
    """
    # Register smart notification callback handler
    application.add_handler(
        CallbackQueryHandler(
            handle_notification_callback,
            pattern=r"^(disable_alert:|track_item:)",
        ),
    )

    # Start notification checker
    api = application.bot_data.get("dmarket_api")
    notification_queue = application.bot_data.get("notification_queue")

    if api:
        checker_task = asyncio.create_task(
            start_notification_checker(
                api,
                application.bot,
                interval=300,
                notification_queue=notification_queue,
            ),
        )
        logger.info("Started notification checker (task: %s)", checker_task.get_name())
    else:
        logger.error("Could not start notification checker: DMarketAPI not found in bot_data")
