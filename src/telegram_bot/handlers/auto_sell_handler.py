"""Auto-sell Telegram handler.

Provides Telegram commands for managing the auto-sell system:
- /auto_sell status - View auto-sell statistics and active sales
- /auto_sell config - View/modify auto-sell configuration
- /auto_sell toggle - Enable/disable auto-sell
- /auto_sell cancel <item_id> - Cancel a scheduled sale

Part of P1-17: Auto-sale functionality implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

if TYPE_CHECKING:
    from src.dmarket.auto_seller import AutoSeller

logger = logging.getLogger(__name__)

# Conversation states
CONFIG_EDIT = 1


class AutoSellHandler:
    """Handler for auto-sell Telegram commands.

    Provides user interface for managing automatic selling:
    - View statistics and active sales
    - Configure pricing parameters
    - Enable/disable auto-sell
    - Cancel individual sales

    Attributes:
        auto_seller: AutoSeller instance to manage
    """

    def __init__(self, auto_seller: AutoSeller | None = None) -> None:
        """Initialize handler.

        Args:
            auto_seller: AutoSeller instance (can be set later via set_auto_seller)
        """
        self._auto_seller = auto_seller

    def set_auto_seller(self, auto_seller: AutoSeller) -> None:
        """Set the AutoSeller instance.

        Args:
            auto_seller: AutoSeller to use for operations
        """
        self._auto_seller = auto_seller

    @property
    def auto_seller(self) -> AutoSeller | None:
        """Get the AutoSeller instance."""
        return self._auto_seller

    async def handle_auto_sell_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /auto_sell command.

        Shows main auto-sell menu with options.

        Args:
            update: Telegram update
            context: Callback context
        """
        if not update.message:
            return

        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="auto_sell:status"),
                InlineKeyboardButton("⚙️ Config", callback_data="auto_sell:config"),
            ],
            [
                InlineKeyboardButton("🔄 Toggle", callback_data="auto_sell:toggle"),
                InlineKeyboardButton("📋 Active Sales", callback_data="auto_sell:active"),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="auto_sell:cancel_menu"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        status = "✅ Enabled" if self._is_enabled() else "❌ Disabled"
        await update.message.reply_text(
            f"🤖 *Auto-Sell Management*\n\nStatus: {status}\n\nChoose an option:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int | None:
        """Handle auto-sell callback queries.

        Args:
            update: Telegram update
            context: Callback context

        Returns:
            Conversation state or None
        """
        query = update.callback_query
        if not query or not query.data:
            return None

        await query.answer()

        data = query.data
        if data == "auto_sell:status":
            await self._show_status(query)
        elif data == "auto_sell:config":
            await self._show_config(query)
        elif data == "auto_sell:toggle":
            await self._toggle_auto_sell(query)
        elif data == "auto_sell:active":
            await self._show_active_sales(query)
        elif data == "auto_sell:cancel_menu":
            await self._show_cancel_menu(query)
        elif data.startswith("auto_sell:cancel:"):
            item_id = data.split(":")[-1]
            await self._cancel_sale(query, item_id)
        elif data.startswith("auto_sell:config:"):
            param = data.split(":")[-1]
            return await self._start_config_edit(query, param)
        elif data == "auto_sell:back":
            await self._show_main_menu(query)

        return None

    async def handle_config_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle config parameter input.

        Args:
            update: Telegram update
            context: Callback context

        Returns:
            ConversationHandler.END
        """
        if not update.message or not context.user_data:
            return ConversationHandler.END

        param = context.user_data.get("editing_param")
        if not param:
            await update.message.reply_text("❌ No parameter selected")
            return ConversationHandler.END

        try:
            value = float(update.message.text)
            await self._update_config(param, value)
            await update.message.reply_text(
                f"✅ Updated {param} to {value}",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid value. Please enter a number.",
            )

        return ConversationHandler.END

    def _is_enabled(self) -> bool:
        """Check if auto-sell is enabled."""
        if not self._auto_seller:
            return False
        return self._auto_seller.config.enabled

    async def _show_status(self, query) -> None:
        """Show auto-sell statistics."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        stats = self._auto_seller.get_statistics()

        text = (
            "📊 *Auto-Sell Statistics*\n\n"
            f"*Active Sales:* {stats['active_sales']}\n"
            f"  • Pending: {stats['pending']}\n"
            f"  • Listed: {stats['listed']}\n\n"
            f"*Totals:*\n"
            f"  • Scheduled: {stats['scheduled_count']}\n"
            f"  • Listed: {stats['listed_count']}\n"
            f"  • Sold: {stats['sold_count']}\n"
            f"  • Failed: {stats['failed_count']}\n"
            f"  • Stop-loss: {stats['stop_loss_count']}\n\n"
            f"*Price Adjustments:* {stats['adjustments_count']}\n"
            f"*Total Profit:* ${stats['total_profit']:.2f}"
        )

        keyboard = [[InlineKeyboardButton("« Back", callback_data="auto_sell:back")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _show_config(self, query) -> None:
        """Show auto-sell configuration."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        config = self._auto_seller.config

        text = (
            "⚙️ *Auto-Sell Configuration*\n\n"
            f"*Enabled:* {'Yes' if config.enabled else 'No'}\n"
            f"*Pricing Strategy:* {config.pricing_strategy.value}\n\n"
            f"*Margins:*\n"
            f"  • Min: {config.min_margin_percent}%\n"
            f"  • Target: {config.target_margin_percent}%\n"
            f"  • Max: {config.max_margin_percent}%\n\n"
            f"*Undercut:* ${config.undercut_cents / 100:.2f}\n"
            f"*DMarket Fee:* {config.dmarket_fee_percent}%\n\n"
            f"*Stop-Loss:*\n"
            f"  • After: {config.stop_loss_hours}h\n"
            f"  • Max Loss: {config.stop_loss_percent}%\n\n"
            f"*Price Check:* every {config.price_check_interval_minutes}m\n"
            f"*Max Active Sales:* {config.max_active_sales}\n"
            f"*List Delay:* {config.delay_before_list_seconds}s"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "Min Margin", callback_data="auto_sell:config:min_margin_percent"
                ),
                InlineKeyboardButton(
                    "Target Margin",
                    callback_data="auto_sell:config:target_margin_percent",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Stop-Loss %", callback_data="auto_sell:config:stop_loss_percent"
                ),
                InlineKeyboardButton(
                    "Stop-Loss Hours", callback_data="auto_sell:config:stop_loss_hours"
                ),
            ],
            [InlineKeyboardButton("« Back", callback_data="auto_sell:back")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _toggle_auto_sell(self, query) -> None:
        """Toggle auto-sell on/off."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        # Toggle the enabled state
        self._auto_seller.config.enabled = not self._auto_seller.config.enabled
        status = "✅ Enabled" if self._auto_seller.config.enabled else "❌ Disabled"

        await query.edit_message_text(
            f"🔄 Auto-sell has been {status}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
            ]),
        )

    async def _show_active_sales(self, query) -> None:
        """Show list of active sales."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        sales = self._auto_seller.get_active_sales()

        if not sales:
            await query.edit_message_text(
                "📋 *Active Sales*\n\nNo active sales.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
                ]),
                parse_mode="Markdown",
            )
            return

        # Show first 10 sales
        lines = ["📋 *Active Sales*\n"]
        for sale in sales[:10]:
            profit_str = (
                f"+${sale['profit']:.2f}" if sale["profit"] >= 0 else f"-${abs(sale['profit']):.2f}"
            )
            lines.append(
                f"• *{sale['item_name'][:25]}*\n"
                f"  Status: {sale['status']} | Price: ${sale['current_price']:.2f}\n"
                f"  Profit: {profit_str} ({sale['profit_percent']:.1f}%)"
            )

        if len(sales) > 10:
            lines.append(f"\n_...and {len(sales) - 10} more_")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
            ]),
            parse_mode="Markdown",
        )

    async def _show_cancel_menu(self, query) -> None:
        """Show menu to cancel active sales."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        sales = self._auto_seller.get_active_sales()

        if not sales:
            await query.edit_message_text(
                "❌ *Cancel Sale*\n\nNo active sales to cancel.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
                ]),
                parse_mode="Markdown",
            )
            return

        # Create button for each sale (max 5)
        keyboard = []
        for sale in sales[:5]:
            short_name = (
                sale["item_name"][:20] + "..." if len(sale["item_name"]) > 20 else sale["item_name"]
            )
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {short_name}",
                    callback_data=f"auto_sell:cancel:{sale['item_id']}",
                )
            ])

        keyboard.append([InlineKeyboardButton("« Back", callback_data="auto_sell:back")])

        await query.edit_message_text(
            "❌ *Cancel Sale*\n\nSelect a sale to cancel:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _cancel_sale(self, query, item_id: str) -> None:
        """Cancel a specific sale."""
        if not self._auto_seller:
            await query.edit_message_text("❌ Auto-sell not configured")
            return

        success = await self._auto_seller.cancel_sale(item_id)

        if success:
            await query.edit_message_text(
                f"✅ Sale cancelled: {item_id[:20]}...",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
                ]),
            )
        else:
            await query.edit_message_text(
                "❌ Failed to cancel sale. Item may already be sold.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Back", callback_data="auto_sell:back")]
                ]),
            )

    async def _start_config_edit(self, query, param: str) -> int:
        """Start editing a config parameter."""
        query.message.chat.send_message(
            f"Enter new value for {param}:",
        )
        # Store param in user_data for later
        return CONFIG_EDIT

    async def _update_config(self, param: str, value: float) -> None:
        """Update a config parameter."""
        if not self._auto_seller:
            return

        config = self._auto_seller.config

        if param == "min_margin_percent":
            config.min_margin_percent = value
        elif param == "target_margin_percent":
            config.target_margin_percent = value
        elif param == "max_margin_percent":
            config.max_margin_percent = value
        elif param == "stop_loss_percent":
            config.stop_loss_percent = value
        elif param == "stop_loss_hours":
            config.stop_loss_hours = int(value)

        logger.info(
            "auto_sell_config_updated",
            extra={"param": param, "value": value},
        )

    async def _show_main_menu(self, query) -> None:
        """Show main auto-sell menu."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="auto_sell:status"),
                InlineKeyboardButton("⚙️ Config", callback_data="auto_sell:config"),
            ],
            [
                InlineKeyboardButton("🔄 Toggle", callback_data="auto_sell:toggle"),
                InlineKeyboardButton("📋 Active Sales", callback_data="auto_sell:active"),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="auto_sell:cancel_menu"),
            ],
        ]

        status = "✅ Enabled" if self._is_enabled() else "❌ Disabled"
        await query.edit_message_text(
            f"🤖 *Auto-Sell Management*\n\nStatus: {status}\n\nChoose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    def get_handlers(self) -> list:
        """Get list of handlers for registration.

        Returns:
            List of handler objects
        """
        return [
            CommandHandler("auto_sell", self.handle_auto_sell_command),
            CallbackQueryHandler(
                self.handle_callback,
                pattern=r"^auto_sell:",
            ),
        ]


def format_auto_sell_notification(
    item_name: str,
    action: str,
    price: float,
    profit: float | None = None,
) -> str:
    """Format auto-sell notification message.

    Args:
        item_name: Name of the item
        action: Action taken (listed, sold, cancelled, stop_loss)
        price: Price of the action
        profit: Profit/loss amount (for sold items)

    Returns:
        Formatted notification string
    """
    emoji_map = {
        "listed": "📤",
        "sold": "✅",
        "cancelled": "❌",
        "stop_loss": "⚠️",
        "adjusted": "🔄",
    }

    emoji = emoji_map.get(action, "📝")
    action_text = action.replace("_", " ").title()

    message = f"{emoji} *Auto-Sell: {action_text}*\n\n"
    message += f"Item: {item_name}\n"
    message += f"Price: ${price:.2f}\n"

    if profit is not None:
        profit_emoji = "📈" if profit >= 0 else "📉"
        profit_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
        message += f"{profit_emoji} Profit: {profit_str}"

    return message
