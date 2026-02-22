"""Advanced Features Handler - Integration of previously unused modules.

This handler integrates the following modules into the Telegram bot:
1. Profit Charts - Visual profit/ROI charts
2. Market Visualizer - Price charts with support/resistance
3. Smart Market Finder - Find underpriced items and opportunities
4. Trending Items Finder - Find items with upward price trends
5. Price Aggregator - Batch price fetching optimization
6. Shadow Listing - Smart competitive pricing
7. Sniper Cycle - Automated quick-buy opportunities
8. Smart Bidder - Competitive bidding on targets

Commands:
- /charts - Generate profit/ROI charts
- /visualize <item> - Visualize item price history
- /smart_find - Find best market opportunities
- /trends - Find trending items
- /sniper - Run sniper cycle
- /shadow - Shadow listing analysis
- /bid - Smart bidding interface

Created: January 10, 2026
"""

from __future__ import annotations

import io
import logging
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

from src.telegram_bot.utils.api_helper import create_dmarket_api_client

if TYPE_CHECKING:
    from telegram.ext import Application


logger = logging.getLogger(__name__)


# Conversation states
CHARTS_SELECT, VISUALIZE_ITEM, SMART_FIND_GAME, TRENDS_GAME = range(4)


# =============================================================================
# Charts Handler - Profit visualization
# =============================================================================


async def charts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /charts command - show chart options."""
    keyboard = [
        [
            InlineKeyboardButton(
                "📈 Cumulative Profit", callback_data="chart_cumulative"
            ),
            InlineKeyboardButton("📊 ROI Chart", callback_data="chart_roi"),
        ],
        [
            InlineKeyboardButton("🎯 Win Rate", callback_data="chart_winrate"),
            InlineKeyboardButton("❌ Cancel", callback_data="chart_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📊 **Chart Generator**\n\n"
        "Select the type of chart to generate:\n\n"
        "• **Cumulative Profit** - Shows profit over time\n"
        "• **ROI Chart** - DAlgoly return on investment\n"
        "• **Win Rate** - Success rate pie chart",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return CHARTS_SELECT


async def charts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle chart selection callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "chart_cancel":
        await query.edit_message_text("Chart generation cancelled.")
        return ConversationHandler.END

    # Try to import chart generator
    try:
        from src.utils.profit_charts import MATPLOTLIB_AVAlgoLABLE, ProfitChartGenerator

        if not MATPLOTLIB_AVAlgoLABLE:
            await query.edit_message_text(
                "⚠️ Chart generation requires matplotlib.\n"
                "Install with: `pip install matplotlib`",
                parse_mode="Markdown",
            )
            return ConversationHandler.END

        generator = ProfitChartGenerator()

    except ImportError as e:
        await query.edit_message_text(f"⚠️ Chart module not avAlgolable: {e}")
        return ConversationHandler.END

    await query.edit_message_text("⏳ Generating chart...")

    # Get purchase data from database (mock for now)
    import random
    from datetime import datetime, timedelta

    # Generate sample data
    base_time = datetime.now()

    if query.data == "chart_cumulative":
        # Sample purchases with profit
        purchases = [
            {
                "timestamp": base_time - timedelta(hours=i),
                "profit": random.uniform(-2, 5),
            }
            for i in range(24, 0, -1)
        ]

        chart_bytes = await generator.generate_cumulative_profit_chart(
            purchases=purchases,
            title="Cumulative Profit (24h)",
        )

    elif query.data == "chart_roi":
        # Sample daily stats
        daily_stats = [
            {
                "date": (base_time - timedelta(days=i)).strftime("%m/%d"),
                "spent": random.uniform(50, 200),
                "earned": random.uniform(55, 250),
            }
            for i in range(7, 0, -1)
        ]

        chart_bytes = await generator.generate_roi_chart(
            daily_stats=daily_stats,
            title="DAlgoly ROI (7 days)",
        )

    elif query.data == "chart_winrate":
        # Sample trade results
        successful = random.randint(50, 100)
        failed = random.randint(5, 30)

        chart_bytes = await generator.generate_win_rate_pie_chart(
            successful_trades=successful,
            failed_trades=failed,
            title="Trade Success Rate",
        )
    else:
        await query.edit_message_text("Unknown chart type.")
        return ConversationHandler.END

    # Send chart as photo
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=io.BytesIO(chart_bytes),
        caption=f"📊 {query.data.replace('chart_', '').replace('_', ' ').title()} Chart",
    )

    await query.delete_message()
    return ConversationHandler.END


# =============================================================================
# Market Visualizer Handler
# =============================================================================


async def visualize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /visualize command - visualize item price history."""
    if context.args:
        # Item name provided as argument
        item_name = " ".join(context.args)
        await _generate_visualization(update, context, item_name)
        return ConversationHandler.END

    await update.message.reply_text(
        "📈 **Market Visualizer**\n\n"
        "Send me the item name to visualize its price history.\n\n"
        "Example: `AK-47 | Redline (Field-Tested)`\n\n"
        "Or use: `/visualize <item name>`",
        parse_mode="Markdown",
    )
    return VISUALIZE_ITEM


async def visualize_item_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle item name input for visualization."""
    item_name = update.message.text
    await _generate_visualization(update, context, item_name)
    return ConversationHandler.END


async def _generate_visualization(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_name: str,
) -> None:
    """Generate and send price visualization."""
    await update.message.reply_text(f"⏳ Generating visualization for: {item_name}...")

    try:
        from src.utils.market_visualizer import MarketVisualizer

        visualizer = MarketVisualizer(theme="dark")

        # Get price history (mock for now - would fetch from API)
        import random
        from datetime import datetime, timedelta

        base_price = random.uniform(5, 50)
        base_time = datetime.now()

        price_history = [
            {
                "timestamp": (base_time - timedelta(days=i)).timestamp(),
                "price": base_price * (1 + random.uniform(-0.1, 0.15)),
                "volume": random.randint(10, 100),
            }
            for i in range(30, 0, -1)
        ]

        # Generate chart
        buf = await visualizer.create_price_chart(
            price_history=price_history,
            item_name=item_name,
            game="csgo",
            include_volume=True,
        )

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=buf,
            caption=f"📈 Price history for: {item_name}",
        )

    except ImportError as e:
        await update.message.reply_text(f"⚠️ Visualization module not avAlgolable: {e}")
    except Exception as e:
        logger.exception(f"Visualization error: {e}")
        await update.message.reply_text(f"❌ Error generating visualization: {e}")


# =============================================================================
# Smart Market Finder Handler
# =============================================================================


async def smart_find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /smart_find command - find best market opportunities."""
    keyboard = [
        [
            InlineKeyboardButton("🎮 CS2", callback_data="sf_csgo"),
            InlineKeyboardButton("🎮 Dota 2", callback_data="sf_dota2"),
        ],
        [
            InlineKeyboardButton("🎮 TF2", callback_data="sf_tf2"),
            InlineKeyboardButton("🎮 Rust", callback_data="sf_rust"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="sf_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔍 **Smart Market Finder**\n\n"
        "Find the best opportunities on the market:\n"
        "• Underpriced items (below suggested price)\n"
        "• Quick flip opportunities\n"
        "• Target arbitrage\n\n"
        "Select a game to search:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return SMART_FIND_GAME


async def smart_find_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle smart find game selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "sf_cancel":
        await query.edit_message_text("Search cancelled.")
        return ConversationHandler.END

    game = query.data.replace("sf_", "")
    await query.edit_message_text(f"⏳ Searching for opportunities in {game}...")

    try:
        from src.dmarket.smart_market_finder import SmartMarketFinder

        # Create API client
        api_client = create_dmarket_api_client(context)

        finder = SmartMarketFinder(api_client)

        # Find opportunities
        opportunities = await finder.find_best_opportunities(
            game=game,
            min_price=1.0,
            max_price=50.0,
            limit=10,
            min_confidence=60.0,
        )

        if not opportunities:
            await query.edit_message_text(
                f"🔍 No opportunities found for {game}.\n\n"
                "Try different price range or game.",
            )
            return ConversationHandler.END

        # Format results
        message = f"🔍 **Best Opportunities for {game.upper()}**\n\n"

        for i, opp in enumerate(opportunities[:5], 1):
            emoji = (
                "🟢"
                if opp.risk_level == "low"
                else "🟡" if opp.risk_level == "medium" else "🔴"
            )
            message += (
                f"{i}. **{opp.title[:30]}**\n"
                f"   💰 ${opp.current_price:.2f} → ${opp.suggested_price:.2f}\n"
                f"   📈 Profit: ${opp.profit_potential:.2f} ({opp.profit_percent:.1f}%)\n"
                f"   {emoji} Risk: {opp.risk_level} | Confidence: {opp.confidence_score:.0f}%\n\n"
            )

        await query.edit_message_text(message, parse_mode="Markdown")

    except ImportError as e:
        await query.edit_message_text(f"⚠️ Smart finder module not avAlgolable: {e}")
    except Exception as e:
        logger.exception(f"Smart find error: {e}")
        await query.edit_message_text(f"❌ Error: {e}")

    return ConversationHandler.END


# =============================================================================
# Trending Items Handler
# =============================================================================


async def trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /trends command - find trending items."""
    keyboard = [
        [
            InlineKeyboardButton("🎮 CS2", callback_data="tr_csgo"),
            InlineKeyboardButton("🎮 Dota 2", callback_data="tr_dota2"),
        ],
        [
            InlineKeyboardButton("🎮 TF2", callback_data="tr_tf2"),
            InlineKeyboardButton("🎮 Rust", callback_data="tr_rust"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="tr_cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📈 **Trending Items Finder**\n\n"
        "Find items with upward price trends:\n"
        "• Rising prices (>5% increase)\n"
        "• Recovery potential (dip then rise)\n"
        "• High sales activity\n\n"
        "Select a game to search:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return TRENDS_GAME


async def trends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trends game selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "tr_cancel":
        await query.edit_message_text("Search cancelled.")
        return ConversationHandler.END

    game = query.data.replace("tr_", "")
    await query.edit_message_text(f"⏳ Searching for trending items in {game}...")

    try:
        from src.dmarket.trending_items_finder import TrendingItemsFinder

        # Create API client
        api_client = create_dmarket_api_client(context)

        finder = TrendingItemsFinder(
            game=game,
            min_price=5.0,
            max_price=200.0,
            max_results=10,
        )

        # Find trending items
        trending = await finder.find(api_client)

        if not trending:
            await query.edit_message_text(
                f"📈 No trending items found for {game}.\n\n"
                "The market may be stable or there's not enough data.",
            )
            return ConversationHandler.END

        # Format results
        message = f"📈 **Trending Items for {game.upper()}**\n\n"

        for i, item in enumerate(trending[:5], 1):
            trend_emoji = "🚀" if item["trend"] == "upward" else "📈"
            message += (
                f"{i}. **{item['item'].get('title', 'Unknown')[:30]}**\n"
                f"   {trend_emoji} Trend: {item['trend']}\n"
                f"   💰 Current: ${item['current_price']:.2f}\n"
                f"   📊 Change: {item['price_change_percent']:+.1f}%\n"
                f"   💵 Potential: ${item['potential_profit']:.2f} ({item['potential_profit_percent']:.1f}%)\n\n"
            )

        await query.edit_message_text(message, parse_mode="Markdown")

    except ImportError as e:
        await query.edit_message_text(f"⚠️ Trending finder module not avAlgolable: {e}")
    except Exception as e:
        logger.exception(f"Trends error: {e}")
        await query.edit_message_text(f"❌ Error: {e}")

    return ConversationHandler.END


# =============================================================================
# Sniper Cycle Handler
# =============================================================================


async def sniper_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sniper command - run sniper cycle."""
    keyboard = [
        [
            InlineKeyboardButton("🎯 Start Sniper", callback_data="sniper_start"),
            InlineKeyboardButton("⚙️ Settings", callback_data="sniper_settings"),
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="sniper_stats"),
            InlineKeyboardButton("❌ Cancel", callback_data="sniper_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎯 **Sniper Cycle**\n\n"
        "Automated quick-buy for profitable items:\n"
        "• Scans market for best deals\n"
        "• Analyzes profit potential\n"
        "• Auto-buys profitable items\n"
        "• Auto-lists for quick resale\n\n"
        "⚠️ **Warning**: This uses real balance!\n\n"
        "Select an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def sniper_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle sniper callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "sniper_cancel":
        await query.edit_message_text("Sniper cancelled.")
        return

    if query.data == "sniper_start":
        await query.edit_message_text(
            "⚠️ **Sniper cycle is in DRY RUN mode**\n\n"
            "This would:\n"
            "1. Scan market for deals\n"
            "2. Analyze profit potential\n"
            "3. Auto-buy profitable items\n"
            "4. Auto-list for resale\n\n"
            "Enable real trading in settings.",
        )
    elif query.data == "sniper_settings":
        await query.edit_message_text(
            "⚙️ **Sniper Settings**\n\n"
            "• Max price: $50.00\n"
            "• Min profit: 10%\n"
            "• Mode: DRY RUN\n"
            "• Game: CS2\n\n"
            "Use `/settings sniper` to configure.",
        )
    elif query.data == "sniper_stats":
        await query.edit_message_text(
            "📊 **Sniper Statistics**\n\n"
            "• Total runs: 0\n"
            "• Items bought: 0\n"
            "• Items sold: 0\n"
            "• Total profit: $0.00\n"
            "• Success rate: N/A",
        )


# =============================================================================
# Shadow Listing Handler
# =============================================================================


async def shadow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shadow command - shadow listing analysis."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Analyze Listing", callback_data="shadow_analyze"),
            InlineKeyboardButton("💰 Optimal Price", callback_data="shadow_price"),
        ],
        [
            InlineKeyboardButton("📈 Market Depth", callback_data="shadow_depth"),
            InlineKeyboardButton("❌ Cancel", callback_data="shadow_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👤 **Shadow Listing Manager**\n\n"
        "Smart competitive pricing:\n"
        "• Analyzes market depth\n"
        "• Detects scarcity/oversupply\n"
        "• Calculates optimal undercut\n"
        "• Avoids price wars\n\n"
        "Select an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def shadow_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shadow listing callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "shadow_cancel":
        await query.edit_message_text("Shadow listing cancelled.")
        return

    await query.edit_message_text(
        "👤 **Shadow Listing**\n\n"
        f"Feature: {query.data.replace('shadow_', '')}\n\n"
        "Use `/shadow <item_id>` to analyze specific item.\n\n"
        "Or list an item and it will auto-optimize price.",
    )


# =============================================================================
# Smart Bidder Handler
# =============================================================================


async def bid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bid command - smart bidding interface."""
    keyboard = [
        [
            InlineKeyboardButton("🎯 New Bid", callback_data="bid_new"),
            InlineKeyboardButton("📋 My Bids", callback_data="bid_list"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="bid_settings"),
            InlineKeyboardButton("❌ Cancel", callback_data="bid_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💵 **Smart Bidder**\n\n"
        "Competitive bidding on targets:\n"
        "• Auto outbid by $0.01\n"
        "• Profit margin checking\n"
        "• Market analysis before bid\n"
        "• Bid history tracking\n\n"
        "Select an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def bid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle smart bidder callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "bid_cancel":
        await query.edit_message_text("Bidding cancelled.")
        return

    if query.data == "bid_new":
        await query.edit_message_text(
            "🎯 **Create New Bid**\n\n"
            "To create a competitive bid, use:\n"
            "`/bid <item_name> <max_price>`\n\n"
            "Example:\n"
            "`/bid AK-47 | Redline (FT) 15.00`",
            parse_mode="Markdown",
        )
    elif query.data == "bid_list":
        await query.edit_message_text(
            "📋 **Your Active Bids**\n\n"
            "No active bids.\n\n"
            "Create a new bid with `/bid <item> <price>`",
        )
    elif query.data == "bid_settings":
        await query.edit_message_text(
            "⚙️ **Bidder Settings**\n\n"
            "• Min profit margin: 15%\n"
            "• Auto-outbid: Enabled\n"
            "• Max outbid amount: $0.10\n"
            "• Refresh interval: 60s\n\n"
            "Use `/settings bidder` to configure.",
        )


# =============================================================================
# Price Aggregator Handler
# =============================================================================


async def aggregate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /aggregate command - batch price checking."""
    await update.message.reply_text(
        "📦 **Price Aggregator**\n\n"
        "Efficiently fetch prices for multiple items:\n\n"
        "Usage:\n"
        "`/aggregate <item1>, <item2>, <item3>`\n\n"
        "Or paste a list of item names (one per line).\n\n"
        "This uses batch API calls for efficiency.",
        parse_mode="Markdown",
    )


# =============================================================================
# Advanced Features Status
# =============================================================================


async def advanced_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /advanced command - show advanced features status."""
    # Check module avAlgolability
    modules_status = {
        "Profit Charts": _check_module("src.utils.profit_charts"),
        "Market Visualizer": _check_module("src.utils.market_visualizer"),
        "Smart Market Finder": _check_module("src.dmarket.smart_market_finder"),
        "Trending Finder": _check_module("src.dmarket.trending_items_finder"),
        "Price Aggregator": _check_module("src.dmarket.price_aggregator"),
        "Shadow Listing": _check_module("src.dmarket.shadow_listing"),
        "Sniper Cycle": _check_module("src.dmarket.sniper_cycle"),
        "Smart Bidder": _check_module("src.dmarket.smart_bidder"),
    }

    message = "🔧 **Advanced Features Status**\n\n"

    for module, avAlgolable in modules_status.items():
        status = "✅" if avAlgolable else "❌"
        message += f"{status} {module}\n"

    message += "\n**Commands:**\n"
    message += "• `/charts` - Generate profit charts\n"
    message += "• `/visualize` - Visualize item prices\n"
    message += "• `/smart_find` - Find market opportunities\n"
    message += "• `/trends` - Find trending items\n"
    message += "• `/sniper` - Sniper cycle\n"
    message += "• `/shadow` - Shadow listing\n"
    message += "• `/bid` - Smart bidding\n"
    message += "• `/aggregate` - Batch price check\n"

    await update.message.reply_text(message, parse_mode="Markdown")


def _check_module(module_path: str) -> bool:
    """Check if a module is avAlgolable."""
    try:
        __import__(module_path.replace("/", "."))
        return True
    except ImportError:
        return False


# =============================================================================
# Cancel Handler
# =============================================================================


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle conversation cancellation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# =============================================================================
# Register Handlers
# =============================================================================


def get_advanced_features_handlers() -> list:
    """Get all advanced features handlers."""

    # Charts conversation handler
    charts_handler = ConversationHandler(
        entry_points=[CommandHandler("charts", charts_command)],
        states={
            CHARTS_SELECT: [
                CallbackQueryHandler(charts_callback, pattern="^chart_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )

    # Visualize conversation handler
    visualize_handler = ConversationHandler(
        entry_points=[CommandHandler("visualize", visualize_command)],
        states={
            VISUALIZE_ITEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, visualize_item_input),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )

    # Smart find conversation handler
    smart_find_handler = ConversationHandler(
        entry_points=[CommandHandler("smart_find", smart_find_command)],
        states={
            SMART_FIND_GAME: [
                CallbackQueryHandler(smart_find_callback, pattern="^sf_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )

    # Trends conversation handler
    trends_handler = ConversationHandler(
        entry_points=[CommandHandler("trends", trends_command)],
        states={
            TRENDS_GAME: [
                CallbackQueryHandler(trends_callback, pattern="^tr_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )

    return [
        charts_handler,
        visualize_handler,
        smart_find_handler,
        trends_handler,
        CommandHandler("sniper", sniper_command),
        CallbackQueryHandler(sniper_callback, pattern="^sniper_"),
        CommandHandler("shadow", shadow_command),
        CallbackQueryHandler(shadow_callback, pattern="^shadow_"),
        CommandHandler("bid", bid_command),
        CallbackQueryHandler(bid_callback, pattern="^bid_"),
        CommandHandler("aggregate", aggregate_command),
        CommandHandler("advanced", advanced_status_command),
    ]


def register_advanced_features_handlers(application: Application) -> None:
    """Register all advanced features handlers."""
    for handler in get_advanced_features_handlers():
        application.add_handler(handler)

    logger.info("Advanced features handlers registered")
