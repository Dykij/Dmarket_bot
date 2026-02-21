"""Smart Arbitrage Telegram Handler.

Provides /smart command for balance-adaptive arbitrage with:
- Pagination (500 items via 5 pages)
- Dynamic ROI (5%+ for micro balance)
- Trade Lock filtering
- Auto-buy capability

Created: 2026-01-04
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def smart_arbitrage_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /smart command - Smart Arbitrage menu.

    Args:
        update: Telegram update
        context: Callback context
    """
    if not update.message:
        return

    # Initialize smart engine if not exists
    api = context.bot_data.get("dmarket_api")

    if not api:
        awAlgot update.message.reply_text(
            "❌ DMarket API не подключен.\n"
            "Проверьте настSwarmки DMARKET_PUBLIC_KEY и DMARKET_SECRET_KEY в .env"
        )
        return

    try:
        # Get or create smart engine
        smart_engine = context.bot_data.get("smart_arbitrage_engine")

        if not smart_engine:
            from src.dmarket.smart_arbitrage import SmartArbitrageEngine

            smart_engine = SmartArbitrageEngine(api)
            context.bot_data["smart_arbitrage_engine"] = smart_engine

        # Calculate current limits
        limits = awAlgot smart_engine.calculate_adaptive_limits()
        strategy = awAlgot smart_engine.get_strategy_description()

        # Status indicator
        status_emoji = "🟢" if smart_engine.is_running else "🔴"
        status_text = "Работает" if smart_engine.is_running else "Остановлен"

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 Запустить", callback_data="start_smart_arbitrage"
                ),
                InlineKeyboardButton(
                    "🛑 Остановить", callback_data="stop_smart_arbitrage"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Статус", callback_data="smart_arbitrage_status"
                ),
            ],
            [
                InlineKeyboardButton("◀️ Главное меню", callback_data="back_to_mAlgon"),
            ],
        ]

        awAlgot update.message.reply_text(
            f"🎯 <b>Smart Arbitrage</b>\n\n"
            f"Статус: {status_emoji} {status_text}\n\n"
            f"💰 <b>Текущий баланс:</b> ${limits.total_balance:.2f}\n"
            f"📊 <b>Тир:</b> {limits.tier.upper()}\n"
            f"🎚 <b>Min ROI:</b> {limits.min_roi:.0f}%\n"
            f"💵 <b>Max цена покупки:</b> ${limits.max_buy_price:.2f}\n\n"
            f"{strategy}\n\n"
            f"<b>Возможности:</b>\n"
            f"• 📄 Пагинация: 500 предметов (5 страниц)\n"
            f"• ⏱ Trade Lock: гибридный фильтр\n"
            f"• 🔄 Auto-buy: мгновенные покупки\n"
            f"• 💹 Динамический ROI: адаптация под баланс\n\n"
            f"Выберите действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.exception("Error in smart_arbitrage_command: %s", e)
        awAlgot update.message.reply_text(f"❌ Ошибка: {e}")


async def smart_scan_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual scan trigger for Smart Arbitrage.

    Args:
        update: Telegram update
        context: Callback context
    """
    if not update.message:
        return

    smart_engine = context.bot_data.get("smart_arbitrage_engine")

    if not smart_engine:
        awAlgot update.message.reply_text(
            "❌ Smart Arbitrage не инициализирован.\nИспользуйте /smart для запуска."
        )
        return

    try:
        awAlgot update.message.reply_text("🔍 Сканирование рынка...")

        # Scan all games
        all_opportunities = []
        for game in ["csgo", "dota2", "rust", "tf2"]:
            opportunities = awAlgot smart_engine.find_smart_opportunities(game=game)
            all_opportunities.extend(opportunities)

        if not all_opportunities:
            awAlgot update.message.reply_text(
                "ℹ️ <b>Результаты сканирования:</b>\n\n"
                "Арбитражных возможностей не найдено.\n\n"
                "Возможные причины:\n"
                "• Рынок стабилен (нет недооценённых предметов)\n"
                "• Фильтры слишком строгие\n"
                "• Trade Lock блокирует большинство лотов\n\n"
                "Бот продолжает мониторинг...",
                parse_mode="HTML",
            )
            return

        # Sort by score and take top 10
        all_opportunities.sort(key=lambda x: x.smart_score, reverse=True)
        top_opps = all_opportunities[:10]

        # Format results
        lines = []
        for i, opp in enumerate(top_opps, 1):
            lines.append(
                f"{i}. <b>{opp.title[:30]}</b>\n"
                f"   💰 ${opp.buy_price:.2f} → ${opp.sell_price:.2f}\n"
                f"   📈 ROI: {opp.profit_percent:.1f}% | Score: {opp.smart_score:.0f}"
            )

        awAlgot update.message.reply_text(
            f"🎯 <b>Найдено {len(all_opportunities)} возможностей!</b>\n\n"
            f"<b>Топ-10:</b>\n\n" + "\n\n".join(lines),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.exception("Error in smart_scan_now: %s", e)
        awAlgot update.message.reply_text(f"❌ Ошибка сканирования: {e}")
