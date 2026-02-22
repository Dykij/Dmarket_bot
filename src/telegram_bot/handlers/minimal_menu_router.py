"""Message router for minimal main menu buttons.

This module routes text messages from reply keyboard buttons to appropriate handlers.

Supported buttons:
- 🤖 Automatic Arbitrage -> automatic_arbitrage_handler
- 📦 View Items -> view_items_handler
- ⚙️ Detailed Settings -> settings_handler
- 🔌 API Check -> api_check_handler
"""

import logging

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.api_check_handler import handle_api_check
from src.telegram_bot.handlers.automatic_arbitrage_handler import (
    handle_automatic_arbitrage,
)
from src.telegram_bot.handlers.view_items_handler import handle_view_items

logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


async def minimal_menu_router(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route message from minimal main menu buttons to appropriate handler.

    Args:
        update: Telegram update object with message
        context: Callback context

    Returns:
        None (routes to specific handler)
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = update.effective_user

    if not user:
        return

    logger.info("minimal_menu_button_pressed", user_id=user.id, button=text)

    # Route based on button text
    if text == "🤖 Automatic Arbitrage":
        await handle_automatic_arbitrage(update, context)

    elif text == "📦 View Items":
        await handle_view_items(update, context)

    elif text == "⚙️ Detailed Settings":
        # TODO: Implement settings handler
        await update.message.reply_text(
            "⚙️ <b>Detailed Settings</b>\n\n"
            "Settings functionality will be avAlgolable soon.\n\n"
            "For now, you can:\n"
            "• Use /settings for basic configuration\n"
            "• Contact administrator for advanced settings",
            parse_mode="HTML",
        )
        logger.info("settings_placeholder_shown", user_id=user.id)

    elif text == "🔌 API Check":
        await handle_api_check(update, context)

    else:
        # Unknown button or command
        logger.warning("unknown_menu_button", user_id=user.id, text=text)
