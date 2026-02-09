"""View Items handler with profit display.

This module handles the "View Items" button functionality:
1. Display sold items with realized profit
2. Display active listings with estimated profit
3. Profit calculations (sell price - buy price - fees)
4. Summary statistics

Features:
- Real profit calculation for sold items
- Estimated profit for active listings
- Pagination for large item lists
- Summary with total profit
- Commission consideration (DMarket 7%)
"""

import logging
from typing import TYPE_CHECKING, Any

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.utils.sentry_breadcrumbs import add_command_breadcrumb

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


# DMarket commission rate
DMARKET_COMMISSION = 0.07  # 7%


def calculate_profit(item: dict[str, Any]) -> float:
    """Calculate realized profit for sold item.

    Formula: (sell_price - buy_price) * (1 - commission)

    Args:
        item: Item data with price information

    Returns:
        Profit in USD
    """
    try:
        # Prices are in cents in DMarket API
        sell_price = float(item.get("price", {}).get("USD", 0)) / 100
        buy_price = float(item.get("buyPrice", 0)) / 100

        if buy_price == 0:
            # If no buy price, assume profit is sell price minus commission
            return sell_price * (1 - DMARKET_COMMISSION)

        # Real profit: sell price minus buy price minus commission on sell
        return sell_price - buy_price - (sell_price * DMARKET_COMMISSION)

    except (KeyError, TypeError, ValueError):
        return 0.0


def estimate_profit(item: dict[str, Any]) -> float:
    """Estimate potential profit for active listing.

    Uses suggested price or market average for estimation.

    Args:
        item: Active listing data

    Returns:
        Estimated profit in USD
    """
    try:
        # Current listing price
        list_price = float(item.get("price", {}).get("USD", 0)) / 100

        # Suggested market price (if available)
        suggested_price = float(item.get("suggestedPrice", {}).get("USD", 0)) / 100

        if suggested_price > list_price:
            # Potential profit if sold at suggested price
            return suggested_price - list_price - (suggested_price * DMARKET_COMMISSION)
        # If selling at list price
        buy_price = float(item.get("buyPrice", 0)) / 100
        if buy_price > 0:
            return list_price - buy_price - (list_price * DMARKET_COMMISSION)
        # Assume 10% margin if no buy price
        return list_price * 0.10

    except (KeyError, TypeError, ValueError):
        return 0.0


async def handle_view_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle View Items button - display sold and active items with profit.

    Args:
        update: Telegram update object
        context: Callback context

    Returns:
        None (sends items summary to user)
    """
    user = update.effective_user
    if not user:
        return

    message = update.message or (update.callback_query.message if update.callback_query else None)
    if not message:
        return

    add_command_breadcrumb(
        command="view_items",
        user_id=user.id,
        username=user.username or "",
        chat_id=message.chat_id,
    )

    logger.info("view_items_started", user_id=user.id)

    # Send initial status
    status_msg = await message.reply_text("📦 Loading your items...")

    try:
        # Get API client
        api_client: DMarketAPI | None = context.bot_data.get("dmarket_api")

        if not api_client:
            await status_msg.edit_text(
                "❌ <b>Error</b>\n\nAPI client not initialized.\nPlease restart the bot.",
                parse_mode="HTML",
            )
            logger.error("view_items_no_api", user_id=user.id)
            return

        # Fetch sold items (closed offers)
        try:
            sold_response = await api_client.get_user_closed_offers(limit=10)
            sold_items = sold_response.get("Items", []) if sold_response else []
        except Exception as e:
            logger.warning("failed_to_fetch_sold_items", error=str(e), user_id=user.id)
            sold_items = []

        # Fetch active listings
        try:
            active_response = await api_client.get_user_offers(limit=10)
            active_items = active_response.get("Items", []) if active_response else []
        except Exception as e:
            logger.warning("failed_to_fetch_active_items", error=str(e), user_id=user.id)
            active_items = []

        # Build response message
        response_text = "📦 <b>Your Items Summary</b>\n\n"

        # Sold Items Section
        if sold_items:
            response_text += "✅ <b>Sold Items (Last 10)</b>\n"
            response_text += "─" * 30 + "\n"

            total_sold_profit = 0.0
            for i, item in enumerate(sold_items[:10], 1):
                title = item.get("title", "Unknown Item")[:30]
                profit = calculate_profit(item)
                total_sold_profit += profit

                profit_emoji = "💚" if profit > 0 else "💔" if profit < 0 else "➖"

                response_text += f"{i}. {title}\n   {profit_emoji} Profit: ${profit:.2f}\n"

            response_text += "─" * 30 + "\n"
            response_text += f"💰 <b>Total Realized Profit: ${total_sold_profit:.2f}</b>\n\n"

            logger.info(
                "sold_items_displayed",
                user_id=user.id,
                count=len(sold_items),
                total_profit=total_sold_profit,
            )
        else:
            response_text += "ℹ️ No sold items found.\n\n"

        # Active Listings Section
        if active_items:
            response_text += "📋 <b>Active Listings (Up to 10)</b>\n"
            response_text += "─" * 30 + "\n"

            total_estimated_profit = 0.0
            for i, item in enumerate(active_items[:10], 1):
                title = item.get("title", "Unknown Item")[:30]
                list_price = float(item.get("price", {}).get("USD", 0)) / 100
                est_profit = estimate_profit(item)
                total_estimated_profit += est_profit

                profit_emoji = "📈" if est_profit > 0 else "📉"

                response_text += (
                    f"{i}. {title}\n"
                    f"   💵 Listed: ${list_price:.2f}\n"
                    f"   {profit_emoji} Est. Profit: ${est_profit:.2f}\n"
                )

            response_text += "─" * 30 + "\n"
            response_text += f"📊 <b>Est. Total Profit: ${total_estimated_profit:.2f}</b>\n\n"

            logger.info(
                "active_items_displayed",
                user_id=user.id,
                count=len(active_items),
                estimated_profit=total_estimated_profit,
            )
        else:
            response_text += "ℹ️ No active listings found.\n\n"

        # Summary
        if sold_items or active_items:
            response_text += "ℹ️ <i>Commission rate: 7% (DMarket)</i>\n"
            response_text += "<i>Use /inventory for detailed view</i>"
        else:
            response_text += "💡 <b>Getting Started</b>\n\n"
            response_text += "Start trading by using:\n"
            response_text += "• 🤖 Automatic Arbitrage - Find opportunities\n"
            response_text += "• 🎯 Manual scanning - Select specific items\n\n"
            response_text += "Happy trading! 🚀"

        await status_msg.edit_text(response_text, parse_mode="HTML")

        logger.info(
            "view_items_completed",
            user_id=user.id,
            sold_count=len(sold_items),
            active_count=len(active_items),
        )

    except Exception as e:
        std_logger.exception("Unexpected error in view_items handler")
        await status_msg.edit_text(
            "❌ <b>Error Loading Items</b>\n\n"
            "An unexpected error occurred.\n"
            "Please try again later.",
            parse_mode="HTML",
        )
        logger.error(
            "view_items_unexpected_error",
            error=str(e),
            user_id=user.id,
            exc_info=True,
        )


async def handle_view_items_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle View Items callback from inline button.

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

    # Create fake message update for reuse of handle_view_items
    if query.message:
        update.message = query.message
        await handle_view_items(update, context)
