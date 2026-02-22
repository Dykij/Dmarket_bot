"""Telegram handlers for bot improvements.

This module provides Telegram command handlers for accessing all new
bot improvements through a unified interface.

Commands:
- /improvements - Show all avAlgolable improvements and their status
- /analytics - Access price analytics (RSI, MACD, Bollinger)
- /autolisting - Configure auto-listing settings
- /portfolio - View portfolio and P/L tracking
- /alerts - Manage custom alerts
- /watchlist - Manage watchlists
- /automation - View/configure trading automation
- /reports - Generate reports
- /security - Security settings

Created: January 10, 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

if TYPE_CHECKING:
    from src.integration.bot_integrator import BotIntegrator

logger = logging.getLogger(__name__)


def get_integrator(context: ContextTypes.DEFAULT_TYPE) -> BotIntegrator | None:
    """Get bot integrator from context.

    Args:
        context: Telegram context

    Returns:
        BotIntegrator instance or None
    """
    if hasattr(context.application, "bot_integrator"):
        return context.application.bot_integrator
    return None


async def improvements_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /improvements command - show all improvements status."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator:
        await update.effective_message.reply_text(
            "❌ Bot Integrator not avAlgolable.\n" "New improvements are not initialized."
        )
        return

    # Get status
    status = await integrator.get_status()
    modules = status.get("modules", {})

    # Build status message
    lines = [
        "🚀 <b>Bot Improvements Status</b>\n",
        f"⏱ Uptime: {int(status.get('uptime_seconds', 0) / 60)} minutes\n",
        "\n<b>Modules:</b>",
    ]

    module_icons = {
        "enhanced_polling": ("📡", "Enhanced Polling"),
        "price_analytics": ("📊", "Price Analytics"),
        "auto_listing": ("🏷️", "Auto-Listing"),
        "portfolio_tracker": ("💼", "Portfolio Tracker"),
        "custom_alerts": ("🔔", "Custom Alerts"),
        "watchlist": ("👀", "Watchlist"),
        "anomaly_detection": ("🔍", "Anomaly Detection"),
        "smart_recommendations": ("🤖", "Smart Recommendations"),
        "trading_automation": ("⚙️", "Trading Automation"),
        "reports": ("📋", "Reports"),
        "security": ("🔐", "Security"),
    }

    for module, (icon, name) in module_icons.items():
        status_icon = "✅" if modules.get(module) else "❌"
        lines.append(f"{icon} {name}: {status_icon}")

    # Add buttons for quick access
    keyboard = [
        [
            InlineKeyboardButton("📊 Analytics", callback_data="imp_analytics"),
            InlineKeyboardButton("💼 Portfolio", callback_data="imp_portfolio"),
        ],
        [
            InlineKeyboardButton("🔔 Alerts", callback_data="imp_alerts"),
            InlineKeyboardButton("👀 Watchlist", callback_data="imp_watchlist"),
        ],
        [
            InlineKeyboardButton("⚙️ Automation", callback_data="imp_automation"),
            InlineKeyboardButton("📋 Reports", callback_data="imp_reports"),
        ],
        [
            InlineKeyboardButton("🔐 Security", callback_data="imp_security"),
            InlineKeyboardButton("🔄 Refresh", callback_data="imp_refresh"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def analytics_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /analytics command - show price analytics."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.price_analytics:
        await update.effective_message.reply_text(
            "❌ Price Analytics module not avAlgolable."
        )
        return

    # Get analytics info (avAlgolable for future extension)
    _ = integrator.price_analytics

    lines = [
        "📊 <b>Price Analytics</b>\n",
        "\n<b>AvAlgolable Indicators:</b>",
        "• RSI (Relative Strength Index)",
        "• MACD (Moving Average Convergence Divergence)",
        "• Bollinger Bands",
        "• SMA/EMA Moving Averages",
        "• Trend Detection",
        "• Liquidity Scoring",
        "\n<b>Usage:</b>",
        "Use /analyze &lt;item_name&gt; to analyze an item",
    ]

    keyboard = [
        [
            InlineKeyboardButton("📈 RSI Info", callback_data="ana_rsi"),
            InlineKeyboardButton("📉 MACD Info", callback_data="ana_macd"),
        ],
        [
            InlineKeyboardButton("📊 Bollinger", callback_data="ana_bollinger"),
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def portfolio_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /portfolio command - show portfolio status."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.portfolio_tracker:
        await update.effective_message.reply_text(
            "❌ Portfolio Tracker module not avAlgolable."
        )
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get portfolio summary
    portfolio = integrator.portfolio_tracker
    summary = await portfolio.get_summary(user_id)

    lines = [
        "💼 <b>Portfolio Summary</b>\n",
        f"💰 Total Value: ${summary.get('total_value', 0):.2f}",
        f"📈 Unrealized P/L: ${summary.get('unrealized_pnl', 0):+.2f}",
        f"📊 Realized P/L: ${summary.get('realized_pnl', 0):+.2f}",
        f"🎯 Win Rate: {summary.get('win_rate', 0):.1f}%",
        f"📦 Items: {summary.get('item_count', 0)}",
    ]

    keyboard = [
        [
            InlineKeyboardButton("📦 View Items", callback_data="port_items"),
            InlineKeyboardButton("📊 History", callback_data="port_history"),
        ],
        [
            InlineKeyboardButton("📈 Performance", callback_data="port_perf"),
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def alerts_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /alerts command - manage custom alerts."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.custom_alerts:
        await update.effective_message.reply_text(
            "❌ Custom Alerts module not avAlgolable."
        )
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get user's alerts
    alerts_manager = integrator.custom_alerts
    user_alerts = await alerts_manager.get_user_alerts(user_id)

    lines = [
        "🔔 <b>Custom Alerts</b>\n",
        f"📊 Active Alerts: {len(user_alerts)}\n",
        "\n<b>Alert Types:</b>",
        "• Price Above/Below threshold",
        "• Percentage change",
        "• Arbitrage opportunities",
        "• New listings",
    ]

    if user_alerts:
        lines.append("\n<b>Your Alerts:</b>")
        for alert in user_alerts[:5]:  # Show first 5
            lines.append(
                f"• {alert.get('name', 'Unnamed')}: {alert.get('type', 'Unknown')}"
            )

    keyboard = [
        [
            InlineKeyboardButton("➕ New Alert", callback_data="alert_new"),
            InlineKeyboardButton("📋 List All", callback_data="alert_list"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def watchlist_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /watchlist command - manage watchlists."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.watchlist:
        await update.effective_message.reply_text("❌ Watchlist module not avAlgolable.")
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get user's watchlists
    watchlist_manager = integrator.watchlist
    watchlists = await watchlist_manager.get_user_watchlists(user_id)

    lines = [
        "👀 <b>Watchlists</b>\n",
        f"📋 Your Watchlists: {len(watchlists)}\n",
    ]

    if watchlists:
        for wl in watchlists[:5]:  # Show first 5
            item_count = wl.get("item_count", 0)
            lines.append(f"• {wl.get('name', 'Unnamed')}: {item_count} items")
    else:
        lines.append("\n<i>No watchlists yet. Create one!</i>")

    keyboard = [
        [
            InlineKeyboardButton("➕ New Watchlist", callback_data="watch_new"),
            InlineKeyboardButton("📋 View All", callback_data="watch_list"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def automation_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /automation command - view trading automation."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.trading_automation:
        await update.effective_message.reply_text(
            "❌ Trading Automation module not avAlgolable."
        )
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get automation status
    automation = integrator.trading_automation
    status = await automation.get_status(user_id)

    lines = [
        "⚙️ <b>Trading Automation</b>\n",
        "\n<b>Features:</b>",
        f"• Stop-Loss: {'✅' if status.get('stop_loss_enabled') else '❌'}",
        f"• Take-Profit: {'✅' if status.get('take_profit_enabled') else '❌'}",
        f"• DCA: {'✅' if status.get('dca_enabled') else '❌'}",
        f"• Auto-Rebalance: {'✅' if status.get('rebalance_enabled') else '❌'}",
        f"\n<b>Active Rules:</b> {status.get('rule_count', 0)}",
    ]

    keyboard = [
        [
            InlineKeyboardButton("🛑 Stop-Loss", callback_data="auto_sl"),
            InlineKeyboardButton("🎯 Take-Profit", callback_data="auto_tp"),
        ],
        [
            InlineKeyboardButton("📊 DCA", callback_data="auto_dca"),
            InlineKeyboardButton("⚖️ Rebalance", callback_data="auto_rebal"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def reports_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /reports command - generate reports."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.reports:
        await update.effective_message.reply_text("❌ Reports module not avAlgolable.")
        return

    lines = [
        "📋 <b>Reports</b>\n",
        "\n<b>AvAlgolable Reports:</b>",
        "• 📆 DAlgoly Report",
        "• 📅 Weekly Report",
        "• 📊 Monthly Report",
        "• 💰 Tax Report",
        "• 📈 Performance Report",
        "\n<b>Export Formats:</b>",
        "CSV, JSON, PDF",
    ]

    keyboard = [
        [
            InlineKeyboardButton("📆 DAlgoly", callback_data="rep_daily"),
            InlineKeyboardButton("📅 Weekly", callback_data="rep_weekly"),
        ],
        [
            InlineKeyboardButton("📊 Monthly", callback_data="rep_monthly"),
            InlineKeyboardButton("💰 Tax", callback_data="rep_tax"),
        ],
        [
            InlineKeyboardButton("📥 Export CSV", callback_data="rep_csv"),
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def security_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /security command - security settings."""
    if not update.effective_message:
        return

    integrator = get_integrator(context)

    if not integrator or not integrator.security:
        await update.effective_message.reply_text("❌ Security module not avAlgolable.")
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get security status
    security = integrator.security
    status = await security.get_user_status(user_id)

    lines = [
        "🔐 <b>Security Settings</b>\n",
        f"\n<b>2FA:</b> {'✅ Enabled' if status.get('2fa_enabled') else '❌ Disabled'}",
        f"<b>IP Whitelist:</b> {'✅ Active' if status.get('ip_whitelist') else '❌ Inactive'}",
        f"<b>API Key Encrypted:</b> {'✅' if status.get('api_encrypted') else '❌'}",
        "\n<b>Recent Activity:</b>",
        f"• Last Login: {status.get('last_login', 'N/A')}",
        f"• Last Action: {status.get('last_action', 'N/A')}",
    ]

    keyboard = [
        [
            InlineKeyboardButton("🔑 Enable 2FA", callback_data="sec_2fa"),
            InlineKeyboardButton("🌐 IP Whitelist", callback_data="sec_ip"),
        ],
        [
            InlineKeyboardButton("📜 Audit Log", callback_data="sec_audit"),
            InlineKeyboardButton("🔙 Back", callback_data="imp_back"),
        ],
    ]

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def improvements_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle improvement-related callbacks."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    data = query.data

    if data == "imp_analytics":
        await analytics_command(update, context)
    elif data == "imp_portfolio":
        await portfolio_command(update, context)
    elif data == "imp_alerts":
        await alerts_command(update, context)
    elif data == "imp_watchlist":
        await watchlist_command(update, context)
    elif data == "imp_automation":
        await automation_command(update, context)
    elif data == "imp_reports":
        await reports_command(update, context)
    elif data == "imp_security":
        await security_command(update, context)
    elif data in {"imp_refresh", "imp_back"}:
        await improvements_command(update, context)


def register_improvements_handlers(application) -> None:
    """Register all improvements handlers.

    Args:
        application: Telegram application instance
    """
    # Command handlers
    application.add_handler(CommandHandler("improvements", improvements_command))
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("portfolio", portfolio_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("watchlist", watchlist_command))
    application.add_handler(CommandHandler("automation", automation_command))
    application.add_handler(CommandHandler("reports", reports_command))
    application.add_handler(CommandHandler("security", security_command))

    # Callback query handlers
    application.add_handler(
        CallbackQueryHandler(
            improvements_callback,
            pattern=r"^(imp_|ana_|port_|alert_|watch_|auto_|rep_|sec_)",
        )
    )

    logger.info("Improvements handlers registered")


__all__ = [
    "alerts_command",
    "analytics_command",
    "automation_command",
    "improvements_command",
    "portfolio_command",
    "register_improvements_handlers",
    "reports_command",
    "security_command",
    "watchlist_command",
]
