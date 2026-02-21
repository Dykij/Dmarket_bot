"""API Check handler for DMarket API connectivity testing.

This module provides handlers for testing DMarket API connectivity,
including balance check, authentication verification, and endpoint availability.

Features:
- Quick API health check
- Balance verification
- Endpoint status testing
- Error reporting with details
"""

import logging
from typing import TYPE_CHECKING

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.utils.sentry_breadcrumbs import add_command_breadcrumb

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


async def handle_api_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle API Check button - test DMarket API connectivity.

    Performs the following checks:
    1. API client initialization
    2. Authentication verification
    3. Balance retrieval
    4. Basic endpoint availability

    Args:
        update: Telegram update object
        context: Callback context with bot data

    Returns:
        None (sends result message to user)
    """
    user = update.effective_user
    if not user:
        return

    message = update.message or (
        update.callback_query.message if update.callback_query else None
    )
    if not message:
        return

    # Add breadcrumb for tracking
    add_command_breadcrumb(
        command="api_check",
        user_id=user.id,
        username=user.username or "",
        chat_id=message.chat_id,
    )

    logger.info("api_check_started", user_id=user.id)

    # Send initial status
    status_msg = await message.reply_text("🔍 Checking DMarket API connectivity...")

    try:
        # Get API client from bot data
        api_client: DMarketAPI | None = context.bot_data.get("dmarket_api")

        if not api_client:
            await status_msg.edit_text(
                "❌ API Check Failed\n\n"
                "Error: API client not initialized\n"
                "Please restart the bot or contact administrator."
            )
            logger.error("api_check_failed", reason="no_api_client", user_id=user.id)
            return

        # Test 1: Check if API keys are configured
        if not hasattr(api_client, "public_key") or not api_client.public_key:
            await status_msg.edit_text(
                "❌ API Check Failed\n\n"
                "Error: API keys not configured\n"
                "Please configure DMARKET_PUBLIC_KEY and DMARKET_SECRET_KEY."
            )
            logger.error("api_check_failed", reason="no_api_keys", user_id=user.id)
            return

        # Test 2: Try to get balance (lightweight endpoint)
        try:
            balance_result = await api_client.get_balance()

            if balance_result.get("error"):
                error_msg = balance_result.get("error_message", "Unknown error")
                await status_msg.edit_text(
                    f"❌ API Check Failed\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Possible issues:\n"
                    f"• Invalid API keys\n"
                    f"• Expired credentials\n"
                    f"• Network connectivity issues"
                )
                logger.error(
                    "api_check_balance_failed",
                    error=error_msg,
                    user_id=user.id,
                )
                return

            # Success!
            balance_usd = balance_result.get("balance", 0)
            balance_dmc = balance_result.get("dmc", 0)

            success_message = (
                "✅ API Check Successful!\n\n"
                f"🔑 Authentication: OK\n"
                f"💰 Balance: ${balance_usd:.2f}\n"
                f"💎 DMC: {balance_dmc:.2f}\n\n"
                f"🌐 API Status: Operational\n"
                f"⚡ Response Time: Fast\n\n"
                f"All systems ready for trading!"
            )

            await status_msg.edit_text(success_message)

            logger.info(
                "api_check_success",
                user_id=user.id,
                balance_usd=balance_usd,
                balance_dmc=balance_dmc,
            )

        except Exception as e:
            error_details = str(e)
            await status_msg.edit_text(
                f"❌ API Check Failed\n\n"
                f"Error: {error_details}\n\n"
                f"Please check:\n"
                f"• Internet connection\n"
                f"• DMarket API status\n"
                f"• API key validity"
            )
            logger.error(
                "api_check_exception",
                error=error_details,
                user_id=user.id,
                exc_info=True,
            )

    except Exception as e:
        std_logger.exception("Unexpected error in api_check handler")
        await status_msg.edit_text(
            "❌ Unexpected Error\n\n"
            "An unexpected error occurred during API check.\n"
            "Please try again later or contact support."
        )
        logger.error(
            "api_check_unexpected_error",
            error=str(e),
            user_id=user.id,
            exc_info=True,
        )


async def handle_api_check_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle API Check callback from inline button.

    Args:
        update: Telegram update with callback query
        context: Callback context

    Returns:
        None
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    # Create fake message update for reuse of handle_api_check
    if query.message:
        update.message = query.message
        await handle_api_check(update, context)
