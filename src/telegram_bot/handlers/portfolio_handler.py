"""Telegram handler for portfolio management commands.

Provides commands for viewing and managing portfolio:
- /portfolio - View portfolio summary
- /portfolio add - Add item to portfolio
- /portfolio remove - Remove item
- /portfolio sync - Sync with DMarket inventory
"""

from __future__ import annotations

import logging
import operator
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.portfolio import PortfolioAnalyzer, PortfolioManager, PortfolioMetrics

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)

# Conversation states
WAlgoTING_ITEM_ID = 1
WAlgoTING_PRICE = 2


class PortfolioHandler:
    """Handler for portfolio Telegram commands.

    Provides user interface for portfolio management:
    - View summary and metrics
    - Add/remove items
    - Sync with inventory
    - Risk and diversification analysis
    """

    def __init__(
        self,
        api: IDMarketAPI | None = None,
    ) -> None:
        """Initialize handler.

        Args:
            api: DMarket API client
        """
        self._api = api
        self._manager = PortfolioManager(api=api)
        self._analyzer = PortfolioAnalyzer()

    def set_api(self, api: IDMarketAPI) -> None:
        """Set the API client."""
        self._api = api
        self._manager.set_api(api)

    async def handle_portfolio_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /portfolio command.

        Shows portfolio summary and options.
        """
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        metrics = self._manager.get_metrics(user_id)

        keyboard = [
            [
                InlineKeyboardButton("📊 Details", callback_data="portfolio:details"),
                InlineKeyboardButton(
                    "📈 Performance", callback_data="portfolio:performance"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎯 Risk Analysis", callback_data="portfolio:risk"
                ),
                InlineKeyboardButton(
                    "🔀 Diversification", callback_data="portfolio:diversification"
                ),
            ],
            [
                InlineKeyboardButton("➕ Add Item", callback_data="portfolio:add"),
                InlineKeyboardButton("🔄 Sync", callback_data="portfolio:sync"),
            ],
            [
                InlineKeyboardButton(
                    "💰 Update Prices", callback_data="portfolio:update_prices"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format summary
        text = self._format_summary(metrics)

        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int | None:
        """Handle portfolio callback queries."""
        query = update.callback_query
        if not query or not query.data or not update.effective_user:
            return None

        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        if data == "portfolio:details":
            await self._show_details(query, user_id)
        elif data == "portfolio:performance":
            await self._show_performance(query, user_id)
        elif data == "portfolio:risk":
            await self._show_risk_analysis(query, user_id)
        elif data == "portfolio:diversification":
            await self._show_diversification(query, user_id)
        elif data == "portfolio:add":
            return await self._start_add_item(query, context)
        elif data == "portfolio:sync":
            await self._sync_portfolio(query, user_id)
        elif data == "portfolio:update_prices":
            await self._update_prices(query, user_id)
        elif data == "portfolio:back":
            await self._show_main_menu(query, user_id)
        elif data.startswith("portfolio:remove:"):
            item_id = data.split(":")[-1]
            await self._remove_item(query, user_id, item_id)

        return None

    async def handle_add_item_id(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle item ID input for adding."""
        if not update.message or not context.user_data:
            return ConversationHandler.END

        text = update.message.text
        if not text:
            return ConversationHandler.END

        # Parse item details from text (format: "item_name, game, price")
        parts = [p.strip() for p in text.split(",")]

        if len(parts) < 3:
            await update.message.reply_text(
                "❌ Invalid format.\n\n"
                "Please use: `item_name, game, buy_price`\n"
                "Example: `AK-47 | Redline, csgo, 25.50`",
                parse_mode="Markdown",
            )
            return WAlgoTING_ITEM_ID

        try:
            title = parts[0]
            game = parts[1].lower()
            price = float(parts[2])

            user_id = update.effective_user.id if update.effective_user else 0

            # Generate a simple item ID
            item_id = f"{game}_{title.replace(' ', '_')[:20]}_{int(price * 100)}"

            self._manager.add_item(
                user_id=user_id,
                item_id=item_id,
                title=title,
                game=game,
                buy_price=price,
            )

            await update.message.reply_text(
                f"✅ Added to portfolio:\n\n"
                f"*{title}*\n"
                f"Game: {game.upper()}\n"
                f"Buy Price: ${price:.2f}",
                parse_mode="Markdown",
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Invalid price. Please enter a valid number.",
            )
            return WAlgoTING_ITEM_ID

        return ConversationHandler.END

    def _format_summary(self, metrics: PortfolioMetrics) -> str:
        """Format portfolio summary for display."""
        if metrics.items_count == 0:
            return "📁 *Your Portfolio*\n\n_Empty portfolio. Add items or sync with DMarket!_"

        pnl_emoji = "📈" if metrics.total_pnl >= 0 else "📉"
        pnl_str = (
            f"+${float(metrics.total_pnl):.2f}"
            if metrics.total_pnl >= 0
            else f"-${abs(float(metrics.total_pnl)):.2f}"
        )

        return (
            f"📁 *Your Portfolio*\n\n"
            f"*Value:* ${float(metrics.total_value):.2f}\n"
            f"*Cost:* ${float(metrics.total_cost):.2f}\n"
            f"{pnl_emoji} *P&L:* {pnl_str} ({metrics.total_pnl_percent:+.1f}%)\n\n"
            f"*Items:* {metrics.items_count} ({metrics.total_quantity} total)\n"
            f"*Avg Hold:* {metrics.avg_holding_days:.0f} days\n\n"
            f"📈 *Best:* {metrics.best_performer[:20]}... ({metrics.best_performer_pnl:+.1f}%)\n"
            f"📉 *Worst:* {metrics.worst_performer[:20]}... ({metrics.worst_performer_pnl:+.1f}%)"
        )

    async def _show_details(self, query, user_id: int) -> None:
        """Show portfolio item details."""
        items = self._manager.get_items(user_id)

        if not items:
            await query.edit_message_text(
                "📋 *Portfolio Items*\n\nNo items in portfolio.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
                parse_mode="Markdown",
            )
            return

        # Show first 10 items
        lines = ["📋 *Portfolio Items*\n"]
        for item in items[:10]:
            pnl_emoji = "🟢" if item.pnl >= 0 else "🔴"
            lines.append(
                f"{pnl_emoji} *{item.title[:25]}*\n"
                f"   ${float(item.current_price):.2f} | "
                f"P&L: {item.pnl_percent:+.1f}%"
            )

        if len(items) > 10:
            lines.append(f"\n_...and {len(items) - 10} more items_")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
            ),
            parse_mode="Markdown",
        )

    async def _show_performance(self, query, user_id: int) -> None:
        """Show portfolio performance."""
        portfolio = self._manager.get_portfolio(user_id)
        top_performers = self._analyzer.get_top_performers(portfolio, 5)
        worst_performers = self._analyzer.get_worst_performers(portfolio, 5)

        lines = ["📈 *Portfolio Performance*\n\n*Top Performers:*"]
        for i, item in enumerate(top_performers, 1):
            lines.append(f"{i}. {item.title[:20]}... ({item.pnl_percent:+.1f}%)")

        lines.append("\n*Worst Performers:*")
        for i, item in enumerate(worst_performers, 1):
            lines.append(f"{i}. {item.title[:20]}... ({item.pnl_percent:+.1f}%)")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
            ),
            parse_mode="Markdown",
        )

    async def _show_risk_analysis(self, query, user_id: int) -> None:
        """Show risk analysis."""
        portfolio = self._manager.get_portfolio(user_id)
        report = self._analyzer.analyze_risk(portfolio)

        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }.get(report.risk_level, "⚪")

        lines = [
            (
                f"🎯 *Risk Analysis*\n\n"
                f"{risk_emoji} *Risk Level:* {report.risk_level.upper()}\n"
                f"*Overall Score:* {report.overall_risk_score:.0f}/100\n\n"
                f"*Breakdown:*\n"
                f"  Volatility: {report.volatility_score:.0f}/100\n"
                f"  Liquidity: {report.liquidity_score:.0f}/100\n"
                f"  Concentration: {report.concentration_score:.0f}/100\n\n"
                f"*Recommendations:*"
            )
        ]

        for rec in report.recommendations[:3]:
            lines.append(f"• {rec}")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
            ),
            parse_mode="Markdown",
        )

    async def _show_diversification(self, query, user_id: int) -> None:
        """Show diversification analysis."""
        portfolio = self._manager.get_portfolio(user_id)
        report = self._analyzer.analyze_diversification(portfolio)

        lines = [
            (
                f"🔀 *Diversification Analysis*\n\n"
                f"*Score:* {report.diversification_score:.0f}/100\n\n"
                f"*By Game:*"
            )
        ]

        for game, pct in report.by_game.items():
            lines.append(f"  {game.upper()}: {pct:.1f}%")

        lines.append("\n*By Category:*")
        for cat, pct in sorted(
            report.by_category.items(), key=operator.itemgetter(1), reverse=True
        )[:5]:
            lines.append(f"  {cat}: {pct:.1f}%")

        lines.append("\n*Recommendations:*")
        for rec in report.recommendations[:3]:
            lines.append(f"• {rec}")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
            ),
            parse_mode="Markdown",
        )

    async def _start_add_item(self, query, context) -> int:
        """Start add item conversation."""
        await query.edit_message_text(
            "➕ *Add Item to Portfolio*\n\n"
            "Send item details in format:\n"
            "`item_name, game, buy_price`\n\n"
            "Example:\n"
            "`AK-47 | Redline (Field-Tested), csgo, 25.50`\n\n"
            "Send /cancel to abort.",
            parse_mode="Markdown",
        )
        return WAlgoTING_ITEM_ID

    async def _sync_portfolio(self, query, user_id: int) -> None:
        """Sync portfolio with DMarket inventory."""
        await query.edit_message_text("🔄 Syncing with DMarket inventory...")

        synced = await self._manager.sync_with_inventory(user_id)

        if synced > 0:
            await query.edit_message_text(
                f"✅ Synced {synced} items from your inventory!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )
        else:
            await query.edit_message_text(
                "ℹ️ No new items to sync or API not configured.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )

    async def _update_prices(self, query, user_id: int) -> None:
        """Update portfolio prices."""
        await query.edit_message_text("💰 Updating prices...")

        updated = await self._manager.update_prices(user_id)

        if updated > 0:
            metrics = self._manager.get_metrics(user_id)
            await query.edit_message_text(
                f"✅ Updated {updated} prices!\n\n"
                f"New portfolio value: ${float(metrics.total_value):.2f}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )
        else:
            await query.edit_message_text(
                "ℹ️ No prices to update or API not configured.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )

    async def _remove_item(self, query, user_id: int, item_id: str) -> None:
        """Remove item from portfolio."""
        removed = self._manager.remove_item(user_id, item_id)

        if removed:
            await query.edit_message_text(
                f"✅ Removed {removed.title} from portfolio.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )
        else:
            await query.edit_message_text(
                "❌ Item not found in portfolio.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="portfolio:back")]]
                ),
            )

    async def _show_main_menu(self, query, user_id: int) -> None:
        """Show main portfolio menu."""
        metrics = self._manager.get_metrics(user_id)
        text = self._format_summary(metrics)

        keyboard = [
            [
                InlineKeyboardButton("📊 Details", callback_data="portfolio:details"),
                InlineKeyboardButton(
                    "📈 Performance", callback_data="portfolio:performance"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎯 Risk Analysis", callback_data="portfolio:risk"
                ),
                InlineKeyboardButton(
                    "🔀 Diversification", callback_data="portfolio:diversification"
                ),
            ],
            [
                InlineKeyboardButton("➕ Add Item", callback_data="portfolio:add"),
                InlineKeyboardButton("🔄 Sync", callback_data="portfolio:sync"),
            ],
            [
                InlineKeyboardButton(
                    "💰 Update Prices", callback_data="portfolio:update_prices"
                ),
            ],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    def get_handlers(self) -> list:
        """Get list of handlers for registration."""
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.handle_callback,
                    pattern=r"^portfolio:add$",
                ),
            ],
            states={
                WAlgoTING_ITEM_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_add_item_id,
                    ),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            ],
        )

        return [
            CommandHandler("portfolio", self.handle_portfolio_command),
            CallbackQueryHandler(
                self.handle_callback,
                pattern=r"^portfolio:",
            ),
            conv_handler,
        ]


__all__ = ["PortfolioHandler"]
